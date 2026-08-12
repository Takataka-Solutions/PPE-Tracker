# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for PPE Compliance Summary report.

Tests cover:
- Required count calculated as active employees × assignment quantity (Requirement 25.1, 25.3)
- Issued qty sums only active PPE Issues (Requirement 25.1)
- Gap calculation: Required - Issued - Available Stock (Requirement 25.4)
- Department filter restricts data correctly (Requirement 25.2)
- PPE Item filter restricts data correctly (Requirement 25.2)
- Empty data when no PPE Role Assignments exist (Requirement 25.1)
"""

import unittest
from unittest.mock import patch, MagicMock

MODULE_PATH = "ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary"


class AttrDict(dict):
    """Dict subclass that supports attribute-style access (like frappe._dict)."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def D(d):
    """Convert a plain dict to an AttrDict for mocking frappe.db.sql as_dict results."""
    return AttrDict(d)


class TestPPEComplianceSummaryRequiredCount(unittest.TestCase):
    """Validates that Required Qty = active employees × assignment quantity.

    **Validates: Requirements 25.1, 25.3**
    """

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_required_count_single_assignment(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Required = 3 employees × quantity 2 = 6 for a single assignment."""
        mock_frappe.db.sql.side_effect = [
            # First call: fetch PPE Role Assignments
            [D({"assignment_name": "PRA-001", "department": "Operations", "designation": None,
                "ppe_item": "Safety Helmet", "quantity": 2})],
            # Second call: count employees matching dept "Operations"
            [D({"cnt": 3})],
        ]

        # PPE Item details lookup
        mock_frappe.db.get_value.return_value = D({"ppe_category": "Head Protection", "item_code": "ITEM-HELMET"})

        mock_requested.return_value = 0
        mock_issued.return_value = 0
        mock_stock.return_value = 0

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ppe_item"], "Safety Helmet")
        self.assertEqual(result[0]["required_qty"], 6)  # 3 employees × 2 qty

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_required_count_multiple_assignments_same_item(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Required aggregates across multiple assignments for the same PPE Item.

        Assignment 1: Dept A, qty 1, 5 employees = 5
        Assignment 2: Dept B, qty 3, 2 employees = 6
        Total required for item = 11
        """
        mock_frappe.db.sql.side_effect = [
            # Assignments query
            [
                D({"assignment_name": "PRA-001", "department": "Dept A", "designation": None,
                   "ppe_item": "Gloves", "quantity": 1}),
                D({"assignment_name": "PRA-002", "department": "Dept B", "designation": None,
                   "ppe_item": "Gloves", "quantity": 3}),
            ],
            # Employee count for Dept A
            [D({"cnt": 5})],
            # Employee count for Dept B
            [D({"cnt": 2})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "Hand Protection", "item_code": "ITEM-GLOVES"})

        mock_requested.return_value = 0
        mock_issued.return_value = 0
        mock_stock.return_value = 0

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ppe_item"], "Gloves")
        self.assertEqual(result[0]["required_qty"], 11)  # 5×1 + 2×3


class TestPPEComplianceSummaryIssuedQty(unittest.TestCase):
    """Validates that Issued Qty sums only active PPE Issues (docstatus=1, status=Active).

    **Validates: Requirements 25.1**
    """

    @patch(f"{MODULE_PATH}.frappe")
    def test_issued_qty_sums_active_issues(self, mock_frappe):
        """get_issued_qty() returns sum of quantities from active PPE Issues."""
        mock_frappe.db.sql.return_value = [D({"total": 7})]

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_issued_qty

        result = get_issued_qty("Safety Helmet")

        self.assertEqual(result, 7)

        # Verify the query filters for docstatus=1 and status='Active'
        call_args = mock_frappe.db.sql.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        self.assertIn("docstatus = 1", query)
        self.assertIn("status = 'Active'", query)
        self.assertEqual(params["ppe_item"], "Safety Helmet")

    @patch(f"{MODULE_PATH}.frappe")
    def test_issued_qty_returns_zero_when_no_issues(self, mock_frappe):
        """get_issued_qty() returns 0 when no active PPE Issues exist."""
        mock_frappe.db.sql.return_value = [D({"total": 0})]

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_issued_qty

        result = get_issued_qty("Nonexistent Item")

        self.assertEqual(result, 0)


class TestPPEComplianceSummaryGapCalculation(unittest.TestCase):
    """Validates Gap = Required - Issued - Available Stock.

    **Validates: Requirements 25.4**
    """

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_gap_positive_shortfall(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Gap is positive when required exceeds issued + stock.

        Required=10, Issued=3, Stock=2 → Gap=5
        """
        mock_frappe.db.sql.side_effect = [
            # Assignments
            [D({"assignment_name": "PRA-001", "department": "Ops", "designation": None,
                "ppe_item": "Boots", "quantity": 2})],
            # 5 employees × qty 2 = required 10
            [D({"cnt": 5})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "Foot Protection", "item_code": "ITEM-BOOTS"})

        mock_requested.return_value = 1
        mock_issued.return_value = 3
        mock_stock.return_value = 2

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["required_qty"], 10)
        self.assertEqual(result[0]["issued_qty"], 3)
        self.assertEqual(result[0]["available_stock"], 2)
        self.assertEqual(result[0]["gap"], 5)  # 10 - 3 - 2 = 5

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_gap_negative_adequate_supply(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Gap is negative when issued + stock exceeds required.

        Required=4, Issued=3, Stock=5 → Gap=-4
        """
        mock_frappe.db.sql.side_effect = [
            [D({"assignment_name": "PRA-001", "department": "Warehouse", "designation": None,
                "ppe_item": "Goggles", "quantity": 1})],
            [D({"cnt": 4})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "Eye Protection", "item_code": "ITEM-GOGGLES"})

        mock_requested.return_value = 0
        mock_issued.return_value = 3
        mock_stock.return_value = 5

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(result[0]["gap"], -4)  # 4 - 3 - 5 = -4

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_gap_zero_exact_match(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Gap is zero when issued + stock equals required.

        Required=6, Issued=4, Stock=2 → Gap=0
        """
        mock_frappe.db.sql.side_effect = [
            [D({"assignment_name": "PRA-001", "department": "IT", "designation": None,
                "ppe_item": "ESD Gloves", "quantity": 3})],
            [D({"cnt": 2})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "ESD Protection", "item_code": "ITEM-ESD"})

        mock_requested.return_value = 0
        mock_issued.return_value = 4
        mock_stock.return_value = 2

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(result[0]["gap"], 0)  # 6 - 4 - 2 = 0


class TestPPEComplianceSummaryDepartmentFilter(unittest.TestCase):
    """Validates that Department filter restricts results correctly.

    **Validates: Requirements 25.1, 25.3**
    """

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_department_filter_restricts_assignments(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """Only assignments matching the filtered department are queried."""
        mock_frappe.db.sql.side_effect = [
            [D({"assignment_name": "PRA-001", "department": "Safety", "designation": None,
                "ppe_item": "Hard Hat", "quantity": 1})],
            [D({"cnt": 8})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "Head Protection", "item_code": "ITEM-HAT"})

        mock_requested.return_value = 2
        mock_issued.return_value = 5
        mock_stock.return_value = 1

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({"department": "Safety"})

        # Verify the assignment SQL included the department filter
        first_sql_call = mock_frappe.db.sql.call_args_list[0]
        query = first_sql_call[0][0]
        params = first_sql_call[0][1]

        self.assertIn("pra.department = %(department)s", query)
        self.assertEqual(params["department"], "Safety")

        # Result should reflect only the filtered assignment
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ppe_item"], "Hard Hat")
        self.assertEqual(result[0]["required_qty"], 8)  # 8 employees × 1


class TestPPEComplianceSummaryPPEItemFilter(unittest.TestCase):
    """Validates that PPE Item filter restricts results to a single item.

    **Validates: Requirements 25.1, 25.3**
    """

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_ppe_item_filter_returns_only_matching_item(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """When ppe_item filter is set, only data for that item is returned."""
        mock_frappe.db.sql.side_effect = [
            # Assignments return multiple items
            [
                D({"assignment_name": "PRA-001", "department": "Ops", "designation": None,
                   "ppe_item": "Helmet", "quantity": 1}),
                D({"assignment_name": "PRA-002", "department": "Ops", "designation": None,
                   "ppe_item": "Gloves", "quantity": 2}),
            ],
            # Employee count for Helmet assignment
            [D({"cnt": 4})],
            # Employee count for Gloves assignment
            [D({"cnt": 4})],
        ]

        mock_frappe.db.get_value.return_value = D({"ppe_category": "Hand Protection", "item_code": "ITEM-GLOVES"})

        mock_requested.return_value = 1
        mock_issued.return_value = 2
        mock_stock.return_value = 3

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({"ppe_item": "Gloves"})

        # Only the Gloves item should be in result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ppe_item"], "Gloves")
        self.assertEqual(result[0]["required_qty"], 8)  # 4 employees × 2

    @patch(f"{MODULE_PATH}.get_available_stock")
    @patch(f"{MODULE_PATH}.get_issued_qty")
    @patch(f"{MODULE_PATH}.get_requested_qty")
    @patch(f"{MODULE_PATH}.frappe")
    def test_ppe_item_filter_nonexistent_returns_empty(self, mock_frappe, mock_requested, mock_issued, mock_stock):
        """When ppe_item filter doesn't match any assignment, return empty."""
        mock_frappe.db.sql.side_effect = [
            [D({"assignment_name": "PRA-001", "department": "Ops", "designation": None,
                "ppe_item": "Helmet", "quantity": 1})],
            [D({"cnt": 3})],
        ]

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({"ppe_item": "Nonexistent PPE"})

        self.assertEqual(result, [])


class TestPPEComplianceSummaryNoAssignments(unittest.TestCase):
    """Validates that report returns empty data when no PPE Role Assignments exist.

    **Validates: Requirements 25.1**
    """

    @patch(f"{MODULE_PATH}.frappe")
    def test_empty_data_when_no_assignments(self, mock_frappe):
        """get_data() returns empty list when no PPE Role Assignments are found."""
        mock_frappe.db.sql.return_value = []

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({})

        self.assertEqual(result, [])

    @patch(f"{MODULE_PATH}.frappe")
    def test_empty_data_with_filters_no_matching_assignments(self, mock_frappe):
        """get_data() returns empty when dept filter yields no assignments."""
        mock_frappe.db.sql.return_value = []

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_data

        result = get_data({"department": "Nonexistent Dept"})

        self.assertEqual(result, [])


class TestPPEComplianceSummaryHelperFunctions(unittest.TestCase):
    """Tests for individual helper functions: get_requested_qty, get_available_stock.

    **Validates: Requirements 25.1**
    """

    @patch(f"{MODULE_PATH}.frappe")
    def test_get_requested_qty(self, mock_frappe):
        """get_requested_qty() sums from pending/approved/submitted PPE Requests."""
        mock_frappe.db.sql.return_value = [D({"total": 12})]

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_requested_qty

        result = get_requested_qty("Safety Boots")

        self.assertEqual(result, 12)

        # Verify status filter includes correct statuses
        call_args = mock_frappe.db.sql.call_args
        query = call_args[0][0]
        self.assertIn("Pending Approval", query)
        self.assertIn("Approved", query)
        self.assertIn("Submitted", query)

    @patch(f"{MODULE_PATH}.frappe")
    def test_get_available_stock(self, mock_frappe):
        """get_available_stock() fetches total actual_qty from tabBin."""
        mock_frappe.db.sql.return_value = [D({"total": 25.0})]

        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_available_stock

        result = get_available_stock("ITEM-BOOTS")

        self.assertEqual(result, 25.0)

        # Verify correct item_code was queried
        call_args = mock_frappe.db.sql.call_args
        params = call_args[0][1]
        self.assertEqual(params["item_code"], "ITEM-BOOTS")

    @patch(f"{MODULE_PATH}.frappe")
    def test_get_available_stock_returns_zero_for_none_item_code(self, mock_frappe):
        """get_available_stock() returns 0 when item_code is None."""
        from ppe_tracker.ppe_tracker.ppe_tracker.report.ppe_compliance_summary.ppe_compliance_summary import get_available_stock

        result = get_available_stock(None)

        self.assertEqual(result, 0)
        # Should not query DB when item_code is None
        mock_frappe.db.sql.assert_not_called()


if __name__ == "__main__":
    unittest.main()
