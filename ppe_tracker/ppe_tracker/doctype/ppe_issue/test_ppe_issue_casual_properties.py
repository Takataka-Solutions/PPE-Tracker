# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for casual PPE Issue validation.

Property 12: Casual Issue Requires Expected Return Date
Property 14: Casual Issue Validates Employee Type

**Validates: Requirements 9.2, 9.5**
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    dates,
    none,
    sampled_from,
    one_of,
    just,
    text,
)


class TestCasualIssueRequiresExpectedReturnDate(unittest.TestCase):
    """Property 12: Casual Issue Requires Expected Return Date

    For any PPE Issue with issue_type = "Casual", the system SHALL enforce
    expected_return_date as mandatory — rejecting validation if the field is
    empty and passing when it is set to a valid date.

    **Validates: Requirements 9.2**
    """

    @given(
        empty_date=one_of(none(), just(""), just(None)),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_rejects_empty_expected_return_date(self, empty_date):
        """Casual PPE Issues with empty/None expected_return_date always raise ValidationError.

        **Validates: Requirements 9.2**
        """
        from frappe.exceptions import ValidationError
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        # Create a mock PPE Issue document with issue_type = "Casual"
        mock_doc = MagicMock()
        mock_doc.get = lambda field: {
            "issue_type": "Casual",
            "expected_return_date": empty_date,
        }.get(field)
        mock_doc.employee = "EMP-001"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.throw",
            side_effect=ValidationError,
        ) as mock_throw:
            with self.assertRaises(ValidationError):
                PPEIssue._validate_casual_issue(mock_doc)

            # Verify frappe.throw was called with the expected message
            mock_throw.assert_called_once()
            call_args = mock_throw.call_args[0][0]
            self.assertIn("Expected Return Date", call_args)

    @given(
        return_date=dates(
            min_value=date(2020, 1, 1),
            max_value=date(2099, 12, 31),
        ),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_accepts_valid_expected_return_date(self, return_date):
        """Casual PPE Issues with a valid expected_return_date do NOT throw for missing date.

        **Validates: Requirements 9.2**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        # Create a mock PPE Issue document with issue_type = "Casual" and valid date
        mock_doc = MagicMock()
        mock_doc.get = lambda field: {
            "issue_type": "Casual",
            "expected_return_date": return_date,
        }.get(field)
        mock_doc.employee = "EMP-001"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.throw",
        ) as mock_throw:
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.db.get_value",
                return_value="Casual",
            ):
                with patch(
                    "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.bold",
                    side_effect=lambda x: x,
                ):
                    PPEIssue._validate_casual_issue(mock_doc)

        # frappe.throw should NOT have been called
        mock_throw.assert_not_called()

    @given(
        issue_type=sampled_from(["Standard", "", None]),
    )
    @settings(max_examples=25, deadline=None)
    def test_non_casual_issue_skips_return_date_validation(self, issue_type):
        """Non-Casual issue types skip expected_return_date validation entirely.

        **Validates: Requirements 9.2**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        # Create a mock PPE Issue document with non-Casual issue_type
        mock_doc = MagicMock()
        mock_doc.get = lambda field: {
            "issue_type": issue_type,
            "expected_return_date": None,  # No date set — should still pass
        }.get(field)
        mock_doc.employee = "EMP-001"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.throw",
        ) as mock_throw:
            PPEIssue._validate_casual_issue(mock_doc)

        # frappe.throw should NOT have been called
        mock_throw.assert_not_called()


class TestCasualIssueValidatesEmployeeType(unittest.TestCase):
    """Property 14: Casual Issue Validates Employee Type

    For any PPE Issue with issue_type = "Casual", the system SHALL validate that
    the linked Employee has employment_type = "Casual" — rejecting submission
    if the employee is not a casual worker.

    **Validates: Requirements 9.5**
    """

    @given(
        employment_type=sampled_from(["Permanent", "Contract", "Intern", "Temporary", "Part-Time"]),
        return_date=dates(
            min_value=date(2020, 1, 1),
            max_value=date(2099, 12, 31),
        ),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_rejects_non_casual_employee(self, employment_type, return_date):
        """Casual PPE Issues for employees with non-Casual employment_type always raise.

        **Validates: Requirements 9.5**
        """
        from frappe.exceptions import ValidationError
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        # Create a mock PPE Issue document with issue_type = "Casual"
        mock_doc = MagicMock()
        mock_doc.get = lambda field: {
            "issue_type": "Casual",
            "expected_return_date": return_date,
        }.get(field)
        mock_doc.employee = "EMP-001"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.db.get_value",
            return_value=employment_type,
        ):
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.bold",
                side_effect=lambda x: x,
            ):
                with patch(
                    "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.throw",
                    side_effect=ValidationError,
                ) as mock_throw:
                    with self.assertRaises(ValidationError):
                        PPEIssue._validate_casual_issue(mock_doc)

                    # Verify the throw message mentions employment type
                    mock_throw.assert_called_once()
                    call_args = mock_throw.call_args[0][0]
                    self.assertIn("Casual", call_args)
                    self.assertIn("EMP-001", call_args)

    @given(
        return_date=dates(
            min_value=date(2020, 1, 1),
            max_value=date(2099, 12, 31),
        ),
    )
    @settings(max_examples=25, deadline=None)
    def test_casual_issue_accepts_casual_employee(self, return_date):
        """Casual PPE Issues for employees with employment_type = "Casual" pass validation.

        **Validates: Requirements 9.5**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        # Create a mock PPE Issue document with issue_type = "Casual"
        mock_doc = MagicMock()
        mock_doc.get = lambda field: {
            "issue_type": "Casual",
            "expected_return_date": return_date,
        }.get(field)
        mock_doc.employee = "EMP-001"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.db.get_value",
            return_value="Casual",
        ):
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.bold",
                side_effect=lambda x: x,
            ):
                with patch(
                    "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe.throw",
                ) as mock_throw:
                    PPEIssue._validate_casual_issue(mock_doc)

        # frappe.throw should NOT have been called
        mock_throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
