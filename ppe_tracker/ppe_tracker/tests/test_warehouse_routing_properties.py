# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Tracker warehouse routing logic.

Feature: ppe-tracker-enhancements-v2

Property 11: Damaged/Unusable Returns Route to Wornout Warehouse
Property 13: Casual Issues Source From Returned PPE Warehouse

**Validates: Requirements 2.1, 2.3, 8.1, 8.4, 9.3**
"""

import unittest
from unittest.mock import patch, MagicMock, call

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    text,
    integers,
    composite,
    sampled_from,
    just,
)


# --- Strategies ---


@composite
def damaged_or_unusable_return_data(draw):
    """Generate PPE Return data with condition 'Damaged' or 'Unusable'.

    Returns a dict with:
      - condition: one of "Damaged", "Unusable"
      - ppe_item: a PPE item identifier
      - name: the PPE Return document name
      - quantity_returned: a positive integer
      - wornout_warehouse: simulated configured warehouse name
    """
    condition = draw(sampled_from(["Damaged", "Unusable"]))
    ppe_item = draw(text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-"))
    name = draw(text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    quantity_returned = draw(integers(min_value=1, max_value=100))
    wornout_warehouse = draw(text(min_size=3, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz -"))

    return {
        "condition": condition,
        "ppe_item": ppe_item,
        "name": name,
        "quantity_returned": quantity_returned,
        "wornout_warehouse": wornout_warehouse,
    }


@composite
def casual_issue_data(draw):
    """Generate PPE Issue data with issue_type 'Casual'.

    Returns a dict with:
      - issue_type: always "Casual"
      - ppe_item: a PPE item identifier
      - name: the PPE Issue document name
      - quantity: a positive integer
      - employee: an employee identifier
      - item_variant: empty string (no variant for simplicity)
      - returned_ppe_warehouse: simulated configured warehouse name
    """
    ppe_item = draw(text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-"))
    name = draw(text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    quantity = draw(integers(min_value=1, max_value=100))
    employee = draw(text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"))
    returned_ppe_warehouse = draw(text(min_size=3, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz -"))

    return {
        "issue_type": "Casual",
        "ppe_item": ppe_item,
        "name": name,
        "quantity": quantity,
        "employee": employee,
        "item_variant": "",
        "returned_ppe_warehouse": returned_ppe_warehouse,
    }


# --- Property 11 ---


class TestDamagedUnusableReturnsRouteToWornoutWarehouse(unittest.TestCase):
    """Property 11: Damaged/Unusable Returns Route to Wornout Warehouse

    For any PPE Return with condition "Damaged" or "Unusable", the
    Material Receipt target warehouse is the Wornout PPE Warehouse
    (from PPE Tracker Settings).

    Feature: ppe-tracker-enhancements-v2, Property 11
    **Validates: Requirements 2.1, 8.1, 8.4**
    """

    @given(data=damaged_or_unusable_return_data())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_damaged_unusable_returns_target_wornout_warehouse(self, data):
        """_get_target_warehouse() returns wornout_ppe_warehouse for Damaged/Unusable conditions.

        Feature: ppe-tracker-enhancements-v2, Property 11
        **Validates: Requirements 2.1, 8.1, 8.4**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        condition = data["condition"]
        wornout_warehouse = data["wornout_warehouse"]

        # Create a mock PPEReturn instance
        mock_self = MagicMock(spec=PPEReturn)
        mock_self.condition = condition

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe") as mock_frappe:
            # Mock frappe.db.get_single_value to return configured warehouse
            def get_single_value_side_effect(doctype, fieldname):
                if doctype == "PPE Tracker Settings" and fieldname == "wornout_ppe_warehouse":
                    return wornout_warehouse
                return None

            mock_frappe.db.get_single_value.side_effect = get_single_value_side_effect

            # Call _get_target_warehouse with the mock instance
            result = PPEReturn._get_target_warehouse(mock_self)

        # ASSERTION: The returned warehouse is always the wornout_ppe_warehouse
        self.assertEqual(result, wornout_warehouse)

        # ASSERTION: frappe.db.get_single_value was called with wornout_ppe_warehouse
        mock_frappe.db.get_single_value.assert_called_with(
            "PPE Tracker Settings", "wornout_ppe_warehouse"
        )


# --- Property 13 ---


class TestCasualIssuesSourceFromReturnedPPEWarehouse(unittest.TestCase):
    """Property 13: Casual Issues Source From Returned PPE Warehouse

    For any PPE Issue with issue_type "Casual", the Material Issue
    Stock Entry source warehouse is the Returned PPE Warehouse
    (from PPE Tracker Settings).

    Feature: ppe-tracker-enhancements-v2, Property 13
    **Validates: Requirements 2.3, 9.3**
    """

    @given(data=casual_issue_data())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_casual_issues_source_from_returned_ppe_warehouse(self, data):
        """_create_material_issue_stock_entry() uses returned_ppe_warehouse for Casual issues.

        Feature: ppe-tracker-enhancements-v2, Property 13
        **Validates: Requirements 2.3, 9.3**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        returned_ppe_warehouse = data["returned_ppe_warehouse"]
        ppe_item = data["ppe_item"]
        name = data["name"]
        quantity = data["quantity"]

        # Create a mock PPEIssue instance (no spec to allow .get() access)
        mock_self = MagicMock()
        mock_self.get.side_effect = lambda field: {
            "issue_type": "Casual",
            "item_variant": "",
        }.get(field, "")
        mock_self.name = name
        mock_self.ppe_item = ppe_item
        mock_self.quantity = quantity

        # Mock the Stock Entry document
        mock_se = MagicMock()
        mock_se.name = "SE-MOCK-001"

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe") as mock_frappe:
            # Mock frappe.db.get_single_value
            def get_single_value_side_effect(doctype, fieldname):
                if doctype == "PPE Tracker Settings" and fieldname == "returned_ppe_warehouse":
                    return returned_ppe_warehouse
                return None

            mock_frappe.db.get_single_value.side_effect = get_single_value_side_effect

            # Mock frappe.db.get_value for item_code lookup
            mock_frappe.db.get_value.return_value = "ITEM-CODE-001"

            # Mock frappe.new_doc to return our mock Stock Entry
            mock_frappe.new_doc.return_value = mock_se

            # Call _create_material_issue_stock_entry with the mock instance
            PPEIssue._create_material_issue_stock_entry(mock_self)

        # ASSERTION 1: frappe.db.get_single_value was called with returned_ppe_warehouse
        mock_frappe.db.get_single_value.assert_called_with(
            "PPE Tracker Settings", "returned_ppe_warehouse"
        )

        # ASSERTION 2: The Stock Entry was created with the correct source warehouse
        mock_se.append.assert_called_once()
        append_args = mock_se.append.call_args
        items_dict = append_args[0][1]
        self.assertEqual(items_dict["s_warehouse"], returned_ppe_warehouse)

        # ASSERTION 3: Stock Entry type is Material Issue
        self.assertEqual(mock_se.stock_entry_type, "Material Issue")

        # ASSERTION 4: The quantity matches the PPE Issue quantity
        self.assertEqual(items_dict["qty"], quantity)


if __name__ == "__main__":
    unittest.main()
