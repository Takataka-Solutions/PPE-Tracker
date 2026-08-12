# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Issue Acknowledgement grouping logic.

Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping

**Validates: Requirements 12.3**
"""

import unittest

from hypothesis import given, settings
from hypothesis.strategies import (
    composite,
    integers,
    lists,
    sampled_from,
    text,
)

from ppe_tracker.api.acknowledgement_utils import group_issues_by_employee


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

employee_strategy = sampled_from([
    "EMP-001", "EMP-002", "EMP-003", "EMP-004", "EMP-005"
])


@composite
def bulk_issue_batch(draw):
    """Generate a batch of successfully created PPE Issues for 1-5 distinct employees.

    Each employee gets 1-10 issues. Returns a list of dicts with 'employee' and
    'ppe_issue' keys, simulating the successes list from a bulk issue operation.
    """
    # Pick 1-5 distinct employees
    num_employees = draw(integers(min_value=1, max_value=5))
    all_employees = ["EMP-001", "EMP-002", "EMP-003", "EMP-004", "EMP-005"]
    employees = all_employees[:num_employees]

    issues = []
    issue_counter = 1

    for employee in employees:
        # Each employee gets 1-10 issues
        num_issues = draw(integers(min_value=1, max_value=10))
        for _ in range(num_issues):
            issues.append({
                "employee": employee,
                "ppe_issue": f"PPE-ISS-{issue_counter:04d}",
            })
            issue_counter += 1

    return issues


# ---------------------------------------------------------------------------
# Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping
# ---------------------------------------------------------------------------


class TestMultiEmployeeAcknowledgementGrouping(unittest.TestCase):
    """Property 18: Multi-Employee Bulk Issue Acknowledgement Grouping

    For any bulk issue batch that creates PPE Issues for N distinct employees,
    the system SHALL offer exactly N acknowledgement records — one per employee —
    where each acknowledgement's child table contains exactly the PPE Issues
    belonging to that employee from the batch.

    **Validates: Requirements 12.3**
    """

    @given(issues=bulk_issue_batch())
    @settings(max_examples=25, deadline=None)
    def test_grouping_produces_one_acknowledgement_per_employee(self, issues):
        """group_issues_by_employee() produces exactly N groups for N distinct employees,
        each containing ONLY that employee's issues, with no issues lost or duplicated.

        **Validates: Requirements 12.3**
        """
        # Compute expected distinct employees
        distinct_employees = set(issue["employee"] for issue in issues)

        # Run the grouping function
        grouped = group_issues_by_employee(issues)

        # ASSERTION 1: Number of groups == number of distinct employees
        self.assertEqual(
            len(grouped),
            len(distinct_employees),
            f"Expected {len(distinct_employees)} groups but got {len(grouped)}",
        )

        # ASSERTION 2: Each group contains ONLY issues belonging to that employee
        for employee, ppe_issues in grouped.items():
            expected_issues = [
                issue["ppe_issue"]
                for issue in issues
                if issue["employee"] == employee
            ]
            self.assertEqual(
                sorted(ppe_issues),
                sorted(expected_issues),
                f"Employee {employee} group contains incorrect issues",
            )

        # ASSERTION 3: Union of all groups == the full set of issues (nothing lost)
        all_grouped_issues = set()
        for ppe_issues in grouped.values():
            all_grouped_issues.update(ppe_issues)

        all_original_issues = set(issue["ppe_issue"] for issue in issues)
        self.assertEqual(
            all_grouped_issues,
            all_original_issues,
            "Some issues were lost during grouping",
        )

        # ASSERTION 4: No issue appears in more than one acknowledgement group
        total_issues_in_groups = sum(len(v) for v in grouped.values())
        self.assertEqual(
            total_issues_in_groups,
            len(all_original_issues),
            "Some issues appear in multiple groups (duplicated)",
        )

        # ASSERTION 5: All grouped keys are actual employees from the batch
        self.assertEqual(
            set(grouped.keys()),
            distinct_employees,
            "Grouped keys don't match original distinct employees",
        )


if __name__ == "__main__":
    unittest.main()
