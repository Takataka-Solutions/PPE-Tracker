# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Employee PPE Size DocType validation.

Properties 20-24 from the PPE Tracker Enhancements v2 design document.

**Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    text,
    lists,
    integers,
    composite,
    sampled_from,
    booleans,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

VALID_SIZES = ["S", "M", "L", "XL", "XXL", "6", "7", "8", "9", "10", "11", "12"]
PPE_ITEM_NAMES = [f"PPE-ITEM-{i:03d}" for i in range(1, 21)]
ITEM_CODES = [f"ITEM-{i:03d}" for i in range(1, 21)]
EMPLOYEE_IDS = [f"HR-EMP-{i:05d}" for i in range(1, 51)]


@composite
def size_mismatch_data(draw):
    """Generate a PPE Size Item row where the size does NOT match any attribute value."""
    ppe_item = draw(sampled_from(PPE_ITEM_NAMES))
    item_code = draw(sampled_from(ITEM_CODES))
    # Valid attribute values for this item
    valid_values = draw(
        lists(sampled_from(VALID_SIZES), min_size=1, max_size=5, unique=True)
    )
    # Generate an invalid size that is NOT in valid_values
    invalid_size = draw(text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))
    assume(invalid_size not in valid_values)
    return {
        "ppe_item": ppe_item,
        "item_code": item_code,
        "valid_values": valid_values,
        "invalid_size": invalid_size,
    }


@composite
def size_match_data(draw):
    """Generate a PPE Size Item row where the size DOES match a valid attribute value."""
    ppe_item = draw(sampled_from(PPE_ITEM_NAMES))
    item_code = draw(sampled_from(ITEM_CODES))
    valid_values = draw(
        lists(sampled_from(VALID_SIZES), min_size=1, max_size=5, unique=True)
    )
    # Pick a valid size from the attribute values
    valid_size = draw(sampled_from(valid_values))
    variant_name = f"{item_code}-{valid_size}"
    return {
        "ppe_item": ppe_item,
        "item_code": item_code,
        "valid_values": valid_values,
        "valid_size": valid_size,
        "variant_name": variant_name,
        "attribute": "Size",
    }


@composite
def duplicate_ppe_items_table(draw):
    """Generate a child table with at least one duplicate PPE Item."""
    # Pick 2-5 unique items, then force a duplicate
    unique_items = draw(
        lists(sampled_from(PPE_ITEM_NAMES), min_size=2, max_size=5, unique=True)
    )
    # Duplicate the first item
    items_with_dup = list(unique_items) + [unique_items[0]]
    return items_with_dup


@composite
def unique_ppe_items_table(draw):
    """Generate a child table with all unique PPE Items."""
    items = draw(
        lists(sampled_from(PPE_ITEM_NAMES), min_size=1, max_size=8, unique=True)
    )
    return items


@composite
def role_assignment_data(draw):
    """Generate PPE Role Assignment data with a mix of sized and non-sized items."""
    num_items = draw(integers(min_value=1, max_value=8))
    items = []
    for i in range(num_items):
        ppe_item = f"PPE-ITEM-{i + 1:03d}"
        has_sizes = draw(booleans())
        items.append({"ppe_item": ppe_item, "has_sizes": has_sizes})
    return items
