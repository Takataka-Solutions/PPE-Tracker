# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the PPE Loss DocType.

Feature: tts-ppe-tracker
"""

import json
import os
import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis.strategies import integers, text, sampled_from, dates

from frappe.exceptions import ValidationError


def _make_ppe_loss_doc(
    acknowledgement_method="Supervisor Uploaded",
    acknowledgement_status="Acknowledged",
    acknowledgement_attachment=None,
    surcharge_amount=500,
):
    """Create a mock PPE Loss document with the given acknowledgement fields."""
    doc = MagicMock()
    doc.ppe_issue = "PPE-ISS-0001"
    doc.employee = "HR-EMP-0001"
    doc.employee_name = "Test Employee"
    doc.ppe_item = "PPE-ITEM-001"
    doc.loss_date = "2024-01-15"
    doc.reason = "Lost during fieldwork"
    doc.surcharge_amount = surcharge_amount
    doc.acknowledgement_status = acknowledgement_status
    doc.acknowledgement_method = acknowledgement_method
    doc.acknowledgement_attachment = acknowledgement_attachment
    doc.additional_salary = None
    return doc


def _get_ppe_loss_schema():
    """Load the PPE Loss DocType JSON schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__), "ppe_loss.json"
    )
    with open(schema_path, "r") as f:
        return json.load(f)


def _get_field_default(schema, fieldname):
    """Get the default value for a given field from the schema."""
    for field in schema.get("fields", []):
        if field.get("fieldname") == fieldname:
            return field.get("default")
    return None


class TestSupervisorUploadedRequiresAttachment(unittest.TestCase):
    """Property 16: Supervisor Uploaded Acknowledgement Requires Attachment

    For any PPE Loss with acknowledgement_method = "Supervisor Uploaded" and no
    attachment, assert validate() raises ValidationError when
    acknowledgement_status = "Acknowledged".

    Feature: tts-ppe-tracker, Property 16: Supervisor Uploaded Acknowledgement Requires Attachment
    **Validates: Requirements 6.6**
    """

    @given(surcharge=integers(min_value=100, max_value=100000))
    @settings(max_examples=25)
    @patch("frappe.throw", side_effect=ValidationError)
    def test_supervisor_uploaded_without_attachment_raises_validation_error(
        self, mock_throw, surcharge
    ):
        """Supervisor Uploaded method with no attachment must raise ValidationError.

        Feature: tts-ppe-tracker, Property 16: Supervisor Uploaded Acknowledgement Requires Attachment
        **Validates: Requirements 6.6**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

        doc = _make_ppe_loss_doc(
            acknowledgement_method="Supervisor Uploaded",
            acknowledgement_status="Acknowledged",
            acknowledgement_attachment=None,
            surcharge_amount=surcharge,
        )

        with self.assertRaises(ValidationError):
            PPELoss._validate_acknowledgement_attachment(doc)


class TestAcknowledgementAutoCreatesAdditionalSalary(unittest.TestCase):
    """Property 17: Acknowledgement Auto-Creates Additional Salary with Correct Amount

    For any PPE Loss transitioning to Acknowledged, assert an Additional Salary
    of deduction type is created for the exact surcharge_amount, linked to the
    correct employee, and the additional_salary field is set.

    Feature: tts-ppe-tracker, Property 17: Acknowledgement Auto-Creates Additional Salary with Correct Amount
    **Validates: Requirements 6.7, 6.8**
    """

    @given(
        surcharge=integers(min_value=1, max_value=999999),
        employee_id=integers(min_value=1, max_value=99999),
    )
    @settings(max_examples=25)
    @patch("ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss.frappe")
    def test_acknowledgement_creates_additional_salary_with_correct_fields(
        self, mock_frappe, surcharge, employee_id
    ):
        """Acknowledging a PPE Loss creates an Additional Salary deduction with
        the correct amount, employee, salary component, and type.

        Feature: tts-ppe-tracker, Property 17: Acknowledgement Auto-Creates Additional Salary with Correct Amount
        **Validates: Requirements 6.7, 6.8**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

        employee = f"HR-EMP-{employee_id:05d}"

        # Build a mock PPE Loss document (no spec= to avoid attribute restrictions)
        doc = MagicMock()
        doc.name = f"PPE-LOSS-{employee_id:05d}"
        doc.employee = employee
        doc.surcharge_amount = surcharge
        doc.acknowledgement_status = "Pending"
        doc.additional_salary = None

        # Configure mock Additional Salary document returned by frappe.new_doc
        mock_additional_salary = MagicMock()
        mock_additional_salary.name = f"HR-SAL-{employee_id:05d}"
        mock_frappe.new_doc.return_value = mock_additional_salary
        mock_frappe.utils.today.return_value = "2024-06-15"

        # Call the method under test
        PPELoss._create_additional_salary(doc)

        # Assert frappe.new_doc was called with "Additional Salary"
        mock_frappe.new_doc.assert_called_once_with("Additional Salary")

        # Assert the Additional Salary has deduction type
        self.assertEqual(
            mock_additional_salary.type,
            "Deduction",
            "Additional Salary must be of type 'Deduction'",
        )

        # Assert the amount equals the exact surcharge_amount
        self.assertEqual(
            mock_additional_salary.amount,
            surcharge,
            "Additional Salary amount must equal the PPE Loss surcharge_amount",
        )

        # Assert the employee matches the PPE Loss employee
        self.assertEqual(
            mock_additional_salary.employee,
            employee,
            "Additional Salary employee must match the PPE Loss employee",
        )

        # Assert the salary component is "PPE Loss Deduction"
        self.assertEqual(
            mock_additional_salary.salary_component,
            "PPE Loss Deduction",
            "Additional Salary salary_component must be 'PPE Loss Deduction'",
        )

        # Assert insert and submit were called
        mock_additional_salary.insert.assert_called_once()
        mock_additional_salary.submit.assert_called_once()

        # Assert the additional_salary link field on the PPE Loss is set
        self.assertEqual(
            doc.additional_salary,
            mock_additional_salary.name,
            "PPE Loss additional_salary field must be set to the created record name",
        )


class TestNewPPELossAcknowledgementStatusIsPending(unittest.TestCase):
    """Property 15: New PPE Loss Acknowledgement Status is Pending

    For any newly created PPE Loss record, the acknowledgement_status field
    SHALL be "Pending".

    Feature: tts-ppe-tracker, Property 15: New PPE Loss Acknowledgement Status is Pending
    **Validates: Requirements 6.3**
    """

    @given(
        surcharge=integers(min_value=100, max_value=100000),
        reason=text(min_size=1, max_size=200).filter(lambda s: s.strip() != ""),
        ack_method=sampled_from(["Direct", "Supervisor Uploaded"]),
    )
    @settings(max_examples=25)
    def test_new_ppe_loss_acknowledgement_status_is_pending(
        self, surcharge, reason, ack_method
    ):
        """For any newly created PPE Loss record, acknowledgement_status must be 'Pending'.

        This validates the DocType schema default and ensures that regardless of
        the input values provided for other fields (surcharge amount, reason,
        acknowledgement method), a new PPE Loss always starts with Pending status.

        Feature: tts-ppe-tracker, Property 15: New PPE Loss Acknowledgement Status is Pending
        **Validates: Requirements 6.3**
        """
        # Load the schema and verify the default for acknowledgement_status
        schema = _get_ppe_loss_schema()
        default_value = _get_field_default(schema, "acknowledgement_status")

        # The schema default MUST be "Pending" for any new document
        assert default_value == "Pending", (
            f"Expected acknowledgement_status default to be 'Pending', "
            f"got '{default_value}'"
        )

        # Simulate creating a new PPE Loss doc with the schema default applied
        # (as Frappe would do before any user interaction)
        doc = _make_ppe_loss_doc(
            acknowledgement_method=ack_method,
            acknowledgement_status=default_value,  # schema default applied
            acknowledgement_attachment=None,
            surcharge_amount=surcharge,
        )
        doc.reason = reason

        # Assert the invariant: new record always has Pending status
        assert doc.acknowledgement_status == "Pending", (
            f"Expected acknowledgement_status == 'Pending' for a new PPE Loss, "
            f"got '{doc.acknowledgement_status}'"
        )

    @given(
        surcharge=integers(min_value=1, max_value=999999),
    )
    @settings(max_examples=25)
    def test_schema_acknowledgement_status_options_include_pending(self, surcharge):
        """The acknowledgement_status field options must include 'Pending' as a valid value.

        Feature: tts-ppe-tracker, Property 15: New PPE Loss Acknowledgement Status is Pending
        **Validates: Requirements 6.3**
        """
        schema = _get_ppe_loss_schema()

        # Find the acknowledgement_status field
        ack_field = None
        for field in schema.get("fields", []):
            if field.get("fieldname") == "acknowledgement_status":
                ack_field = field
                break

        assert ack_field is not None, "acknowledgement_status field not found in schema"

        # Verify options include "Pending"
        options = ack_field.get("options", "").split("\n")
        assert "Pending" in options, (
            f"'Pending' not found in acknowledgement_status options: {options}"
        )

        # Verify the default is "Pending"
        assert ack_field.get("default") == "Pending", (
            f"Default is not 'Pending', got: {ack_field.get('default')}"
        )


if __name__ == "__main__":
    unittest.main()
