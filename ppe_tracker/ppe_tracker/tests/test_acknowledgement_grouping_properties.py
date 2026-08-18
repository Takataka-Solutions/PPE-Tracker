# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for multi-employee bulk issue acknowledgement grouping.

Feature: ppe-tracker-enhancements-v2

Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping

**Validates: Requirements 12.3**

NOTE: The production grouping logic lives in JavaScript (bulk_ppe_issue.js,
offerAcknowledgement function). This test validates the grouping *algorithm*
via a Python mirror of the same logic. The contract is: given a list of
success items from issue_selected(), group them by employee so that exactly
N distinct employees produce N acknowledgement groups, each containing only
that employee's PPE Issues with no duplication or loss.
"""

import unittest

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    text,
    integers,
    lists,
    composite,
    sampled_from,
    just,
)


# ---------------------------------------------------------------------------
# System Under Test: Python mirror of JS offerAcknowledgement grouping logic
# ---------------------------------------------------------------------------

def group_issues_by_employee(successes):
    """Group bulk issue successes by employee (mirrors JS offerAcknowledgement logic).

    This function replicates the grouping algorithm from bulk_ppe_issue.js:
        var byEmployee = {};
        successes.forEach(function (item) {
            var emp = item.employee;
            if (!byEmployee[emp]) {
                byEmployee[emp] = { employee: emp, employee_name: ..., issues: [] };
            }
            byEmployee[emp].issues.push(item.ppe_issue);
        });

    Args:
        successes: list of dicts with keys: employee, employee_name, ppe_issue

    Returns:
        dict: employee -> {"employee": str, "employee_name": str, "issues": [str]}
    """
    by_employee = {}
    for item in successes:
        emp = item["employee"]
        if emp not in by_employee:
            by_employee[emp] = {
                "employee": emp,
                "employee_name": item["employee_name"],
                "issues": [],
            }
        by_employee[emp]["issues"].append(item["ppe_issue"])
    return by_employee


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

@composite
def bulk_issue_success_batch(draw):
    """Generate a batch of success items from a bulk PPE issue operation.

    Each item has: employee, employee_name, ppe_issue (unique across batch).
    The batch contains 1–30 items spread across 1–M distinct employees (M <= N).

    Returns:
        list[dict]: list of success items with keys employee, employee_name, ppe_issue
    """
    # Generate between 1 and 15 distinct employees
    num_employees = draw(integers(min_value=1, max_value=15))
    employees = []
    for i in range(num_employees):
        emp_id = f"HR-EMP-{i + 1:04d}"
        emp_name = f"Employee {i + 1}"
        employees.append({"employee": emp_id, "employee_name": emp_name})

    # Generate between num_employees and 30 success items (at least one per employee)
    max_items = max(num_employees, 30)
    num_items = draw(integers(min_value=num_employees, max_value=max_items))

    successes = []
    # Ensure every employee gets at least one issue
    for i, emp in enumerate(employees):
        successes.append({
            "employee": emp["employee"],
            "employee_name": emp["employee_name"],
            "ppe_issue": f"PPE-ISS-{i + 1:05d}",
        })

    # Fill remaining slots by picking from existing employees
    for i in range(num_employees, num_items):
        emp_idx = draw(integers(min_value=0, max_value=num_employees - 1))
        emp = employees[emp_idx]
        successes.append({
            "employee": emp["employee"],
            "employee_name": emp["employee_name"],
            "ppe_issue": f"PPE-ISS-{i + 1:05d}",
        })

    return successes


class TestMultiEmployeeBulkIssueAcknowledgementGrouping(unittest.TestCase):
    """Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping

    For any bulk issue batch that creates PPE Issues for N distinct employees,
    the system SHALL offer exactly N acknowledgement records — one per employee —
    where each acknowledgement's child table contains exactly the PPE Issues
    belonging to that employee from the batch.

    Feature: ppe-tracker-enhancements-v2, Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping
    **Validates: Requirements 12.3**
    """

    @given(successes=bulk_issue_success_batch())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_grouping_produces_exactly_n_groups_for_n_distinct_employees(self, successes):
        """group_issues_by_employee() produces exactly N groups for N distinct employees,
        each containing only that employee's issues with no cross-contamination or loss.

        Feature: ppe-tracker-enhancements-v2, Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping
        **Validates: Requirements 12.3**
        """
        result = group_issues_by_employee(successes)

        # Compute expected distinct employees
        distinct_employees = set(item["employee"] for item in successes)
        n = len(distinct_employees)

        # ASSERTION 1: Exactly N groups for N distinct employees
        self.assertEqual(
            len(result), n,
            f"Expected {n} groups for {n} distinct employees, got {len(result)}"
        )

        # ASSERTION 2: Each group key matches a distinct employee from the batch
        self.assertEqual(set(result.keys()), distinct_employees)

        # ASSERTION 3: Each group contains ONLY that employee's issues (no cross-contamination)
        for emp_id, group in result.items():
            expected_issues = [
                item["ppe_issue"] for item in successes
                if item["employee"] == emp_id
            ]
            self.assertEqual(
                group["issues"], expected_issues,
                f"Group for {emp_id} has incorrect issues"
            )

        # ASSERTION 4: All issues are accounted for (no duplication, no loss)
        all_grouped_issues = []
        for group in result.values():
            all_grouped_issues.extend(group["issues"])
        all_source_issues = [item["ppe_issue"] for item in successes]
        self.assertEqual(
            sorted(all_grouped_issues), sorted(all_source_issues),
            "Union of grouped issues does not equal the full batch"
        )
        # No duplicates in grouped output
        self.assertEqual(
            len(all_grouped_issues), len(all_source_issues),
            "Duplication detected in grouped output"
        )

        # ASSERTION 5: Each group has the correct employee and employee_name
        for emp_id, group in result.items():
            self.assertEqual(group["employee"], emp_id)
            # Find the expected employee_name from the source data
            expected_name = next(
                item["employee_name"] for item in successes
                if item["employee"] == emp_id
            )
            self.assertEqual(
                group["employee_name"], expected_name,
                f"Group for {emp_id} has wrong employee_name"
            )
