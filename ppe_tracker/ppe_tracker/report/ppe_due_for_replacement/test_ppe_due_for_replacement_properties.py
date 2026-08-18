# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the PPE Due for Replacement report.

Feature: tts-ppe-tracker, Property 23: Due for Replacement Report Respects Configurable Window

**Validates: Requirements 14.1, 14.2**
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    dates,
    integers,
    lists,
    composite,
    sampled_from,
    none,
    one_of,
    just,
)


class _dict(dict):
    """Minimal replica of frappe._dict that supports attribute-style access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


@composite
def due_for_replacement_dataset(draw):
    """Generate a dataset of PPE Issues with varying statuses and expiry dates,
    along with a configurable days_window value.

    Each record has:
      - name: unique issue identifier
      - employee: employee ID
      - employee_name: employee display name
      - ppe_item: PPE item name
      - issue_date: date of issuance
      - expiry_date: a date relative to reference_today
      - quantity: integer quantity issued
      - status: one of "Active", "Returned", "Replaced", "Expired"

    Returns a tuple of (all_issues, reference_today, days_window) where:
      - reference_today is the fixed "today" date
      - days_window is an integer (1-365) or None (to test the default of 30)
    """
    reference_today = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    # Generate days_window: either a specific value (1-365) or None for default
    days_window = draw(one_of(integers(min_value=1, max_value=365), none()))

    num_issues = draw(integers(min_value=1, max_value=20))

    statuses = ["Active", "Returned", "Replaced", "Expired"]

    issues = []
    for i in range(num_issues):
        status = draw(sampled_from(statuses))
        # Expiry dates spread across a wide range relative to today
        offset_days = draw(integers(min_value=-90, max_value=400))
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

    return (issues, reference_today, days_window)


def _to_frappe_dicts(issues):
    """Convert a list of plain dicts to frappe-style _dict objects with string dates."""
    return [
        _dict(
            name=issue["name"],
            employee=issue["employee"],
            employee_name=issue["employee_name"],
            ppe_item=issue["ppe_item"],
            issue_date=str(issue["issue_date"]),
            expiry_date=str(issue["expiry_date"]),
            quantity=issue["quantity"],
        )
        for issue in issues
    ]


class TestDueForReplacementReportRespectsConfigurableWindow(unittest.TestCase):
    """Property 23: Due for Replacement Report Respects Configurable Window

    For any configured replacement window N days and any dataset of PPE Issue
    records, the PPE Due for Replacement report SHALL return exactly those records
    with status = "Active" and today <= expiry_date <= today + N, defaulting
    N = 30 when unspecified.

    Feature: tts-ppe-tracker, Property 23: Due for Replacement Report Respects Configurable Window
    **Validates: Requirements 14.1, 14.2**
    """

    @given(dataset=due_for_replacement_dataset())
    @settings(max_examples=25)
    def test_report_uses_correct_threshold_for_given_days_window(self, dataset):
        """get_data() computes threshold as today + N where N is the days_window
        filter value, and queries for Active issues with expiry_date between
        today and today + N.

        Feature: tts-ppe-tracker, Property 23: Due for Replacement Report Respects Configurable Window
        **Validates: Requirements 14.1, 14.2**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import get_data

        all_issues, reference_today, days_window = dataset

        # Determine the effective window
        effective_window = days_window if days_window is not None else 30
        threshold = reference_today + timedelta(days=effective_window)

        # Compute which issues qualify: Active + today <= expiry_date <= threshold
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]

        # Build mock return value as frappe.get_all would return (attribute-accessible dicts)
        mock_get_all_return = _to_frappe_dicts(qualifying_issues)

        # Build filters dict
        filters = {}
        if days_window is not None:
            filters["days_window"] = days_window

        with patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.frappe") as mock_frappe, \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.today", return_value=str(reference_today)), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.add_days", return_value=str(threshold)), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.date_diff") as mock_date_diff:

            mock_frappe.get_all.return_value = mock_get_all_return
            mock_frappe.db.get_value.return_value = _dict(department="Engineering", designation="Engineer")
            mock_date_diff.side_effect = lambda exp, cur: (date.fromisoformat(str(exp)) - date.fromisoformat(str(cur))).days

            result = get_data(filters)

        # ASSERTION 1: frappe.get_all was called with the correct list-style filters
        mock_frappe.get_all.assert_called_once_with(
            "PPE Issue",
            filters=[
                ["PPE Issue", "status", "=", "Active"],
                ["PPE Issue", "expiry_date", "<=", str(threshold)],
                ["PPE Issue", "expiry_date", ">=", str(reference_today)],
            ],
            fields=["name", "employee", "employee_name", "ppe_item", "issue_date", "expiry_date", "quantity"],
        )

        # ASSERTION 2: The result contains exactly the qualifying issues
        result_employees = {row["employee"] for row in result}
        expected_employees = {issue["employee"] for issue in qualifying_issues}
        self.assertEqual(
            result_employees,
            expected_employees,
            f"Report data should contain exactly the qualifying Active issues "
            f"within {effective_window}-day window",
        )

    @given(dataset=due_for_replacement_dataset())
    @settings(max_examples=25)
    def test_default_window_is_30_when_absent(self, dataset):
        """When days_window is not specified in filters (None or absent),
        the report defaults to a 30-day window: threshold = today + 30.

        Feature: tts-ppe-tracker, Property 23: Due for Replacement Report Respects Configurable Window
        **Validates: Requirements 14.2**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import get_data

        all_issues, reference_today, _ = dataset

        # Force days_window to be absent/None to test default behavior
        default_window = 30
        threshold = reference_today + timedelta(days=default_window)

        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]

        mock_get_all_return = _to_frappe_dicts(qualifying_issues)

        # Empty filters — no days_window key at all
        filters = {}

        add_days_called_with = []

        def mock_add_days_fn(current_date, days):
            add_days_called_with.append((current_date, days))
            return str(threshold)

        with patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.frappe") as mock_frappe, \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.today", return_value=str(reference_today)), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.add_days", side_effect=mock_add_days_fn), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.date_diff") as mock_date_diff:

            mock_frappe.get_all.return_value = mock_get_all_return
            mock_frappe.db.get_value.return_value = _dict(department="Engineering", designation="Engineer")
            mock_date_diff.side_effect = lambda exp, cur: (date.fromisoformat(str(exp)) - date.fromisoformat(str(cur))).days

            result = get_data(filters)

        # ASSERTION: add_days was called with 30 (the default) when no days_window is provided
        self.assertTrue(len(add_days_called_with) > 0, "add_days should have been called")
        self.assertEqual(
            add_days_called_with[0][1],
            30,
            "When days_window is absent from filters, it should default to 30",
        )

    @given(dataset=due_for_replacement_dataset())
    @settings(max_examples=25)
    def test_only_active_issues_within_window_are_returned(self, dataset):
        """The report returns ONLY Active issues whose expiry_date falls within
        the configured window [today, today + N]. Non-Active issues and issues
        outside the window are excluded.

        Feature: tts-ppe-tracker, Property 23: Due for Replacement Report Respects Configurable Window
        **Validates: Requirements 14.1, 14.2**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import get_data

        all_issues, reference_today, days_window = dataset

        effective_window = days_window if days_window is not None else 30
        threshold = reference_today + timedelta(days=effective_window)

        # Determine which issues qualify
        qualifying_issues = [
            issue for issue in all_issues
            if issue["status"] == "Active"
            and reference_today <= issue["expiry_date"] <= threshold
        ]

        # Non-qualifying issues (should never appear in results)
        non_qualifying_issues = [
            issue for issue in all_issues
            if not (issue["status"] == "Active"
                    and reference_today <= issue["expiry_date"] <= threshold)
        ]

        assume(len(non_qualifying_issues) > 0)

        mock_get_all_return = _to_frappe_dicts(qualifying_issues)

        filters = {}
        if days_window is not None:
            filters["days_window"] = days_window

        with patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.frappe") as mock_frappe, \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.today", return_value=str(reference_today)), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.add_days", return_value=str(threshold)), \
             patch("ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement.date_diff") as mock_date_diff:

            mock_frappe.get_all.return_value = mock_get_all_return
            mock_frappe.db.get_value.return_value = _dict(department="Engineering", designation="Engineer")
            mock_date_diff.side_effect = lambda exp, cur: (date.fromisoformat(str(exp)) - date.fromisoformat(str(cur))).days

            result = get_data(filters)

        # ASSERTION: The count of results matches exactly the qualifying issues count
        self.assertEqual(
            len(result),
            len(qualifying_issues),
            f"Report should return exactly {len(qualifying_issues)} records "
            f"(Active issues within {effective_window}-day window), "
            f"but got {len(result)}",
        )


if __name__ == "__main__":
    unittest.main()
