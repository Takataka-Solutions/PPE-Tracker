# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Integration smoke tests for PPE Loss → Additional Salary flow.

Feature: tts-ppe-tracker

Tests the end-to-end flow: PPE Loss acknowledgement triggers creation of
an Additional Salary deduction record with the correct amount, employee,
and salary component.

**Validates: Requirements 6.7, 6.8**
"""

import sys
import importlib
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fix frappe mock so that @frappe.whitelist() is a pass-through decorator
# and Document is a real base class. This must happen BEFORE importing any
# DocType modules or API modules that use these features.
# ---------------------------------------------------------------------------
import frappe

# Make @frappe.whitelist() a pass-through decorator
frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args or callable(args[0]) is False else (lambda fn: fn)


# Provide a real Document base class so that DocType classes are real classes
class _Document:
    pass


frappe.model.document.Document = _Document

# Also make frappe._ a pass-through for translations
frappe._ = lambda x: x


# ---------------------------------------------------------------------------
# Force re-import of the modules under test (they may have been cached
# with the incorrect frappe mock before our fixes above).
# ---------------------------------------------------------------------------
_loss_module_key = "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss"
_api_module_key = "ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api"
_issue_module_key = "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue"

# Remove cached modules so they get re-imported with our fixed frappe mock
for key in list(sys.modules.keys()):
    if key in (_loss_module_key, _api_module_key, _issue_module_key):
        del sys.modules[key]


class TestPPELossAcknowledgementCreatesAdditionalSalary(unittest.TestCase):
    """Integration smoke test: PPE Loss acknowledgement → Additional Salary creation.

    Verifies that calling _trigger_acknowledgement() on a PPE Loss document:
    1. Sets acknowledgement_status to "Acknowledged"
    2. Creates an Additional Salary with correct employee, amount, component, and type
    3. Submits the Additional Salary
    4. Links the Additional Salary back on the PPE Loss record

    Feature: tts-ppe-tracker
    **Validates: Requirements 6.7, 6.8**
    """

    def test_ppe_loss_acknowledgement_creates_additional_salary_with_correct_amount(
        self,
    ):
        """End-to-end: create PPE Loss → acknowledge → assert Additional Salary
        created with correct amount, employee, salary component, and type.

        Feature: tts-ppe-tracker
        **Validates: Requirements 6.7, 6.8**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

        # --- Setup mock Additional Salary document ---
        mock_additional_salary = MagicMock()
        mock_additional_salary.name = "HR-SAL-00001"

        # Configure frappe mocks for this test
        frappe.new_doc = MagicMock(return_value=mock_additional_salary)
        frappe.utils.today = MagicMock(return_value="2024-06-15")
        frappe.db = MagicMock()
        frappe.throw = MagicMock()

        # --- Create PPE Loss document instance ---
        doc = PPELoss()
        doc.name = "PPE-LOSS-001"
        doc.employee = "EMP-001"
        doc.ppe_item = "PPE-ITEM-001"
        doc.surcharge_amount = 2500
        doc.acknowledgement_status = "Pending"
        doc.acknowledgement_method = "Direct"
        doc.acknowledgement_attachment = None
        doc.additional_salary = None

        # Mock the save method
        doc.save = MagicMock()

        # --- Execute ---
        doc._trigger_acknowledgement()

        # --- Assertions ---

        # 1. Acknowledgement status is now "Acknowledged"
        self.assertEqual(doc.acknowledgement_status, "Acknowledged")

        # 2. frappe.new_doc("Additional Salary") was called
        frappe.new_doc.assert_called_once_with("Additional Salary")

        # 3. Additional Salary attributes were set correctly
        self.assertEqual(mock_additional_salary.employee, "EMP-001")
        self.assertEqual(
            mock_additional_salary.salary_component, "PPE Loss Deduction"
        )
        self.assertEqual(mock_additional_salary.amount, 2500)
        self.assertEqual(mock_additional_salary.type, "Deduction")
        self.assertEqual(mock_additional_salary.payroll_date, "2024-06-15")

        # 4. Additional Salary was inserted and submitted
        mock_additional_salary.insert.assert_called_once()
        mock_additional_salary.submit.assert_called_once()

        # 5. additional_salary link field on PPE Loss is populated
        self.assertEqual(doc.additional_salary, "HR-SAL-00001")

        # 6. PPE Loss save() was called
        doc.save.assert_called_once()


class TestAcknowledgeLossAPICreatesAdditionalSalary(unittest.TestCase):
    """Integration smoke test: acknowledge_loss API → Additional Salary creation.

    Verifies the full API flow: acknowledge_loss() fetches the PPE Loss document,
    validates authorization, triggers acknowledgement, and returns a response with
    the linked Additional Salary name.

    Feature: tts-ppe-tracker
    **Validates: Requirements 6.7, 6.8**
    """

    def test_acknowledge_loss_api_creates_additional_salary(self):
        """End-to-end via API: call acknowledge_loss → assert response contains
        the Additional Salary name and the document was properly processed.

        Feature: tts-ppe-tracker
        **Validates: Requirements 6.7, 6.8**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import acknowledge_loss

        # --- Setup mock PPE Loss document ---
        mock_doc = MagicMock()
        mock_doc.employee = "EMP-001"
        mock_doc.surcharge_amount = 2500
        mock_doc.acknowledgement_status = "Pending"
        mock_doc.additional_salary = None

        # Simulate _trigger_acknowledgement setting the additional_salary link
        def trigger_side_effect():
            mock_doc.additional_salary = "HR-SAL-00002"
            mock_doc.acknowledgement_status = "Acknowledged"

        mock_doc._trigger_acknowledgement.side_effect = trigger_side_effect

        # Configure frappe.get_doc to return our mock doc
        frappe.get_doc = MagicMock(return_value=mock_doc)

        # Mock _is_authorized_for_acknowledgement to return True
        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api._is_authorized_for_acknowledgement",
            return_value=True,
        ) as mock_is_authorized:
            # --- Execute ---
            result = acknowledge_loss("PPE-LOSS-001", "Direct")

            # --- Assertions ---

            # 1. frappe.get_doc was called with the correct PPE Loss name
            frappe.get_doc.assert_called_once_with("PPE Loss", "PPE-LOSS-001")

            # 2. Authorization was checked
            mock_is_authorized.assert_called_once_with(mock_doc)

        # 3. Acknowledgement method was set on the document
        self.assertEqual(mock_doc.acknowledgement_method, "Direct")

        # 4. via_api flag was set
        self.assertTrue(mock_doc.flags.via_api)

        # 5. _trigger_acknowledgement was called
        mock_doc._trigger_acknowledgement.assert_called_once()

        # 6. Response has the expected shape
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["additional_salary"], "HR-SAL-00002")


if __name__ == "__main__":
    unittest.main()
