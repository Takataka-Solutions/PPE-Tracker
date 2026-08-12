# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


def resolve_lifespan(ppe_item_name: str, employee_name: str) -> int:
	"""
	Resolve the applicable lifespan (months) for a given employee + PPE item combination.

	1. Fetch employee's custom_position_type field from Employee record.
	2. Scan PPE Item Lifespan child rows for a matching position_type.
	3. If found, return that row's lifespan.
	4. Otherwise, return the PPE Item's default_lifespan as fallback.
	"""
	employee = frappe.get_doc("Employee", employee_name)
	position_type = employee.get("custom_position_type")

	ppe_item = frappe.get_doc("PPE Item", ppe_item_name)

	for row in ppe_item.lifespan_table:
		if row.position_type == position_type:
			return row.lifespan

	return ppe_item.default_lifespan


class PPEIssue(Document):
	"""Controller for the PPE Issue DocType.

	Validates:
	- Quantity must be at least 1.
	- Expiry date is auto-calculated based on issue_date + resolved lifespan.

	On Submit:
	- PPE Request must have status "Approved".
	- PPE Item must be Active.
	- Sets status to "Active".
	- Creates a Material Issue Stock Entry.
	- Updates PPE Request status to "Issued".
	- Marks existing Active issues for same employee+item as "Replaced".
	"""

	def validate(self):
		self._validate_quantity()
		self._set_expiry_date()
		self._validate_casual_issue()
		self._resolve_size_if_applicable()

	def on_submit(self):
		self._validate_request_approved()
		self._validate_ppe_item_active()
		self._validate_return_or_loss_prerequisite()
		self._validate_max_issued_quantity()
		self.status = "Active"
		self._create_material_issue_stock_entry()
		self._update_request_to_issued()
		self._mark_replaced_if_needed()

	def on_cancel(self):
		"""Cancel the linked Stock Entry to reverse inventory movement."""
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			se.cancel()

	def _validate_request_approved(self):
		"""Throw if the linked PPE Request does not have status 'Approved'."""
		request_status = frappe.db.get_value("PPE Request", self.ppe_request, "status")
		if request_status != "Approved":
			frappe.throw(
				_("PPE Issue can only be submitted against an Approved PPE Request. "
				  "Linked PPE Request {0} has status '{1}'.").format(
					self.ppe_request, request_status
				)
			)

	def _validate_ppe_item_active(self):
		"""Throw if the linked PPE Item has status 'Inactive'."""
		ppe_item_status = frappe.db.get_value("PPE Item", self.ppe_item, "status")
		if ppe_item_status == "Inactive":
			frappe.throw(
				_("Cannot issue an Inactive PPE Item ({0}). Please activate it first.").format(
					self.ppe_item
				)
			)

	def _validate_return_or_loss_prerequisite(self):
		"""Block submission if justification requires a prior PPE Return or PPE Loss.

		If the linked PPE Request has justification matching replacement triggers,
		check that the employee's previous PPE Issue for the same item has an
		associated PPE Return or PPE Loss record. If neither exists, throw.
		"""
		REPLACEMENT_JUSTIFICATIONS = (
			"Worn Out Before Lifespan End (Cost Charged to Employee)",
			"Exceeded Lifespan",
		)

		justification = frappe.db.get_value(
			"PPE Request", self.ppe_request, "justification"
		)

		if justification not in REPLACEMENT_JUSTIFICATIONS:
			return

		# Find the employee's previous PPE Issue for the same PPE Item
		# Include all statuses except Cancelled — any prior issue requires return/loss
		previous_issues = frappe.get_all(
			"PPE Issue",
			filters={
				"employee": self.employee,
				"ppe_item": self.ppe_item,
				"name": ["!=", self.name],
				"docstatus": 1,
			},
			fields=["name"],
			order_by="issue_date desc",
			limit_page_length=1,
		)

		if not previous_issues:
			# No prior issue in the system — but justification implies PPE was
			# previously held (possibly issued through a legacy system).
			# Require a PPE Return or PPE Loss for this employee + item regardless.
			has_return = frappe.db.exists(
				"PPE Return", {"employee": self.employee, "ppe_item": self.ppe_item, "docstatus": 1}
			)
			has_loss = frappe.db.exists(
				"PPE Loss", {"employee": self.employee, "ppe_item": self.ppe_item}
			)

			if not has_return and not has_loss:
				frappe.throw(
					_("Cannot issue replacement PPE. The justification \"{0}\" indicates "
					  "the employee previously held this item. A PPE Return or PPE Loss "
					  "record must be created before a new issue can be submitted.").format(
						justification
					)
				)
			return

		previous_issue = previous_issues[0].name

		# Check if a PPE Return exists for the previous issue
		has_return = frappe.db.exists(
			"PPE Return", {"ppe_issue": previous_issue, "docstatus": 1}
		)

		# Check if a PPE Loss exists for the previous issue
		has_loss = frappe.db.exists(
			"PPE Loss", {"ppe_issue": previous_issue}
		)

		if not has_return and not has_loss:
			frappe.throw(
				_("Cannot issue replacement PPE. A PPE Return or PPE Loss record "
				  "must be created for the previous issue ({0}) before a new issue "
				  "can be submitted with justification \"{1}\".").format(
					previous_issue, justification
				)
			)

	def _validate_max_issued_quantity(self):
		"""Block submission if total issued qty would exceed PPE Role Assignment limit.

		Looks up the employee's department/designation, finds a matching PPE Role Assignment
		with a row for this ppe_item, and checks that existing active issues + current qty
		does not exceed the assignment's allowed quantity.
		If no matching assignment is found, no cap is enforced.
		"""
		employee = frappe.get_doc("Employee", self.employee)
		department = employee.get("department")
		designation = employee.get("designation")

		# Build filters to find matching PPE Role Assignment(s)
		# Match on department and/or designation
		or_filters = []
		if department and designation:
			or_filters = [
				{"department": department, "designation": designation},
				{"department": department, "designation": ["in", ["", None]]},
				{"designation": designation, "department": ["in", ["", None]]},
			]
		elif department:
			or_filters = [
				{"department": department},
			]
		elif designation:
			or_filters = [
				{"designation": designation},
			]
		else:
			return  # No department or designation — no cap enforced

		assignments = frappe.get_all(
			"PPE Role Assignment",
			or_filters=or_filters,
			pluck="name",
		)

		if not assignments:
			return  # No matching assignment — no cap enforced

		# Find the matching item row across all matching assignments
		max_allowed_quantity = None
		for assignment_name in assignments:
			assignment = frappe.get_doc("PPE Role Assignment", assignment_name)
			for row in assignment.required_items:
				if row.ppe_item == self.ppe_item:
					# Use the highest quantity if multiple assignments match
					if max_allowed_quantity is None or row.quantity > max_allowed_quantity:
						max_allowed_quantity = row.quantity
					break

		if max_allowed_quantity is None:
			return  # PPE item not in any matching assignment — no cap enforced

		# Query total qty from existing Active PPE Issues for same employee + ppe_item
		existing_total = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(quantity), 0)
			FROM `tabPPE Issue`
			WHERE employee = %(employee)s
			  AND ppe_item = %(ppe_item)s
			  AND docstatus = 1
			  AND status = 'Active'
			  AND name != %(current_name)s
			""",
			{
				"employee": self.employee,
				"ppe_item": self.ppe_item,
				"current_name": self.name,
			},
		)[0][0] or 0

		total_after_issue = existing_total + self.quantity

		if total_after_issue > max_allowed_quantity:
			frappe.throw(
				_("Cannot issue {0} unit(s) of {1} to {2}. "
				  "Maximum allowed quantity is {3} (per PPE Role Assignment), "
				  "and {4} unit(s) are already actively issued. "
				  "Total after this issue would be {5}.").format(
					self.quantity,
					self.ppe_item,
					self.employee,
					max_allowed_quantity,
					int(existing_total),
					int(total_after_issue),
				)
			)

	def _validate_quantity(self):
		"""Throw if quantity is less than 1."""
		if self.quantity < 1:
			frappe.throw(
				_("Quantity must be at least 1. Got {0}.").format(self.quantity)
			)

	def _set_expiry_date(self):
		"""Calculate and set expiry_date based on issue_date + resolved lifespan months."""
		lifespan = resolve_lifespan(self.ppe_item, self.employee)
		self.expiry_date = frappe.utils.add_months(self.issue_date, lifespan)

	def _validate_casual_issue(self):
		"""Validate casual issue requirements.

		For Casual issue types:
		- expected_return_date must be set
		- linked Employee must have employment_type == 'Casual'
		"""
		issue_type = self.get("issue_type")
		if issue_type != "Casual":
			return

		# Validate expected_return_date is set
		if not self.get("expected_return_date"):
			frappe.throw(
				_("Expected Return Date is required for Casual PPE Issues.")
			)

		# Validate employee is a casual worker
		employment_type = frappe.db.get_value("Employee", self.employee, "employment_type")
		if employment_type != "Casual":
			frappe.throw(
				_("Employee {0} does not have employment type 'Casual'. "
				  "Casual PPE Issues can only be created for casual workers.").format(
					frappe.bold(self.employee)
				)
			)

	def _resolve_size_if_applicable(self):
		"""Auto-populate size and item_variant if the PPE Item has sizes enabled."""
		has_sizes = frappe.db.get_value("PPE Item", self.ppe_item, "has_sizes")
		if not has_sizes:
			self.size = ""
			self.item_variant = ""
			return

		from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size
		size, item_variant = resolve_employee_ppe_size(self.employee, self.ppe_item)
		self.size = size
		self.item_variant = item_variant

	def _create_material_issue_stock_entry(self):
		"""Create a Material Issue Stock Entry to decrement stock for the issued PPE.

		Source warehouse is determined by issue_type:
		- Standard (or not set): Default Issue Warehouse from PPE Tracker Settings
		- Casual: Returned PPE Warehouse from PPE Tracker Settings

		Item code is determined by item_variant:
		- If item_variant is set (sized item), use it instead of template item_code
		- Otherwise, use the item_code from the PPE Item record
		"""
		issue_type = self.get("issue_type")

		if issue_type == "Casual":
			source_warehouse = frappe.db.get_single_value(
				"PPE Tracker Settings", "returned_ppe_warehouse"
			)
			if not source_warehouse:
				frappe.throw(
					_("Returned PPE Warehouse is not configured. Please set it in PPE Tracker Settings.")
				)
		else:
			source_warehouse = frappe.db.get_single_value(
				"PPE Tracker Settings", "default_issue_warehouse"
			)
			if not source_warehouse:
				frappe.throw(
					_("Default Issue Warehouse is not configured. Please set it in PPE Tracker Settings.")
				)

		# If item_variant is set (sized item), use it instead of template item_code
		if self.get("item_variant"):
			item_code = self.item_variant
		else:
			item_code = frappe.db.get_value("PPE Item", self.ppe_item, "item_code")

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		se.custom_ppe_issue = self.name
		se.append("items", {
			"item_code": item_code,
			"qty": self.quantity,
			"s_warehouse": source_warehouse,
		})

		try:
			se.insert(ignore_permissions=True)
			se.submit()
		except Exception as e:
			frappe.throw(
				_("Failed to create Stock Entry for PPE Issue {0}: {1}").format(
					self.name, str(e)
				)
			)

		self.db_set("stock_entry", se.name)

	def _update_request_to_issued(self):
		"""Transition the linked PPE Request status to 'Issued'."""
		frappe.db.set_value("PPE Request", self.ppe_request, "status", "Issued")

	def _mark_replaced_if_needed(self):
		"""Mark existing Active PPE Issues for the same employee + ppe_item as Replaced."""
		existing_issues = frappe.get_all(
			"PPE Issue",
			filters={
				"employee": self.employee,
				"ppe_item": self.ppe_item,
				"status": "Active",
				"name": ["!=", self.name],
			},
			pluck="name",
		)

		for issue_name in existing_issues:
			frappe.db.set_value("PPE Issue", issue_name, "status", "Replaced")
