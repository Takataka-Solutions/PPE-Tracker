# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Tracker scheduled tasks.

Feature: tts-ppe-tracker, Property 20: Expiry Job Transitions All Qualifying Issues to Expired

**Validates: Requirements 7.4**
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
)


@composite
def ppe_issue_dataset(draw):
    """Generate a list of Active PPE Issue records with varying expiry dates.

    Each record is a dict with:
      - name: unique issue identifier
      - status: always "Active" (only Active issues are candidates)
      - expiry_date: a date that may be before, on, or after today

    Returns a tuple of (all_issues, reference_today) where reference_today
    is the fixed "today" date used for partitioning.
    """
    # Use a fixed reference date as "today" for deterministic assertions
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    # Generate between 1 and 20 PPE Issue records
    num_issues = draw(integers(min_value=1, max_value=20))

    issues = []
    for i in range(num_issues):
        # Generate expiry dates: some in the past, some today, some in the future
        offset_days = draw(integers(min_value=-365, max_value=365))
        expiry_date = reference_today + timedelta(days=offset_days)

        issues.append({
            "name": f"PPE-ISSUE-{i:04d}",
            "status": "Active",
            "expiry_date": expiry_date,
        })

    return (issues, reference_today)


class TestExpiryJobTransitionsAllQualifyingIssues(unittest.TestCase):
    """Property 20: Expiry Job Transitions All Qualifying Issues to Expired

    WHEN the Scheduled Job runs and a PPE Issue record has a status of "Active"
    and its expiry date is on or before the current date, THE System SHALL
    transition that PPE Issue status to "Expired".

    All issues with expiry_date > today must remain "Active" (untouched).

    Feature: tts-ppe-tracker, Property 20: Expiry Job Transitions All Qualifying Issues to Expired
    **Validates: Requirements 7.4**
    """

    @given(dataset=ppe_issue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_mark_expired_issues_transitions_all_qualifying(self, dataset):
        """mark_expired_issues() transitions ALL Active issues with expiry_date <= today
        to 'Expired', and does NOT touch issues with expiry_date > today.

        Feature: tts-ppe-tracker, Property 20: Expiry Job Transitions All Qualifying Issues to Expired
        **Validates: Requirements 7.4**
        """
        from ppe_tracker.ppe_tracker.tasks import mark_expired_issues

        all_issues, reference_today = dataset

        # Partition issues into those that should expire vs those that should remain Active
        expected_expired = [
            issue for issue in all_issues
            if issue["expiry_date"] <= reference_today
        ]
        expected_still_active = [
            issue for issue in all_issues
            if issue["expiry_date"] > reference_today
        ]

        # The names that frappe.get_all should return (simulating the DB query)
        expired_names = [issue["name"] for issue in expected_expired]

        # Track all set_value calls
        set_value_calls = []

        def mock_set_value(doctype, name, field, value=None):
            set_value_calls.append((doctype, name, field, value))

        mock_commit = MagicMock()

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            # Mock today() to return our reference date
            mock_frappe.utils.today.return_value = str(reference_today)

            # Mock frappe.get_all to return the expired issue names
            mock_frappe.get_all.return_value = expired_names

            # Mock frappe.db.set_value to track status changes
            mock_frappe.db.set_value = mock_set_value

            # Mock frappe.db.commit
            mock_frappe.db.commit = mock_commit

            mark_expired_issues()

        # ASSERTION 1: frappe.get_all was called with correct filters
        mock_frappe.get_all.assert_called_once_with(
            "PPE Issue",
            filters={
                "status": "Active",
                "expiry_date": ["<=", str(reference_today)],
            },
            pluck="name",
        )

        # ASSERTION 2: Every qualifying issue was transitioned to "Expired"
        expected_set_value_calls = [
            ("PPE Issue", name, "status", "Expired")
            for name in expired_names
        ]
        self.assertEqual(set_value_calls, expected_set_value_calls)

        # ASSERTION 3: The number of set_value calls equals exactly the number of expired issues
        self.assertEqual(len(set_value_calls), len(expected_expired))

        # ASSERTION 4: No non-qualifying issue names appear in set_value calls
        transitioned_names = {c[1] for c in set_value_calls}
        still_active_names = {issue["name"] for issue in expected_still_active}
        self.assertTrue(
            transitioned_names.isdisjoint(still_active_names),
            "Issues with expiry_date > today should NOT be transitioned",
        )

        # ASSERTION 5: Commit is always called (the implementation calls commit unconditionally)
        mock_commit.assert_called_once()

    @given(dataset=ppe_issue_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_no_false_positives_only_expired_issues_are_transitioned(self, dataset):
        """mark_expired_issues() never transitions issues whose expiry_date is
        strictly after today. The count of transitions equals the count of
        qualifying issues exactly.

        Feature: tts-ppe-tracker, Property 20: Expiry Job Transitions All Qualifying Issues to Expired
        **Validates: Requirements 7.4**
        """
        from ppe_tracker.ppe_tracker.tasks import mark_expired_issues

        all_issues, reference_today = dataset

        # Only issues with expiry_date <= today qualify
        qualifying_count = sum(
            1 for issue in all_issues
            if issue["expiry_date"] <= reference_today
        )
        qualifying_names = [
            issue["name"] for issue in all_issues
            if issue["expiry_date"] <= reference_today
        ]

        transition_count = 0

        def mock_set_value(doctype, name, field, value=None):
            nonlocal transition_count
            transition_count += 1

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.get_all.return_value = qualifying_names
            mock_frappe.db.set_value = mock_set_value
            mock_frappe.db.commit = MagicMock()

            mark_expired_issues()

        # The number of transitions must equal exactly the number of qualifying issues
        self.assertEqual(transition_count, qualifying_count)


# ---------------------------------------------------------------------------
# Property 21: Expiry Alert Job Identifies Exactly the Right Records
# ---------------------------------------------------------------------------

@composite
def expiry_alert_dataset(draw):
    """Generate a dataset of PPE Issues with varying statuses and expiry dates.

    Each record has:
      - name: unique issue identifier
      - employee: employee ID
      - employee_name: employee display name
      - ppe_item: PPE item name
      - issue_date: date of issuance
      - expiry_date: a date that may be before, on, or after (today + 30)
      - quantity: integer quantity issued
      - status: one of "Active", "Returned", "Replaced", "Expired"

    Returns a tuple of (all_issues, reference_today) where reference_today
    is the fixed "today" date used for determining the 30-day threshold.
    """
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    num_issues = draw(integers(min_value=1, max_value=25))

    statuses = ["Active", "Returned", "Replaced", "Expired"]

    issues = []
    for i in range(num_issues):
        status = draw(sampled_from(statuses))
        # Expiry dates spread across a wide range relative to today
        offset_days = draw(integers(min_value=-180, max_value=180))
        expiry_date = reference_today + timedelta(days=offset_days)
        # Issue date is always before expiry date
        issue_date = expiry_date - timedelta(days=draw(integers(min_value=30, max_value=365)))

        issues.append({
            "name": f"PPE-ISS-{i:04d}",
            "employee": f"EMP-{i:04d}",
            "employee_name": f"Employee {i}",
            "ppe_item": f"PPE-ITEM-{i % 5:02d}",
            "issue_date": issue_date,
            "expiry_date": expiry_date,
            "quantity": draw(integers(min_value=1, max_value=10)),
            "status": status,
        })

    return (issues, reference_today)


class TestExpiryAlertJobIdentifiesRightRecords(unittest.TestCase):
    """Property 21: Expiry Alert Job Identifies Exactly the Right Records

    WHEN send_expiry_alerts() runs, it SHALL query for PPE Issues with
    status = "Active" AND expiry_date <= today + 30 days. The resulting
    issues (and ONLY those issues) are passed to the alert email functions.

    Issues outside this window (wrong status or expiry_date > today + 30)
    must NOT appear in any alert payload.

    Feature: tts-ppe-tracker, Property 21: Expiry Alert Job Identifies Exactly the Right Records
    **Validates: Requirements 8.1**
    """

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_get_all_called_with_correct_filter(self, dataset):
        """send_expiry_alerts() calls frappe.get_all with the correct filter:
        status=Active AND expiry_date <= today + 30 days.

        Feature: tts-ppe-tracker, Property 21: Expiry Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 8.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_expiry_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=30)

        # Compute which issues SHOULD be returned by get_all (the qualifying set)
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active" and issue["expiry_date"] <= threshold
        ]

        # Build mock return value in the format frappe.get_all would return
        # (frappe returns dicts with string dates)
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=[]) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email") as mock_send_alert:
                send_expiry_alerts()

        # ASSERTION: frappe.get_all was called with the correct filters
        mock_frappe.get_all.assert_called_once_with(
            "PPE Issue",
            filters={
                "status": "Active",
                "expiry_date": ["<=", str(threshold)],
            },
            fields=["name", "employee", "employee_name", "ppe_item", "issue_date", "expiry_date", "quantity"],
        )

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_alert_payload_contains_only_qualifying_issues(self, dataset):
        """send_expiry_alerts() passes ONLY the issues returned by frappe.get_all
        (i.e., Active issues within the 30-day window) to alert functions. No
        additional or missing issues in the alert payload.

        Feature: tts-ppe-tracker, Property 21: Expiry Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 8.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_expiry_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=30)

        # Compute qualifying issues
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active" and issue["expiry_date"] <= threshold
        ]

        # Build the mock return as frappe would
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        # Skip trivial case of no qualifying issues (returns early, no alerts sent)
        assume(len(mock_return) > 0)

        # Track what gets passed to alert emails
        alert_payloads = []

        def capture_alert_email(recipients, issues_arg, template):
            alert_payloads.append(issues_arg)

        # Simulate a supervisor map that includes all issues
        # This ensures _send_alert_email is called with the full list for HR
        hr_emails = ["hr@example.com"]

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=hr_emails) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email", side_effect=capture_alert_email) as mock_send_alert:
                send_expiry_alerts()

        # ASSERTION: The HR alert payload contains exactly the qualifying issues
        # (The HR email gets the full `issues` list from get_all)
        self.assertTrue(len(alert_payloads) > 0, "At least one alert should have been sent")

        # The last call is the HR email with all issues
        hr_payload = alert_payloads[-1]
        hr_payload_names = {issue["name"] for issue in hr_payload}
        expected_names = {issue["name"] for issue in mock_return}

        self.assertEqual(
            hr_payload_names,
            expected_names,
            "HR alert payload must contain exactly the qualifying issues from get_all",
        )

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_issues_outside_window_are_excluded(self, dataset):
        """Issues with status != Active or expiry_date > today + 30 are never
        included in any alert payload. The filtering is enforced by the query.

        Feature: tts-ppe-tracker, Property 21: Expiry Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 8.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_expiry_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=30)

        # Partition: qualifying vs non-qualifying
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active" and issue["expiry_date"] <= threshold
        ]
        non_qualifying_issues = [
            issue for issue in all_issues
            if not (issue["status"] == "Active" and issue["expiry_date"] <= threshold)
        ]

        # Only proceed if we have both qualifying and non-qualifying issues
        assume(len(qualifying_issues) > 0)
        assume(len(non_qualifying_issues) > 0)

        non_qualifying_names = {issue["name"] for issue in non_qualifying_issues}

        # Build mock return (only qualifying issues, as frappe.get_all filters them)
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        # Collect all issue names that appear in any alert
        alerted_names = set()

        def capture_alert_email(recipients, issues_arg, template):
            for issue in issues_arg:
                alerted_names.add(issue["name"])

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=["hr@example.com"]) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email", side_effect=capture_alert_email) as mock_send_alert:
                send_expiry_alerts()

        # ASSERTION: No non-qualifying issue name appears in any alert payload
        self.assertTrue(
            alerted_names.isdisjoint(non_qualifying_names),
            f"Non-qualifying issues should NEVER appear in alerts. "
            f"Found: {alerted_names & non_qualifying_names}",
        )


# ---------------------------------------------------------------------------
# Property 22: Replacement Alert Job Identifies Exactly the Right Records
# ---------------------------------------------------------------------------


class TestReplacementAlertJobIdentifiesRightRecords(unittest.TestCase):
    """Property 22: Replacement Alert Job Identifies Exactly the Right Records

    WHEN send_replacement_alerts() runs, it SHALL query for PPE Issues with
    status = "Active" AND expiry_date BETWEEN today AND today + 7 days. The
    resulting issues (and ONLY those issues) are passed to the alert email functions.

    Issues outside the 7-day replacement window (wrong status, expiry_date < today,
    or expiry_date > today + 7) must NOT appear in any alert payload.

    Feature: tts-ppe-tracker, Property 22: Replacement Alert Job Identifies Exactly the Right Records
    **Validates: Requirements 9.1**
    """

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_get_all_called_with_correct_between_filter(self, dataset):
        """send_replacement_alerts() calls frappe.get_all with the correct filter:
        status=Active AND expiry_date between [today, today+7].

        Feature: tts-ppe-tracker, Property 22: Replacement Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 9.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_replacement_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=7)

        # Compute qualifying issues: Active + expiry_date between today and today+7
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]

        # Build mock return value in the format frappe.get_all would return
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=[]) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email") as mock_send_alert:
                send_replacement_alerts()

        # ASSERTION: frappe.get_all was called with the correct between filter
        mock_frappe.get_all.assert_called_once_with(
            "PPE Issue",
            filters={
                "status": "Active",
                "expiry_date": ["between", [str(reference_today), str(threshold)]],
            },
            fields=["name", "employee", "employee_name", "ppe_item", "issue_date",
                    "expiry_date", "quantity"],
        )

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_alert_payload_contains_only_qualifying_issues(self, dataset):
        """send_replacement_alerts() passes ONLY the issues returned by frappe.get_all
        (i.e., Active issues within the 7-day replacement window) to alert functions.
        No additional or missing issues in the alert payload.

        Feature: tts-ppe-tracker, Property 22: Replacement Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 9.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_replacement_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=7)

        # Compute qualifying issues: Active + expiry between today and today+7
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]

        # Build mock return as frappe would
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        # Skip trivial case of no qualifying issues (returns early, no alerts sent)
        assume(len(mock_return) > 0)

        # Track what gets passed to alert emails
        alert_payloads = []

        def capture_alert_email(recipients, issues_arg, template):
            alert_payloads.append(issues_arg)

        hr_emails = ["hr@example.com"]

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=hr_emails) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email", side_effect=capture_alert_email) as mock_send_alert:
                send_replacement_alerts()

        # ASSERTION: The HR alert payload contains exactly the qualifying issues
        self.assertTrue(len(alert_payloads) > 0, "At least one alert should have been sent")

        # The last call is the HR email with all due_issues
        hr_payload = alert_payloads[-1]
        hr_payload_names = {issue["name"] for issue in hr_payload}
        expected_names = {issue["name"] for issue in mock_return}

        self.assertEqual(
            hr_payload_names,
            expected_names,
            "HR replacement alert payload must contain exactly the qualifying issues from get_all",
        )

    @given(dataset=expiry_alert_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_issues_outside_7_day_window_are_excluded(self, dataset):
        """Issues with status != Active, expiry_date > today + 7, or
        expiry_date < today are never included in any replacement alert payload.
        The filtering is enforced by the between query.

        Feature: tts-ppe-tracker, Property 22: Replacement Alert Job Identifies Exactly the Right Records
        **Validates: Requirements 9.1**
        """
        from ppe_tracker.ppe_tracker.tasks import send_replacement_alerts

        all_issues, reference_today = dataset
        threshold = reference_today + timedelta(days=7)

        # Partition: qualifying vs non-qualifying
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]
        non_qualifying_issues = [
            issue for issue in all_issues
            if not (issue["status"] == "Active"
                    and reference_today <= issue["expiry_date"] <= threshold)
        ]

        # Only proceed if we have both qualifying and non-qualifying issues
        assume(len(qualifying_issues) > 0)
        assume(len(non_qualifying_issues) > 0)

        non_qualifying_names = {issue["name"] for issue in non_qualifying_issues}

        # Build mock return (only qualifying issues, as frappe.get_all filters them)
        mock_return = [
            {
                "name": issue["name"],
                "employee": issue["employee"],
                "employee_name": issue["employee_name"],
                "ppe_item": issue["ppe_item"],
                "issue_date": str(issue["issue_date"]),
                "expiry_date": str(issue["expiry_date"]),
                "quantity": issue["quantity"],
            }
            for issue in qualifying_issues
        ]

        # Collect all issue names that appear in any alert
        alerted_names = set()

        def capture_alert_email(recipients, issues_arg, template):
            for issue in issues_arg:
                alerted_names.add(issue["name"])

        with patch("ppe_tracker.ppe_tracker.tasks.frappe") as mock_frappe:
            mock_frappe.utils.today.return_value = str(reference_today)
            mock_frappe.utils.add_days.return_value = str(threshold)
            mock_frappe.get_all.return_value = mock_return
            mock_frappe.db.set_value = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.db.get_value = MagicMock(return_value=None)
            mock_frappe.log_error = MagicMock()
            mock_frappe.sendmail = MagicMock()

            with patch("ppe_tracker.ppe_tracker.tasks._build_supervisor_map", return_value={}) as mock_sup_map, \
                 patch("ppe_tracker.ppe_tracker.tasks._get_role_email_list", return_value=["hr@example.com"]) as mock_role_list, \
                 patch("ppe_tracker.ppe_tracker.tasks._send_alert_email", side_effect=capture_alert_email) as mock_send_alert:
                send_replacement_alerts()

        # ASSERTION: No non-qualifying issue name appears in any alert payload
        self.assertTrue(
            alerted_names.isdisjoint(non_qualifying_names),
            f"Non-qualifying issues should NEVER appear in replacement alerts. "
            f"Found: {alerted_names & non_qualifying_names}",
        )


# ---------------------------------------------------------------------------
# Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
# ---------------------------------------------------------------------------


class TestRequestedQuantityCannotExceedRoleAssignment(unittest.TestCase):
    """Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity

    WHEN a PPE Request is saved with a requested_quantity that exceeds the quantity
    specified in the matching PPE Role Assignment Item for that employee's
    department/designation and PPE Item, THE System SHALL raise a validation error.

    Conversely, WHEN requested_quantity <= the assigned quantity, no validation
    error SHALL be raised by _validate_max_quantity().

    Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
    **Validates: Requirements 24.1, 24.2**
    """

    @given(
        assignment_quantity=integers(min_value=1, max_value=100),
        excess=integers(min_value=1, max_value=100),
    )
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_exceeding_quantity_triggers_validation_error(self, assignment_quantity, excess):
        """For ALL generated (assignment_quantity, requested_quantity) pairs where
        requested_quantity > assignment_quantity, _validate_max_quantity() calls
        frappe.throw().

        Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.1, 24.2**
        """
        requested_quantity = assignment_quantity + excess  # Always exceeds

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe"
        ) as mock_frappe:
            from ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

            # Configure mock frappe.throw to raise ValidationError
            mock_frappe.throw.side_effect = Exception("ValidationError")
            mock_frappe.bold.side_effect = lambda x: x
            mock_frappe._.side_effect = lambda x: x

            # Mock employee lookup
            mock_employee = MagicMock()
            mock_employee.department = "Engineering"
            mock_employee.designation = "Engineer"
            mock_frappe.get_doc.return_value = mock_employee

            # Mock PPE Role Assignment lookup - return a matching assignment
            mock_frappe.get_all.side_effect = [
                # First call: get PPE Role Assignment names
                ["PPERA-001"],
                # Second call: get PPE Role Assignment Item rows
                [MagicMock(quantity=assignment_quantity)],
            ]

            # Create a mock PPE Request document
            doc = MagicMock(spec=PPERequest)
            doc.employee = "EMP-001"
            doc.ppe_item = "Safety Helmet"
            doc.requested_quantity = requested_quantity

            # Call the method under test
            try:
                PPERequest._validate_max_quantity(doc)
            except Exception:
                pass  # Expected — frappe.throw raises

            # ASSERTION: frappe.throw was called (validation error raised)
            mock_frappe.throw.assert_called_once()

    @given(
        assignment_quantity=integers(min_value=1, max_value=100),
        reduction=integers(min_value=0, max_value=99),
    )
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_within_limit_quantity_does_not_trigger_error(self, assignment_quantity, reduction):
        """For ALL generated (assignment_quantity, requested_quantity) pairs where
        requested_quantity <= assignment_quantity, _validate_max_quantity() does NOT
        call frappe.throw().

        Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.1, 24.2**
        """
        # Ensure requested_quantity is between 1 and assignment_quantity (inclusive)
        requested_quantity = max(1, assignment_quantity - reduction)
        assume(requested_quantity <= assignment_quantity)

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe"
        ) as mock_frappe:
            from ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

            # Configure mock frappe - throw should NOT be called
            mock_frappe.throw.side_effect = Exception("ValidationError")
            mock_frappe.bold.side_effect = lambda x: x
            mock_frappe._.side_effect = lambda x: x

            # Mock employee lookup
            mock_employee = MagicMock()
            mock_employee.department = "Engineering"
            mock_employee.designation = "Engineer"
            mock_frappe.get_doc.return_value = mock_employee

            # Mock PPE Role Assignment lookup - return a matching assignment
            mock_frappe.get_all.side_effect = [
                # First call: get PPE Role Assignment names
                ["PPERA-001"],
                # Second call: get PPE Role Assignment Item rows
                [MagicMock(quantity=assignment_quantity)],
            ]

            # Create a mock PPE Request document
            doc = MagicMock(spec=PPERequest)
            doc.employee = "EMP-001"
            doc.ppe_item = "Safety Helmet"
            doc.requested_quantity = requested_quantity

            # Call the method under test
            PPERequest._validate_max_quantity(doc)

            # ASSERTION: frappe.throw was NOT called (no validation error)
            mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
