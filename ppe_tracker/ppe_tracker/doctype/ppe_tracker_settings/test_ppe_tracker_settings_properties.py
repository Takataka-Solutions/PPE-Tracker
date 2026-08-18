# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Tracker Settings validation.

Feature: ppe-tracker-enhancements-v2
Property 1: Warehouse Uniqueness Validation
Property 2: Warehouse Existence Validation

**Validates: Requirements 1.2, 1.7**
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis.strategies import text, composite, booleans, sampled_from


# --- Strategies ---


@composite
def warehouse_triple(draw):
    """Generate a triple of warehouse names (some may be duplicates).

    Returns a tuple of (returned_wh, default_wh, wornout_wh).
    Names are non-empty alphanumeric strings simulating warehouse link values.
    """
    # Use a small pool of warehouse names to increase collision probability
    pool = [f"Warehouse-{i}" for i in range(1, 8)]
    returned = draw(sampled_from(pool))
    default = draw(sampled_from(pool))
    wornout = draw(sampled_from(pool))
    return (returned, default, wornout)


@composite
def distinct_warehouse_triple(draw):
    """Generate a triple of warehouse names guaranteed to be all distinct."""
    pool = [f"Warehouse-{i}" for i in range(1, 20)]
    returned = draw(sampled_from(pool))
    default = draw(sampled_from(pool))
    assume(default != returned)
    wornout = draw(sampled_from(pool))
    assume(wornout != returned and wornout != default)
    return (returned, default, wornout)


@composite
def warehouse_existence_scenario(draw):
    """Generate a scenario for warehouse existence/disabled validation.

    Returns a dict with:
      - warehouse_name: the warehouse reference value
      - exists: whether the warehouse exists in the DB
      - disabled: whether the warehouse is disabled (only relevant if exists=True)
    """
    name = draw(sampled_from([f"WH-{i}" for i in range(1, 10)]))
    exists = draw(booleans())
    disabled = draw(booleans()) if exists else False
    return {"warehouse_name": name, "exists": exists, "disabled": disabled}


# --- Test Classes ---


class TestWarehouseUniquenessValidation(unittest.TestCase):
    """Property 1: Warehouse Uniqueness Validation

    For any triple of warehouse references (returned, default, wornout),
    the system SHALL reject the configuration if any two warehouses are the same,
    and accept it only when all three are distinct.

    Feature: ppe-tracker-enhancements-v2, Property 1: Warehouse Uniqueness Validation
    **Validates: Requirements 1.2**
    """

    @given(triple=warehouse_triple())
    @settings(max_examples=25, deadline=None)
    def test_duplicate_warehouses_are_rejected(self, triple):
        """When any two (or all three) warehouse references in the triple are
        the same, _validate_warehouses_are_different() SHALL call frappe.throw.

        Feature: ppe-tracker-enhancements-v2, Property 1: Warehouse Uniqueness Validation
        **Validates: Requirements 1.2**
        """
        returned_wh, default_wh, wornout_wh = triple

        # Only test cases where at least two are the same
        assume(len(set(triple)) < 3)

        from ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings import (
            PPETrackerSettings,
        )

        # Create a mock settings doc
        doc = MagicMock(spec=PPETrackerSettings)
        doc.returned_ppe_warehouse = returned_wh
        doc.default_issue_warehouse = default_wh
        doc.wornout_ppe_warehouse = wornout_wh
        doc.get = lambda field: getattr(doc, field)

        threw = False

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x

            try:
                PPETrackerSettings._validate_warehouses_are_different(doc)
            except Exception:
                threw = True

        self.assertTrue(
            threw,
            f"Expected validation error for duplicate warehouses: "
            f"returned={returned_wh}, default={default_wh}, wornout={wornout_wh}",
        )

    @given(triple=distinct_warehouse_triple())
    @settings(max_examples=25, deadline=None)
    def test_distinct_warehouses_are_accepted(self, triple):
        """When all three warehouse references are distinct,
        _validate_warehouses_are_different() SHALL NOT call frappe.throw.

        Feature: ppe-tracker-enhancements-v2, Property 1: Warehouse Uniqueness Validation
        **Validates: Requirements 1.2**
        """
        returned_wh, default_wh, wornout_wh = triple

        from ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings import (
            PPETrackerSettings,
        )

        # Create a mock settings doc
        doc = MagicMock(spec=PPETrackerSettings)
        doc.returned_ppe_warehouse = returned_wh
        doc.default_issue_warehouse = default_wh
        doc.wornout_ppe_warehouse = wornout_wh
        doc.get = lambda field: getattr(doc, field)

        threw = False

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x

            try:
                PPETrackerSettings._validate_warehouses_are_different(doc)
            except Exception:
                threw = True

        self.assertFalse(
            threw,
            f"Should NOT reject distinct warehouses: "
            f"returned={returned_wh}, default={default_wh}, wornout={wornout_wh}",
        )


class TestWarehouseExistenceValidation(unittest.TestCase):
    """Property 2: Warehouse Existence Validation

    For any warehouse reference set in PPE Tracker Settings, the system SHALL reject
    the configuration if the referenced warehouse does not exist or is disabled,
    and accept it when all referenced warehouses are existing and active.

    Feature: ppe-tracker-enhancements-v2, Property 2: Warehouse Existence Validation
    **Validates: Requirements 1.7**
    """

    @given(scenario=warehouse_existence_scenario())
    @settings(max_examples=25, deadline=None)
    def test_nonexistent_warehouse_is_rejected(self, scenario):
        """When a warehouse reference points to a non-existent warehouse,
        _validate_warehouses_exist_and_active() SHALL call frappe.throw.

        Feature: ppe-tracker-enhancements-v2, Property 2: Warehouse Existence Validation
        **Validates: Requirements 1.7**
        """
        # Only test cases where warehouse does NOT exist
        assume(not scenario["exists"])

        wh_name = scenario["warehouse_name"]

        from ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings import (
            PPETrackerSettings,
        )

        # Create a mock settings doc with the warehouse set in one field
        doc = MagicMock(spec=PPETrackerSettings)
        doc.returned_ppe_warehouse = wh_name
        doc.default_issue_warehouse = ""
        doc.wornout_ppe_warehouse = ""
        doc.get = lambda field: getattr(doc, field)

        threw = False

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            # Warehouse does not exist — get_value returns None
            mock_frappe.db.get_value.return_value = None

            try:
                PPETrackerSettings._validate_warehouses_exist_and_active(doc)
            except Exception:
                threw = True

        self.assertTrue(
            threw,
            f"Expected validation error for non-existent warehouse: {wh_name}",
        )

    @given(scenario=warehouse_existence_scenario())
    @settings(max_examples=25, deadline=None)
    def test_disabled_warehouse_is_rejected(self, scenario):
        """When a warehouse reference points to a disabled warehouse,
        _validate_warehouses_exist_and_active() SHALL call frappe.throw.

        Feature: ppe-tracker-enhancements-v2, Property 2: Warehouse Existence Validation
        **Validates: Requirements 1.7**
        """
        # Only test cases where warehouse exists but is disabled
        assume(scenario["exists"] and scenario["disabled"])

        wh_name = scenario["warehouse_name"]

        from ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings import (
            PPETrackerSettings,
        )

        doc = MagicMock(spec=PPETrackerSettings)
        doc.returned_ppe_warehouse = wh_name
        doc.default_issue_warehouse = ""
        doc.wornout_ppe_warehouse = ""
        doc.get = lambda field: getattr(doc, field)

        threw = False

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            # Warehouse exists but is disabled
            mock_frappe.db.get_value.return_value = SimpleNamespace(name=wh_name, disabled=1)

            try:
                PPETrackerSettings._validate_warehouses_exist_and_active(doc)
            except Exception:
                threw = True

        self.assertTrue(
            threw,
            f"Expected validation error for disabled warehouse: {wh_name}",
        )

    @given(scenario=warehouse_existence_scenario())
    @settings(max_examples=25, deadline=None)
    def test_existing_active_warehouse_is_accepted(self, scenario):
        """When a warehouse reference points to an existing, active (not disabled)
        warehouse, _validate_warehouses_exist_and_active() SHALL NOT call frappe.throw.

        Feature: ppe-tracker-enhancements-v2, Property 2: Warehouse Existence Validation
        **Validates: Requirements 1.7**
        """
        # Only test cases where warehouse exists and is NOT disabled
        assume(scenario["exists"] and not scenario["disabled"])

        wh_name = scenario["warehouse_name"]

        from ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings import (
            PPETrackerSettings,
        )

        doc = MagicMock(spec=PPETrackerSettings)
        doc.returned_ppe_warehouse = wh_name
        doc.default_issue_warehouse = ""
        doc.wornout_ppe_warehouse = ""
        doc.get = lambda field: getattr(doc, field)

        threw = False

        with patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("ValidationError"))
            mock_frappe._ = lambda x: x
            # Warehouse exists and is active (disabled=0)
            mock_frappe.db.get_value.return_value = SimpleNamespace(name=wh_name, disabled=0)

            try:
                PPETrackerSettings._validate_warehouses_exist_and_active(doc)
            except Exception:
                threw = True

        self.assertFalse(
            threw,
            f"Should NOT reject existing active warehouse: {wh_name}",
        )


if __name__ == "__main__":
    unittest.main()
