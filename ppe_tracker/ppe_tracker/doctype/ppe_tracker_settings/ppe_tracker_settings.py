# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPETrackerSettings(Document):
	"""Controller for the PPE Tracker Settings Single DocType.

	Validates:
	- All three warehouse fields reference different warehouses.
	- Each configured warehouse exists and is not disabled in ERPNext.
	"""

	def validate(self):
		self._validate_warehouses_are_different()
		self._validate_warehouses_exist_and_active()

	def _validate_warehouses_are_different(self):
		"""Ensure Returned PPE, Default Issue, and Wornout PPE warehouses are all distinct."""
		warehouses = [
			self.returned_ppe_warehouse,
			self.default_issue_warehouse,
			self.wornout_ppe_warehouse,
		]

		# Only validate if all three are set (mandatory check handles empty values)
		if not all(warehouses):
			return

		if len(set(warehouses)) != 3:
			frappe.throw(
				_("Returned PPE Warehouse, Default Issue Warehouse, and Wornout PPE Warehouse must all be different warehouses.")
			)

	def _validate_warehouses_exist_and_active(self):
		"""Ensure each configured warehouse exists and is not disabled."""
		warehouse_fields = {
			"returned_ppe_warehouse": "Returned PPE Warehouse",
			"default_issue_warehouse": "Default Issue Warehouse",
			"wornout_ppe_warehouse": "Wornout PPE Warehouse",
		}

		for fieldname, label in warehouse_fields.items():
			warehouse = self.get(fieldname)
			if not warehouse:
				continue

			warehouse_doc = frappe.db.get_value(
				"Warehouse", warehouse, ["name", "disabled"], as_dict=True
			)

			if not warehouse_doc:
				frappe.throw(
					_("Warehouse '{0}' set in {1} does not exist.").format(warehouse, label)
				)

			if warehouse_doc.disabled:
				frappe.throw(
					_("Warehouse '{0}' set in {1} is disabled. Please select an active warehouse.").format(
						warehouse, label
					)
				)
