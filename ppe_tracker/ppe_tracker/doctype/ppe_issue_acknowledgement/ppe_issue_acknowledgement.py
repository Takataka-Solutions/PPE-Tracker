# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPEIssueAcknowledgement(Document):
	"""Controller for the PPE Issue Acknowledgement DocType.

	Validates:
	- All PPE Issues in the child table must belong to the same Employee.

	On Submit:
	- Sets acknowledgement_received=1 and acknowledgement=self.name on each linked PPE Issue.

	On Cancel:
	- Clears acknowledgement_received and acknowledgement on all linked PPE Issues.
	"""

	def validate(self):
		self._validate_issues_belong_to_employee()

	def on_submit(self):
		self._set_acknowledgement_on_issues()

	def on_cancel(self):
		self._clear_acknowledgement_on_issues()

	def _validate_issues_belong_to_employee(self):
		"""Ensure all PPE Issues in child table belong to the parent's Employee."""
		for row in self.ppe_issues:
			issue_employee = frappe.db.get_value("PPE Issue", row.ppe_issue, "employee")
			if issue_employee != self.employee:
				frappe.throw(
					_("All PPE Issues must belong to employee {0}. "
					  "Issue {1} belongs to a different employee.").format(
						frappe.bold(self.employee), frappe.bold(row.ppe_issue)
					)
				)

	def _set_acknowledgement_on_issues(self):
		"""Set acknowledgement_received and acknowledgement link on each linked PPE Issue."""
		for row in self.ppe_issues:
			frappe.db.set_value("PPE Issue", row.ppe_issue, {
				"acknowledgement_received": 1,
				"acknowledgement": self.name
			})

	def _clear_acknowledgement_on_issues(self):
		"""Clear acknowledgement fields on all linked PPE Issues."""
		for row in self.ppe_issues:
			frappe.db.set_value("PPE Issue", row.ppe_issue, {
				"acknowledgement_received": 0,
				"acknowledgement": ""
			})
