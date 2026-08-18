# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Unit tests for PPE Tracker scheduled task helpers.

Tests cover:
- mark_expired_issues() status transitions (Requirements 7.4)
- send_expiry_alerts() early return when no issues found (Requirements 8.5)
- _build_supervisor_map() error logging when reports_to is empty (Requirements 8.6)
"""

import unittest
from unittest.mock import patch, MagicMock, call


class TestMarkExpiredIssues(unittest.TestCase):
    """Unit tests for mark_expired_issues().

    Validates: Requirements 7.4
    """

    @patch("ppe_tracker.ppe_tracker.tasks.frappe")
    def test_mark_expired_issues_transitions_correct_records(self, mock_frappe):
        """mark_expired_issues() transitions all qualifying records to Expired status.

        Mocks frappe.get_all to return 3 issue names, then asserts that
        frappe.db.set_value is called 3 times with status='Expired' and
        frappe.db.commit is called once.

        Validates: Requirements 7.4
        """
        from ppe_tracker.ppe_tracker.tasks import mark_expired_issues

        # Setup: get_all returns 3 expired issue names
        mock_frappe.utils.today.return_value = "2024-06-15"
        mock_frappe.get_all.return_value = [
            "PPE-ISSUE-0001",
            "PPE-ISSUE-0002",
            "PPE-ISSUE-0003",
        ]

        mark_expired_issues()

        # Assert set_value called 3 times with correct arguments
        expected_calls = [
            call("PPE Issue", "PPE-ISSUE-0001", "status", "Expired"),
            call("PPE Issue", "PPE-ISSUE-0002", "status", "Expired"),
            call("PPE Issue", "PPE-ISSUE-0003", "status", "Expired"),
        ]
        mock_frappe.db.set_value.assert_has_calls(expected_calls, any_order=False)
        self.assertEqual(mock_frappe.db.set_value.call_count, 3)

        # Assert commit called once
        mock_frappe.db.commit.assert_called_once()

    @patch("ppe_tracker.ppe_tracker.tasks.frappe")
    def test_mark_expired_issues_does_not_touch_future_issues(self, mock_frappe):
        """mark_expired_issues() does not call set_value when no issues qualify.

        When frappe.get_all returns an empty list (no Active issues with
        expiry_date <= today), set_value should never be called. Commit is
        still called unconditionally.

        Validates: Requirements 7.4
        """
        from ppe_tracker.ppe_tracker.tasks import mark_expired_issues

        # Setup: no qualifying issues
        mock_frappe.utils.today.return_value = "2024-06-15"
        mock_frappe.get_all.return_value = []

        mark_expired_issues()

        # Assert set_value never called
        mock_frappe.db.set_value.assert_not_called()

        # Assert commit still called (unconditional in implementation)
        mock_frappe.db.commit.assert_called_once()


class TestSendExpiryAlerts(unittest.TestCase):
    """Unit tests for send_expiry_alerts().

    Validates: Requirements 8.5
    """

    @patch("ppe_tracker.ppe_tracker.tasks.frappe")
    def test_send_expiry_alerts_no_issues_returns_silently(self, mock_frappe):
        """send_expiry_alerts() returns early without sending email when no issues exist.

        When frappe.get_all returns an empty list, frappe.sendmail should never
        be called — the function returns silently.

        Validates: Requirements 8.5
        """
        from ppe_tracker.ppe_tracker.tasks import send_expiry_alerts

        # Setup: no expiring issues found
        mock_frappe.utils.today.return_value = "2024-06-15"
        mock_frappe.utils.add_days.return_value = "2024-07-15"
        mock_frappe.get_all.return_value = []

        send_expiry_alerts()

        # Assert sendmail never called
        mock_frappe.sendmail.assert_not_called()


class TestBuildSupervisorMap(unittest.TestCase):
    """Unit tests for _build_supervisor_map().

    Validates: Requirements 8.6
    """

    @patch("ppe_tracker.ppe_tracker.tasks.frappe")
    def test_build_supervisor_map_logs_error_when_no_reports_to(self, mock_frappe):
        """_build_supervisor_map() logs error and skips issue when employee has no reports_to.

        When frappe.db.get_value returns None for reports_to, the function should:
        - Call frappe.log_error with title="PPE Expiry Alert"
        - Exclude that issue from the returned supervisor map

        Validates: Requirements 8.6
        """
        from ppe_tracker.ppe_tracker.tasks import _build_supervisor_map

        # Setup: one issue whose employee has no reports_to
        issues = [
            {
                "name": "PPE-ISSUE-0001",
                "employee": "EMP-001",
                "employee_name": "John Doe",
                "ppe_item": "Safety Helmet",
                "issue_date": "2024-01-15",
                "expiry_date": "2024-07-15",
                "quantity": 1,
            }
        ]

        # Mock: reports_to returns None (no supervisor set)
        mock_frappe.db.get_value.return_value = None

        result = _build_supervisor_map(issues)

        # Assert log_error was called with the expected title
        mock_frappe.log_error.assert_called_once()
        call_kwargs = mock_frappe.log_error.call_args
        self.assertEqual(call_kwargs[1]["title"], "PPE Expiry Alert")

        # Assert the issue is NOT in the returned map (map should be empty)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
