# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Casual PPE Issue validation.

Feature: ppe-tracker-enhancements-v2, Property 12 & Property 14

**Validates: Requirements 9.2, 9.5**
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    dates,
    sampled_from,
    none,
    one_of,
    just,
    composite,
    text,
)


# Module path for patching
PPE_ISSUE_MODULE = "ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue"


def _make_mock_doc(fields_dict):
    """Create a mock PPE Issue document with a working .get() method.

    Args:
        fields_dict: dict of field names to their values.
    """
    mock_doc = MagicMock()
    mock_doc.get = lambda field: fields_dict.get(field)
    # Also set attributes directly for attribute-style access
    for key, value in fields_dict.items():
        setattr(mock_doc, key, value)
    return mock_doc


@composite
def empty_return_date(draw):
    """Generate an empty expected_return_date (None or empty string)."""
    return draw(sampled_from([None, ""]))


@composite
def valid_return_date(draw):
    """Generate a valid expected_return_date (non-empty date string)."""
    d = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    return str(d)


class TestCasualIssueRequiresExpectedReturnDate(unittest.TestCase):
    """Property 12: Casual Issue Requires Expected Return Date

    For any PPE Issue with issue_type = "Casual", the system SHALL enforce
    expected_return_date as mandatory — rejecting validation if the field is
    empty and passing when it is set to a valid date.

    Feature: ppe-tracker-enhancements-v2, Property 12: Casual Issue Requires Expected Return Date
    **Validates: Requirements 9.2**
    """

    @given(expected_return_date=empty_return_date())
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_rejects_empty_expected_return_date(self, expected_return_date):
        """When issue_type is 'Casual' and expected_return_date is empty/None,
        frappe.throw is called to reject validation.

        Feature: ppe-tracker-enhancements-v2, Property 12: Casual Issue Requires Expected Return Date
        **Validates: Requirements 9.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_doc = _make_mock_doc({
            "issue_type": "Casual",
            "expected_return_date": expected_return_date,
            "employee": "EMP-001",
        })

        with patch(f"{PPE_ISSUE_MODULE}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x

            with self.assertRaises(Exception):
                PPEIssue._validate_casual_issue(mock_doc)

            # Verify frappe.throw was called (validation rejected)
            mock_frappe.throw.assert_called_once()

    @given(expected_return_date=valid_return_date())
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_accepts_valid_expected_return_date(self, expected_return_date):
        """When issue_type is 'Casual' and expected_return_date is a valid date string,
        the expected_return_date check passes (frappe.throw is NOT called for missing date).

        Feature: ppe-tracker-enhancements-v2, Property 12: Casual Issue Requires Expected Return Date
        **Validates: Requirements 9.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_doc = _make_mock_doc({
            "issue_type": "Casual",
            "expected_return_date": expected_return_date,
            "employee": "EMP-001",
        })

        with patch(f"{PPE_ISSUE_MODULE}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold = lambda x: f"<b>{x}</b>"
            # Employee is casual — so the second validation also passes
            mock_frappe.db.get_value.return_value = "Casual"

            # Should NOT raise — both checks pass
            PPEIssue._validate_casual_issue(mock_doc)

            # frappe.throw should NOT have been called
            mock_frappe.throw.assert_not_called()


class TestCasualIssueValidatesEmployeeType(unittest.TestCase):
    """Property 14: Casual Issue Validates Employee Type

    For any PPE Issue with issue_type = "Casual", the system SHALL validate that
    the linked Employee has employment_type = "Casual" — rejecting if the employee
    is not a casual worker.

    Feature: ppe-tracker-enhancements-v2, Property 14: Casual Issue Validates Employee Type
    **Validates: Requirements 9.5**
    """

    @given(
        employment_type=sampled_from(["Permanent", "Probation", "Intern", "Contract", "Temporary"]),
        employee_id=text(min_size=3, max_size=15, alphabet="ABCDEFGHIJKLMNOP0123456789-"),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_rejects_non_casual_employee(self, employment_type, employee_id):
        """When issue_type is 'Casual' but the linked Employee does not have
        employment_type 'Casual', frappe.throw is called.

        Feature: ppe-tracker-enhancements-v2, Property 14: Casual Issue Validates Employee Type
        **Validates: Requirements 9.5**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_doc = _make_mock_doc({
            "issue_type": "Casual",
            "expected_return_date": "2024-06-15",  # Valid date so first check passes
            "employee": employee_id,
        })

        with patch(f"{PPE_ISSUE_MODULE}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold = lambda x: f"<b>{x}</b>"
            mock_frappe.db.get_value.return_value = employment_type

            with self.assertRaises(Exception):
                PPEIssue._validate_casual_issue(mock_doc)

            # Verify frappe.db.get_value was called for the employee's employment_type
            mock_frappe.db.get_value.assert_called_once_with(
                "Employee", employee_id, "employment_type"
            )
            # Verify frappe.throw was called (validation rejected)
            mock_frappe.throw.assert_called_once()

    @given(
        employee_id=text(min_size=3, max_size=15, alphabet="ABCDEFGHIJKLMNOP0123456789-"),
        expected_return_date=valid_return_date(),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_accepts_casual_employee(self, employee_id, expected_return_date):
        """When issue_type is 'Casual' and the linked Employee has
        employment_type 'Casual', validation passes without error.

        Feature: ppe-tracker-enhancements-v2, Property 14: Casual Issue Validates Employee Type
        **Validates: Requirements 9.5**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_doc = _make_mock_doc({
            "issue_type": "Casual",
            "expected_return_date": expected_return_date,
            "employee": employee_id,
        })

        with patch(f"{PPE_ISSUE_MODULE}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold = lambda x: f"<b>{x}</b>"
            mock_frappe.db.get_value.return_value = "Casual"

            # Should NOT raise — both checks pass
            PPEIssue._validate_casual_issue(mock_doc)

            # frappe.throw should NOT have been called
            mock_frappe.throw.assert_not_called()


class TestNonCasualIssueSkipsValidation(unittest.TestCase):
    """Non-Casual issues skip casual validation entirely.

    When issue_type != "Casual", the _validate_casual_issue method returns
    early without performing any validation — no frappe.throw regardless
    of the state of expected_return_date or employee type.

    Feature: ppe-tracker-enhancements-v2, Property 12 & 14 (boundary condition)
    **Validates: Requirements 9.2, 9.5**
    """

    @given(
        issue_type=sampled_from(["Standard", "", None]),
        expected_return_date=sampled_from([None, "", "2024-06-15"]),
        employment_type=sampled_from(["Permanent", "Probation", "Casual", "Intern"]),
    )
    @settings(max_examples=25, deadline=None)
    def test_non_casual_issue_returns_early_without_validation(
        self, issue_type, expected_return_date, employment_type
    ):
        """When issue_type is not 'Casual', _validate_casual_issue returns immediately
        without calling frappe.throw, regardless of other field values.

        Feature: ppe-tracker-enhancements-v2, Property 12 & 14 (boundary condition)
        **Validates: Requirements 9.2, 9.5**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_doc = _make_mock_doc({
            "issue_type": issue_type,
            "expected_return_date": expected_return_date,
            "employee": "EMP-001",
        })

        with patch(f"{PPE_ISSUE_MODULE}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold = lambda x: f"<b>{x}</b>"
            mock_frappe.db.get_value.return_value = employment_type

            # Should NOT raise — method returns early for non-Casual types
            PPEIssue._validate_casual_issue(mock_doc)

            # frappe.throw should NOT have been called
            mock_frappe.throw.assert_not_called()
            # frappe.db.get_value should NOT have been called (no employee check needed)
            mock_frappe.db.get_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
