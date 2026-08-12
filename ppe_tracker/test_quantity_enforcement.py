# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Unit tests for PPE quantity enforcement logic.

Tests cover:
- PPE Request: _validate_max_quantity() blocks requests exceeding assignment limit (Req 24.1, 24.2)
- PPE Issue: _validate_max_issued_quantity() blocks issues exceeding cumulative limit (Req 24.3, 24.4)
"""

import unittest
from unittest.mock import patch, MagicMock


class TestPPERequestMaxQuantity(unittest.TestCase):
    """Unit tests for PPERequest._validate_max_quantity().

    Validates: Requirements 24.1, 24.2
    """

    def _make_request(self, employee="EMP-001", ppe_item="Safety Helmet", requested_quantity=1):
        """Create a mock PPERequest instance with the given fields."""
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

        req = PPERequest.__new__(PPERequest)
        req.employee = employee
        req.ppe_item = ppe_item
        req.requested_quantity = requested_quantity
        req.status = "Draft"
        req.rejection_reason = None
        return req

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe")
    def test_request_exceeds_assignment_quantity_raises_error(self, mock_frappe):
        """PPE Request with requested_quantity=3 when assignment allows 2 raises error.

        Validates: Requirements 24.1, 24.2
        """
        # Setup mock employee
        mock_employee = MagicMock()
        mock_employee.department = "Operations"
        mock_employee.designation = "Operator"
        mock_frappe.get_doc.return_value = mock_employee

        # Mock: find matching PPE Role Assignments
        mock_frappe.get_all.side_effect = [
            # First call: get PPE Role Assignment names
            ["PPERA-001"],
            # Second call: get PPE Role Assignment Item rows for this ppe_item
            [MagicMock(quantity=2)],
        ]

        mock_frappe.bold.side_effect = lambda x: x
        mock_frappe._.side_effect = lambda x: x

        req = self._make_request(requested_quantity=3)
        req._validate_max_quantity()

        # Should throw because 3 > 2
        mock_frappe.throw.assert_called_once()
        call_msg = mock_frappe.throw.call_args[0][0]
        self.assertIn("3", call_msg)
        self.assertIn("2", call_msg)

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe")
    def test_request_at_assignment_limit_passes(self, mock_frappe):
        """PPE Request with requested_quantity=2 when assignment allows 2 passes.

        Validates: Requirements 24.1, 24.2
        """
        mock_employee = MagicMock()
        mock_employee.department = "Operations"
        mock_employee.designation = "Operator"
        mock_frappe.get_doc.return_value = mock_employee

        mock_frappe.get_all.side_effect = [
            ["PPERA-001"],
            [MagicMock(quantity=2)],
        ]

        mock_frappe.bold.side_effect = lambda x: x
        mock_frappe._.side_effect = lambda x: x

        req = self._make_request(requested_quantity=2)
        req._validate_max_quantity()

        # Should NOT throw — quantity equals the cap
        mock_frappe.throw.assert_not_called()

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe")
    def test_request_below_assignment_limit_passes(self, mock_frappe):
        """PPE Request with requested_quantity=1 when assignment allows 5 passes.

        Validates: Requirements 24.1, 24.2
        """
        mock_employee = MagicMock()
        mock_employee.department = "Operations"
        mock_employee.designation = "Operator"
        mock_frappe.get_doc.return_value = mock_employee

        mock_frappe.get_all.side_effect = [
            ["PPERA-001"],
            [MagicMock(quantity=5)],
        ]

        mock_frappe.bold.side_effect = lambda x: x
        mock_frappe._.side_effect = lambda x: x

        req = self._make_request(requested_quantity=1)
        req._validate_max_quantity()

        # Should NOT throw — 1 < 5
        mock_frappe.throw.assert_not_called()

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe")
    def test_request_no_matching_assignment_passes(self, mock_frappe):
        """PPE Request with no matching assignment passes (no restriction).

        When no PPE Role Assignment matches the employee's department/designation,
        no quantity cap is enforced and the request proceeds without error.

        Validates: Requirements 24.1, 24.2
        """
        mock_employee = MagicMock()
        mock_employee.department = "Operations"
        mock_employee.designation = "Operator"
        mock_frappe.get_doc.return_value = mock_employee

        # No matching assignments found
        mock_frappe.get_all.return_value = []

        mock_frappe.bold.side_effect = lambda x: x
        mock_frappe._.side_effect = lambda x: x

        req = self._make_request(requested_quantity=10)
        req._validate_max_quantity()

        # Should NOT throw — no cap applied
        mock_frappe.throw.assert_not_called()


class TestPPEIssueMaxIssuedQuantity(unittest.TestCase):
    """Unit tests for PPEIssue._validate_max_issued_quantity().

    Validates: Requirements 24.3, 24.4
    """

    def _make_issue(self, employee="EMP-001", ppe_item="Safety Helmet", quantity=1):
        """Create a mock PPEIssue instance with the given fields."""
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        issue = PPEIssue.__new__(PPEIssue)
        issue.name = "PPE-ISSUE-NEW"
        issue.employee = employee
        issue.ppe_item = ppe_item
        issue.quantity = quantity
        return issue

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe")
    def test_issue_exceeds_cumulative_limit_raises_error(self, mock_frappe):
        """PPE Issue submit when existing active total + new qty exceeds assignment raises error.

        Scenario: Assignment allows 3, existing active total is 2, new issue qty is 2.
        Total would be 4 > 3, so validation should throw.

        Validates: Requirements 24.3, 24.4
        """
        # Mock employee doc
        mock_employee = MagicMock()
        mock_employee.get.side_effect = lambda field: {
            "department": "Operations",
            "designation": "Operator",
        }.get(field)
        mock_frappe.get_doc.side_effect = self._get_doc_side_effect(
            mock_employee,
            assignment_items=[MagicMock(ppe_item="Safety Helmet", quantity=3)],
        )

        # Mock: find matching assignments
        mock_frappe.get_all.return_value = ["PPERA-001"]

        # Mock: existing active total = 2
        mock_frappe.db.sql.return_value = [[2]]

        mock_frappe._.side_effect = lambda x: x

        issue = self._make_issue(quantity=2)
        issue._validate_max_issued_quantity()

        # Should throw because 2 (existing) + 2 (new) = 4 > 3 (max allowed)
        mock_frappe.throw.assert_called_once()
        call_msg = mock_frappe.throw.call_args[0][0]
        self.assertIn("3", call_msg)  # max allowed

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe")
    def test_issue_within_cumulative_limit_passes(self, mock_frappe):
        """PPE Issue submit when total stays within limit passes.

        Scenario: Assignment allows 5, existing active total is 2, new issue qty is 2.
        Total would be 4 <= 5, so validation passes.

        Validates: Requirements 24.3, 24.4
        """
        mock_employee = MagicMock()
        mock_employee.get.side_effect = lambda field: {
            "department": "Operations",
            "designation": "Operator",
        }.get(field)
        mock_frappe.get_doc.side_effect = self._get_doc_side_effect(
            mock_employee,
            assignment_items=[MagicMock(ppe_item="Safety Helmet", quantity=5)],
        )

        mock_frappe.get_all.return_value = ["PPERA-001"]

        # Existing active total = 2
        mock_frappe.db.sql.return_value = [[2]]

        mock_frappe._.side_effect = lambda x: x

        issue = self._make_issue(quantity=2)
        issue._validate_max_issued_quantity()

        # Should NOT throw — 2 + 2 = 4 <= 5
        mock_frappe.throw.assert_not_called()

    @patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe")
    def test_issue_no_matching_assignment_passes(self, mock_frappe):
        """PPE Issue submit with no matching assignment passes (no restriction).

        When no PPE Role Assignment matches the employee's department/designation,
        no cap is enforced.

        Validates: Requirements 24.3, 24.4
        """
        mock_employee = MagicMock()
        mock_employee.get.side_effect = lambda field: {
            "department": "Operations",
            "designation": "Operator",
        }.get(field)
        mock_frappe.get_doc.return_value = mock_employee

        # No matching assignments found
        mock_frappe.get_all.return_value = []

        mock_frappe._.side_effect = lambda x: x

        issue = self._make_issue(quantity=10)
        issue._validate_max_issued_quantity()

        # Should NOT throw — no cap applied
        mock_frappe.throw.assert_not_called()

    def _get_doc_side_effect(self, mock_employee, assignment_items=None):
        """Return a side_effect function for frappe.get_doc that handles Employee and Assignment."""
        def _side_effect(doctype, name=None):
            if doctype == "Employee":
                return mock_employee
            elif doctype == "PPE Role Assignment":
                mock_assignment = MagicMock()
                mock_assignment.required_items = assignment_items or []
                return mock_assignment
            return MagicMock()
        return _side_effect


if __name__ == "__main__":
    unittest.main()
