# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for PPE report data functions.

Tests cover:
- PPE Inventory Report: active_issued count from get_data() (Requirement 10.1)
- Employee PPE Register: employee filter restriction for Employee-only users (Requirement 13.4)
- PPE Due for Replacement: default days_window of 30 when filter absent (Requirement 14.2)
"""

import unittest
from unittest.mock import patch, MagicMock


class TestPPEInventoryReportActiveIssuedCount(unittest.TestCase):
    """Validates PPE Inventory Report get_data() computes active_issued correctly.

    Requirement 10.1: The report SHALL display active issued quantity per PPE Item.
    """

    @patch("ppe_tracker.ppe_tracker.report.ppe_inventory_report.ppe_inventory_report.get_stock_qty")
    @patch("ppe_tracker.ppe_tracker.report.ppe_inventory_report.ppe_inventory_report.frappe")
    def test_ppe_inventory_report_active_issued_count(self, mock_frappe, mock_get_stock_qty):
        """get_data() returns correct active_issued count from frappe.db.count."""
        # Setup: one PPE Item returned
        mock_ppe_item = MagicMock()
        mock_ppe_item.name = "PPE-HELMET"
        mock_ppe_item.item_name = "Safety Helmet"
        mock_ppe_item.item_code = "ITEM-001"
        mock_ppe_item.ppe_category = "Head Protection"
        mock_ppe_item.status = "Active"

        mock_frappe.get_all.return_value = [mock_ppe_item]

        # Mock stock qty from Bin
        mock_get_stock_qty.return_value = 50

        # Mock frappe.db.count for PPE Issue active records
        mock_frappe.db.count.return_value = 5

        from ppe_tracker.ppe_tracker.report.ppe_inventory_report.ppe_inventory_report import get_data

        result = get_data({"ppe_item": None})

        # Assert active_issued is 5
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["active_issued"], 5)

        # Verify db.count was called with correct filters
        mock_frappe.db.count.assert_called_once_with(
            "PPE Issue", filters={"ppe_item": "PPE-HELMET", "status": "Active"}
        )


class TestEmployeePPERegisterEmployeeFilter(unittest.TestCase):
    """Validates Employee PPE Register restricts to own record for Employee-only users.

    Requirement 13.4: WHEN a user holds only the Employee role, the report
    SHALL automatically restrict results to that user's own linked Employee record.
    """

    @patch("ppe_tracker.ppe_tracker.report.employee_ppe_register.employee_ppe_register.frappe")
    def test_employee_ppe_register_restricts_to_own_record(self, mock_frappe):
        """get_employee_filter() sets filters['employee'] when user is Employee-only."""
        # Setup: user only has Employee and All roles (no elevated roles)
        mock_frappe.get_roles.return_value = ["Employee", "All"]
        mock_frappe.session = MagicMock()
        mock_frappe.session.user = "employee@example.com"

        # Mock lookup of Employee record by user_id
        mock_frappe.db.get_value.return_value = "EMP-001"

        from ppe_tracker.ppe_tracker.report.employee_ppe_register.employee_ppe_register import (
            get_employee_filter,
        )

        filters = {}
        get_employee_filter(filters)

        # Assert filter was restricted to the employee's own record
        self.assertEqual(filters["employee"], "EMP-001")

        # Verify the correct lookup was performed
        mock_frappe.db.get_value.assert_called_once_with(
            "Employee", {"user_id": "employee@example.com"}, "name"
        )


class TestPPEDueForReplacementDefaultWindow(unittest.TestCase):
    """Validates PPE Due for Replacement defaults days_window to 30.

    Requirement 14.2: WHEN the days_window filter is not specified,
    THE report SHALL default to 30 days.
    """

    @patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.date_diff")
    @patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.add_days")
    @patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.today")
    @patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.frappe")
    def test_ppe_due_for_replacement_defaults_window_to_30(
        self, mock_frappe, mock_today, mock_add_days, mock_date_diff
    ):
        """execute() uses 30 as default days_window when filter is absent."""
        mock_today.return_value = "2024-06-15"
        mock_add_days.return_value = "2024-07-15"
        mock_frappe.get_all.return_value = []  # No issues found

        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import (
            execute,
        )

        columns, data = execute({})

        # Assert add_days was called with today's date and default window of 30
        mock_add_days.assert_called_once_with("2024-06-15", 30)


if __name__ == "__main__":
    unittest.main()
