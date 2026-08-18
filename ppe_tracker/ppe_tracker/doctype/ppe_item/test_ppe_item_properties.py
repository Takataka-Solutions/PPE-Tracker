# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the PPE Item DocType.

Feature: tts-ppe-tracker, Property 3: Lifespan Values Must Be Positive

**Validates: Requirements 1.5, 1.6**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis.strategies import integers, sampled_from, text

import frappe
from frappe.exceptions import ValidationError


def _make_ppe_item(default_lifespan, lifespan_table=None):
    """Create a mock PPE Item document with given lifespan values."""
    doc = MagicMock()
    doc.item_code = "TEST-PPE-001"
    doc.default_lifespan = default_lifespan
    doc.lifespan_table = lifespan_table or []
    return doc


def _make_lifespan_row(position_type, lifespan):
    """Create a mock PPE Item Lifespan child row."""
    row = MagicMock()
    row.position_type = position_type
    row.lifespan = lifespan
    row.idx = 1
    return row


class TestLifespanValuesMustBePositive(unittest.TestCase):
    """Property 3: Lifespan Values Must Be Positive

    For any integer value n where n <= 0, setting it as the default_lifespan on
    a PPE Item OR as the lifespan on a PPE Item Lifespan child row SHALL cause
    the system to raise a validation error and prevent saving.

    **Validates: Requirements 1.5, 1.6**
    """

    @given(invalid_lifespan=integers(max_value=0))
    @settings(max_examples=25)
    @patch("frappe.db.get_value", return_value="PPE")
    @patch("frappe.throw", side_effect=ValidationError)
    def test_default_lifespan_must_be_positive(self, mock_throw, mock_get_value, invalid_lifespan):
        """Any default_lifespan <= 0 must raise ValidationError.

        Feature: tts-ppe-tracker, Property 3: Lifespan Values Must Be Positive
        **Validates: Requirements 1.5, 1.6**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        doc = _make_ppe_item(default_lifespan=invalid_lifespan)
        # Bind the validate method from the controller to our mock doc
        with self.assertRaises(ValidationError):
            PPEItem._validate_lifespan_values(doc)

    @given(invalid_lifespan=integers(max_value=0))
    @settings(max_examples=25)
    @patch("frappe.db.get_value", return_value="PPE")
    @patch("frappe.throw", side_effect=ValidationError)
    def test_child_row_lifespan_must_be_positive(self, mock_throw, mock_get_value, invalid_lifespan):
        """Any child row lifespan <= 0 must raise ValidationError.

        Feature: tts-ppe-tracker, Property 3: Lifespan Values Must Be Positive
        **Validates: Requirements 1.5, 1.6**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Use a valid default_lifespan (>= 1) so only the child row triggers the error
        child_row = _make_lifespan_row(position_type="Heavy Duty", lifespan=invalid_lifespan)
        doc = _make_ppe_item(default_lifespan=12, lifespan_table=[child_row])

        with self.assertRaises(ValidationError):
            PPEItem._validate_lifespan_values(doc)


class TestPPEItemLinkedItemGroupValidation(unittest.TestCase):
    """Property 1: PPE Item Linked Item Group Validation

    For any ERPNext Item whose item_group is not "PPE", attempting to save a
    PPE Item record that links to it SHALL raise a validation error and prevent
    saving.

    Feature: tts-ppe-tracker, Property 1: PPE Item Linked Item Group Validation
    **Validates: Requirements 1.2**
    """

    @given(non_ppe_group=text(min_size=1).filter(lambda s: s.strip() != "PPE"))
    @settings(max_examples=25)
    @patch("frappe.throw", side_effect=ValidationError)
    @patch("frappe.db.get_value")
    def test_non_ppe_item_group_raises_validation_error(
        self, mock_get_value, mock_throw, non_ppe_group
    ):
        """Any linked Item with item_group != 'PPE' must raise ValidationError.

        Feature: tts-ppe-tracker, Property 1: PPE Item Linked Item Group Validation
        **Validates: Requirements 1.2**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Mock frappe.db.get_value to return the generated non-PPE item group
        mock_get_value.return_value = non_ppe_group

        # Create a mock PPE Item doc with an item_code
        doc = MagicMock()
        doc.item_code = "TEST-ITEM-001"

        with self.assertRaises(ValidationError):
            PPEItem._validate_item_group(doc)


class TestPositionTypeUniqueness(unittest.TestCase):
    """Property 2: PPE Item Lifespan Position Type Uniqueness

    For any PPE Item record, if its PPE Item Lifespan child table contains
    two or more rows with the same position_type value, saving the record
    SHALL raise a validation error.

    **Validates: Requirements 1.4**
    """

    @given(position_type=sampled_from(["Heavy Duty", "Standard"]))
    @settings(max_examples=25)
    @patch("frappe.throw", side_effect=ValidationError)
    def test_duplicate_position_type_raises_validation_error(self, mock_throw, position_type):
        """Two or more child rows with the same position_type must raise ValidationError.

        Feature: tts-ppe-tracker, Property 2: PPE Item Lifespan Position Type Uniqueness
        **Validates: Requirements 1.4**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Create 2 child rows with the SAME position_type
        row1 = _make_lifespan_row(position_type=position_type, lifespan=12)
        row1.idx = 1
        row2 = _make_lifespan_row(position_type=position_type, lifespan=6)
        row2.idx = 2
        doc = _make_ppe_item(default_lifespan=12, lifespan_table=[row1, row2])

        with self.assertRaises(ValidationError):
            PPEItem._validate_position_type_uniqueness(doc)

    @given(position_type=sampled_from(["Heavy Duty", "Standard"]))
    @settings(max_examples=25)
    @patch("frappe.throw", side_effect=ValidationError)
    def test_three_duplicate_rows_raises_validation_error(self, mock_throw, position_type):
        """Three child rows with the same position_type must raise ValidationError.

        Feature: tts-ppe-tracker, Property 2: PPE Item Lifespan Position Type Uniqueness
        **Validates: Requirements 1.4**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Create 3 child rows with the SAME position_type
        rows = []
        for i in range(3):
            row = _make_lifespan_row(position_type=position_type, lifespan=12 + i)
            row.idx = i + 1
            rows.append(row)
        doc = _make_ppe_item(default_lifespan=12, lifespan_table=rows)

        with self.assertRaises(ValidationError):
            PPEItem._validate_position_type_uniqueness(doc)


if __name__ == "__main__":
    unittest.main()


# --- Property 19: has_sizes Validation Enforces Template Constraint ---
# Feature: ppe-tracker-enhancements-v2


def _make_ppe_item_with_sizes(item_code, has_sizes):
    """Create a mock PPE Item document with has_sizes field."""
    doc = MagicMock()
    doc.item_code = item_code
    doc.has_sizes = has_sizes
    return doc


class TestHasSizesValidationEnforcesTemplateConstraint(unittest.TestCase):
    """Property 19: has_sizes Validation Enforces Template Constraint

    If `has_sizes = 1`, the linked item_code must reference an ERPNext Item with
    `has_variants = 1` (a template). If `has_sizes = 0`, no constraint is applied
    regardless of the linked Item's type.

    **Validates: Requirements 15.2, 15.3**
    """

    @given(item_code=sampled_from(["ITEM-001", "ITEM-002", "HELMET-TPL", "GLOVE-STD"]))
    @settings(max_examples=25)
    @patch("frappe.bold", side_effect=lambda x: x)
    @patch("frappe.throw", side_effect=ValidationError)
    @patch("frappe.db.get_value")
    def test_has_sizes_enabled_non_template_rejects(self, mock_get_value, mock_throw, mock_bold, item_code):
        """When has_sizes=1 and item is NOT a template (has_variants=0/None), validation must reject.

        Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint
        **Validates: Requirements 15.2, 15.3**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Mock: item does NOT have variants (not a template)
        mock_get_value.return_value = 0

        doc = _make_ppe_item_with_sizes(item_code=item_code, has_sizes=1)

        with self.assertRaises(ValidationError):
            PPEItem._validate_has_sizes(doc)

        # Verify frappe.throw was called
        mock_throw.assert_called()

    @given(item_code=sampled_from(["ITEM-001", "ITEM-002", "HELMET-TPL", "GLOVE-STD"]))
    @settings(max_examples=25)
    @patch("frappe.bold", side_effect=lambda x: x)
    @patch("frappe.throw", side_effect=ValidationError)
    @patch("frappe.db.get_value")
    def test_has_sizes_enabled_with_template_passes(self, mock_get_value, mock_throw, mock_bold, item_code):
        """When has_sizes=1 and item IS a template (has_variants=1), validation must pass (no throw).

        Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint
        **Validates: Requirements 15.2, 15.3**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Mock: item HAS variants (is a template)
        mock_get_value.return_value = 1

        doc = _make_ppe_item_with_sizes(item_code=item_code, has_sizes=1)

        # Should NOT raise — validation passes
        PPEItem._validate_has_sizes(doc)

        # frappe.throw should NOT have been called
        mock_throw.assert_not_called()

    @given(
        item_code=sampled_from(["ITEM-001", "ITEM-002", "HELMET-TPL", "GLOVE-STD"]),
        has_variants=sampled_from([0, 1, None])
    )
    @settings(max_examples=25)
    @patch("frappe.bold", side_effect=lambda x: x)
    @patch("frappe.throw", side_effect=ValidationError)
    @patch("frappe.db.get_value")
    def test_has_sizes_disabled_no_constraint(self, mock_get_value, mock_throw, mock_bold, item_code, has_variants):
        """When has_sizes=0, no constraint is applied regardless of item's template status.

        Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint
        **Validates: Requirements 15.2, 15.3**
        """
        from ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        # Mock: return whatever has_variants value — it should not matter
        mock_get_value.return_value = has_variants

        doc = _make_ppe_item_with_sizes(item_code=item_code, has_sizes=0)

        # Should NOT raise — has_sizes is disabled, so no constraint
        PPEItem._validate_has_sizes(doc)

        # frappe.throw should NOT have been called
        mock_throw.assert_not_called()
        # frappe.db.get_value should NOT have been called (early return)
        mock_get_value.assert_not_called()
