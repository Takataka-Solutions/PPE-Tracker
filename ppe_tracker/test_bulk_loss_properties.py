# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Bulk PPE Loss API logic.

Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue
Property 7: Bulk Processing Continues On Individual Failure

**Validates: Requirements 4.5, 4.6, 4.8**
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import (
    composite,
    dates,
    integers,
    floats,
    sampled_from,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

reason_strategy = sampled_from([
    "Lost during fieldwork",
    "Theft from locker",
    "Misplaced on site",
    "Damaged beyond repair",
    "Transport batch loss",
])

employee_strategy = sampled_from(["EMP-001", "EMP-002", "EMP-003", "EMP-004", "EMP-005"])


@composite
def bulk_loss_batch(draw):
    """Generate a batch of items for process_bulk_losses.

    Returns (items, ppe_issue_details, loss_date, reason, ppe_item_to_item_code,
    item_code_to_valuation) where the last two maps allow realistic mock lookups
    (same ppe_item always yields same item_code and valuation_rate).
    """
    num_items = draw(integers(min_value=1, max_value=8))
    loss_date = draw(dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 28)))
    reason = draw(reason_strategy)

    # Pre-generate consistent mappings: ppe_item -> item_code -> valuation_rate
    # This mirrors reality: a given PPE Item always maps to the same ERPNext Item
    ppe_item_to_item_code = {}
    item_code_to_valuation = {}

    items = []
    ppe_issue_details = {}

    for i in range(num_items):
        ppe_issue_name = f"PPE-ISS-{i+1:04d}"
        employee = draw(employee_strategy)
        # Use unique ppe_item per issue to avoid ambiguity in mock lookups
        ppe_item = f"PPE-ITEM-{i+1:04d}"
        item_code = f"ITEM-CODE-{i+1:04d}"
        quantity = draw(integers(min_value=1, max_value=10))
        valuation_rate = draw(floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False))

        ppe_item_to_item_code[ppe_item] = item_code
        item_code_to_valuation[item_code] = valuation_rate

        items.append({
            "ppe_issue": ppe_issue_name,
            "loss_date": str(loss_date),
            "reason": reason,
        })

        ppe_issue_details[ppe_issue_name] = {
            "employee": employee,
            "employee_name": f"Employee {i+1}",
            "ppe_item": ppe_item,
            "quantity": quantity,
            "item_code": item_code,
            "valuation_rate": valuation_rate,
        }

    return (items, ppe_issue_details, str(loss_date), reason, ppe_item_to_item_code, item_code_to_valuation)


@composite
def bulk_loss_mixed_batch(draw):
    """Generate a batch with a mix of valid and invalid items for failure testing.

    Returns (items, valid_names, invalid_names, ppe_issue_details,
    ppe_item_to_item_code, item_code_to_valuation).
    """
    num_valid = draw(integers(min_value=1, max_value=5))
    num_invalid = draw(integers(min_value=1, max_value=4))

    loss_date = str(draw(dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 28))))
    reason = draw(reason_strategy)

    items = []
    valid_names = set()
    invalid_names = set()
    ppe_issue_details = {}
    ppe_item_to_item_code = {}
    item_code_to_valuation = {}

    # Add valid items
    for i in range(num_valid):
        name = f"PPE-ISS-VALID-{i+1:04d}"
        employee = draw(employee_strategy)
        ppe_item = f"PPE-ITEM-V-{i+1:04d}"
        item_code = f"ITEM-CODE-V-{i+1:04d}"
        quantity = draw(integers(min_value=1, max_value=10))
        valuation_rate = draw(floats(min_value=100.0, max_value=10000.0, allow_nan=False, allow_infinity=False))

        ppe_item_to_item_code[ppe_item] = item_code
        item_code_to_valuation[item_code] = valuation_rate

        items.append({
            "ppe_issue": name,
            "loss_date": loss_date,
            "reason": reason,
        })
        valid_names.add(name)
        ppe_issue_details[name] = {
            "employee": employee,
            "employee_name": f"Valid Employee {i+1}",
            "ppe_item": ppe_item,
            "quantity": quantity,
            "item_code": item_code,
            "valuation_rate": valuation_rate,
        }

    # Add invalid items (will raise exceptions when get_doc is called)
    for i in range(num_invalid):
        name = f"PPE-ISS-INVALID-{i+1:04d}"
        items.append({
            "ppe_issue": name,
            "loss_date": loss_date,
            "reason": reason,
        })
        invalid_names.add(name)

    return (items, valid_names, invalid_names, ppe_issue_details, ppe_item_to_item_code, item_code_to_valuation)


# ---------------------------------------------------------------------------
# Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue
# ---------------------------------------------------------------------------


class TestBulkLossCreatesOnePerIssue(unittest.TestCase):
    """Property 6: Bulk Loss Creates One PPE Loss Per Selected Issue

    For any batch of selected Active PPE Issues with a specified loss date
    and reason, the bulk loss process SHALL create exactly one PPE Loss record
    per issue with the specified date, reason, surcharge auto-populated from
    the Item's valuation rate, and acknowledgement_status set to "Pending".

    **Validates: Requirements 4.5, 4.8**
    """

    @given(dataset=bulk_loss_batch())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_one_loss_per_selected_issue(self, dataset):
        """process_bulk_losses() creates exactly one PPE Loss per selected issue
        with correct loss_date, reason, surcharge, and acknowledgement_status.

        **Validates: Requirements 4.5, 4.8**
        """
        items, ppe_issue_details, loss_date, reason, ppe_item_to_item_code, item_code_to_valuation = dataset

        created_losses = []

        def mock_get_doc(doctype, name):
            if name not in ppe_issue_details:
                raise Exception(f"PPE Issue {name} not found")
            details = ppe_issue_details[name]
            doc = MagicMock()
            doc.employee = details["employee"]
            doc.employee_name = details["employee_name"]
            doc.ppe_item = details["ppe_item"]
            doc.quantity = details["quantity"]
            return doc

        def mock_get_value(doctype, filters_or_name, fieldname=None):
            """Mock frappe.db.get_value for item_code and valuation_rate lookups."""
            if doctype == "PPE Item":
                # Lookup item_code from PPE Item name
                return ppe_item_to_item_code.get(filters_or_name)
            elif doctype == "Item":
                # Lookup valuation_rate from ERPNext Item
                return item_code_to_valuation.get(filters_or_name)
            elif doctype == "Bin":
                # Fallback valuation_rate from Bin
                return None
            return None

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.name = f"PPE-LOSS-{len(created_losses)+1:04d}"
            created_losses.append(doc)
            return doc

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe.get_doc.side_effect = mock_get_doc
            mock_frappe.new_doc.side_effect = mock_new_doc
            mock_frappe.db = MagicMock()
            mock_frappe.db.get_value.side_effect = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            from ppe_tracker.ppe_tracker.api.bulk_loss import process_bulk_losses
            result = process_bulk_losses(items)

        # ASSERTION 1: Exactly one PPE Loss created per item
        self.assertEqual(len(created_losses), len(items))
        self.assertEqual(len(result["successes"]), len(items))
        self.assertEqual(len(result["failures"]), 0)

        # ASSERTION 2: Each loss has the correct loss_date and reason
        for loss_doc in created_losses:
            self.assertEqual(loss_doc.loss_date, loss_date)
            self.assertEqual(loss_doc.reason, reason)

        # ASSERTION 3: Surcharge = valuation_rate * quantity for each
        for i, loss_doc in enumerate(created_losses):
            ppe_issue_name = items[i]["ppe_issue"]
            details = ppe_issue_details[ppe_issue_name]
            expected_surcharge = details["valuation_rate"] * details["quantity"]
            self.assertAlmostEqual(
                loss_doc.surcharge_amount,
                expected_surcharge,
                places=2,
                msg=f"Surcharge mismatch for {ppe_issue_name}",
            )

        # ASSERTION 4: acknowledgement_status set to "Pending" for each
        for loss_doc in created_losses:
            self.assertEqual(loss_doc.acknowledgement_status, "Pending")

        # ASSERTION 5: insert called for each loss doc
        for loss_doc in created_losses:
            loss_doc.insert.assert_called_once_with(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Property 7: Bulk Processing Continues On Individual Failure
# ---------------------------------------------------------------------------


class TestBulkLossProcessingContinuesOnFailure(unittest.TestCase):
    """Property 7: Bulk Processing Continues On Individual Failure

    For any batch containing a mix of valid and invalid items, the bulk
    processing function SHALL continue processing remaining items after
    an individual failure, and SHALL return an accurate summary with all
    successes and all failures listed.

    **Validates: Requirements 4.6**
    """

    @given(dataset=bulk_loss_mixed_batch())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_continues_after_failure_accurate_summary(self, dataset):
        """process_bulk_losses() continues processing after individual failures
        and returns accurate successes and failures lists.

        **Validates: Requirements 4.6**
        """
        items, valid_names, invalid_names, ppe_issue_details, ppe_item_to_item_code, item_code_to_valuation = dataset

        created_losses = []

        def mock_get_doc(doctype, name):
            if name in invalid_names:
                raise Exception(f"PPE Issue {name} not found or already processed")
            if name not in ppe_issue_details:
                raise Exception(f"PPE Issue {name} not found")
            details = ppe_issue_details[name]
            doc = MagicMock()
            doc.employee = details["employee"]
            doc.employee_name = details["employee_name"]
            doc.ppe_item = details["ppe_item"]
            doc.quantity = details["quantity"]
            return doc

        def mock_get_value(doctype, filters_or_name, fieldname=None):
            if doctype == "PPE Item":
                return ppe_item_to_item_code.get(filters_or_name)
            elif doctype == "Item":
                return item_code_to_valuation.get(filters_or_name)
            elif doctype == "Bin":
                return None
            return None

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.name = f"PPE-LOSS-{len(created_losses)+1:04d}"
            created_losses.append(doc)
            return doc

        with patch("ppe_tracker.ppe_tracker.api.bulk_loss.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe.get_doc.side_effect = mock_get_doc
            mock_frappe.new_doc.side_effect = mock_new_doc
            mock_frappe.db = MagicMock()
            mock_frappe.db.get_value.side_effect = mock_get_value
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            from ppe_tracker.ppe_tracker.api.bulk_loss import process_bulk_losses
            result = process_bulk_losses(items)

        # ASSERTION 1: Total processed equals total items
        self.assertEqual(
            len(result["successes"]) + len(result["failures"]),
            len(items),
            "All items must be accounted for in successes + failures",
        )

        # ASSERTION 2: Correct number of successes and failures
        self.assertEqual(len(result["successes"]), len(valid_names))
        self.assertEqual(len(result["failures"]), len(invalid_names))

        # ASSERTION 3: Success entries reference the valid PPE issues
        success_issues = {s["ppe_issue"] for s in result["successes"]}
        self.assertEqual(success_issues, valid_names)

        # ASSERTION 4: Failure entries reference the invalid PPE issues
        failure_issues = {f["ppe_issue"] for f in result["failures"]}
        self.assertEqual(failure_issues, invalid_names)

        # ASSERTION 5: Each failure has an error message
        for failure in result["failures"]:
            self.assertIn("error", failure)
            self.assertIsNotNone(failure["error"])
            self.assertTrue(len(str(failure["error"])) > 0)

        # ASSERTION 6: Each success has ppe_loss and surcharge_amount keys
        for success in result["successes"]:
            self.assertIn("ppe_loss", success)
            self.assertIn("surcharge_amount", success)


if __name__ == "__main__":
    unittest.main()
