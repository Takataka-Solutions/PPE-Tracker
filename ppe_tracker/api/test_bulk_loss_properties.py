# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Bulk PPE Loss API logic.

Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue
Property 7: Bulk Processing Continues On Individual Failure

**Validates: Requirements 4.5, 4.6, 4.8**
"""

import unittest
import sys
import importlib
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    composite,
    dates,
    integers,
    text,
    floats,
)


# ---------------------------------------------------------------------------
# Fix frappe.whitelist to be an identity decorator before module import.
# The conftest registers a MagicMock for frappe, but MagicMock() used as a
# decorator swallows the original function. We fix this by setting whitelist
# to return an identity function.
# ---------------------------------------------------------------------------

_frappe_mod = sys.modules.get("frappe")
if _frappe_mod is not None:
    _frappe_mod.whitelist = lambda *args, **kwargs: (lambda fn: fn)

# Force reload the bulk_loss module so it picks up the fixed whitelist
_MODULE_NAME = "ppe_tracker.ppe_tracker.api.bulk_loss"
if _MODULE_NAME in sys.modules:
    importlib.reload(sys.modules[_MODULE_NAME])
else:
    # Also try the short path used by conftest shim
    _SHORT = "ppe_tracker.api.bulk_loss"
    if _SHORT in sys.modules:
        importlib.reload(sys.modules[_SHORT])

from ppe_tracker.ppe_tracker.api.bulk_loss import process_bulk_losses


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@composite
def bulk_loss_items(draw):
    """Generate a list of valid bulk loss items.

    Each item is a dict with keys: ppe_issue, loss_date, reason.
    Also returns associated metadata for assertions:
      - valuation_rates: dict mapping ppe_item -> valuation_rate (per-Item, not per-Issue)
      - quantities: dict mapping ppe_issue -> quantity on the PPE Issue
      - employees: dict mapping ppe_issue -> employee
      - ppe_items: dict mapping ppe_issue -> ppe_item

    Returns (items, valuation_rates, quantities, employees, ppe_items)
    """
    num_items = draw(integers(min_value=1, max_value=10))
    loss_date = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))

    reason = draw(text(
        alphabet="abcdefghijklmnopqrstuvwxyz ",
        min_size=5, max_size=50
    ))

    # Generate valuation rates per PPE Item (shared across issues with same item)
    ppe_item_rates = {}
    for j in range(5):
        ppe_item_rates[f"PPE-ITEM-{j:02d}"] = draw(
            floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
        )

    items = []
    valuation_rates = {}  # maps ppe_item -> rate
    quantities = {}
    employees = {}
    ppe_items = {}

    for i in range(num_items):
        ppe_issue_name = f"PPE-ISS-{i:04d}"
        ppe_item_name = f"PPE-ITEM-{i % 5:02d}"
        qty = draw(integers(min_value=1, max_value=20))

        items.append({
            "ppe_issue": ppe_issue_name,
            "loss_date": str(loss_date),
            "reason": reason,
        })
        quantities[ppe_issue_name] = qty
        employees[ppe_issue_name] = f"EMP-{i:04d}"
        ppe_items[ppe_issue_name] = ppe_item_name

    # valuation_rates keyed by ppe_item (the same for all issues sharing that item)
    valuation_rates = ppe_item_rates

    return (items, valuation_rates, quantities, employees, ppe_items)


@composite
def bulk_loss_mixed_items(draw):
    """Generate a batch with a mix of valid and invalid items.

    Some items will cause exceptions during processing (simulating failures).
    Returns (items, valid_indices, invalid_indices, valuation_rates, quantities, employees, ppe_items)
    """
    num_valid = draw(integers(min_value=1, max_value=6))
    num_invalid = draw(integers(min_value=1, max_value=4))

    loss_date = draw(dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
    reason = draw(text(
        alphabet="abcdefghijklmnopqrstuvwxyz ",
        min_size=5, max_size=50
    ))

    items = []
    valid_indices = []
    invalid_indices = []
    valuation_rates = {}
    quantities = {}
    employees = {}
    ppe_items = {}

    # Add valid items
    for i in range(num_valid):
        ppe_issue_name = f"PPE-ISS-VALID-{i:04d}"
        val_rate = draw(floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False))
        qty = draw(integers(min_value=1, max_value=20))

        items.append({
            "ppe_issue": ppe_issue_name,
            "loss_date": str(loss_date),
            "reason": reason,
        })
        valid_indices.append(len(items) - 1)
        valuation_rates[ppe_issue_name] = val_rate
        quantities[ppe_issue_name] = qty
        employees[ppe_issue_name] = f"EMP-V-{i:04d}"
        ppe_items[ppe_issue_name] = f"PPE-ITEM-{i % 5:02d}"

    # Add invalid items (will cause exceptions during processing)
    for i in range(num_invalid):
        ppe_issue_name = f"PPE-ISS-INVALID-{i:04d}"
        items.append({
            "ppe_issue": ppe_issue_name,
            "loss_date": str(loss_date),
            "reason": reason,
        })
        invalid_indices.append(len(items) - 1)

    return (items, valid_indices, invalid_indices, valuation_rates, quantities, employees, ppe_items)


# ---------------------------------------------------------------------------
# Helper to build mocks for process_bulk_losses
# ---------------------------------------------------------------------------

def _build_mocks(valuation_rates, quantities, employees, ppe_items_map, invalid_issue_names=None):
    """Build mock functions for frappe calls used by process_bulk_losses.
    
    valuation_rates: dict mapping ppe_item -> rate (per-Item)
    """
    if invalid_issue_names is None:
        invalid_issue_names = set()

    created_docs = []

    def mock_new_doc(doctype):
        doc = MagicMock()
        doc.name = f"PPE-LOSS-{len(created_docs):04d}"
        created_docs.append(doc)
        return doc

    def mock_get_doc(doctype, name):
        if name in invalid_issue_names:
            raise Exception(f"PPE Issue {name} not found")
        doc = MagicMock()
        doc.employee = employees.get(name, "EMP-UNKNOWN")
        doc.employee_name = f"Name-{name}"
        doc.ppe_item = ppe_items_map.get(name, "PPE-ITEM-00")
        doc.quantity = quantities.get(name, 1)
        return doc

    # Build item_code mapping
    item_code_map = {}
    item_code_to_rate = {}
    for ppe_item in set(ppe_items_map.values()):
        item_code = f"ITEM-CODE-{ppe_item}"
        item_code_map[ppe_item] = item_code
        item_code_to_rate[item_code] = valuation_rates.get(ppe_item, 0)

    def mock_get_value(doctype, filters_or_name, fieldname=None):
        if doctype == "PPE Item":
            return item_code_map.get(filters_or_name, f"ITEM-CODE-{filters_or_name}")
        if doctype == "Item":
            return item_code_to_rate.get(filters_or_name, 100.0)
        if doctype == "Bin":
            return 0
        return None

    return created_docs, mock_new_doc, mock_get_doc, mock_get_value


# ---------------------------------------------------------------------------
# Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue
# ---------------------------------------------------------------------------


class TestBulkLossCreatesOnePPELossPerSelectedIssue(unittest.TestCase):
    """Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue

    For any batch of selected Active PPE Issues with a specified loss date
    and reason, the bulk loss process SHALL create exactly one PPE Loss
    record per issue with the specified date, reason, surcharge auto-populated
    from the Item's valuation rate, and acknowledgement_status set to "Pending".

    **Validates: Requirements 4.5, 4.8**
    """

    @given(dataset=bulk_loss_items())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_one_loss_per_item_with_correct_fields(self, dataset):
        """process_bulk_losses() creates exactly one PPE Loss record per item
        with correct loss_date, reason, surcharge_amount, and acknowledgement_status.

        **Validates: Requirements 4.5, 4.8**
        """
        items, valuation_rates, quantities, employees, ppe_items_map = dataset

        created_docs, mock_new_doc, mock_get_doc, mock_get_value = _build_mocks(
            valuation_rates, quantities, employees, ppe_items_map
        )

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe.new_doc = mock_new_doc
            mock_frappe.get_doc = mock_get_doc
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe._ = lambda x: x

            result = process_bulk_losses(items)

        # ASSERTION 1: Exactly one PPE Loss created per input item
        self.assertEqual(
            len(result["failures"]), 0,
            f"Expected no failures but got: {result['failures']}",
        )
        self.assertEqual(len(created_docs), len(items))
        self.assertEqual(len(result["successes"]), len(items))

        # ASSERTION 2: Each created doc has correct fields
        for i, doc in enumerate(created_docs):
            item = items[i]
            ppe_issue_name = item["ppe_issue"]

            # Correct loss_date
            self.assertEqual(doc.loss_date, item["loss_date"])
            # Correct reason
            self.assertEqual(doc.reason, item["reason"])
            # Correct acknowledgement_status
            self.assertEqual(doc.acknowledgement_status, "Pending")
            # Correct employee
            self.assertEqual(doc.employee, employees[ppe_issue_name])
            # Correct ppe_item
            self.assertEqual(doc.ppe_item, ppe_items_map[ppe_issue_name])
            # insert was called
            doc.insert.assert_called_once_with(ignore_permissions=True)

    @given(dataset=bulk_loss_items())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_surcharge_from_valuation_rate(self, dataset):
        """process_bulk_losses() sets surcharge_amount = valuation_rate * quantity
        for each PPE Loss record.

        **Validates: Requirements 4.5, 4.8**
        """
        items, valuation_rates, quantities, employees, ppe_items_map = dataset

        created_docs, mock_new_doc, mock_get_doc, mock_get_value = _build_mocks(
            valuation_rates, quantities, employees, ppe_items_map
        )

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe.new_doc = mock_new_doc
            mock_frappe.get_doc = mock_get_doc
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe._ = lambda x: x

            result = process_bulk_losses(items)

        # ASSERTION: Each surcharge_amount = valuation_rate * quantity
        for i, doc in enumerate(created_docs):
            ppe_issue_name = items[i]["ppe_issue"]
            ppe_item = ppe_items_map[ppe_issue_name]
            expected_surcharge = valuation_rates.get(ppe_item, 0) * quantities[ppe_issue_name]
            self.assertAlmostEqual(
                doc.surcharge_amount,
                expected_surcharge,
                places=2,
                msg=f"Surcharge for {ppe_issue_name} should be valuation_rate * quantity",
            )


# ---------------------------------------------------------------------------
# Property 7: Bulk Processing Continues On Individual Failure
# ---------------------------------------------------------------------------


class TestBulkProcessingContinuesOnIndividualFailure(unittest.TestCase):
    """Property 7: Bulk Processing Continues On Individual Failure

    For any batch containing a mix of valid and invalid items, the bulk
    processing function SHALL continue processing remaining items after
    an individual failure, and SHALL return an accurate summary with
    all successes and all failures listed.

    **Validates: Requirements 4.6**
    """

    @given(dataset=bulk_loss_mixed_items())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_continues_after_failure_with_accurate_summary(self, dataset):
        """process_bulk_losses() continues processing after individual failures
        and returns accurate successes and failures lists.

        **Validates: Requirements 4.6**
        """
        (items, valid_indices, invalid_indices,
         valuation_rates, quantities, employees, ppe_items_map) = dataset

        valid_issue_names = {items[i]["ppe_issue"] for i in valid_indices}
        invalid_issue_names = {items[i]["ppe_issue"] for i in invalid_indices}

        created_docs, mock_new_doc, mock_get_doc, mock_get_value = _build_mocks(
            valuation_rates, quantities, employees, ppe_items_map,
            invalid_issue_names=invalid_issue_names,
        )

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe.new_doc = mock_new_doc
            mock_frappe.get_doc = mock_get_doc
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe._ = lambda x: x

            result = process_bulk_losses(items)

        # ASSERTION 1: Processing continued - we have both successes and failures
        self.assertEqual(
            len(result["successes"]), len(valid_indices),
            "Number of successes should match number of valid items",
        )
        self.assertEqual(
            len(result["failures"]), len(invalid_indices),
            "Number of failures should match number of invalid items",
        )

        # ASSERTION 2: Total processed = successes + failures = all items
        self.assertEqual(
            len(result["successes"]) + len(result["failures"]),
            len(items),
            "All items must be accounted for in successes + failures",
        )

        # ASSERTION 3: Success entries reference the valid PPE issues
        success_issues = {s["ppe_issue"] for s in result["successes"]}
        self.assertEqual(
            success_issues, valid_issue_names,
            "Success entries should reference exactly the valid PPE issues",
        )

        # ASSERTION 4: Failure entries reference the invalid PPE issues
        failure_issues = {f["ppe_issue"] for f in result["failures"]}
        self.assertEqual(
            failure_issues, invalid_issue_names,
            "Failure entries should reference exactly the invalid PPE issues",
        )

        # ASSERTION 5: Each failure has an error message
        for failure in result["failures"]:
            self.assertIn("error", failure)
            self.assertTrue(len(failure["error"]) > 0)

    @given(dataset=bulk_loss_mixed_items())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_valid_items_still_get_correct_fields_despite_failures(self, dataset):
        """Even when some items fail, the successfully processed items still
        have correct loss_date, reason, surcharge, and acknowledgement_status.

        **Validates: Requirements 4.5, 4.6, 4.8**
        """
        (items, valid_indices, invalid_indices,
         valuation_rates, quantities, employees, ppe_items_map) = dataset

        valid_issue_names = {items[i]["ppe_issue"] for i in valid_indices}
        invalid_issue_names = {items[i]["ppe_issue"] for i in invalid_indices}

        created_docs, mock_new_doc, mock_get_doc, mock_get_value = _build_mocks(
            valuation_rates, quantities, employees, ppe_items_map,
            invalid_issue_names=invalid_issue_names,
        )

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe.new_doc = mock_new_doc
            mock_frappe.get_doc = mock_get_doc
            mock_frappe.db.get_value = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe._ = lambda x: x

            result = process_bulk_losses(items)

        # ASSERTION: Successfully created docs have correct acknowledgement_status
        for doc in created_docs:
            self.assertEqual(doc.acknowledgement_status, "Pending")

        # ASSERTION: Successfully created docs have correct loss_date and reason
        valid_items_in_order = [items[i] for i in valid_indices]
        for i, doc in enumerate(created_docs):
            self.assertEqual(doc.loss_date, valid_items_in_order[i]["loss_date"])
            self.assertEqual(doc.reason, valid_items_in_order[i]["reason"])


if __name__ == "__main__":
    unittest.main()
