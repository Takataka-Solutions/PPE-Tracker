# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Item controller validations.

Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint

**Validates: Requirements 15.2, 15.3**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    composite,
    sampled_from,
    text,
    integers,
)


@composite
def has_sizes_scenario(draw):
    """Generate a combination of has_sizes flag and has_variants value.

    Returns a tuple of (has_sizes, item_code, has_variants) where:
      - has_sizes: 0 or 1 (Check field on PPE Item)
      - item_code: a non-empty string representing the linked ERPNext Item
      - has_variants: 0, 1, or None (simulating the linked Item's has_variants field)
    """
    has_sizes = draw(sampled_from([0, 1]))
    item_code = draw(text(min_size=3, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"))
    has_variants = draw(sampled_from([0, 1, None]))

    return (has_sizes, item_code, has_variants)


class TestHasSizesValidationEnforcesTemplateConstraint(unittest.TestCase):
    """Property 19: has_sizes Validation Enforces Template Constraint

    For any PPE Item with has_sizes = 1, the system SHALL validate that the linked
    item_code references an ERPNext Item with has_variants = 1 (a template);
    for any PPE Item with has_sizes = 0, the system SHALL NOT enforce this constraint
    regardless of the linked Item's type.

    Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint
    **Validates: Requirements 15.2, 15.3**
    """

    @given(scenario=has_sizes_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_has_sizes_validation_enforces_template_constraint(self, scenario):
        """If has_sizes = 1, linked item must be a template (has_variants=1);
        if has_sizes = 0, no constraint is applied.

        Feature: ppe-tracker-enhancements-v2, Property 19: has_sizes Validation Enforces Template Constraint
        **Validates: Requirements 15.2, 15.3**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

        has_sizes, item_code, has_variants = scenario

        # Create a mock PPEItem instance
        mock_self = MagicMock(spec=PPEItem)
        mock_self.has_sizes = has_sizes
        mock_self.item_code = item_code

        with patch("ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item.frappe") as mock_frappe:
            # Mock frappe.db.get_value to return the generated has_variants value
            mock_frappe.db.get_value.return_value = has_variants

            # Mock frappe.throw to track if it's called
            mock_frappe.throw = MagicMock()

            # Mock frappe.bold to return a formatted string
            mock_frappe.bold.return_value = f"<b>{item_code}</b>"

            # Mock the translation function
            mock_frappe._ = lambda x: x

            # Call the actual method with our mock instance
            PPEItem._validate_has_sizes(mock_self)

            if has_sizes == 0:
                # ASSERTION: When has_sizes is 0, frappe.throw should NEVER be called
                # regardless of has_variants value (Requirement 15.3)
                mock_frappe.throw.assert_not_called()

                # Also: frappe.db.get_value should NOT be called since method returns early
                mock_frappe.db.get_value.assert_not_called()

            elif has_sizes == 1 and not has_variants:
                # ASSERTION: When has_sizes is 1 AND has_variants is falsy (0 or None),
                # frappe.throw MUST be called (Requirement 15.2)
                mock_frappe.throw.assert_called_once()

            elif has_sizes == 1 and has_variants:
                # ASSERTION: When has_sizes is 1 AND has_variants is truthy (1),
                # frappe.throw should NOT be called — item is a valid template
                mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
