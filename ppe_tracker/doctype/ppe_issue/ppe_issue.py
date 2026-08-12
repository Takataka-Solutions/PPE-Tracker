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

	def on_submit(self):
		self._validate_request_approved()
		self._validate_ppe_item_active()
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

	def _create_material_issue_stock_entry(self):
		"""Create a Material Issue Stock Entry to decrement stock for the issued PPE."""
		item_code = frappe.db.get_value("PPE Item", self.ppe_item, "item_code")

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		se.custom_ppe_issue = self.name
		se.append("items", {
			"item_code": item_code,
			"qty": self.quantity,
			"s_warehouse": frappe.db.get_single_value(
				"Stock Settings", "default_warehouse"
			),
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
