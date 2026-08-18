# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the PPE Issue Acknowledgement DocType.

Properties tested:
- Property 8: Acknowledgement Employee Validation
- Property 9: Acknowledgement Submit/Cancel Round-Trip

**Validates: Requirements 5.3, 5.4, 5.7**
"""

import unittest
from unittest.mock import patch, MagicMock, call

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    text,
    integers,
    lists,
    booleans,
    composite,
    sampled_from,
    just,
)


@composite
def ppe_issues_with_mixed_employees(draw, parent_employee):
    """Generate a list of PPE Issue child rows where at least one belongs to a
    different employee than the parent.

    Each row has a `ppe_issue` field (the PPE Issue name).
    Returns (rows, employee_lookup) where employee_lookup maps ppe_issue -> employee.
    """
    num_issues = draw(integers(min_value=1, max_value=10))
    rows = []
    employee_lookup = {}

    # Ensure at least one row belongs to a different employee
    has_mismatch = False

    for i in range(num_issues):
        ppe_issue_name = f"PPE-ISS-{i:04d}"
        row = MagicMock()
        row.ppe_issue = ppe_issue_name

        # Decide if this row's employee matches the parent or not
        if i == 0 and not has_mismatch:
            # Force at least one mismatch
            issue_employee = f"EMP-OTHER-{draw(integers(min_value=1, max_value=99)):03d}"
            has_mismatch = True
        else:
            match = draw(booleans())
            if match:
                issue_employee = parent_employee
            else:
                issue_employee = f"EMP-OTHER-{draw(integers(min_value=1, max_value=99)):03d}"
                has_mismatch = True

        employee_lookup[ppe_issue_name] = issue_employee
        rows.append(row)

    # Ensure there's at least one mismatch
    assume(any(emp != parent_employee for emp in employee_lookup.values()))

    return rows, employee_lookup


@composite
def ppe_issues_all_same_employee(draw, parent_employee):
    """Generate a list of PPE Issue child rows where ALL belong to the same employee
    as the parent.

    Returns (rows, employee_lookup).
    """
    num_issues = draw(integers(min_value=1, max_value=10))
    rows = []
    employee_lookup = {}

    for i in range(num_issues):
        ppe_issue_name = f"PPE-ISS-{i:04d}"
        row = MagicMock()
        row.ppe_issue = ppe_issue_name
        employee_lookup[ppe_issue_name] = parent_employee
        rows.append(row)

    return rows, employee_lookup


class TestAcknowledgementEmployeeValidation(unittest.TestCase):
    """Property 8: Acknowledgement Employee Validation

    For any PPE Issue Acknowledgement with a child table of PPE Issues, the system
    SHALL reject saving if any PPE Issue in the child table belongs to a different
    employee than the one specified in the parent's Employee field, and accept when
    all belong to the same employee.

    **Validates: Requirements 5.3**
    """

    @given(
        parent_employee=sampled_from(["EMP-001", "EMP-002", "EMP-003", "EMP-010"]),
    )
    @settings(max_examples=25, deadline=None)
    def test_rejects_when_any_issue_belongs_to_different_employee(self, parent_employee):
        """Validation raises when at least one PPE Issue belongs to a different employee.

        **Validates: Requirements 5.3**
        """
        from hypothesis import given as h_given
        from ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )
        from frappe.exceptions import ValidationError

        # Generate mixed-employee issue rows using the composite strategy inline
        from hypothesis import find
        from hypothesis.strategies import just as st_just

        # Build rows manually with guaranteed mismatch
        rows = []
        employee_lookup = {}

        # One matching row
        row_match = MagicMock()
        row_match.ppe_issue = "PPE-ISS-MATCH"
        rows.append(row_match)
        employee_lookup["PPE-ISS-MATCH"] = parent_employee

        # One mismatched row
        other_employee = "EMP-DIFFERENT-999"
        row_mismatch = MagicMock()
        row_mismatch.ppe_issue = "PPE-ISS-MISMATCH"
        rows.append(row_mismatch)
        employee_lookup["PPE-ISS-MISMATCH"] = other_employee

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.employee = parent_employee
        mock_doc.ppe_issues = rows

        # Mock frappe.db.get_value to return the employee for each PPE Issue
        def get_value_side_effect(doctype, name, field):
            if doctype == "PPE Issue":
                return employee_lookup.get(name, None)
            return None

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.db.get_value",
            side_effect=get_value_side_effect,
        ):
            with patch(
                "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.throw",
                side_effect=ValidationError,
            ) as mock_throw:
                with patch(
                    "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.bold",
                    side_effect=lambda x: f"<b>{x}</b>",
                ):
                    with self.assertRaises(ValidationError):
                        PPEIssueAcknowledgement._validate_issues_belong_to_employee(mock_doc)

                    # Verify throw was called
                    mock_throw.assert_called()

    @given(
        parent_employee=sampled_from(["EMP-001", "EMP-002", "EMP-003", "EMP-010"]),
        num_issues=integers(min_value=1, max_value=8),
    )
    @settings(max_examples=25, deadline=None)
    def test_accepts_when_all_issues_belong_to_same_employee(self, parent_employee, num_issues):
        """Validation passes when all PPE Issues belong to the same employee as parent.

        **Validates: Requirements 5.3**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        # Generate rows all belonging to the parent employee
        rows = []
        for i in range(num_issues):
            row = MagicMock()
            row.ppe_issue = f"PPE-ISS-{i:04d}"
            rows.append(row)

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.employee = parent_employee
        mock_doc.ppe_issues = rows

        # Mock frappe.db.get_value to always return the parent employee
        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.db.get_value",
            return_value=parent_employee,
        ):
            with patch(
                "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.throw",
            ) as mock_throw:
                # Should NOT raise
                PPEIssueAcknowledgement._validate_issues_belong_to_employee(mock_doc)

                # frappe.throw should NOT have been called
                mock_throw.assert_not_called()


class TestAcknowledgementSubmitCancelRoundTrip(unittest.TestCase):
    """Property 9: Acknowledgement Submit/Cancel Round-Trip

    For any submitted PPE Issue Acknowledgement with N linked PPE Issues, submitting
    SHALL set `acknowledgement_received = 1` and `acknowledgement = <ack_name>` on
    all N linked PPE Issues; subsequently cancelling the same acknowledgement SHALL
    clear both fields on all N linked PPE Issues, restoring them to their
    pre-acknowledgement state.

    **Validates: Requirements 5.4, 5.7**
    """

    @given(
        num_issues=integers(min_value=1, max_value=10),
        ack_name=sampled_from([
            "PPE-ACK-2024-0001",
            "PPE-ACK-2024-0042",
            "PPE-ACK-2025-0100",
        ]),
    )
    @settings(max_examples=25, deadline=None)
    def test_submit_sets_acknowledgement_on_all_issues(self, num_issues, ack_name):
        """On submit, acknowledgement_received=1 and acknowledgement=self.name are set
        on every linked PPE Issue.

        **Validates: Requirements 5.4**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        # Generate child rows
        rows = []
        for i in range(num_issues):
            row = MagicMock()
            row.ppe_issue = f"PPE-ISS-{i:04d}"
            rows.append(row)

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.name = ack_name
        mock_doc.ppe_issues = rows

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.db.set_value"
        ) as mock_set_value:
            PPEIssueAcknowledgement._set_acknowledgement_on_issues(mock_doc)

            # Verify set_value called once per issue with correct values
            self.assertEqual(mock_set_value.call_count, num_issues)

            for row in rows:
                mock_set_value.assert_any_call(
                    "PPE Issue",
                    row.ppe_issue,
                    {
                        "acknowledgement_received": 1,
                        "acknowledgement": ack_name,
                    },
                )

    @given(
        num_issues=integers(min_value=1, max_value=10),
    )
    @settings(max_examples=25, deadline=None)
    def test_cancel_clears_acknowledgement_on_all_issues(self, num_issues):
        """On cancel, acknowledgement_received=0 and acknowledgement="" are cleared
        on every linked PPE Issue.

        **Validates: Requirements 5.7**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        # Generate child rows
        rows = []
        for i in range(num_issues):
            row = MagicMock()
            row.ppe_issue = f"PPE-ISS-{i:04d}"
            rows.append(row)

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.name = "PPE-ACK-2024-0001"
        mock_doc.ppe_issues = rows

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.db.set_value"
        ) as mock_set_value:
            PPEIssueAcknowledgement._clear_acknowledgement_on_issues(mock_doc)

            # Verify set_value called once per issue with cleared values
            self.assertEqual(mock_set_value.call_count, num_issues)

            for row in rows:
                mock_set_value.assert_any_call(
                    "PPE Issue",
                    row.ppe_issue,
                    {
                        "acknowledgement_received": 0,
                        "acknowledgement": "",
                    },
                )

    @given(
        num_issues=integers(min_value=1, max_value=8),
        ack_name=sampled_from([
            "PPE-ACK-2024-0001",
            "PPE-ACK-2024-0077",
            "PPE-ACK-2025-0200",
        ]),
    )
    @settings(max_examples=25, deadline=None)
    def test_submit_then_cancel_round_trip_restores_state(self, num_issues, ack_name):
        """Submitting then cancelling an acknowledgement results in all linked PPE Issues
        having their acknowledgement fields cleared (round-trip property).

        **Validates: Requirements 5.4, 5.7**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        # Generate child rows
        rows = []
        for i in range(num_issues):
            row = MagicMock()
            row.ppe_issue = f"PPE-ISS-{i:04d}"
            rows.append(row)

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.name = ack_name
        mock_doc.ppe_issues = rows

        # Track all set_value calls across submit AND cancel
        all_calls = []

        def track_set_value(doctype, name, values):
            all_calls.append((doctype, name, values.copy()))

        with patch(
            "ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement.frappe.db.set_value",
            side_effect=track_set_value,
        ):
            # Submit
            PPEIssueAcknowledgement._set_acknowledgement_on_issues(mock_doc)
            # Cancel
            PPEIssueAcknowledgement._clear_acknowledgement_on_issues(mock_doc)

        # After round-trip: total calls should be 2 * num_issues
        self.assertEqual(len(all_calls), 2 * num_issues)

        # Verify each issue had submit (set) then cancel (clear)
        for i, row in enumerate(rows):
            # Submit call: sets acknowledgement
            submit_call = all_calls[i]
            self.assertEqual(submit_call[0], "PPE Issue")
            self.assertEqual(submit_call[1], row.ppe_issue)
            self.assertEqual(submit_call[2]["acknowledgement_received"], 1)
            self.assertEqual(submit_call[2]["acknowledgement"], ack_name)

            # Cancel call: clears acknowledgement
            cancel_call = all_calls[num_issues + i]
            self.assertEqual(cancel_call[0], "PPE Issue")
            self.assertEqual(cancel_call[1], row.ppe_issue)
            self.assertEqual(cancel_call[2]["acknowledgement_received"], 0)
            self.assertEqual(cancel_call[2]["acknowledgement"], "")


if __name__ == "__main__":
    unittest.main()
