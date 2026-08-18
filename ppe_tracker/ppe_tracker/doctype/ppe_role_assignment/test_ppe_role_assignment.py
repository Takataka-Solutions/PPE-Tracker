# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the PPE Role Assignment DocType controller.

Tests validate() behaviour for:
- Scope validation: at least one of department or designation must be set (Req 2.1)
- Items validation: at least one child row is required (Req 2.4)
- Quantity validation: each child row quantity must be >= 1 (Req 23.3)

Requirements: 23.1, 23.3, 2.1, 2.4
"""

import unittest
from unittest.mock import patch, MagicMock

import frappe
from frappe.exceptions import ValidationError


def _make_role_assignment(department=None, designation=None, required_items=None):
    """Create a mock PPE Role Assignment document with given field values."""
    doc = MagicMock()
    doc.department = department
    doc.designation = designation
    doc.required_items = required_items if required_items is not None else []
    return doc


def _make_item_row(ppe_item="TEST-PPE-ITEM", quantity=1, idx=1):
    """Create a mock PPE Role Assignment Item child row."""
    row = MagicMock()
    row.ppe_item = ppe_item
    row.quantity = quantity
    row.idx = idx
    return row


# Target module path for patching frappe.throw inside the controller
_CONTROLLER_MODULE = (
    "ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment"
)


class TestPPERoleAssignment(unittest.TestCase):
    """Unit tests for PPE Role Assignment validate() method.

    Requirements: 23.1, 23.3, 2.1, 2.4
    """

    # ─── Scope Validation Tests (Requirement 2.1) ─────────────────────────

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_neither_department_nor_designation_raises_error(self, mock_frappe):
        """Save with neither department nor designation raises ValidationError.

        Requirement 2.1: A PPE Role Assignment must reference either a
        Department, a Designation, or both. If both are empty, save is blocked.
        """
        mock_frappe.throw.side_effect = ValidationError("scope error")
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=1)
        doc = _make_role_assignment(department=None, designation=None, required_items=[item_row])

        with self.assertRaises(ValidationError):
            PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_called_once()

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_department_only_succeeds(self, mock_frappe):
        """Save with department only (no designation) passes validation.

        Requirement 2.1: Either Department or Designation is sufficient.
        """
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=1)
        doc = _make_role_assignment(department="Operations", designation=None, required_items=[item_row])

        PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_not_called()

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_designation_only_succeeds(self, mock_frappe):
        """Save with designation only (no department) passes validation.

        Requirement 2.1: Either Department or Designation is sufficient.
        """
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=1)
        doc = _make_role_assignment(department=None, designation="Driver", required_items=[item_row])

        PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_not_called()

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_both_department_and_designation_succeeds(self, mock_frappe):
        """Save with both department and designation passes validation.

        Requirement 2.1: Both simultaneously is also valid.
        """
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=1)
        doc = _make_role_assignment(
            department="Operations", designation="Driver", required_items=[item_row]
        )

        PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_not_called()

    # ─── Items Validation Tests (Requirement 2.4) ─────────────────────────

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_no_child_rows_raises_error(self, mock_frappe):
        """Save with no child rows in required_items raises ValidationError.

        Requirement 2.4: At least one PPE Item child row is required.
        """
        mock_frappe.throw.side_effect = ValidationError("items error")
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        doc = _make_role_assignment(department="Operations", designation=None, required_items=[])

        with self.assertRaises(ValidationError):
            PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_called_once()

    # ─── Quantity Validation Tests (Requirement 23.3) ─────────────────────

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_child_row_quantity_zero_raises_error(self, mock_frappe):
        """Save with a child row quantity = 0 raises ValidationError.

        Requirement 23.3: Quantity must be at least 1 (minimum 1).
        """
        mock_frappe.throw.side_effect = ValidationError("quantity error")
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=0, idx=1)
        doc = _make_role_assignment(department="Operations", required_items=[item_row])

        with self.assertRaises(ValidationError):
            PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_called_once()

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_child_row_quantity_one_succeeds(self, mock_frappe):
        """Save with a child row quantity = 1 passes validation.

        Requirement 23.3: Quantity >= 1 is valid.
        """
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=1, idx=1)
        doc = _make_role_assignment(department="Operations", required_items=[item_row])

        PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_not_called()

    @patch(f"{_CONTROLLER_MODULE}.frappe")
    def test_save_with_child_row_quantity_five_succeeds(self, mock_frappe):
        """Save with a child row quantity = 5 passes validation.

        Requirement 23.3: Quantity >= 1 is valid. Larger values are allowed.
        """
        mock_frappe._ = lambda s: s

        from ppe_tracker.ppe_tracker.doctype.ppe_role_assignment.ppe_role_assignment import (
            PPERoleAssignment,
        )

        item_row = _make_item_row(quantity=5, idx=1)
        doc = _make_role_assignment(department="Operations", required_items=[item_row])

        PPERoleAssignment.validate(doc)

        mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
