# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Bulk PPE Return API logic.

Property 3: Eligible Issue Queries Return Only Active Issues
Property 4: Bulk Tool Filter Logic
Property 5: Bulk Return Creates One PPE Return Per Selected Issue
Property 7: Bulk Processing Continues On Individual Failure

**Validates: Requirements 3.2, 3.3, 3.5, 3.6, 3.7**
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    composite,
    dates,
    integers,
    lists,
    booleans,
    sampled_from,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

status_strategy = sampled_from(["Active", "Returned", "Expired", "Replaced"])
condition_strategy = sampled_from(["Good", "Damaged", "Unusable"])
department_strategy = sampled_from(["Engineering", "Operations", "HR", "Finance", "Safety"])
employee_strategy = sampled_from(["EMP-001", "EMP-002", "EMP-003", "EMP-004", "EMP-005"])
ppe_item_strategy = sampled_from(["Safety Helmet", "Gloves", "Safety Boots", "Goggles", "Ear Muffs"])


@composite
def ppe_issue_records(draw, min_size=1, max_size=15):
    """Generate a list of PPE Issue records with mixed statuses."""
    num = draw(integers(min_value=min_size, max_value=max_size))
    records = []
    for i in range(num):
        records.append({
            "name": f"PPE-ISS-{i+1:04d}",
            "employee": draw(employee_strategy),
            "employee_name": f"Employee {i+1}",
            "department": draw(department_strategy),
            "ppe_item": draw(ppe_item_strategy),
            "issue_date": str(draw(dates(min_value=date(2024, 1, 1), max_value=date(2024, 12, 28)))),
            "expiry_date": str(draw(dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 28)))),
            "quantity": draw(integers(min_value=1, max_value=10)),
            "status": draw(status_strategy),
            "docstatus": 1,
        })
    return records


@composite
def filter_combination(draw):
    """Generate a random subset of filter parameters."""
    filters = {}
    if draw(booleans()):
        filters["employee"] = draw(employee_strategy)
    if draw(booleans()):
        filters["department"] = draw(department_strategy)
    if draw(booleans()):
        filters["ppe_item"] = draw(ppe_item_strategy)
    return filters


@composite
def bulk_return_batch(draw):
    """Generate a batch of items for process_bulk_returns.

    Returns (items, condition, return_date, quantity_issued_map).
    """
    num_items = draw(integers(min_value=1, max_value=8))
    condition = draw(condition_strategy)
    return_date = draw(dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 28)))

    items = []
    quantity_issued_map = {}

    for i in range(num_items):
        ppe_issue_name = f"PPE-ISS-{i+1:04d}"
        qty_issued = draw(integers(min_value=1, max_value=10))
        quantity_issued_map[ppe_issue_name] = qty_issued

        item_data = {
            "ppe_issue": ppe_issue_name,
            "condition": condition,
            "return_date": str(return_date),
        }
        # Optionally override quantity
        if draw(booleans()):
            item_data["quantity_returned"] = draw(integers(min_value=1, max_value=qty_issued))

        items.append(item_data)

    return (items, condition, str(return_date), quantity_issued_map)


@composite
def bulk_return_mixed_batch(draw):
    """Generate a batch with mix of valid and invalid items for failure testing.

    Returns (items, valid_names, invalid_names, quantity_issued_map).
    """
    num_valid = draw(integers(min_value=1, max_value=5))
    num_invalid = draw(integers(min_value=1, max_value=4))

    condition = draw(condition_strategy)
    return_date = str(draw(dates(min_value=date(2025, 1, 1), max_value=date(2025, 12, 28))))

    items = []
    valid_names = set()
    invalid_names = set()
    quantity_issued_map = {}

    # Add valid items first
    for i in range(num_valid):
        name = f"PPE-ISS-VALID-{i+1:04d}"
        qty = draw(integers(min_value=1, max_value=10))
        items.append({
            "ppe_issue": name,
            "condition": condition,
            "return_date": return_date,
        })
        valid_names.add(name)
        quantity_issued_map[name] = qty

    # Add invalid items
    for i in range(num_invalid):
        name = f"PPE-ISS-INVALID-{i+1:04d}"
        items.append({
            "ppe_issue": name,
            "condition": condition,
            "return_date": return_date,
        })
        invalid_names.add(name)

    return (items, valid_names, invalid_names, quantity_issued_map)


# ---------------------------------------------------------------------------
# Property 3: Eligible Issue Queries Return Only Active Issues
# ---------------------------------------------------------------------------


class TestEligibleIssueQueriesReturnOnlyActive(unittest.TestCase):
    """Property 3: Eligible Issue Queries Return Only Active Issues

    For any set of PPE Issue records with mixed statuses (Active, Returned,
    Expired, Replaced), the eligible-for-return query function SHALL return
    only those with status "Active" and exclude all others.

    **Validates: Requirements 3.2**
    """

    @given(issues=ppe_issue_records(min_size=1, max_size=15))
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_only_active_issues_returned(self, issues):
        """get_eligible_returns() returns only Active status issues.

        **Validates: Requirements 3.2**
        """
        # Compute expected: only Active + docstatus=1
        expected_active = [i for i in issues if i["status"] == "Active" and i["docstatus"] == 1]

        # Simulate frappe.get_all filtering behavior
        def mock_get_all(doctype, filters=None, fields=None, order_by=None):
            result = []
            for issue in issues:
                match = all(issue.get(k) == v for k, v in (filters or {}).items())
                if match:
                    if fields:
                        result.append({f: issue.get(f) for f in fields})
                    else:
                        result.append(issue.copy())
            return result

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.get_all.side_effect = mock_get_all

            from ppe_tracker.ppe_tracker.api.bulk_return import get_eligible_returns
            result = get_eligible_returns(filters=None)

        # ASSERTION 1: Result count equals Active issues count
        self.assertEqual(len(result), len(expected_active))

        # ASSERTION 2: The query was called with status=Active and docstatus=1
        call_kwargs = mock_frappe.get_all.call_args
        actual_filters = call_kwargs.kwargs.get("filters")
        self.assertEqual(actual_filters["status"], "Active")
        self.assertEqual(actual_filters["docstatus"], 1)


# ---------------------------------------------------------------------------
# Property 4: Bulk Tool Filter Logic
# ---------------------------------------------------------------------------


class TestBulkToolFilterLogic(unittest.TestCase):
    """Property 4: Bulk Tool Filter Logic

    For any set of Active PPE Issues and any combination of filter parameters
    (Employee, Department, PPE Item), the filtered result set SHALL contain
    only issues matching ALL applied filters and SHALL include every Active
    issue that satisfies all filter criteria.

    **Validates: Requirements 3.3**
    """

    @given(issues=ppe_issue_records(min_size=2, max_size=15), filters=filter_combination())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_filtered_results_match_all_applied_filters(self, issues, filters):
        """get_eligible_returns(filters) returns only issues matching ALL filters.

        **Validates: Requirements 3.3**
        """
        # Compute expected: Active + docstatus=1 + all user filters
        expected_filters = {"status": "Active", "docstatus": 1}
        expected_filters.update(filters)
        expected = [i for i in issues if all(i.get(k) == v for k, v in expected_filters.items())]

        def mock_get_all(doctype, filters=None, fields=None, order_by=None):
            result = []
            for issue in issues:
                match = all(issue.get(k) == v for k, v in (filters or {}).items())
                if match:
                    if fields:
                        result.append({f: issue.get(f) for f in fields})
                    else:
                        result.append(issue.copy())
            return result

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.get_all.side_effect = mock_get_all

            from ppe_tracker.ppe_tracker.api.bulk_return import get_eligible_returns
            result = get_eligible_returns(filters=filters)

        # ASSERTION 1: Result count matches expected
        self.assertEqual(len(result), len(expected))

        # ASSERTION 2: The query includes all user-supplied filters
        call_kwargs = mock_frappe.get_all.call_args
        actual_filters = call_kwargs.kwargs.get("filters")

        for key, val in filters.items():
            self.assertIn(key, actual_filters)
            self.assertEqual(actual_filters[key], val)

        # ASSERTION 3: Base filters always present
        self.assertEqual(actual_filters["status"], "Active")
        self.assertEqual(actual_filters["docstatus"], 1)


# ---------------------------------------------------------------------------
# Property 5: Bulk Return Creates One PPE Return Per Selected Issue
# ---------------------------------------------------------------------------


class TestBulkReturnCreatesOnePerIssue(unittest.TestCase):
    """Property 5: Bulk Return Creates One PPE Return Per Selected Issue

    For any batch of selected Active PPE Issues with a specified condition
    and return date, the bulk return process SHALL create exactly one PPE
    Return record per selected issue, with the specified condition, date,
    and quantity (defaulting to full issued quantity unless overridden).

    **Validates: Requirements 3.5, 3.6**
    """

    @given(dataset=bulk_return_batch())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_one_return_per_selected_issue(self, dataset):
        """process_bulk_returns() creates exactly one PPE Return per selected issue
        with specified condition, date, and quantity.

        **Validates: Requirements 3.5, 3.6**
        """
        items, condition, return_date, quantity_issued_map = dataset

        created_returns = []

        def mock_get_doc(doctype, name):
            doc = MagicMock()
            doc.employee = "EMP-001"
            doc.employee_name = "Test Employee"
            doc.ppe_item = "Safety Helmet"
            doc.quantity = quantity_issued_map.get(name, 1)
            return doc

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.name = f"PPE-RET-{len(created_returns)+1:04d}"
            created_returns.append(doc)
            return doc

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe.get_doc.side_effect = mock_get_doc
            mock_frappe.new_doc.side_effect = mock_new_doc
            mock_frappe.db = MagicMock()
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            from ppe_tracker.ppe_tracker.api.bulk_return import process_bulk_returns
            result = process_bulk_returns(items)

        # ASSERTION 1: Exactly one PPE Return created per item
        self.assertEqual(len(created_returns), len(items))
        self.assertEqual(len(result["successes"]), len(items))
        self.assertEqual(len(result["failures"]), 0)

        # ASSERTION 2: Each return has the correct condition and date
        for ret_doc in created_returns:
            self.assertEqual(ret_doc.condition, condition)
            self.assertEqual(ret_doc.return_date, return_date)

        # ASSERTION 3: Quantity defaults to issued quantity unless overridden
        for i, ret_doc in enumerate(created_returns):
            item = items[i]
            ppe_issue_name = item["ppe_issue"]
            if item.get("quantity_returned"):
                expected_qty = item["quantity_returned"]
            else:
                expected_qty = quantity_issued_map[ppe_issue_name]
            self.assertEqual(ret_doc.quantity_returned, expected_qty)

        # ASSERTION 4: insert and submit called for each
        for ret_doc in created_returns:
            ret_doc.insert.assert_called_once_with(ignore_permissions=True)
            ret_doc.submit.assert_called_once()


# ---------------------------------------------------------------------------
# Property 7: Bulk Processing Continues On Individual Failure
# ---------------------------------------------------------------------------


class TestBulkProcessingContinuesOnFailure(unittest.TestCase):
    """Property 7: Bulk Processing Continues On Individual Failure

    For any batch containing a mix of valid and invalid items (e.g., some
    already returned), the bulk processing function SHALL continue processing
    remaining items after an individual failure, and SHALL return an accurate
    summary with all successes and all failures listed.

    **Validates: Requirements 3.7**
    """

    @given(dataset=bulk_return_mixed_batch())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_continues_after_failure_accurate_summary(self, dataset):
        """process_bulk_returns() continues processing after individual failures
        and returns accurate successes and failures lists.

        **Validates: Requirements 3.7**
        """
        items, valid_names, invalid_names, quantity_issued_map = dataset

        created_returns = []

        def mock_get_doc(doctype, name):
            if name in invalid_names:
                raise Exception(f"PPE Issue {name} already returned")
            doc = MagicMock()
            doc.employee = "EMP-001"
            doc.employee_name = "Test Employee"
            doc.ppe_item = "Safety Helmet"
            doc.quantity = quantity_issued_map.get(name, 1)
            return doc

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.name = f"PPE-RET-{len(created_returns)+1:04d}"
            created_returns.append(doc)
            return doc

        with patch("ppe_tracker.ppe_tracker.api.bulk_return.frappe") as mock_frappe:
            mock_frappe.only_for = MagicMock()
            mock_frappe.parse_json = MagicMock(side_effect=lambda x: x)
            mock_frappe._ = lambda x: x
            mock_frappe.throw = MagicMock(side_effect=Exception("frappe.throw"))
            mock_frappe.get_doc.side_effect = mock_get_doc
            mock_frappe.new_doc.side_effect = mock_new_doc
            mock_frappe.db = MagicMock()
            mock_frappe.db.savepoint = MagicMock()
            mock_frappe.db.rollback = MagicMock()
            mock_frappe.db.commit = MagicMock()

            from ppe_tracker.ppe_tracker.api.bulk_return import process_bulk_returns
            result = process_bulk_returns(items)

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

        # ASSERTION 6: Each success has ppe_return key
        for success in result["successes"]:
            self.assertIn("ppe_return", success)


if __name__ == "__main__":
    unittest.main()
