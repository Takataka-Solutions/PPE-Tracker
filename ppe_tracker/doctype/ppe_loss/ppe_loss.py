# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPELoss(Document):
	"""Controller for the PPE Loss DocType.

	Handles acknowledgement and automatic Additional Salary creation for payroll deduction.
	"""

	def validate(self):
		self._validate_acknowledgement_attachment()

	def before_save(self):
		"""When acknowledgement_status transitions to Acknowledged, create Additional Salary."""
		if self.acknowledgement_status == "Acknowledged" and not self.additional_salary:
			self._create_additional_salary()

	def _validate_acknowledgement_attachment(self):
		"""Throw if method is Supervisor Uploaded, status is Acknowledged, but no attachment."""
		if (
			self.acknowledgement_method == "Supervisor Uploaded"
			and self.acknowledgement_status == "Acknowledged"
			and not self.acknowledgement_attachment
		):
			frappe.throw(
				_("An acknowledgement attachment is required when the method is 'Supervisor Uploaded'.")
			)

	def _create_additional_salary(self):
		"""Create an Additional Salary deduction record for the surcharge amount."""
		additional_salary = frappe.new_doc("Additional Salary")
		additional_salary.employee = self.employee
		additional_salary.salary_component = "PPE Loss Deduction"
		additional_salary.amount = self.surcharge_amount
		additional_salary.type = "Deduction"
		additional_salary.overwrite_salary_structure_amount = 0
		additional_salary.custom_ppe_loss = self.name
		additional_salary.insert(ignore_permissions=True)
		additional_salary.submit()

		self.additional_salary = additional_salary.name
