# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PPEItem(Document):
	"""Controller for the PPE Item DocType.

	Validates:
	- Linked ERPNext Item must belong to the "PPE" item group.
	- Default lifespan and all child row lifespans must be >= 1.
	- No duplicate position_type values in the lifespan child table.
	"""

	def validate(self):
		self._validate_item_group()
		self._validate_lifespan_values()
		self._validate_position_type_uniqueness()
		self._validate_has_sizes()

	def before_save(self):
		self._set_available_sizes_display()

	def _validate_item_group(self):
		"""Fetch the linked Item's item_group and throw if it is not 'PPE'."""
		item_group = frappe.db.get_value("Item", self.item_code, "item_group")
		if item_group != "PPE":
			frappe.throw(
				_("The linked Item {0} must belong to the 'PPE' item group. Current item group is '{1}'.").format(
					frappe.bold(self.item_code), item_group
				)
			)

	def _validate_lifespan_values(self):
		"""Throw if default_lifespan < 1 or any child row lifespan < 1."""
		if self.default_lifespan < 1:
			frappe.throw(
				_("Default Lifespan must be at least 1 month. Got {0}.").format(self.default_lifespan)
			)

		for row in self.lifespan_table or []:
			if row.lifespan < 1:
				frappe.throw(
					_("Row {0}: Lifespan must be at least 1 month for position type '{1}'. Got {2}.").format(
						row.idx, row.position_type, row.lifespan
					)
				)

	def _validate_position_type_uniqueness(self):
		"""Throw if any duplicate position_type values exist in the lifespan child table."""
		seen = set()
		for row in self.lifespan_table or []:
			if row.position_type in seen:
				frappe.throw(
					_("Row {0}: Duplicate Position Type '{1}' found in the Lifespan Table. Each position type can only appear once.").format(
						row.idx, row.position_type
					)
				)
			seen.add(row.position_type)

	def _validate_has_sizes(self):
		"""If has_sizes is enabled, validate that the linked item_code is an Item Template."""
		if not self.has_sizes:
			return

		has_variants = frappe.db.get_value("Item", self.item_code, "has_variants")
		if not has_variants:
			frappe.throw(
				_("Item {0} is not an Item Template. When 'Has Sizes' is enabled, "
				  "the linked Item must have variants enabled (has_variants = 1).").format(
					frappe.bold(self.item_code)
				)
			)

	def _set_available_sizes_display(self):
		"""Populate a read-only field showing available size attribute values from the Item Template."""
		if not self.has_sizes:
			self.available_sizes = ""
			return

		# Get variant attributes from the Item Template
		attributes = frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": self.item_code},
			fields=["attribute"],
			order_by="idx"
		)

		if not attributes:
			self.available_sizes = ""
			return

		# Get attribute values for each variant attribute
		sizes = []
		for attr in attributes:
			attr_values = frappe.get_all(
				"Item Attribute Value",
				filters={"parent": attr.attribute},
				fields=["attribute_value"],
				order_by="idx"
			)
			sizes.extend([v.attribute_value for v in attr_values])

		self.available_sizes = ", ".join(sizes) if sizes else ""
