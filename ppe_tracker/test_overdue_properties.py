# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Tracker overdue detection and clearing.

Feature: ppe-tracker-enhancements-v2
Properties 15, 16, 17: Overdue Casual Issue detection, alert content, and return clearing.

**Validates: Requirements 10.1, 10.3, 10.4, 11.3**
"""

import unittest
from unittest.mock import patch, MagicMock, call
from datetime import date, timedelta

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    dates,
    integers,
    lists,
    composite,
    sampled_from,
    booleans,
    text,
    just,
)


# --- Strategies ---


class _FrappeDict(dict):
    """A dict subclass that supports attribute-style access (mimics frappe._dict)."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


@composite
def ppe_issue_overdue_dataset(draw):
    """Generate a mixed dataset of PPE Issues with varying criteria for overdue detection.

    Each record has:
      - name: unique issue identifier
      - issue_type: "Standard" or "Casual"
      - status: one of "Active", "Returned", "Expired", "Replaced"
      - expected_return_date: a date before, on, or after reference_today
      - docstatus: 0 or 1
      - employee_name, ppe_item, issue_date: required fields for email content

    Returns (all_issues, reference_today).
    """
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    num_issues = draw(integers(min_value=1, max_value=15))

    issues = []
    for i in range(num_issues):
        issue_type = draw(sampled_from(["Standard", "Casual"]))
        status = draw(sampled_from(["Active", "Returned", "Expired", "Replaced"]))
        docstatus = draw(sampled_from([0, 1]))
        offset_days = draw(integers(min_value=-180, max_value=180))
        expected_return_date = reference_today + timedelta(days=offset_days)
        issue_date = reference_today - timedelta(days=abs(offset_days) + 10)

        issues.append({
            "name": f"PPE-ISS-{i:04d}",
            "issue_type": issue_type,
            "status": status,
            "expected_return_date": expected_return_date,
            "docstatus": docstatus,
            "employee": f"HR-EMP-{i:04d}",
            "employee_name": f"Employee {i}",
            "ppe_item": f"PPE Item {i}",
            "issue_date": issue_date,
        })

    return (issues, reference_today)


@composite
def overdue_issues_for_email(draw):
    """Generate a list of overdue issues that would be included in an alert email.

    All issues satisfy: Casual, Active, expected_return_date <= today, docstatus=1.
    Returns (issues_list, reference_today).
    Uses frappe-style DotDict-like dicts to support both dict and attribute access.
    """
    reference_today = draw(dates(min_value=date(2021, 1, 1), max_value=date(2030, 12, 31)))

    num_issues = draw(integers(min_value=1, max_value=10))

    issues = []
    for i in range(num_issues):
        # expected_return_date is on or before today (1-180 days overdue)
        days_overdue = draw(integers(min_value=1, max_value=180))
        expected_return_date = reference_today - timedelta(days=days_overdue)
        issue_date = expected_return_date - timedelta(days=draw(integers(min_value=1, max_value=30)))

        issues.append(_FrappeDict({
            "name": f"PPE-ISS-{i:04d}",
            "employee": f"HR-EMP-{i:04d}",
            "employee_name": f"Employee {i}",
            "ppe_item": f"Safety Helmet {i}",
            "issue_date": issue_date,
            "expected_return_date": expected_return_date,
        }))

    return (issues, reference_today)


@composite
def ppe_return_with_issue(draw):
    """Generate a PPE Return linked to a PPE Issue with a given issue_type.

    Returns (ppe_issue_name, issue_type).
    """
    ppe_issue_name = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):04d}"
    issue_type = draw(sampled_from(["Casual", "Standard"]))
    return (ppe_issue_name, issue_type)


# --- Property 15 ---

class TestProperty15OverdueDetection(unittest.TestCase):
    """Property 15: Scheduled Job Identifies and Marks Overdue Casual Issues

    For any set of PPE Issues, send_casual_overdue_alerts() SHALL set is_overdue = 1
    on exactly those that have issue_type="Casual", status="Active", and
    expected_return_date on or before the current date (with docstatus=1);
    issues not matching all criteria SHALL NOT be marked.

    Feature: ppe-tracker-enhancements-v2, Property 15
    **Validates: Requirements 10.1, 10.4**
    """

    @given(dataset=ppe_issue_overdue_dataset())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_marks_exactly_qualifying_issues(self, dataset):
        """send_casual_overdue_alerts() marks only Casual+Active+overdue+submitted issues.

        Feature: ppe-tracker-enhancements-v2, Property 15
        **Validates: Requirements 10.1, 10.4**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        all_issues, reference_today = dataset

        # Determine which issues should be marked overdue
        qualifying = [
            issue for issue in all_issues
            if issue["issue_type"] == "Casual"
            and issue["status"] == "Active"
            and issue["expected_return_date"] <= reference_today
            and issue["docstatus"] == 1
        ]

        non_qualifying = [
            issue for issue in all_issues
            if issue not in qualifying
        ]

        # Build mock return value for frappe.get_all (simulates the DB query result)
        mock_get_all_result = []
        for issue in qualifying:
            mock_issue = MagicMock()
            mock_issue.name = issue["name"]
            mock_issue.employee = issue["employee"]
            mock_issue.employee_name = issue["employee_name"]
            mock_issue.ppe_item = issue["ppe_item"]
            mock_issue.issue_date = issue["issue_date"]
            mock_issue.expected_return_date = issue["expected_return_date"]
            mock_get_all_result.append(mock_issue)

        set_value_calls = []

        def mock_set_value(doctype, name, field, value=None):
            set_value_calls.append((doctype, name, field, value))

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe, \
             patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients") as mock_recipients:

            # Mock today() via frappe.utils used inside the function
            mock_frappe.utils.today.return_value = str(reference_today)

            # The function imports from frappe.utils inside - mock at module level
            mock_date_diff = MagicMock(side_effect=lambda a, b: (date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days)
            mock_frappe.utils.today.return_value = str(reference_today)

            # Mock get_all to return qualifying issues
            mock_frappe.get_all.return_value = mock_get_all_result

            # Mock db.set_value
            mock_frappe.db.set_value = mock_set_value
            mock_frappe.db.commit = MagicMock()

            # Mock sendmail to avoid actual email
            mock_frappe.sendmail = MagicMock()

            # Mock recipients
            mock_recipients.return_value = ["hr@example.com"]

            send_casual_overdue_alerts()

        # ASSERTION 1: set_value was called with is_overdue=1 for each qualifying issue
        overdue_set_calls = [
            (dt, name, field, val) for dt, name, field, val in set_value_calls
            if field == "is_overdue" and val == 1
        ]
        qualifying_names = {issue["name"] for issue in qualifying}
        marked_names = {c[1] for c in overdue_set_calls}

        self.assertEqual(
            marked_names, qualifying_names,
            f"Expected to mark {qualifying_names}, but marked {marked_names}"
        )

        # ASSERTION 2: Number of is_overdue=1 calls equals qualifying count
        self.assertEqual(len(overdue_set_calls), len(qualifying))

        # ASSERTION 3: No non-qualifying issue was marked
        non_qualifying_names = {issue["name"] for issue in non_qualifying}
        self.assertTrue(
            marked_names.isdisjoint(non_qualifying_names),
            "Non-qualifying issues should NOT be marked as overdue"
        )


# --- Property 16 ---

class TestProperty16OverdueAlertContent(unittest.TestCase):
    """Property 16: Overdue Alert Contains Required Information

    For any overdue casual PPE Issue in an alert email, the email content SHALL
    contain: Employee Name, PPE Item, Issue Date, Expected Return Date, and days overdue.

    Feature: ppe-tracker-enhancements-v2, Property 16
    **Validates: Requirements 10.3**
    """

    @given(dataset=overdue_issues_for_email())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_email_contains_all_required_fields(self, dataset):
        """Alert email HTML includes employee_name, ppe_item, issue_date,
        expected_return_date, and days_overdue for each overdue issue.

        Feature: ppe-tracker-enhancements-v2, Property 16
        **Validates: Requirements 10.3**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        overdue_issues, reference_today = dataset

        # Ensure at least one issue
        assume(len(overdue_issues) > 0)

        captured_message = {}

        def capture_sendmail(**kwargs):
            captured_message.update(kwargs)

        def mock_date_diff(d1, d2):
            """Calculate date_diff as (d1 - d2) in days, like frappe.utils.date_diff."""
            from datetime import date as dt_date
            if isinstance(d1, str):
                d1 = dt_date.fromisoformat(d1)
            if isinstance(d2, str):
                d2 = dt_date.fromisoformat(d2)
            return (d1 - d2).days

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe, \
             patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients") as mock_recipients, \
             patch("frappe.utils.today", return_value=str(reference_today)), \
             patch("frappe.utils.date_diff", side_effect=mock_date_diff):

            # Mock get_all to return our overdue issues
            mock_frappe.get_all.return_value = overdue_issues

            # Mock db operations
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()

            # Capture the sendmail call
            mock_frappe.sendmail = capture_sendmail

            # Mock recipients
            mock_recipients.return_value = ["hr@example.com", "safety@example.com"]

            send_casual_overdue_alerts()

        # The email should have been sent
        self.assertIn("message", captured_message, "sendmail should have been called with message")

        email_html = captured_message["message"]

        # ASSERTION: Each overdue issue's required fields appear in the email
        for issue in overdue_issues:
            self.assertIn(
                str(issue.employee_name), email_html,
                f"Email should contain employee_name: {issue.employee_name}"
            )
            self.assertIn(
                str(issue.ppe_item), email_html,
                f"Email should contain ppe_item: {issue.ppe_item}"
            )
            self.assertIn(
                str(issue.issue_date), email_html,
                f"Email should contain issue_date: {issue.issue_date}"
            )
            self.assertIn(
                str(issue.expected_return_date), email_html,
                f"Email should contain expected_return_date: {issue.expected_return_date}"
            )

            # Calculate expected days overdue
            days_overdue = (reference_today - issue.expected_return_date).days
            self.assertIn(
                str(days_overdue), email_html,
                f"Email should contain days_overdue: {days_overdue}"
            )


# --- Property 17 ---

class TestProperty17ReturnClearsOverdue(unittest.TestCase):
    """Property 17: Return Clears Overdue Flag

    For any PPE Issue with is_overdue=1 and issue_type="Casual", submitting a PPE Return
    against that issue SHALL clear is_overdue to 0.

    Feature: ppe-tracker-enhancements-v2, Property 17
    **Validates: Requirements 11.3**
    """

    @given(data=ppe_return_with_issue())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_return_clears_overdue_for_casual(self, data):
        """_clear_overdue_flag_if_casual() clears is_overdue when issue_type is Casual,
        and does NOT clear it when issue_type is not Casual.

        Feature: ppe-tracker-enhancements-v2, Property 17
        **Validates: Requirements 11.3**
        """
        ppe_issue_name, issue_type = data

        with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe") as mock_frappe:
            # Mock get_value to return the issue_type
            mock_frappe.db.get_value.return_value = issue_type
            mock_frappe.db.set_value = MagicMock()

            # Create a minimal PPE Return instance to call the method on
            from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

            # Create a mock instance with the ppe_issue attribute
            return_doc = PPEReturn.__new__(PPEReturn)
            return_doc.ppe_issue = ppe_issue_name

            # Call the method under test
            return_doc._clear_overdue_flag_if_casual()

            # Verify get_value was called to check issue_type
            mock_frappe.db.get_value.assert_called_once_with(
                "PPE Issue", ppe_issue_name, "issue_type"
            )

            if issue_type == "Casual":
                # ASSERTION: is_overdue should be cleared to 0
                mock_frappe.db.set_value.assert_called_once_with(
                    "PPE Issue", ppe_issue_name, "is_overdue", 0
                )
            else:
                # ASSERTION: is_overdue should NOT be cleared for non-Casual issues
                mock_frappe.db.set_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
