# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPERequest(Document):
	"""Controller for the PPE Request DocType.

	Approval/rejection workflow is handled by Frappe's Workflow engine.
	The Workflow transitions the status field through:
	  Draft → Pending Approval → Approved / Rejected

	Validates:
	- PPE Item must be in the employee's PPE Role Assignment (based on department/designation).
	- Rejection reason is mandatory when status is 'Rejected'.
	"""

	def validate(self):
		self._validate_ppe_assignment()
		self._validate_rejection_reason()

	def _validate_ppe_assignment(self):
		"""Throw if the requested PPE Item is not assigned to the employee's department/designation.

		Checks PPE Role Assignment rules matching the employee's department and/or designation.
		If no matching assignment includes this PPE Item, the request is blocked.
		"""
		if not self.employee or not self.ppe_item:
			return

		employee = frappe.get_doc("Employee", self.employee)
		department = employee.department
		designation = employee.designation

		# Find all PPE Role Assignment rules that match this employee's department or designation
		filters = []
		if department and designation:
			# Match: department only, designation only, or both
			filters = [
				["department", "=", department],
				["designation", "=", designation],
			]
			assignments = frappe.get_all(
				"PPE Role Assignment",
				or_filters={
					"department": department,
					"designation": designation,
				},
				pluck="name",
			)
		elif department:
			assignments = frappe.get_all(
				"PPE Role Assignment",
				filters={"department": department},
				pluck="name",
			)
		elif designation:
			assignments = frappe.get_all(
				"PPE Role Assignment",
				filters={"designation": designation},
				pluck="name",
			)
		else:
			# Employee has no department or designation — cannot validate
			return

		if not assignments:
			frappe.throw(
				_("No PPE Role Assignment rule found for employee {0} (Department: {1}, Designation: {2}). "
				  "Please create a PPE Role Assignment rule first.").format(
					frappe.bold(employee.employee_name),
					department or "—",
					designation or "—",
				)
			)

		# Check if the requested PPE Item is in any of the matching assignments
		assigned_items = frappe.get_all(
			"PPE Role Assignment Item",
			filters={"parent": ["in", assignments]},
			pluck="ppe_item",
		)

		if self.ppe_item not in assigned_items:
			frappe.throw(
				_("PPE Item {0} is not assigned to employees in Department: {1}, Designation: {2}. "
				  "Only the following PPE items are allowed: {3}").format(
					frappe.bold(self.ppe_item),
					department or "—",
					designation or "—",
					", ".join(assigned_items) if assigned_items else "None",
				)
			)

	def _validate_rejection_reason(self):
		"""Throw if status is 'Rejected' and rejection_reason is blank."""
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(
				_("Rejection Reason is mandatory when the PPE Request status is 'Rejected'.")
			)
