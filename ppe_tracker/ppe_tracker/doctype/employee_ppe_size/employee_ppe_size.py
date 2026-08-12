# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EmployeePPESize(Document):
	"""Controller for Employee PPE Size DocType.

	Validates:
	- Each PPE Size Item's size matches a valid attribute value on the PPE Item's template
	- No duplicate PPE Items in the child table
	- One record per employee (enforced by unique constraint + controller)

	Auto-resolves item_variant for each row.
	"""

	def before_insert(self):
		"""Pre-populate PPE Size Items from Role Assignment for sized PPE Items."""
		if self.ppe_size_items:
			return  # Don't overwrite if user already added items

		self._prepopulate_from_role_assignment()

	def validate(self):
		self._validate_no_duplicate_ppe_items()
		self._validate_one_record_per_employee()
		self._validate_and_resolve_sizes()

	def _validate_no_duplicate_ppe_items(self):
		"""Ensure each PPE Item appears only once in the child table."""
		seen = set()
		for row in self.ppe_size_items:
			if row.ppe_item in seen:
				frappe.throw(
					_("Row {0}: Duplicate PPE Item '{1}'. Each PPE Item can only appear once.").format(
						row.idx, row.ppe_item
					)
				)
			seen.add(row.ppe_item)

	def _validate_one_record_per_employee(self):
		"""Prevent creation of duplicate records for the same employee."""
		if self.is_new():
			existing = frappe.db.exists(
				"Employee PPE Size",
				{"employee": self.employee, "name": ["!=", self.name]}
			)
			if existing:
				frappe.throw(
					_("An Employee PPE Size record already exists for employee {0}. "
					  "Please edit the existing record instead.").format(
						frappe.bold(self.employee)
					)
				)

	def _validate_and_resolve_sizes(self):
		"""Validate size values and auto-resolve item variants."""
		for row in self.ppe_size_items:
			# Get the item_code from PPE Item
			item_code = frappe.db.get_value("PPE Item", row.ppe_item, "item_code")
			if not item_code:
				frappe.throw(
					_("Row {0}: PPE Item '{1}' does not have a linked Item Code.").format(
						row.idx, row.ppe_item
					)
				)

			# Get variant attributes from the template
			attributes = frappe.get_all(
				"Item Variant Attribute",
				filters={"parent": item_code, "parenttype": "Item"},
				fields=["attribute"],
				order_by="idx"
			)

			if not attributes:
				frappe.throw(
					_("Row {0}: Item '{1}' does not have variant attributes configured.").format(
						row.idx, item_code
					)
				)

			# Check size matches any attribute value
			valid_values = []
			size_attribute = None
			for attr in attributes:
				attr_values = frappe.get_all(
					"Item Attribute Value",
					filters={"parent": attr.attribute},
					pluck="attribute_value"
				)
				valid_values.extend(attr_values)
				if row.size in attr_values:
					size_attribute = attr.attribute

			if not size_attribute:
				frappe.throw(
					_("Row {0}: Size '{1}' is not a valid option for PPE Item '{2}'. "
					  "Valid sizes are: {3}").format(
						row.idx, row.size, row.ppe_item, ", ".join(valid_values)
					)
				)

			# Resolve item variant
			variant = self._get_item_variant(item_code, size_attribute, row.size)
			row.item_variant = variant

	def _get_item_variant(self, item_template, attribute, value):
		"""Look up the ERPNext Item Variant matching template + attribute + value."""
		# Find variants of this template
		variants = frappe.get_all(
			"Item",
			filters={"variant_of": item_template},
			pluck="name"
		)

		for variant_name in variants:
			# Check if this variant has the matching attribute value
			has_match = frappe.db.exists(
				"Item Variant Attribute",
				{
					"parent": variant_name,
					"attribute": attribute,
					"attribute_value": value
				}
			)
			if has_match:
				return variant_name

		# No variant found
		frappe.throw(
			_("No Item Variant found for template '{0}' with {1} = '{2}'. "
			  "Please create the variant in ERPNext first.").format(
				item_template, attribute, value
			)
		)

	def _prepopulate_from_role_assignment(self):
		"""Auto-populate child table with sized PPE Items from employee's Role Assignment."""
		if not self.employee:
			return

		# Get employee's department and designation
		employee = frappe.get_doc("Employee", self.employee)
		department = employee.get("department")
		designation = employee.get("designation")

		if not department and not designation:
			return

		# Find matching PPE Role Assignments
		or_filters = []
		if department and designation:
			or_filters = [
				{"department": department, "designation": designation},
				{"department": department, "designation": ["in", ["", None]]},
				{"designation": designation, "department": ["in", ["", None]]},
			]
		elif department:
			or_filters = [{"department": department}]
		elif designation:
			or_filters = [{"designation": designation}]

		assignments = frappe.get_all(
			"PPE Role Assignment",
			or_filters=or_filters,
			pluck="name"
		)

		if not assignments:
			return

		# Collect unique PPE Items with has_sizes=1 from all matching assignments
		sized_ppe_items = set()
		for assignment_name in assignments:
			assignment = frappe.get_doc("PPE Role Assignment", assignment_name)
			for row in assignment.required_items:
				has_sizes = frappe.db.get_value("PPE Item", row.ppe_item, "has_sizes")
				if has_sizes:
					sized_ppe_items.add(row.ppe_item)

		# Add rows to child table
		for ppe_item in sorted(sized_ppe_items):
			self.append("ppe_size_items", {
				"ppe_item": ppe_item,
			})
