# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for casual PPE overdue detection and clearing.

- Property 15: Scheduled Job Identifies and Marks Overdue Casual Issues
- Property 16: Overdue Alert Contains Required Information
- Property 17: Return Clears Overdue Flag

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
    text,
    just,
    booleans,
)


class AttrDict(dict):
    """Dict subclass that supports attribute access (mimics frappe._dict)."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@composite
def casual_overdue_dataset(draw):
    """Generate a dataset of PPE Issues with mixed issue_type, status, and dates.

    Returns a tuple of (all_issues, reference_today) where each issue has:
      - name: unique identifier
      - employee: employee ID
      - employee_name: display name
      - ppe_item: PPE item name
      - issue_date: date of issuance
      - expected_return_date: date or None
      - issue_type: "Casual" or "Standard"
      - status: one of "Active", "Returned", "Expired", "Replaced"
      - docstatus: 1 (submitted) or 0 (draft)
    """
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    num_issues = draw(integers(min_value=1, max_value=20))

    issue_types = ["Casual", "Standard"]
    statuses = ["Active", "Returned", "Expired", "Replaced"]

    issues = []
    for i in range(num_issues):
        issue_type = draw(sampled_from(issue_types))
        status = draw(sampled_from(statuses))
        docstatus = draw(sampled_from([0, 1]))

        # Generate expected_return_date: some before today, some after
        offset_days = draw(integers(min_value=-60, max_value=60))
        expected_return_date = reference_today + timedelta(days=offset_days)

        # Issue date is always before expected return date
        issue_date = expected_return_date - timedelta(days=draw(integers(min_value=1, max_value=90)))

        issues.append({
            "name": f"PPE-ISS-{i:04d}",
            "employee": f"EMP-{i:04d}",
            "employee_name": f"Employee {i}",
            "ppe_item": f"PPE-ITEM-{i % 5:02d}",
            "issue_date": issue_date,
            "expected_return_date": expected_return_date,
            "issue_type": issue_type,
            "status": status,
            "docstatus": docstatus,
        })

    return (issues, reference_today)


# ---------------------------------------------------------------------------
# Property 15: Scheduled Job Identifies and Marks Overdue Casual Issues
# ---------------------------------------------------------------------------


class TestOverdueDetectionProperty(unittest.TestCase):
    """Property 15: Scheduled Job Identifies and Marks Overdue Casual Issues

    The daily scheduled job SHALL set is_overdue = 1 on exactly those PPE Issues
    matching ALL criteria: issue_type = "Casual", status = "Active",
    expected_return_date <= today, docstatus = 1.

    Issues not matching all criteria SHALL NOT be marked.

    **Validates: Requirements 10.1, 10.4**
    """

    @given(dataset=casual_overdue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_only_qualifying_issues_marked_overdue(self, dataset):
        """send_casual_overdue_alerts() marks ONLY issues matching all four criteria
        (Casual, Active, expected_return_date <= today, docstatus=1) as overdue.

        **Validates: Requirements 10.1, 10.4**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        all_issues, reference_today = dataset

        # Compute which issues SHOULD be marked overdue
        qualifying_issues = [
            issue for issue in all_issues
            if issue["issue_type"] == "Casual"
            and issue["status"] == "Active"
            and issue["expected_return_date"] <= reference_today
            and issue["docstatus"] == 1
        ]

        # Build mock return in the format frappe.get_all would return
        mock_return = [
            AttrDict({
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expected_return_date": issue["expected_return_date"],
            })
            for issue in qualifying_issues
        ]

        # Track set_value calls
        set_value_calls = []

        def mock_set_value(doctype, name, field, value=None):
            set_value_calls.append((doctype, name, field, value))

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = mock_set_value
            mock_frappe.db.commit = MagicMock()
            mock_frappe.sendmail = MagicMock()

            # Patch frappe.utils.today and frappe.utils.date_diff for the local import
            with patch("frappe.utils.today", return_value=str(reference_today)), \
                 patch("frappe.utils.date_diff", side_effect=lambda a, b: (date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days):
                # Also patch get_casual_overdue_alert_recipients
                with patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients", return_value=["hr@example.com"]):
                    send_casual_overdue_alerts()

        # ASSERTION 1: frappe.get_all was called with the correct filters
        mock_frappe.get_all.assert_called_once_with(
            "PPE Issue",
            filters={
                "issue_type": "Casual",
                "status": "Active",
                "expected_return_date": ["<=", str(reference_today)],
                "docstatus": 1,
            },
            fields=["name", "employee", "employee_name", "ppe_item", "issue_date",
                    "expected_return_date"],
        )

        # ASSERTION 2: Every qualifying issue was marked is_overdue=1
        overdue_calls = [
            c for c in set_value_calls
            if c[2] == "is_overdue" and c[3] == 1
        ]
        expected_overdue_names = {issue["name"] for issue in qualifying_issues}
        actual_overdue_names = {c[1] for c in overdue_calls}

        self.assertEqual(
            actual_overdue_names,
            expected_overdue_names,
            "Exactly the qualifying issues should be marked overdue",
        )

        # ASSERTION 3: Count of overdue markings equals qualifying issues count
        self.assertEqual(len(overdue_calls), len(qualifying_issues))

    @given(dataset=casual_overdue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_non_qualifying_issues_not_marked(self, dataset):
        """Issues not matching all criteria (non-Casual, non-Active, future return
        date, or draft) are NEVER marked as overdue.

        **Validates: Requirements 10.1, 10.4**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        all_issues, reference_today = dataset

        # Compute qualifying vs non-qualifying
        qualifying_issues = [
            issue for issue in all_issues
            if issue["issue_type"] == "Casual"
            and issue["status"] == "Active"
            and issue["expected_return_date"] <= reference_today
            and issue["docstatus"] == 1
        ]
        non_qualifying_issues = [
            issue for issue in all_issues
            if not (issue["issue_type"] == "Casual"
                    and issue["status"] == "Active"
                    and issue["expected_return_date"] <= reference_today
                    and issue["docstatus"] == 1)
        ]

        # Need at least one non-qualifying to verify exclusion
        assume(len(non_qualifying_issues) > 0)

        # Build mock return (only qualifying issues come back from DB)
        mock_return = [
            AttrDict({
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expected_return_date": issue["expected_return_date"],
            })
            for issue in qualifying_issues
        ]

        # Track set_value calls
        set_value_calls = []

        def mock_set_value(doctype, name, field, value=None):
            set_value_calls.append((doctype, name, field, value))

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = mock_set_value
            mock_frappe.db.commit = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("frappe.utils.today", return_value=str(reference_today)), \
                 patch("frappe.utils.date_diff", side_effect=lambda a, b: (date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days):
                with patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients", return_value=["hr@example.com"]):
                    send_casual_overdue_alerts()

        # ASSERTION: No non-qualifying issue was marked overdue
        non_qualifying_names = {issue["name"] for issue in non_qualifying_issues}
        marked_names = {c[1] for c in set_value_calls if c[2] == "is_overdue"}

        self.assertTrue(
            marked_names.isdisjoint(non_qualifying_names),
            f"Non-qualifying issues should NOT be marked overdue. Found: {marked_names & non_qualifying_names}",
        )

    @given(dataset=casual_overdue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_no_action_when_no_qualifying_issues(self, dataset):
        """When no issues match the overdue criteria, the function returns early
        without sending emails or calling set_value.

        **Validates: Requirements 10.1, 10.4**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        _, reference_today = dataset

        # Return empty list from get_all (no qualifying issues)
        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.get_all.return_value = []
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("frappe.utils.today", return_value=str(reference_today)), \
                 patch("frappe.utils.date_diff", return_value=0):
                send_casual_overdue_alerts()

        # ASSERTION: No set_value calls and no sendmail calls
        mock_frappe.db.set_value.assert_not_called()
        mock_frappe.sendmail.assert_not_called()


# ---------------------------------------------------------------------------
# Property 16: Overdue Alert Contains Required Information
# ---------------------------------------------------------------------------


@composite
def overdue_email_dataset(draw):
    """Generate a set of overdue casual PPE Issues for email content verification.

    All issues in this dataset qualify as overdue (Casual, Active, past due).
    Returns (overdue_issues, reference_today).
    """
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    num_issues = draw(integers(min_value=1, max_value=10))

    issues = []
    for i in range(num_issues):
        # All are overdue: expected_return_date is in the past
        days_overdue = draw(integers(min_value=1, max_value=90))
        expected_return_date = reference_today - timedelta(days=days_overdue)
        issue_date = expected_return_date - timedelta(days=draw(integers(min_value=1, max_value=60)))

        issues.append({
            "name": f"PPE-ISS-{i:04d}",
            "employee": f"EMP-{i:04d}",
            "employee_name": f"Employee Name {i}",
            "ppe_item": f"PPE Item {i}",
            "issue_date": issue_date,
            "expected_return_date": expected_return_date,
        })

    return (issues, reference_today)


class TestOverdueAlertContentProperty(unittest.TestCase):
    """Property 16: Overdue Alert Contains Required Information

    For any overdue casual PPE Issue included in an alert email, the email
    content SHALL contain: Employee Name, PPE Item, Issue Date, Expected
    Return Date, and days overdue.

    **Validates: Requirements 10.3**
    """

    @given(dataset=overdue_email_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_email_contains_all_required_fields(self, dataset):
        """The email message sent by send_casual_overdue_alerts() contains
        Employee Name, PPE Item, Issue Date, Expected Return Date, and days
        overdue for each overdue issue.

        **Validates: Requirements 10.3**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        overdue_issues, reference_today = dataset

        # Build mock return (all are qualifying overdue issues)
        mock_return = [
            AttrDict({
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expected_return_date": issue["expected_return_date"],
            })
            for issue in overdue_issues
        ]

        # Capture the email message
        captured_emails = []

        def mock_sendmail(**kwargs):
            captured_emails.append(kwargs)

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.sendmail = mock_sendmail

            with patch("frappe.utils.today", return_value=str(reference_today)), \
                 patch("frappe.utils.date_diff", side_effect=lambda a, b: (date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days):
                with patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients", return_value=["hr@example.com"]):
                    send_casual_overdue_alerts()

        # ASSERTION: An email was sent
        self.assertEqual(len(captured_emails), 1, "Exactly one email should be sent")

        email = captured_emails[0]
        message = email.get("message", "")

        # ASSERTION: For each overdue issue, the message contains the required info
        for issue in overdue_issues:
            days_overdue = (reference_today - issue["expected_return_date"]).days

            self.assertIn(
                issue["employee_name"],
                message,
                f"Email must contain employee name: {issue['employee_name']}",
            )
            self.assertIn(
                issue["ppe_item"],
                message,
                f"Email must contain PPE item: {issue['ppe_item']}",
            )
            self.assertIn(
                str(issue["issue_date"]),
                message,
                f"Email must contain issue date: {issue['issue_date']}",
            )
            self.assertIn(
                str(issue["expected_return_date"]),
                message,
                f"Email must contain expected return date: {issue['expected_return_date']}",
            )
            self.assertIn(
                str(days_overdue),
                message,
                f"Email must contain days overdue: {days_overdue}",
            )

    @given(dataset=overdue_email_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_email_has_recipients(self, dataset):
        """The overdue alert email is sent to recipients (users with HR roles).

        **Validates: Requirements 10.3**
        """
        from ppe_tracker.ppe_tracker.tasks import send_casual_overdue_alerts

        overdue_issues, reference_today = dataset

        mock_return = [
            AttrDict({
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expected_return_date": issue["expected_return_date"],
            })
            for issue in overdue_issues
        ]

        captured_emails = []

        def mock_sendmail(**kwargs):
            captured_emails.append(kwargs)

        test_recipients = ["hr@example.com", "safety@example.com"]

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.sendmail = mock_sendmail

            with patch("frappe.utils.today", return_value=str(reference_today)), \
                 patch("frappe.utils.date_diff", side_effect=lambda a, b: (date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days):
                with patch("ppe_tracker.ppe_tracker.tasks.get_casual_overdue_alert_recipients", return_value=test_recipients):
                    send_casual_overdue_alerts()

        # ASSERTION: Email was sent with the correct recipients
        self.assertEqual(len(captured_emails), 1)
        self.assertEqual(captured_emails[0]["recipients"], test_recipients)


# ---------------------------------------------------------------------------
# Property 17: Return Clears Overdue Flag
# ---------------------------------------------------------------------------


@composite
def casual_return_dataset(draw):
    """Generate a dataset for testing that returns clear the overdue flag.

    Returns (issue_type, is_overdue_before) where:
      - issue_type: "Casual" or "Standard"
      - is_overdue_before: 1 (overdue) or 0 (not overdue)
    """
    issue_type = draw(sampled_from(["Casual", "Standard"]))
    is_overdue_before = draw(sampled_from([0, 1]))
    return (issue_type, is_overdue_before)


class TestReturnClearsOverdueFlagProperty(unittest.TestCase):
    """Property 17: Return Clears Overdue Flag

    Submitting a PPE Return for an overdue casual issue clears is_overdue to 0.
    For non-casual issues, the overdue flag is not touched.

    **Validates: Requirements 11.3**
    """

    @given(data=casual_return_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_clear_overdue_flag_if_casual(self, data):
        """_clear_overdue_flag_if_casual() sets is_overdue=0 for Casual issues
        and does nothing for Standard issues.

        **Validates: Requirements 11.3**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        issue_type, is_overdue_before = data

        # Track set_value calls
        set_value_calls = []

        def mock_set_value(doctype, name, field, value=None):
            set_value_calls.append((doctype, name, field, value))

        def mock_get_value(doctype, name, field):
            if field == "issue_type":
                return issue_type
            return None

        # Create a mock PPEReturn instance
        mock_return_doc = MagicMock()
        mock_return_doc.ppe_issue = "PPE-ISS-0001"

        with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe") as mock_frappe:
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.db.set_value = mock_set_value

            # Call the method directly on the class, passing our mock as self
            PPEReturn._clear_overdue_flag_if_casual(mock_return_doc)

        if issue_type == "Casual":
            # ASSERTION: is_overdue was set to 0 for casual issues
            self.assertEqual(len(set_value_calls), 1)
            self.assertEqual(set_value_calls[0], ("PPE Issue", "PPE-ISS-0001", "is_overdue", 0))
        else:
            # ASSERTION: No set_value call for non-casual issues
            self.assertEqual(len(set_value_calls), 0,
                             "Non-casual issues should not have is_overdue cleared")

    @given(dataset=casual_overdue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_return_always_clears_overdue_for_casual_regardless_of_flag_state(self, dataset):
        """For any casual PPE Issue (whether is_overdue is 0 or 1), submitting
        a return always sets is_overdue=0. The method is idempotent.

        **Validates: Requirements 11.3**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        all_issues, _ = dataset

        # Filter to only casual issues for this test
        casual_issues = [i for i in all_issues if i["issue_type"] == "Casual"]
        assume(len(casual_issues) > 0)

        for issue in casual_issues:
            set_value_calls = []

            def mock_set_value(doctype, name, field, value=None):
                set_value_calls.append((doctype, name, field, value))

            def mock_get_value(doctype, name, field):
                if field == "issue_type":
                    return "Casual"
                return None

            mock_return_doc = MagicMock()
            mock_return_doc.ppe_issue = issue["name"]

            with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe") as mock_frappe:
                mock_frappe.db.get_value = mock_get_value
                mock_frappe.db.set_value = mock_set_value

                PPEReturn._clear_overdue_flag_if_casual(mock_return_doc)

            # ASSERTION: is_overdue is always cleared to 0 for casual issues
            self.assertEqual(len(set_value_calls), 1)
            self.assertEqual(
                set_value_calls[0],
                ("PPE Issue", issue["name"], "is_overdue", 0),
                f"is_overdue should be cleared to 0 for casual issue {issue['name']}",
            )


if __name__ == "__main__":
    unittest.main()
