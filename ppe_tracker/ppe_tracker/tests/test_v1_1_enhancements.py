# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for v1.1 enhancement features.

Tests cover:
- PPE Issue blocked when justification requires prior return/loss (Req 18.1, 18.2)
- PPE Issue allowed when prior PPE Return exists (Req 18.2)
- PPE Issue allowed when prior PPE Loss exists (Req 18.2)
- Additional Salary payroll_date = loss_date (Req 19.1)
- Due for Replacement report includes expired items with negative days (Req 20.1, 20.2)

Feature: tts-ppe-tracker
"""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Setup frappe mock infrastructure before importing DocType modules
# ---------------------------------------------------------------------------
import frappe


# Ensure frappe.whitelist is a pass-through decorator
frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args or callable(args[0]) is False else (lambda fn: fn)


class _Document:
    pass


frappe.model.document.Document = _Document
frappe._ = lambda x: x


# ---------------------------------------------------------------------------
# Force re-import of relevant modules
# ---------------------------------------------------------------------------
_issue_module_key = "ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue"
_loss_module_key = "ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss"
_report_module_key = "ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement"

for key in list(sys.modules.keys()):
    if key in (_issue_module_key, _loss_module_key, _report_module_key):
        del sys.modules[key]


# ===========================================================================
# Helper to create frappe-like dicts with dot access (SimpleNamespace)
# ===========================================================================

def _frappe_dict(**kwargs):
    """Simulate frappe._dict which supports both dict and dot access."""
    return SimpleNamespace(**kwargs)


# ===========================================================================
# Tests for Requirement 18.1, 18.2 — Return/Loss prerequisite validation
# ===========================================================================

class TestPPEIssueReturnLossPrerequisite(unittest.TestCase):
    """Tests for _validate_return_or_loss_prerequisite() on PPE Issue.

    Requirement 18.1: IF the justification on the linked PPE Request is
    "Worn Out Before Lifespan End (Cost Charged to Employee)" or "Exceeded Lifespan",
    THE System SHALL check that a PPE Return or PPE Loss exists for the employee's
    previous PPE Issue (same PPE Item).

    Requirement 18.2: IF neither a PPE Return nor PPE Loss exists for the previous
    issue, THE System SHALL block submission with a validation error.

    Feature: tts-ppe-tracker
    """

    @patch("frappe.db.exists")
    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch("frappe.throw", side_effect=Exception("ValidationError"))
    def test_issue_blocked_when_worn_out_justification_and_no_prior_return_or_loss(
        self, mock_throw, mock_get_value, mock_get_all, mock_db_exists
    ):
        """PPE Issue submission raises error when justification is 'Worn Out...'
        and no prior PPE Return or PPE Loss exists.

        Feature: tts-ppe-tracker
        **Validates: Requirements 18.1, 18.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        doc = MagicMock()
        doc.ppe_request = "REQ-001"
        doc.employee = "EMP-001"
        doc.ppe_item = "PPE-HELMET"
        doc.name = "ISS-002"

        # Justification triggers prerequisite check
        mock_get_value.return_value = "Worn Out Before Lifespan End (Cost Charged to Employee)"

        # Previous issue exists — use SimpleNamespace for dot access
        mock_get_all.return_value = [_frappe_dict(name="ISS-001")]

        # No PPE Return and no PPE Loss for previous issue
        mock_db_exists.return_value = None

        with self.assertRaises(Exception) as ctx:
            PPEIssue._validate_return_or_loss_prerequisite(doc)

        self.assertIn("ValidationError", str(ctx.exception))
        mock_throw.assert_called_once()

    @patch("frappe.db.exists")
    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch("frappe.throw", side_effect=Exception("ValidationError"))
    def test_issue_blocked_when_exceeded_lifespan_and_no_prior_return_or_loss(
        self, mock_throw, mock_get_value, mock_get_all, mock_db_exists
    ):
        """PPE Issue submission raises error when justification is 'Exceeded Lifespan'
        and no prior PPE Return or PPE Loss exists.

        Feature: tts-ppe-tracker
        **Validates: Requirements 18.1, 18.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        doc = MagicMock()
        doc.ppe_request = "REQ-002"
        doc.employee = "EMP-001"
        doc.ppe_item = "PPE-GLOVES"
        doc.name = "ISS-003"

        mock_get_value.return_value = "Exceeded Lifespan"
        mock_get_all.return_value = [_frappe_dict(name="ISS-002")]
        mock_db_exists.return_value = None

        with self.assertRaises(Exception):
            PPEIssue._validate_return_or_loss_prerequisite(doc)

        mock_throw.assert_called_once()

    @patch("frappe.db.exists")
    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch("frappe.throw")
    def test_issue_allowed_when_prior_ppe_return_exists(
        self, mock_throw, mock_get_value, mock_get_all, mock_db_exists
    ):
        """PPE Issue submission allowed when prior PPE Return exists for
        the previous issue.

        Feature: tts-ppe-tracker
        **Validates: Requirement 18.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        doc = MagicMock()
        doc.ppe_request = "REQ-003"
        doc.employee = "EMP-001"
        doc.ppe_item = "PPE-HELMET"
        doc.name = "ISS-004"

        mock_get_value.return_value = "Worn Out Before Lifespan End (Cost Charged to Employee)"
        mock_get_all.return_value = [_frappe_dict(name="ISS-001")]

        # First call to db.exists (PPE Return) returns a match
        # Second call (PPE Loss) won't be needed since short-circuit is not guaranteed
        # So we make both return truthy to be safe
        mock_db_exists.return_value = "RET-001"

        # Should NOT throw
        PPEIssue._validate_return_or_loss_prerequisite(doc)
        mock_throw.assert_not_called()

    @patch("frappe.db.exists")
    @patch("frappe.get_all")
    @patch("frappe.db.get_value")
    @patch("frappe.throw")
    def test_issue_allowed_when_prior_ppe_loss_exists(
        self, mock_throw, mock_get_value, mock_get_all, mock_db_exists
    ):
        """PPE Issue submission allowed when prior PPE Loss exists for
        the previous issue (even if no PPE Return exists).

        Feature: tts-ppe-tracker
        **Validates: Requirement 18.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        doc = MagicMock()
        doc.ppe_request = "REQ-004"
        doc.employee = "EMP-001"
        doc.ppe_item = "PPE-BOOTS"
        doc.name = "ISS-005"

        mock_get_value.return_value = "Exceeded Lifespan"
        mock_get_all.return_value = [_frappe_dict(name="ISS-003")]

        # PPE Return check returns None, PPE Loss check returns a match
        def db_exists_side_effect(doctype, filters):
            if doctype == "PPE Return":
                return None
            if doctype == "PPE Loss":
                return "LOSS-001"
            return None

        mock_db_exists.side_effect = db_exists_side_effect

        # Should NOT throw
        PPEIssue._validate_return_or_loss_prerequisite(doc)
        mock_throw.assert_not_called()

    @patch("frappe.db.get_value")
    @patch("frappe.throw")
    def test_issue_not_blocked_for_new_employee_justification(
        self, mock_throw, mock_get_value
    ):
        """PPE Issue submission is NOT blocked when justification is 'New Employee'
        (not a replacement justification).

        Feature: tts-ppe-tracker
        **Validates: Requirements 18.1**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        doc = MagicMock()
        doc.ppe_request = "REQ-005"
        doc.employee = "EMP-002"
        doc.ppe_item = "PPE-HELMET"
        doc.name = "ISS-006"

        mock_get_value.return_value = "New Employee"

        # Should NOT throw — non-replacement justification bypasses the check
        PPEIssue._validate_return_or_loss_prerequisite(doc)
        mock_throw.assert_not_called()


# ===========================================================================
# Tests for Requirement 19.1 — Additional Salary payroll_date = loss_date
# ===========================================================================

class TestAdditionalSalaryPayrollDate(unittest.TestCase):
    """Tests for PPE Loss controller setting payroll_date on Additional Salary.

    Requirement 19.1: WHEN the system creates an Additional Salary from a PPE Loss
    acknowledgement, THE System SHALL set the payroll_date to the PPE Loss loss_date.

    Feature: tts-ppe-tracker
    """

    @patch("frappe.new_doc")
    def test_additional_salary_payroll_date_equals_loss_date(self, mock_new_doc):
        """Additional Salary payroll_date is set to the PPE Loss loss_date.

        Feature: tts-ppe-tracker
        **Validates: Requirement 19.1**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

        mock_additional_salary = MagicMock()
        mock_additional_salary.name = "HR-SAL-00005"
        mock_new_doc.return_value = mock_additional_salary

        doc = PPELoss()
        doc.name = "PPE-LOSS-005"
        doc.employee = "EMP-005"
        doc.ppe_item = "PPE-ITEM-005"
        doc.surcharge_amount = 1200
        doc.loss_date = "2025-03-20"
        doc.acknowledgement_status = "Pending"
        doc.acknowledgement_method = "Direct"
        doc.acknowledgement_attachment = None
        doc.additional_salary = None

        doc._create_additional_salary()

        # Assert payroll_date was set to loss_date
        self.assertEqual(mock_additional_salary.payroll_date, "2025-03-20")
        self.assertEqual(mock_additional_salary.employee, "EMP-005")
        self.assertEqual(mock_additional_salary.amount, 1200)
        self.assertEqual(mock_additional_salary.type, "Deduction")
        self.assertEqual(mock_additional_salary.salary_component, "PPE Loss Deduction")
        mock_additional_salary.insert.assert_called_once()
        mock_additional_salary.submit.assert_called_once()

    @patch("frappe.new_doc")
    def test_additional_salary_payroll_date_varies_with_loss_date(self, mock_new_doc):
        """Verifies payroll_date changes when loss_date changes — not hardcoded.

        Feature: tts-ppe-tracker
        **Validates: Requirement 19.1**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

        mock_additional_salary = MagicMock()
        mock_additional_salary.name = "HR-SAL-00006"
        mock_new_doc.return_value = mock_additional_salary

        doc = PPELoss()
        doc.name = "PPE-LOSS-006"
        doc.employee = "EMP-006"
        doc.ppe_item = "PPE-ITEM-006"
        doc.surcharge_amount = 800
        doc.loss_date = "2025-11-05"
        doc.acknowledgement_status = "Pending"
        doc.acknowledgement_method = "Direct"
        doc.acknowledgement_attachment = None
        doc.additional_salary = None

        doc._create_additional_salary()

        self.assertEqual(mock_additional_salary.payroll_date, "2025-11-05")


# ===========================================================================
# Tests for Requirements 20.1, 20.2 — Due for Replacement includes expired items
# ===========================================================================

# The report module path for patching (imports today, add_days, date_diff directly)
_REPORT_MODULE = "ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement"


class TestDueForReplacementReportIncludesExpired(unittest.TestCase):
    """Tests for PPE Due for Replacement report showing expired items.

    Requirement 20.1: THE System SHALL include PPE Issue records with status
    'Active' or 'Expired' whose expiry date is on or before today + days_window.

    Requirement 20.2: THE System SHALL display records with negative
    days_remaining values (already expired) alongside positive values.

    Feature: tts-ppe-tracker
    """

    @patch("frappe.db.get_value")
    @patch("frappe.get_all")
    @patch(f"{_REPORT_MODULE}.today", return_value="2025-06-01")
    @patch(f"{_REPORT_MODULE}.add_days", return_value="2025-07-01")
    @patch(f"{_REPORT_MODULE}.date_diff")
    def test_report_includes_expired_items_with_negative_days(
        self, mock_date_diff, mock_add_days, mock_today, mock_get_all, mock_get_value
    ):
        """Report data includes Expired PPE Issues with negative days_remaining.

        Feature: tts-ppe-tracker
        **Validates: Requirements 20.1, 20.2**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import (
            get_data,
        )

        # Return mixed Active and Expired records — use SimpleNamespace for dot access
        mock_get_all.return_value = [
            _frappe_dict(
                name="ISS-EXPIRED-001",
                employee="EMP-001",
                employee_name="Alice Smith",
                ppe_item="PPE-HELMET",
                issue_date="2024-01-15",
                expiry_date="2025-01-15",
                quantity=1,
            ),
            _frappe_dict(
                name="ISS-ACTIVE-002",
                employee="EMP-002",
                employee_name="Bob Jones",
                ppe_item="PPE-GLOVES",
                issue_date="2025-01-01",
                expiry_date="2025-06-20",
                quantity=2,
            ),
        ]

        # Employee details
        mock_get_value.side_effect = [
            {"department": "Operations", "designation": "Worker"},
            {"department": "Logistics", "designation": "Driver"},
        ]

        # date_diff returns negative for expired, positive for expiring soon
        mock_date_diff.side_effect = [-137, 19]

        filters = {}
        data = get_data(filters)

        # Both records should be included
        self.assertEqual(len(data), 2)

        # After sorting by days_remaining: -137 first, 19 second
        self.assertEqual(data[0]["days_remaining"], -137)
        self.assertEqual(data[0]["employee"], "EMP-001")

        self.assertEqual(data[1]["days_remaining"], 19)
        self.assertEqual(data[1]["employee"], "EMP-002")

    @patch("frappe.db.get_value")
    @patch("frappe.get_all")
    @patch(f"{_REPORT_MODULE}.today", return_value="2025-06-01")
    @patch(f"{_REPORT_MODULE}.add_days", return_value="2025-07-01")
    @patch(f"{_REPORT_MODULE}.date_diff")
    def test_report_default_window_is_30_days(
        self, mock_date_diff, mock_add_days, mock_today, mock_get_all, mock_get_value
    ):
        """Report defaults days_window to 30 when not provided in filters.

        Feature: tts-ppe-tracker
        **Validates: Requirement 20.1**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import (
            get_data,
        )

        mock_get_all.return_value = []

        # Pass empty filters — should default to 30
        filters = {}
        get_data(filters)

        # Verify add_days was called with 30
        mock_add_days.assert_called_once_with("2025-06-01", 30)

    @patch("frappe.db.get_value")
    @patch("frappe.get_all")
    @patch(f"{_REPORT_MODULE}.today", return_value="2025-06-01")
    @patch(f"{_REPORT_MODULE}.add_days", return_value="2025-06-15")
    @patch(f"{_REPORT_MODULE}.date_diff")
    def test_report_uses_custom_window_when_provided(
        self, mock_date_diff, mock_add_days, mock_today, mock_get_all, mock_get_value
    ):
        """Report uses the custom days_window from filters.

        Feature: tts-ppe-tracker
        **Validates: Requirement 20.1**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import (
            get_data,
        )

        mock_get_all.return_value = []

        filters = {"days_window": 14}
        get_data(filters)

        # Verify add_days was called with custom window
        mock_add_days.assert_called_once_with("2025-06-01", 14)

    @patch("frappe.db.get_value")
    @patch("frappe.get_all")
    @patch(f"{_REPORT_MODULE}.today", return_value="2025-06-01")
    @patch(f"{_REPORT_MODULE}.add_days", return_value="2025-07-01")
    @patch(f"{_REPORT_MODULE}.date_diff")
    def test_report_sorted_by_days_remaining_ascending(
        self, mock_date_diff, mock_add_days, mock_today, mock_get_all, mock_get_value
    ):
        """Report results are sorted by days_remaining ascending (most overdue first).

        Feature: tts-ppe-tracker
        **Validates: Requirement 20.3 (sort order)**
        """
        from ppe_tracker.ppe_tracker.report.ppe_due_for_replacement.ppe_due_for_replacement import (
            get_data,
        )

        # Return records in unsorted order
        mock_get_all.return_value = [
            _frappe_dict(
                name="ISS-001",
                employee="EMP-001",
                employee_name="Alice",
                ppe_item="PPE-A",
                issue_date="2025-01-01",
                expiry_date="2025-06-20",
                quantity=1,
            ),
            _frappe_dict(
                name="ISS-002",
                employee="EMP-002",
                employee_name="Bob",
                ppe_item="PPE-B",
                issue_date="2024-01-01",
                expiry_date="2025-01-01",
                quantity=1,
            ),
            _frappe_dict(
                name="ISS-003",
                employee="EMP-003",
                employee_name="Charlie",
                ppe_item="PPE-C",
                issue_date="2025-03-01",
                expiry_date="2025-06-05",
                quantity=1,
            ),
        ]

        # Employee details
        mock_get_value.side_effect = [
            {"department": "Ops", "designation": "Worker"},
            {"department": "Ops", "designation": "Driver"},
            {"department": "Ops", "designation": "Tech"},
        ]

        # date_diff results (matching order from mock_get_all)
        mock_date_diff.side_effect = [19, -151, 4]

        filters = {}
        data = get_data(filters)

        self.assertEqual(len(data), 3)
        # Verify ascending order by days_remaining
        days_values = [row["days_remaining"] for row in data]
        self.assertEqual(days_values, sorted(days_values))
        self.assertEqual(days_values, [-151, 4, 19])


if __name__ == "__main__":
    unittest.main()
