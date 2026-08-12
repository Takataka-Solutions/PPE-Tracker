# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Bulk PPE Return API logic.

Feature: ppe-tracker-enhancements-v2

Properties tested:
- Property 3: Eligible Issue Queries Return Only Active Issues
- Property 4: Bulk Tool Filter Logic
- Property 5: Bulk Return Creates One PPE Return Per Selected Issue
- Property 7: Bulk Processing Continues On Individual Failure

**Validates: Requirements 3.2, 3.3, 3.5, 3.6, 3.7**
"""

import unittest
from unittest.mock import patch, MagicMock, call
from datetime import date, timedelta

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    text,
    dates,
    integers,
    lists,
    composite,
    sampled_from,
    booleans,
    just,
    one_of,
    none,
    dictionaries,
    fixed_dictionaries,
)


# --- Strategies ---

@composite
def ppe_issue_record(draw, status=None):
    """Generate a PPE Issue record dict with realistic fields."""
    if status is None:
        status = draw(sampled_from(["Active", "Returned", "Expired", "Replaced"]))
    name = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):04d}"
    employee = f"HR-EMP-{draw(integers(min_value=1, max_value=500)):04d}"
    department = draw(sampled_from(["Operations", "Finance", "HR", "Engineering", "Safety"]))
    ppe_item = draw(sampled_from(["Safety Helmet", "Safety Boots", "Gloves", "Goggles", "Hi-Vis Vest"]))
    issue_date = draw(dates(min_value=date(2022, 1, 1), max_value=date(2025, 12, 31)))
    quantity = draw(integers(min_value=1, max_value=10))

    return {
        "name": name,
        "employee": employee,
        "employee_name": f"Employee {employee}",
        "department": department,
        "ppe_item": ppe_item,
        "issue_date": issue_date,
        "expiry_date": issue_date + timedelta(days=365),
        "quantity": quantity,
        "status": status,
        "docstatus": 1,
    }


@composite
def mixed_status_dataset(draw):
    """Generate a dataset of PPE Issues with a mix of statuses."""
    num_records = draw(integers(min_value=1, max_value=25))
    records = []
    for i in range(num_records):
        record = draw(ppe_issue_record())
        # Ensure unique names
        record["name"] = f"PPE-ISS-{i:04d}"
        records.append(record)
    return records


@composite
def filter_combination(draw):
    """Generate a random filter combination (some or all filters may be set)."""
    filters = {}
    if draw(booleans()):
        filters["employee"] = f"HR-EMP-{draw(integers(min_value=1, max_value=500)):04d}"
    if draw(booleans()):
        filters["department"] = draw(sampled_from(["Operations", "Finance", "HR", "Engineering", "Safety"]))
    if draw(booleans()):
        filters["ppe_item"] = draw(sampled_from(["Safety Helmet", "Safety Boots", "Gloves", "Goggles", "Hi-Vis Vest"]))
    return filters


@composite
def bulk_return_item(draw):
    """Generate a single item for bulk return processing."""
    ppe_issue = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):04d}"
    condition = draw(sampled_from(["Good", "Damaged", "Unusable"]))
    return_date = str(draw(dates(min_value=date(2024, 1, 1), max_value=date(2025, 12, 31))))
    quantity_returned = draw(one_of(just(None), integers(min_value=1, max_value=5)))

    return {
        "ppe_issue": ppe_issue,
        "condition": condition,
        "return_date": return_date,
        "quantity_returned": quantity_returned,
    }


@composite
def bulk_return_batch(draw):
    """Generate a batch of items for bulk return processing (1–15 items)."""
    num_items = draw(integers(min_value=1, max_value=15))
    items = []
    for i in range(num_items):
        item = draw(bulk_return_item())
        # Ensure unique PPE Issue names
        item["ppe_issue"] = f"PPE-ISS-{i:04d}"
        items.append(item)
    return items


@composite
def bulk_return_batch_with_failures(draw):
    """Generate a batch where some items will succeed and some will fail.

    Returns (items, failure_indices) tuple.
    """
    num_items = draw(integers(min_value=2, max_value=15))
    items = []
    failure_indices = set()

    for i in range(num_items):
        item = draw(bulk_return_item())
        item["ppe_issue"] = f"PPE-ISS-{i:04d}"
        items.append(item)
        # Randomly mark some for failure
        if draw(booleans()):
            failure_indices.add(i)

    # Ensure at least one success and one failure
    if len(failure_indices) == 0:
        failure_indices.add(0)
    if len(failure_indices) == num_items:
        failure_indices.discard(num_items - 1)

    return (items, failure_indices)


# --- Property Tests ---


class TestEligibleIssueQueriesReturnOnlyActiveIssues(unittest.TestCase):
    """Property 3: Eligible Issue Queries Return Only Active Issues

    For any set of PPE Issue records with mixed statuses (Active, Returned,
    Expired, Replaced), the eligible-for-return query function SHALL return
    only those with status "Active" and docstatus 1, and exclude all others.

    Feature: ppe-tracker-enhancements-v2, Property 3
    **Validates: Requirements 3.2**
    """

    @given(dataset=mixed_status_dataset())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_get_eligible_returns_queries_only_active_submitted(self, dataset):
        """get_eligible_returns() always queries with status='Active' and docstatus=1.

        Feature: ppe-tracker-enhancements-v2, Property 3
        **Validates: Requirements 3.2**
        """
        from ppe_tracker.ppe_tracker.api.bulk_return import get_eligible_returns

        # Only Active+submitted records should be eligible
        expected_eligible = [r for r in dataset if r["status"] == "Active" and r["docstatus"] == 1]

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            # Bypass permission check
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)

            # Mock get_all to return only Active records (simulating the DB query)
            mock_frappe.get_all.return_value = [
                {k: v for k, v in r.items() if k != "status" and k != "docstatus"}
                for r in expected_eligible
            ]

            result = get_eligible_returns(filters=None)

            # ASSERTION 1: frappe.get_all was called with status="Active" and docstatus=1
            call_args = mock_frappe.get_all.call_args
            query_filters = call_args[1].get("filters") if call_args[1] else call_args[0][1] if len(call_args[0]) > 1 else None
            # Handle both positional and keyword args
            if query_filters is None:
                query_filters = call_args.kwargs.get("filters")

            self.assertEqual(query_filters["status"], "Active")
            self.assertEqual(query_filters["docstatus"], 1)

            # ASSERTION 2: The result count matches only the Active records
            self.assertEqual(len(result), len(expected_eligible))


class TestBulkToolFilterLogic(unittest.TestCase):
    """Property 4: Bulk Tool Filter Logic

    For any combination of filter parameters (Employee, Department, PPE Item),
    the query_filters dict SHALL include ALL applied filters, ensuring results
    match ALL criteria simultaneously.

    Feature: ppe-tracker-enhancements-v2, Property 4
    **Validates: Requirements 3.3**
    """

    @given(filters=filter_combination())
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_all_applied_filters_included_in_query(self, filters):
        """get_eligible_returns() includes every non-empty filter in query_filters.

        Feature: ppe-tracker-enhancements-v2, Property 4
        **Validates: Requirements 3.3**
        """
        from ppe_tracker.ppe_tracker.api.bulk_return import get_eligible_returns

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            # Bypass permission check
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe.get_all.return_value = []

            get_eligible_returns(filters=filters)

            # Get the actual query_filters passed to get_all
            call_args = mock_frappe.get_all.call_args
            query_filters = call_args.kwargs.get("filters") if call_args.kwargs else call_args[1].get("filters")

            # ASSERTION 1: Base filters always present
            self.assertEqual(query_filters["status"], "Active")
            self.assertEqual(query_filters["docstatus"], 1)

            # ASSERTION 2: Every provided filter is included in query_filters
            if filters.get("employee"):
                self.assertIn("employee", query_filters)
                self.assertEqual(query_filters["employee"], filters["employee"])

            if filters.get("department"):
                self.assertIn("department", query_filters)
                self.assertEqual(query_filters["department"], filters["department"])

            if filters.get("ppe_item"):
                self.assertIn("ppe_item", query_filters)
                self.assertEqual(query_filters["ppe_item"], filters["ppe_item"])

            # ASSERTION 3: No extra user-facing filters beyond the base + applied
            expected_keys = {"status", "docstatus"}
            for key in ("employee", "department", "ppe_item"):
                if filters.get(key):
                    expected_keys.add(key)
            self.assertEqual(set(query_filters.keys()), expected_keys)


class TestBulkReturnCreatesOnePPEReturnPerSelectedIssue(unittest.TestCase):
    """Property 5: Bulk Return Creates One PPE Return Per Selected Issue

    For any batch of selected Active PPE Issues, the bulk return process SHALL
    create exactly one PPE Return record per selected issue, with the specified
    condition, date, and quantity.

    Feature: ppe-tracker-enhancements-v2, Property 5
    **Validates: Requirements 3.5, 3.6**
    """

    @given(batch=bulk_return_batch())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_one_ppe_return_created_per_item(self, batch):
        """process_bulk_returns() creates exactly one PPE Return per item in batch.

        Feature: ppe-tracker-enhancements-v2, Property 5
        **Validates: Requirements 3.5, 3.6**
        """
        from ppe_tracker.ppe_tracker.api.bulk_return import process_bulk_returns

        created_docs = []

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            # Bypass permission check
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._.return_value = "error"

            # Mock savepoint/rollback/commit
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            # Mock get_doc to return an issue doc with quantity
            def mock_get_doc(doctype, name):
                doc = MagicMock()
                doc.employee = "HR-EMP-0001"
                doc.employee_name = "Test Employee"
                doc.ppe_item = "Safety Helmet"
                doc.quantity = 3
                return doc

            mock_frappe.get_doc = mock_get_doc

            # Mock new_doc to create trackable return docs
            def mock_new_doc(doctype):
                doc = MagicMock()
                doc.name = f"PPE-RET-{len(created_docs):04d}"
                created_docs.append(doc)
                return doc

            mock_frappe.new_doc = mock_new_doc

            result = process_bulk_returns(batch)

            # ASSERTION 1: Exactly one PPE Return created per item in batch
            self.assertEqual(len(created_docs), len(batch))

            # ASSERTION 2: Each created doc has correct condition, date, quantity
            for i, item in enumerate(batch):
                doc = created_docs[i]
                self.assertEqual(doc.ppe_issue, item["ppe_issue"])
                self.assertEqual(doc.condition, item["condition"])
                self.assertEqual(doc.return_date, item["return_date"])

                # Quantity: use provided or default to issue's full quantity (3)
                expected_qty = item["quantity_returned"] if item["quantity_returned"] else 3
                self.assertEqual(doc.quantity_returned, expected_qty)

            # ASSERTION 3: Each doc was inserted and submitted
            for doc in created_docs:
                doc.insert.assert_called_once_with(ignore_permissions=True)
                doc.submit.assert_called_once()

            # ASSERTION 4: All items succeeded (no failures in this scenario)
            self.assertEqual(len(result["successes"]), len(batch))
            self.assertEqual(len(result["failures"]), 0)


class TestBulkProcessingContinuesOnIndividualFailure(unittest.TestCase):
    """Property 7: Bulk Processing Continues On Individual Failure

    For any batch containing a mix of valid and invalid items, the bulk processing
    function SHALL continue processing remaining items after an individual failure,
    and SHALL return an accurate summary with all successes and all failures listed.

    Feature: ppe-tracker-enhancements-v2, Property 7
    **Validates: Requirements 3.7**
    """

    @given(data=bulk_return_batch_with_failures())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_processing_continues_after_failures(self, data):
        """process_bulk_returns() continues processing after individual failures
        and returns accurate success/failure counts.

        Feature: ppe-tracker-enhancements-v2, Property 7
        **Validates: Requirements 3.7**
        """
        from ppe_tracker.ppe_tracker.api.bulk_return import process_bulk_returns

        items, failure_indices = data
        call_counter = [0]

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            # Bypass permission check
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._.side_effect = lambda x: x

            # Mock savepoint/rollback/commit
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            # Mock get_doc — raise exception for failure indices
            def mock_get_doc(doctype, name):
                # Find the index based on name
                idx = int(name.split("-")[-1])
                if idx in failure_indices:
                    raise Exception(f"Simulated failure for {name}")
                doc = MagicMock()
                doc.employee = "HR-EMP-0001"
                doc.employee_name = "Test Employee"
                doc.ppe_item = "Safety Helmet"
                doc.quantity = 2
                return doc

            mock_frappe.get_doc = mock_get_doc

            # Mock new_doc
            def mock_new_doc(doctype):
                doc = MagicMock()
                doc.name = f"PPE-RET-{call_counter[0]:04d}"
                call_counter[0] += 1
                return doc

            mock_frappe.new_doc = mock_new_doc

            result = process_bulk_returns(items)

            expected_successes = len(items) - len(failure_indices)
            expected_failures = len(failure_indices)

            # ASSERTION 1: Processing continues — total items processed equals batch size
            self.assertEqual(
                len(result["successes"]) + len(result["failures"]),
                len(items),
            )

            # ASSERTION 2: Success count matches non-failure items
            self.assertEqual(len(result["successes"]), expected_successes)

            # ASSERTION 3: Failure count matches failure items
            self.assertEqual(len(result["failures"]), expected_failures)

            # ASSERTION 4: Each failure entry has the correct ppe_issue reference
            failure_issues = {f["ppe_issue"] for f in result["failures"]}
            expected_failure_issues = {items[i]["ppe_issue"] for i in failure_indices}
            self.assertEqual(failure_issues, expected_failure_issues)

            # ASSERTION 5: Each failure has an error message
            for failure in result["failures"]:
                self.assertIn("error", failure)
                self.assertTrue(len(failure["error"]) > 0)

            # ASSERTION 6: Each success has the correct ppe_issue reference
            success_issues = {s["ppe_issue"] for s in result["successes"]}
            expected_success_issues = {
                items[i]["ppe_issue"] for i in range(len(items)) if i not in failure_indices
            }
            self.assertEqual(success_issues, expected_success_issues)


if __name__ == "__main__":
    unittest.main()
