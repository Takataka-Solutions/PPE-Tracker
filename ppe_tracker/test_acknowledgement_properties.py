# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Issue Acknowledgement DocType.

Feature: ppe-tracker-enhancements-v2

Property 8: Acknowledgement Employee Validation
Property 9: Acknowledgement Submit/Cancel Round-Trip

**Validates: Requirements 5.3, 5.4, 5.7**
"""

import unittest
from unittest.mock import patch, MagicMock, call

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    text,
    integers,
    lists,
    composite,
    booleans,
    just,
    sampled_from,
)


MODULE_PATH = (
    "ppe_tracker.ppe_tracker.ppe_tracker.doctype."
    "ppe_issue_acknowledgement.ppe_issue_acknowledgement"
)


@composite
def acknowledgement_employee_dataset(draw):
    """Generate a PPE Issue Acknowledgement scenario for employee validation.

    Returns a tuple of:
      - parent_employee: the employee on the Acknowledgement parent
      - ppe_issue_rows: list of dicts with {ppe_issue, assigned_employee}
      - all_match: bool indicating whether all issues belong to parent_employee
    """
    # Generate a parent employee identifier
    parent_employee = f"EMP-{draw(integers(min_value=1, max_value=999)):04d}"

    # Generate 1–10 child rows
    num_rows = draw(integers(min_value=1, max_value=10))

    ppe_issue_rows = []
    all_match = True

    for i in range(num_rows):
        issue_name = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):05d}-{i}"
        # Decide whether this issue's employee matches the parent or is different
        matches_parent = draw(booleans())
        if matches_parent:
            assigned_employee = parent_employee
        else:
            # Generate a different employee
            other_id = draw(integers(min_value=1, max_value=999))
            assigned_employee = f"EMP-{other_id:04d}"
            # Ensure it's actually different
            if assigned_employee == parent_employee:
                assigned_employee = f"EMP-OTHER-{other_id:04d}"
            all_match = False

        ppe_issue_rows.append({
            "ppe_issue": issue_name,
            "assigned_employee": assigned_employee,
        })

    return (parent_employee, ppe_issue_rows, all_match)


@composite
def acknowledgement_submit_cancel_dataset(draw):
    """Generate an Acknowledgement submit/cancel scenario.

    Returns a tuple of:
      - ack_name: the acknowledgement document name
      - ppe_issue_names: list of PPE Issue names in the child table
    """
    ack_name = f"PPE-ACK-{draw(integers(min_value=2024, max_value=2030))}-{draw(integers(min_value=1, max_value=9999)):04d}"
    num_issues = draw(integers(min_value=1, max_value=15))

    ppe_issue_names = [
        f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):05d}-{i}"
        for i in range(num_issues)
    ]

    return (ack_name, ppe_issue_names)


class TestAcknowledgementEmployeeValidation(unittest.TestCase):
    """Property 8: Acknowledgement Employee Validation

    For any PPE Issue Acknowledgement with a child table of PPE Issues,
    the system SHALL reject saving if any PPE Issue in the child table belongs
    to a different employee than the one specified in the parent's Employee field,
    and accept when all belong to the same employee.

    Feature: ppe-tracker-enhancements-v2, Property 8: Acknowledgement Employee Validation
    **Validates: Requirements 5.3**
    """

    @given(dataset=acknowledgement_employee_dataset())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_validate_issues_belong_to_employee(self, dataset):
        """_validate_issues_belong_to_employee() throws if ANY issue belongs to a
        different employee, and does not throw when ALL match.

        Feature: ppe-tracker-enhancements-v2, Property 8: Acknowledgement Employee Validation
        **Validates: Requirements 5.3**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        parent_employee, ppe_issue_rows, all_match = dataset

        # Build a mock self instance
        mock_self = MagicMock(spec=PPEIssueAcknowledgement)
        mock_self.employee = parent_employee

        # Build child table rows
        mock_rows = []
        for row in ppe_issue_rows:
            mock_row = MagicMock()
            mock_row.ppe_issue = row["ppe_issue"]
            mock_rows.append(mock_row)
        mock_self.ppe_issues = mock_rows

        # Build a lookup for frappe.db.get_value to return the assigned employee
        def mock_get_value(doctype, name, field):
            for row in ppe_issue_rows:
                if row["ppe_issue"] == name:
                    return row["assigned_employee"]
            return None

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe.bold = lambda x: x  # passthrough for bold formatting
            mock_frappe._ = lambda x: x  # passthrough for translation

            if all_match:
                # Should NOT throw — validation passes
                PPEIssueAcknowledgement._validate_issues_belong_to_employee(mock_self)
                mock_frappe.throw.assert_not_called()
            else:
                # Should throw — validation fails
                with self.assertRaises(Exception):
                    PPEIssueAcknowledgement._validate_issues_belong_to_employee(mock_self)
                mock_frappe.throw.assert_called()


class TestAcknowledgementSubmitCancelRoundTrip(unittest.TestCase):
    """Property 9: Acknowledgement Submit/Cancel Round-Trip

    For any submitted PPE Issue Acknowledgement with N linked PPE Issues,
    submitting SHALL set acknowledgement_received=1 and acknowledgement=<ack_name>
    on all N linked PPE Issues; subsequently cancelling SHALL clear both fields
    on all N linked PPE Issues.

    Feature: ppe-tracker-enhancements-v2, Property 9: Acknowledgement Submit/Cancel Round-Trip
    **Validates: Requirements 5.4, 5.7**
    """

    @given(dataset=acknowledgement_submit_cancel_dataset())
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_submit_sets_and_cancel_clears_acknowledgement(self, dataset):
        """_set_acknowledgement_on_issues() sets flags on ALL N issues;
        _clear_acknowledgement_on_issues() clears them all.

        Feature: ppe-tracker-enhancements-v2, Property 9: Acknowledgement Submit/Cancel Round-Trip
        **Validates: Requirements 5.4, 5.7**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue_acknowledgement.ppe_issue_acknowledgement import (
            PPEIssueAcknowledgement,
        )

        ack_name, ppe_issue_names = dataset
        n = len(ppe_issue_names)

        # Build a mock self instance
        mock_self = MagicMock(spec=PPEIssueAcknowledgement)
        mock_self.name = ack_name

        # Build child table rows
        mock_rows = []
        for issue_name in ppe_issue_names:
            mock_row = MagicMock()
            mock_row.ppe_issue = issue_name
            mock_rows.append(mock_row)
        mock_self.ppe_issues = mock_rows

        # Track set_value calls
        set_value_calls = []

        def mock_set_value(doctype, name, fields_dict):
            set_value_calls.append((doctype, name, fields_dict))

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            mock_frappe.db.set_value = mock_set_value

            # --- SUBMIT phase ---
            set_value_calls.clear()
            PPEIssueAcknowledgement._set_acknowledgement_on_issues(mock_self)

            # ASSERTION 1: Exactly N set_value calls made during submit
            self.assertEqual(
                len(set_value_calls), n,
                f"Expected {n} set_value calls on submit, got {len(set_value_calls)}"
            )

            # ASSERTION 2: Each call sets acknowledgement_received=1 and acknowledgement=ack_name
            for i, (doctype, name, fields_dict) in enumerate(set_value_calls):
                self.assertEqual(doctype, "PPE Issue")
                self.assertEqual(name, ppe_issue_names[i])
                self.assertEqual(fields_dict["acknowledgement_received"], 1)
                self.assertEqual(fields_dict["acknowledgement"], ack_name)

            # ASSERTION 3: All N issue names are covered
            submitted_names = {c[1] for c in set_value_calls}
            self.assertEqual(submitted_names, set(ppe_issue_names))

            # --- CANCEL phase ---
            set_value_calls.clear()
            PPEIssueAcknowledgement._clear_acknowledgement_on_issues(mock_self)

            # ASSERTION 4: Exactly N set_value calls made during cancel
            self.assertEqual(
                len(set_value_calls), n,
                f"Expected {n} set_value calls on cancel, got {len(set_value_calls)}"
            )

            # ASSERTION 5: Each call clears acknowledgement_received=0 and acknowledgement=""
            for i, (doctype, name, fields_dict) in enumerate(set_value_calls):
                self.assertEqual(doctype, "PPE Issue")
                self.assertEqual(name, ppe_issue_names[i])
                self.assertEqual(fields_dict["acknowledgement_received"], 0)
                self.assertEqual(fields_dict["acknowledgement"], "")

            # ASSERTION 6: All N issue names are covered in cancel
            cancelled_names = {c[1] for c in set_value_calls}
            self.assertEqual(cancelled_names, set(ppe_issue_names))
