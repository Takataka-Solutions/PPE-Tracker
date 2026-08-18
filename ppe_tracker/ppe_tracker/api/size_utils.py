"""
Size Resolution Utility Module

Provides helper functions for resolving employee PPE sizes and looking up
ERPNext Item Variants. Shared between PPE Issue and PPE Request controllers.
"""

import frappe
from frappe import _


def resolve_employee_ppe_size(employee, ppe_item):
	"""Return (size, item_variant) tuple for the given employee + PPE Item.

	Looks up the employee's Employee PPE Size record and finds the matching
	PPE Size Item row for the given PPE Item.

	Args:
		employee: Employee name/ID
		ppe_item: PPE Item name

	Returns:
		tuple: (size_value, item_variant_name)

	Raises:
		frappe.ValidationError: If no size record exists for the employee + PPE Item
	"""
	# Find the Employee PPE Size record
	size_record = frappe.db.exists("Employee PPE Size", {"employee": employee})
	if not size_record:
		frappe.throw(
			_("No PPE Size record found for employee {0}. "
			  "Please define the employee's PPE sizes first.").format(
				frappe.bold(employee)
			)
		)

	# Find the matching row for this PPE Item
	size_item = frappe.db.get_value(
		"PPE Size Item",
		{"parent": size_record, "ppe_item": ppe_item},
		["size", "item_variant"],
		as_dict=True
	)

	if not size_item:
		frappe.throw(
			_("No size defined for PPE Item '{0}' in employee {1}'s PPE Size record. "
			  "Please update the Employee PPE Size record.").format(
				ppe_item, frappe.bold(employee)
			)
		)

	if not size_item.item_variant:
		frappe.throw(
			_("Item Variant not resolved for PPE Item '{0}', size '{1}'. "
			  "Please save the Employee PPE Size record to trigger variant resolution.").format(
				ppe_item, size_item.size
			)
		)

	return (size_item.size, size_item.item_variant)


def get_item_variant_for_size(item_template, size_attribute, size_value):
	"""Look up the ERPNext Item Variant matching template + attribute + value.

	Args:
		item_template: Item name of the template (has_variants=1)
		size_attribute: Name of the Item Attribute (e.g., "Size")
		size_value: Value of the attribute (e.g., "10", "Large")

	Returns:
		str: Item Variant name

	Raises:
		frappe.ValidationError: If no matching variant is found
	"""
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
				"attribute": size_attribute,
				"attribute_value": size_value
			}
		)
		if has_match:
			return variant_name

	frappe.throw(
		_("No Item Variant found for template '{0}' with {1} = '{2}'. "
		  "Please create the variant in ERPNext first.").format(
			item_template, size_attribute, size_value
		)
	)
