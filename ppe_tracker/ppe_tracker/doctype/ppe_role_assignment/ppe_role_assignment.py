# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPERoleAssignment(Document):
	def validate(self):
		self._validate_scope()
		self._validate_items()
		self._validate_quantity()

	def _validate_scope(self):
		"""Throw if both department and designation are empty."""
		if not self.department and not self.designation:
			frappe.throw(
				_("At least one of Department or Designation must be specified")
			)

	def _validate_items(self):
		"""Throw if required_items child table is empty."""
		if not self.required_items:
			frappe.throw(_("At least one PPE Item is required"))

	def _validate_quantity(self):
		"""Throw if any row in required_items has quantity less than 1."""
		for row in self.required_items:
			if row.quantity < 1:
				frappe.throw(
					_("Row {0}: Quantity must be at least 1").format(row.idx)
				)
