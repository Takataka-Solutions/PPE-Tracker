# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Size-Aware PPE Issuing logic.

Property 25: Size Auto-Population on Issue and Request
Property 26: Stock Entry Uses Item Variant for Sized Issues

**Validates: Requirements 17.2, 17.3, 17.4, 17.5**
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from types import SimpleNamespace

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
	composite,
	text,
	sampled_from,
	booleans,
	just,
	one_of,
	none,
	integers,
)


class _FrappeDict(dict):
	"""Mimics frappe._dict: dict subclass with attribute access."""
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			return None

	def __setattr__(self, key, value):
		self[key] = value


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

employee_strategy = text(
	alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
	min_size=3,
	max_size=20,
).map(lambda s: f"EMP-{s}")

ppe_item_strategy = text(
	alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
	min_size=3,
	max_size=20,
).map(lambda s: f"PPE-{s}")

size_strategy = sampled_from(["S", "M", "L", "XL", "XXL", "6", "7", "8", "9", "10", "11", "12"])

item_variant_strategy = text(
	alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
	min_size=3,
	max_size=20,
).map(lambda s: f"ITEM-VAR-{s}")

warehouse_strategy = sampled_from([
	"Main Warehouse - TTS",
	"Returned PPE - TTS",
	"Default Issue - TTS",
])


@composite
def size_record_exists_scenario(draw):
	"""Generate a scenario where an Employee PPE Size record exists
	with a valid size item row for the given PPE Item.

	Returns (employee, ppe_item, size_record_name, size_value, item_variant_value)
	"""
	employee = draw(employee_strategy)
	ppe_item = draw(ppe_item_strategy)
	size_record_name = f"EPS-{employee}"
	size_value = draw(size_strategy)
	item_variant_value = draw(item_variant_strategy)

	return (employee, ppe_item, size_record_name, size_value, item_variant_value)


@composite
def no_size_record_scenario(draw):
	"""Generate a scenario where NO Employee PPE Size record exists for the employee.

	Returns (employee, ppe_item)
	"""
	employee = draw(employee_strategy)
	ppe_item = draw(ppe_item_strategy)

	return (employee, ppe_item)


@composite
def no_size_item_row_scenario(draw):
	"""Generate a scenario where the Employee PPE Size record exists
	but has no matching PPE Size Item row for the given PPE Item.

	Returns (employee, ppe_item, size_record_name)
	"""
	employee = draw(employee_strategy)
	ppe_item = draw(ppe_item_strategy)
	size_record_name = f"EPS-{employee}"

	return (employee, ppe_item, size_record_name)


@composite
def no_item_variant_scenario(draw):
	"""Generate a scenario where the size item row exists but item_variant is empty.

	Returns (employee, ppe_item, size_record_name, size_value)
	"""
	employee = draw(employee_strategy)
	ppe_item = draw(ppe_item_strategy)
	size_record_name = f"EPS-{employee}"
	size_value = draw(size_strategy)

	return (employee, ppe_item, size_record_name, size_value)


@composite
def stock_entry_scenario(draw):
	"""Generate a scenario for _create_material_issue_stock_entry.

	Returns (ppe_item, item_variant, template_item_code, issue_type, warehouse, quantity)
	"""
	ppe_item = draw(ppe_item_strategy)
	has_variant = draw(booleans())

	if has_variant:
		item_variant = draw(item_variant_strategy)
	else:
		item_variant = ""

	template_item_code = f"TEMPLATE-{ppe_item}"
	issue_type = draw(sampled_from(["Standard", "Casual", ""]))
	warehouse = draw(warehouse_strategy)
	quantity = draw(integers(min_value=1, max_value=10))

	return (ppe_item, item_variant, template_item_code, issue_type, warehouse, quantity)


# ---------------------------------------------------------------------------
# Property 25: Size Auto-Population on Issue and Request
# ---------------------------------------------------------------------------


class TestSizeAutoPopulationOnIssueAndRequest(unittest.TestCase):
	"""Property 25: Size Auto-Population on Issue and Request

	For any PPE Issue or PPE Request created for a PPE Item with has_sizes = 1,
	the system SHALL auto-populate the size field from the employee's Employee
	PPE Size record; if no size record exists for the employee + PPE Item
	combination, the system SHALL raise a validation error.

	**Validates: Requirements 17.2, 17.4**
	"""

	@given(scenario=size_record_exists_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_resolve_returns_correct_size_and_variant_when_record_exists(self, scenario):
		"""resolve_employee_ppe_size() returns (size, item_variant) tuple when
		Employee PPE Size record exists with a matching PPE Size Item row.

		**Validates: Requirements 17.2, 17.4**
		"""
		employee, ppe_item, size_record_name, size_value, item_variant_value = scenario

		with patch("ppe_tracker.ppe_tracker.api.size_utils.frappe") as mock_frappe:
			# Mock frappe.db.exists to return the size record name
			mock_frappe.db.exists.return_value = size_record_name

			# Mock frappe.db.get_value to return the size item data (as _FrappeDict for attribute access)
			mock_frappe.db.get_value.return_value = _FrappeDict({
				"size": size_value,
				"item_variant": item_variant_value,
			})

			# Mock frappe.throw to raise Exception so we can detect it
			mock_frappe.throw.side_effect = Exception("frappe.throw")
			mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size
			result = resolve_employee_ppe_size(employee, ppe_item)

		# ASSERTION 1: Returns a tuple
		self.assertIsInstance(result, tuple)
		self.assertEqual(len(result), 2)

		# ASSERTION 2: First element is the size value
		self.assertEqual(result[0], size_value)

		# ASSERTION 3: Second element is the item_variant value
		self.assertEqual(result[1], item_variant_value)

		# ASSERTION 4: frappe.db.exists was called with correct doctype and filters
		mock_frappe.db.exists.assert_called_once_with(
			"Employee PPE Size", {"employee": employee}
		)

		# ASSERTION 5: frappe.db.get_value was called to fetch the size item row
		mock_frappe.db.get_value.assert_called_once_with(
			"PPE Size Item",
			{"parent": size_record_name, "ppe_item": ppe_item},
			["size", "item_variant"],
			as_dict=True,
		)

	@given(scenario=no_size_record_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_raises_error_when_no_size_record_exists(self, scenario):
		"""resolve_employee_ppe_size() raises validation error when no
		Employee PPE Size record exists for the employee.

		**Validates: Requirements 17.2, 17.4**
		"""
		employee, ppe_item = scenario

		with patch("ppe_tracker.ppe_tracker.api.size_utils.frappe") as mock_frappe:
			# Mock frappe.db.exists to return None (no record)
			mock_frappe.db.exists.return_value = None

			# Mock frappe.throw to raise Exception
			mock_frappe.throw.side_effect = Exception("frappe.throw: No PPE Size record")
			mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size

			with self.assertRaises(Exception) as ctx:
				resolve_employee_ppe_size(employee, ppe_item)

		# ASSERTION 1: frappe.throw was called (validation error raised)
		mock_frappe.throw.assert_called_once()

		# ASSERTION 2: The error message references the employee
		call_args = mock_frappe.throw.call_args[0][0]
		self.assertIn(employee, call_args)

	@given(scenario=no_size_item_row_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_raises_error_when_no_size_item_row_for_ppe_item(self, scenario):
		"""resolve_employee_ppe_size() raises validation error when Employee PPE
		Size record exists but no PPE Size Item row matches the given PPE Item.

		**Validates: Requirements 17.2, 17.4**
		"""
		employee, ppe_item, size_record_name = scenario

		with patch("ppe_tracker.ppe_tracker.api.size_utils.frappe") as mock_frappe:
			# Mock frappe.db.exists to return the size record
			mock_frappe.db.exists.return_value = size_record_name

			# Mock frappe.db.get_value to return None (no matching row)
			mock_frappe.db.get_value.return_value = None

			# Mock frappe.throw to raise Exception
			mock_frappe.throw.side_effect = Exception("frappe.throw: No size item")
			mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size

			with self.assertRaises(Exception) as ctx:
				resolve_employee_ppe_size(employee, ppe_item)

		# ASSERTION 1: frappe.throw was called (validation error raised)
		mock_frappe.throw.assert_called_once()

		# ASSERTION 2: The error message references the PPE item
		call_args = mock_frappe.throw.call_args[0][0]
		self.assertIn(ppe_item, call_args)

	@given(scenario=no_item_variant_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_raises_error_when_item_variant_not_resolved(self, scenario):
		"""resolve_employee_ppe_size() raises validation error when the PPE Size
		Item row exists but item_variant is empty (variant not yet resolved).

		**Validates: Requirements 17.2, 17.4**
		"""
		employee, ppe_item, size_record_name, size_value = scenario

		with patch("ppe_tracker.ppe_tracker.api.size_utils.frappe") as mock_frappe:
			# Mock frappe.db.exists to return the size record
			mock_frappe.db.exists.return_value = size_record_name

			# Mock frappe.db.get_value to return row with empty item_variant
			mock_frappe.db.get_value.return_value = _FrappeDict({
				"size": size_value,
				"item_variant": "",
			})

			# Mock frappe.throw to raise Exception
			mock_frappe.throw.side_effect = Exception("frappe.throw: Variant not resolved")
			mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size

			with self.assertRaises(Exception) as ctx:
				resolve_employee_ppe_size(employee, ppe_item)

		# ASSERTION 1: frappe.throw was called (validation error raised)
		mock_frappe.throw.assert_called_once()

		# ASSERTION 2: The error message references the PPE item and size
		call_args = mock_frappe.throw.call_args[0][0]
		self.assertIn(ppe_item, call_args)
		self.assertIn(size_value, call_args)


# ---------------------------------------------------------------------------
# Property 26: Stock Entry Uses Item Variant for Sized Issues
# ---------------------------------------------------------------------------


class TestStockEntryUsesItemVariantForSizedIssues(unittest.TestCase):
	"""Property 26: Stock Entry Uses Item Variant for Sized Issues

	For any PPE Issue where item_variant is populated (sized PPE Item), the
	Material Issue Stock Entry SHALL use the item_variant Item Code in its
	items table rather than the template Item Code, ensuring correct stock
	deduction of the specific sized variant.

	**Validates: Requirements 17.3, 17.5**
	"""

	@given(scenario=stock_entry_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_stock_entry_uses_item_variant_when_set(self, scenario):
		"""_create_material_issue_stock_entry() uses item_variant as item_code
		when item_variant is populated, and uses template item_code when empty.

		**Validates: Requirements 17.3, 17.5**
		"""
		ppe_item, item_variant, template_item_code, issue_type, warehouse, quantity = scenario

		# Build the mock self (PPE Issue document)
		mock_self = MagicMock()
		mock_self.ppe_item = ppe_item
		mock_self.item_variant = item_variant
		mock_self.quantity = quantity
		mock_self.name = "PPE-ISS-TEST-001"

		# .get() should behave like a dict-like accessor
		def mock_get(field):
			attrs = {
				"issue_type": issue_type,
				"item_variant": item_variant,
			}
			return attrs.get(field, "")

		mock_self.get.side_effect = mock_get

		# Track what items are appended to Stock Entry
		appended_items = []
		mock_se = MagicMock()
		mock_se.name = "SE-TEST-001"

		def capture_append(table, item_dict):
			appended_items.append(item_dict)

		mock_se.append.side_effect = capture_append

		with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe") as mock_frappe:
			# Mock frappe.db.get_single_value to return the warehouse
			mock_frappe.db.get_single_value.return_value = warehouse

			# Mock frappe.db.get_value to return template item code
			mock_frappe.db.get_value.return_value = template_item_code

			# Mock frappe.new_doc to return our mock Stock Entry
			mock_frappe.new_doc.return_value = mock_se

			# Mock frappe.throw
			mock_frappe.throw.side_effect = Exception("frappe.throw")
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue
			# Call the method directly, passing mock_self as self
			PPEIssue._create_material_issue_stock_entry(mock_self)

		# ASSERTION 1: Exactly one item was appended to the Stock Entry
		self.assertEqual(len(appended_items), 1)

		appended_item = appended_items[0]

		# ASSERTION 2: If item_variant is set, it is used as item_code
		if item_variant:
			self.assertEqual(
				appended_item["item_code"],
				item_variant,
				f"When item_variant is '{item_variant}', Stock Entry should use it as item_code",
			)
		else:
			# ASSERTION 3: If item_variant is empty, template item_code is used
			self.assertEqual(
				appended_item["item_code"],
				template_item_code,
				"When item_variant is empty, Stock Entry should use template item_code",
			)

		# ASSERTION 4: Quantity matches
		self.assertEqual(appended_item["qty"], quantity)

		# ASSERTION 5: Source warehouse is set
		self.assertEqual(appended_item["s_warehouse"], warehouse)

		# ASSERTION 6: Stock Entry type is Material Issue
		mock_frappe.new_doc.assert_called_once_with("Stock Entry")
		self.assertEqual(mock_se.stock_entry_type, "Material Issue")

		# ASSERTION 7: Stock Entry was inserted and submitted
		mock_se.insert.assert_called_once_with(ignore_permissions=True)
		mock_se.submit.assert_called_once()

		# ASSERTION 8: PPE Issue stock_entry field is set
		mock_self.db_set.assert_called_once_with("stock_entry", mock_se.name)

	@given(scenario=stock_entry_scenario())
	@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
	def test_variant_never_falls_through_to_template_when_set(self, scenario):
		"""When item_variant is populated, frappe.db.get_value for PPE Item
		item_code should NOT be used as the Stock Entry item_code.

		**Validates: Requirements 17.3, 17.5**
		"""
		ppe_item, item_variant, template_item_code, issue_type, warehouse, quantity = scenario

		# Only test cases where item_variant is set
		assume(item_variant != "")

		mock_self = MagicMock()
		mock_self.ppe_item = ppe_item
		mock_self.item_variant = item_variant
		mock_self.quantity = quantity
		mock_self.name = "PPE-ISS-TEST-002"

		def mock_get(field):
			attrs = {
				"issue_type": issue_type,
				"item_variant": item_variant,
			}
			return attrs.get(field, "")

		mock_self.get.side_effect = mock_get

		appended_items = []
		mock_se = MagicMock()
		mock_se.name = "SE-TEST-002"

		def capture_append(table, item_dict):
			appended_items.append(item_dict)

		mock_se.append.side_effect = capture_append

		with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe") as mock_frappe:
			mock_frappe.db.get_single_value.return_value = warehouse
			mock_frappe.db.get_value.return_value = template_item_code
			mock_frappe.new_doc.return_value = mock_se
			mock_frappe.throw.side_effect = Exception("frappe.throw")
			mock_frappe._.side_effect = lambda x: x

			from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue
			PPEIssue._create_material_issue_stock_entry(mock_self)

		# ASSERTION: The appended item_code is the variant, NOT the template
		self.assertEqual(len(appended_items), 1)
		self.assertEqual(appended_items[0]["item_code"], item_variant)
		self.assertNotEqual(
			appended_items[0]["item_code"],
			template_item_code,
			"Stock Entry item_code must be the variant, not the template",
		)


if __name__ == "__main__":
	unittest.main()
