# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for size-aware PPE issuing logic.

Feature: ppe-tracker-enhancements-v2

Property 25: Size Auto-Population on Issue and Request
Property 26: Stock Entry Uses Item Variant for Sized Issues

**Validates: Requirements 17.2, 17.3, 17.4, 17.5**
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    text,
    integers,
    composite,
    sampled_from,
    just,
    booleans,
    none,
)


# --- Strategies ---


@composite
def employee_ppe_size_data(draw):
    """Generate data for resolve_employee_ppe_size scenarios.

    Returns a dict with:
      - employee: employee identifier
      - ppe_item: PPE item identifier
      - size: a size value (e.g., "10", "Large")
      - item_variant: an item variant name
      - scenario: one of "no_record", "no_row", "no_variant", "valid"
    """
    employee = draw(text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    ppe_item = draw(text(min_size=3, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-"))
    size = draw(text(min_size=1, max_size=10, alphabet="0123456789LMSXlarge"))
    item_variant = draw(text(min_size=3, max_size=30, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "))
    scenario = draw(sampled_from(["no_record", "no_row", "no_variant", "valid"]))

    return {
        "employee": employee,
        "ppe_item": ppe_item,
        "size": size,
        "item_variant": item_variant,
        "scenario": scenario,
    }


@composite
def resolve_size_if_applicable_data(draw):
    """Generate data for _resolve_size_if_applicable scenarios.

    Returns a dict with:
      - employee: employee identifier
      - ppe_item: PPE item identifier
      - has_sizes: whether the PPE Item has sizes enabled (0 or 1)
      - size: resolved size value
      - item_variant: resolved item variant
    """
    employee = draw(text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    ppe_item = draw(text(min_size=3, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-"))
    has_sizes = draw(sampled_from([0, 1]))
    size = draw(text(min_size=1, max_size=10, alphabet="0123456789LMSXlarge"))
    item_variant = draw(text(min_size=3, max_size=30, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "))

    return {
        "employee": employee,
        "ppe_item": ppe_item,
        "has_sizes": has_sizes,
        "size": size,
        "item_variant": item_variant,
    }


@composite
def stock_entry_variant_data(draw):
    """Generate data for _create_material_issue_stock_entry item_variant scenarios.

    Returns a dict with:
      - ppe_item: PPE item identifier
      - name: the PPE Issue document name
      - quantity: a positive integer
      - employee: an employee identifier
      - item_variant: an item variant name (non-empty for sized items)
      - template_item_code: the template item code from PPE Item
      - source_warehouse: simulated configured warehouse name
      - use_variant: whether to use item_variant (True) or template (False)
    """
    ppe_item = draw(text(min_size=3, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-"))
    name = draw(text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    quantity = draw(integers(min_value=1, max_value=100))
    employee = draw(text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    item_variant = draw(text(min_size=3, max_size=30, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "))
    template_item_code = draw(text(min_size=3, max_size=30, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    source_warehouse = draw(text(min_size=3, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz -"))
    use_variant = draw(booleans())

    return {
        "ppe_item": ppe_item,
        "name": name,
        "quantity": quantity,
        "employee": employee,
        "item_variant": item_variant,
        "template_item_code": template_item_code,
        "source_warehouse": source_warehouse,
        "use_variant": use_variant,
    }


# --- Property 25: Size Auto-Population on Issue and Request ---


class TestSizeAutoPopulationResolveEmployeePPESize(unittest.TestCase):
    """Property 25: Size Auto-Population on Issue and Request

    Test resolve_employee_ppe_size():
    - Raises error if no Employee PPE Size record exists
    - Raises error if no matching PPE Size Item row for the PPE Item
    - Raises error if item_variant is empty on the matching row
    - Returns (size, item_variant) tuple when valid

    Feature: ppe-tracker-enhancements-v2, Property 25
    **Validates: Requirements 17.2, 17.4**
    """

    @given(data=employee_ppe_size_data())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_resolve_employee_ppe_size_all_scenarios(self, data):
        """resolve_employee_ppe_size() raises error for missing/incomplete records,
        returns (size, item_variant) for valid records.

        Feature: ppe-tracker-enhancements-v2, Property 25
        **Validates: Requirements 17.2, 17.4**
        """
        from ppe_tracker.ppe_tracker.api.size_utils import resolve_employee_ppe_size

        employee = data["employee"]
        ppe_item = data["ppe_item"]
        size = data["size"]
        item_variant = data["item_variant"]
        scenario = data["scenario"]

        with patch("ppe_tracker.ppe_tracker.api.size_utils.frappe") as mock_frappe:
            # Setup mock for frappe.bold (used in error messages)
            mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
            mock_frappe._ = lambda x: x

            # Track thrown errors
            thrown_errors = []

            def mock_throw(msg):
                thrown_errors.append(msg)
                raise Exception(msg)

            mock_frappe.throw.side_effect = mock_throw

            if scenario == "no_record":
                # No Employee PPE Size record exists
                mock_frappe.db.exists.return_value = None

                with self.assertRaises(Exception):
                    resolve_employee_ppe_size(employee, ppe_item)

                # ASSERTION: frappe.throw was called (no size record)
                self.assertEqual(len(thrown_errors), 1)
                mock_frappe.db.exists.assert_called_once_with(
                    "Employee PPE Size", {"employee": employee}
                )

            elif scenario == "no_row":
                # Record exists but no row for this PPE Item
                size_record_name = f"EPS-{employee}"
                mock_frappe.db.exists.return_value = size_record_name
                mock_frappe.db.get_value.return_value = None

                with self.assertRaises(Exception):
                    resolve_employee_ppe_size(employee, ppe_item)

                # ASSERTION: frappe.throw was called (no matching row)
                self.assertEqual(len(thrown_errors), 1)
                mock_frappe.db.get_value.assert_called_once_with(
                    "PPE Size Item",
                    {"parent": size_record_name, "ppe_item": ppe_item},
                    ["size", "item_variant"],
                    as_dict=True,
                )

            elif scenario == "no_variant":
                # Row exists but item_variant is empty
                size_record_name = f"EPS-{employee}"
                mock_frappe.db.exists.return_value = size_record_name

                mock_size_item = MagicMock()
                mock_size_item.size = size
                mock_size_item.item_variant = ""  # Empty variant
                mock_frappe.db.get_value.return_value = mock_size_item

                with self.assertRaises(Exception):
                    resolve_employee_ppe_size(employee, ppe_item)

                # ASSERTION: frappe.throw was called (no item_variant)
                self.assertEqual(len(thrown_errors), 1)

            elif scenario == "valid":
                # Valid: record exists, row exists, item_variant is populated
                size_record_name = f"EPS-{employee}"
                mock_frappe.db.exists.return_value = size_record_name

                mock_size_item = MagicMock()
                mock_size_item.size = size
                mock_size_item.item_variant = item_variant
                mock_frappe.db.get_value.return_value = mock_size_item

                result = resolve_employee_ppe_size(employee, ppe_item)

                # ASSERTION: No error was thrown
                self.assertEqual(len(thrown_errors), 0)

                # ASSERTION: Returns correct (size, item_variant) tuple
                self.assertEqual(result, (size, item_variant))

                # ASSERTION: db.exists was called correctly
                mock_frappe.db.exists.assert_called_once_with(
                    "Employee PPE Size", {"employee": employee}
                )

                # ASSERTION: db.get_value was called correctly
                mock_frappe.db.get_value.assert_called_once_with(
                    "PPE Size Item",
                    {"parent": size_record_name, "ppe_item": ppe_item},
                    ["size", "item_variant"],
                    as_dict=True,
                )


class TestSizeAutoPopulationResolveSizeIfApplicable(unittest.TestCase):
    """Property 25: Size Auto-Population — _resolve_size_if_applicable()

    - If PPE Item has_sizes = 0 → size and item_variant cleared, no error
    - If PPE Item has_sizes = 1 → calls resolve_employee_ppe_size and sets fields

    Feature: ppe-tracker-enhancements-v2, Property 25
    **Validates: Requirements 17.2, 17.4**
    """

    @given(data=resolve_size_if_applicable_data())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_resolve_size_if_applicable_behavior(self, data):
        """_resolve_size_if_applicable() clears size fields when has_sizes=0,
        populates them from resolve_employee_ppe_size when has_sizes=1.

        Feature: ppe-tracker-enhancements-v2, Property 25
        **Validates: Requirements 17.2, 17.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        employee = data["employee"]
        ppe_item = data["ppe_item"]
        has_sizes = data["has_sizes"]
        size = data["size"]
        item_variant = data["item_variant"]

        # Create a mock PPEIssue instance
        mock_self = MagicMock(spec=PPEIssue)
        mock_self.employee = employee
        mock_self.ppe_item = ppe_item
        mock_self.size = "old_size"
        mock_self.item_variant = "old_variant"

        with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe") as mock_frappe:
            # Mock frappe.db.get_value for has_sizes lookup
            mock_frappe.db.get_value.return_value = has_sizes

            if has_sizes:
                # Mock the resolve_employee_ppe_size import
                with patch(
                    "ppe_tracker.ppe_tracker.api.size_utils.resolve_employee_ppe_size",
                    return_value=(size, item_variant),
                ) as mock_resolve:
                    PPEIssue._resolve_size_if_applicable(mock_self)

                # ASSERTION: size and item_variant are set from resolve function
                self.assertEqual(mock_self.size, size)
                self.assertEqual(mock_self.item_variant, item_variant)

            else:
                PPEIssue._resolve_size_if_applicable(mock_self)

                # ASSERTION: size and item_variant are cleared
                self.assertEqual(mock_self.size, "")
                self.assertEqual(mock_self.item_variant, "")

            # ASSERTION: frappe.db.get_value was called to check has_sizes
            mock_frappe.db.get_value.assert_called_with("PPE Item", ppe_item, "has_sizes")


# --- Property 26: Stock Entry Uses Item Variant for Sized Issues ---


class TestStockEntryUsesItemVariantForSizedIssues(unittest.TestCase):
    """Property 26: Stock Entry Uses Item Variant for Sized Issues

    For any PPE Issue where item_variant is populated (sized PPE Item),
    the Material Issue Stock Entry SHALL use the item_variant Item Code
    rather than the template Item Code.

    For any PPE Issue where item_variant is NOT populated,
    the Material Issue Stock Entry SHALL use the template item_code from PPE Item.

    Feature: ppe-tracker-enhancements-v2, Property 26
    **Validates: Requirements 17.3, 17.5**
    """

    @given(data=stock_entry_variant_data())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_stock_entry_uses_item_variant_or_template(self, data):
        """_create_material_issue_stock_entry() uses item_variant when set,
        template item_code otherwise.

        Feature: ppe-tracker-enhancements-v2, Property 26
        **Validates: Requirements 17.3, 17.5**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        ppe_item = data["ppe_item"]
        name = data["name"]
        quantity = data["quantity"]
        item_variant = data["item_variant"]
        template_item_code = data["template_item_code"]
        source_warehouse = data["source_warehouse"]
        use_variant = data["use_variant"]

        # Determine which item_variant the mock will return
        effective_variant = item_variant if use_variant else ""

        # Create a mock PPEIssue instance
        mock_self = MagicMock()
        mock_self.get.side_effect = lambda field: {
            "issue_type": "Standard",
            "item_variant": effective_variant,
        }.get(field, "")
        mock_self.name = name
        mock_self.ppe_item = ppe_item
        mock_self.quantity = quantity
        mock_self.item_variant = effective_variant

        # Mock the Stock Entry document
        mock_se = MagicMock()
        mock_se.name = "SE-MOCK-001"

        with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe") as mock_frappe:
            # Mock frappe.db.get_single_value for warehouse lookup
            mock_frappe.db.get_single_value.return_value = source_warehouse

            # Mock frappe.db.get_value for template item_code lookup
            mock_frappe.db.get_value.return_value = template_item_code

            # Mock frappe.new_doc to return our mock Stock Entry
            mock_frappe.new_doc.return_value = mock_se

            # Mock frappe._ for translations
            mock_frappe._ = lambda x: x

            # Call _create_material_issue_stock_entry with the mock instance
            PPEIssue._create_material_issue_stock_entry(mock_self)

        # ASSERTION: Stock Entry was created
        mock_frappe.new_doc.assert_called_once_with("Stock Entry")

        # ASSERTION: Stock Entry items were appended
        mock_se.append.assert_called_once()
        append_args = mock_se.append.call_args
        items_dict = append_args[0][1]

        if use_variant:
            # ASSERTION: When item_variant is set, it is used as item_code
            self.assertEqual(items_dict["item_code"], item_variant)

            # ASSERTION: frappe.db.get_value was NOT called for template item_code
            mock_frappe.db.get_value.assert_not_called()
        else:
            # ASSERTION: When item_variant is empty, template item_code is used
            self.assertEqual(items_dict["item_code"], template_item_code)

            # ASSERTION: frappe.db.get_value WAS called for template item_code
            mock_frappe.db.get_value.assert_called_once_with(
                "PPE Item", ppe_item, "item_code"
            )

        # ASSERTION: Quantity matches
        self.assertEqual(items_dict["qty"], quantity)

        # ASSERTION: Source warehouse is correctly set
        self.assertEqual(items_dict["s_warehouse"], source_warehouse)

        # ASSERTION: Stock Entry type is Material Issue
        self.assertEqual(mock_se.stock_entry_type, "Material Issue")

        # ASSERTION: Stock Entry was submitted
        mock_se.insert.assert_called_once_with(ignore_permissions=True)
        mock_se.submit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
