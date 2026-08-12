# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPEReturn(Document):
	"""Controller for the PPE Return DocType.

	Validates:
	- Linked PPE Issue must not already have status 'Returned' or 'Replaced'.
	- Quantity returned must not exceed the issued quantity.

	On Submit:
	- Updates PPE Issue status to 'Returned'.
	- Creates a Material Receipt Stock Entry if condition is 'Good'.
	- Skips Stock Entry creation for 'Damaged' or 'Unusable' items (disposed).

	On Cancel:
	- Cancels the linked Stock Entry (if one was created).
	- Reverts PPE Issue status back to 'Active'.
	"""

	def validate(self):
		self._validate_issue_status()
		self._validate_quantity()

	def on_submit(self):
		self._update_issue_status("Returned")
		self._create_material_receipt_stock_entry()

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			se.cancel()
		self._update_issue_status("Active")

	def _validate_issue_status(self):
		"""Throw if the linked PPE Issue already has status 'Returned' or 'Replaced'."""
		issue_status = frappe.db.get_value("PPE Issue", self.ppe_issue, "status")
		if issue_status in ("Returned", "Replaced"):
			frappe.throw(
				_("Cannot create a PPE Return against PPE Issue {0} because it already has status '{1}'.").format(
					frappe.bold(self.ppe_issue), issue_status
				)
			)

	def _validate_quantity(self):
		"""Throw if quantity_returned exceeds the issued quantity on the linked PPE Issue."""
		issued_qty = frappe.db.get_value("PPE Issue", self.ppe_issue, "quantity")
		if self.quantity_returned > issued_qty:
			frappe.throw(
				_("Quantity returned ({0}) cannot exceed the issued quantity ({1}) on PPE Issue {2}.").format(
					self.quantity_returned, issued_qty, frappe.bold(self.ppe_issue)
				)
			)

	def _update_issue_status(self, status):
		"""Update the status of the linked PPE Issue record."""
		frappe.db.set_value("PPE Issue", self.ppe_issue, "status", status)

	def _create_material_receipt_stock_entry(self):
		"""Create a Material Receipt Stock Entry when condition is 'Good'.

		Items returned as 'Damaged' or 'Unusable' are disposed — they are recorded
		for traceability but MUST NOT re-enter warehouse stock.
		"""
		if self.condition in ("Damaged", "Unusable"):
			return  # Disposed — no stock movement

		item_code = frappe.db.get_value("PPE Item", self.ppe_item, "item_code")

		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Receipt"
		se.custom_ppe_return = self.name
		se.append("items", {
			"item_code": item_code,
			"qty": self.quantity_returned,
			"t_warehouse": frappe.db.get_single_value(
				"Stock Settings", "default_warehouse"
			),
		})

		try:
			se.insert(ignore_permissions=True)
			se.submit()
		except frappe.ValidationError as e:
			frappe.throw(
				_("Failed to create Stock Entry for PPE Return {0}: {1}").format(
					self.name, str(e)
				)
			)

		self.db_set("stock_entry", se.name)
