# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the Combined PPE Issue Print Format.

Feature: ppe-tracker-enhancements-v2
Property 10: Combined Print Format Contains Required Fields

For any PPE Issue Acknowledgement with one or more linked PPE Issues, the
rendered Combined PPE Issue Form SHALL contain: the PPE Item name, quantity,
issue date, expiry date, condition (new/returned), and size for each linked issue.

**Validates: Requirements 6.3, 17.7**
"""

import json
import os
import unittest
from unittest.mock import MagicMock
from datetime import date, timedelta

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    integers,
    dates,
    composite,
    sampled_from,
    lists,
)

from jinja2 import Environment


# --- Helper: Load the Jinja HTML template from the JSON file ---

def load_print_format_html():
    """Load the Combined PPE Issue Form HTML template from the JSON definition."""
    json_path = os.path.join(
        os.path.dirname(__file__),
        "ppe_tracker",
        "print_format",
        "combined_ppe_issue_form",
        "combined_ppe_issue_form.json",
    )
    with open(json_path, "r", encoding="utf-8") as f:
        pf_def = json.load(f)
    return pf_def["html"]


# --- Strategies ---

@composite
def ppe_issue_data(draw):
    """Generate a single PPE Issue record with all fields needed by the template.

    Fields:
    - ppe_item: str (PPE Item name)
    - size: str or empty string
    - quantity: int >= 1
    - issue_date: date
    - expiry_date: date or None
    - issue_type: "Standard" or "Casual"
    """
    ppe_item = draw(sampled_from([
        "Safety Helmet",
        "Steel Toe Boots",
        "Reflective Vest",
        "Work Gloves",
        "Safety Goggles",
        "Ear Plugs",
        "Coveralls",
    ]))

    issue_type = draw(sampled_from(["Standard", "Casual"]))

    has_size = draw(sampled_from([True, False]))
    size = draw(sampled_from(["S", "M", "L", "XL", "8", "9", "10", "42"])) if has_size else ""

    quantity = draw(integers(min_value=1, max_value=20))

    issue_date = draw(dates(
        min_value=date(2020, 1, 1),
        max_value=date(2025, 12, 31),
    ))

    # Expiry date: sometimes set, sometimes None
    has_expiry = draw(sampled_from([True, True, True, False]))  # mostly has expiry
    if has_expiry:
        expiry_offset = draw(integers(min_value=30, max_value=730))
        expiry_date = issue_date + timedelta(days=expiry_offset)
    else:
        expiry_date = None

    return {
        "ppe_item": ppe_item,
        "size": size,
        "quantity": quantity,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "issue_type": issue_type,
    }


@composite
def acknowledgement_dataset(draw):
    """Generate a PPE Issue Acknowledgement document with 1-5 linked PPE Issues.

    Returns a tuple: (doc_data, issues_list) where:
    - doc_data: dict with employee_name, employee, department, designation, acknowledgement_date
    - issues_list: list of dicts with ppe_issue name + issue field data
    """
    employee_name = draw(sampled_from([
        "John Doe", "Jane Smith", "Peter Kamau", "Mary Wanjiku", "Ali Hassan"
    ]))
    employee_id = draw(sampled_from([
        "HR-EMP-001", "HR-EMP-002", "HR-EMP-003", "HR-EMP-004", "HR-EMP-005"
    ]))
    department = draw(sampled_from([
        "Operations", "Logistics", "Engineering", "Administration"
    ]))
    designation = draw(sampled_from([
        "Site Worker", "Driver", "Engineer", "Supervisor", "Cleaner"
    ]))
    ack_date = draw(dates(
        min_value=date(2024, 1, 1),
        max_value=date(2025, 12, 31),
    ))

    num_issues = draw(integers(min_value=1, max_value=5))
    issues_list = []
    for i in range(num_issues):
        issue_data = draw(ppe_issue_data())
        issue_data["name"] = f"PPE-ISS-2024-{i:04d}"
        issues_list.append(issue_data)

    doc_data = {
        "employee_name": employee_name,
        "employee": employee_id,
        "department": department,
        "designation": designation,
        "acknowledgement_date": ack_date,
    }

    return doc_data, issues_list


# --- Test Class ---

class TestCombinedPrintFormatContainsRequiredFields(unittest.TestCase):
    """Property 10: Combined Print Format Contains Required Fields

    For any PPE Issue Acknowledgement with one or more linked PPE Issues, the
    rendered Combined PPE Issue Form SHALL contain: the PPE Item name, quantity,
    issue date, expiry date, and condition (new/returned) for each linked issue,
    plus the employee's size where applicable.

    Approach: Load the Jinja template from JSON, render it with mock data using
    jinja2.Environment with custom globals for `frappe`, and verify the rendered
    HTML contains each required field value.

    Feature: ppe-tracker-enhancements-v2, Property 10
    **Validates: Requirements 6.3, 17.7**
    """

    @classmethod
    def setUpClass(cls):
        """Load the template HTML once for all tests."""
        cls.template_html = load_print_format_html()

    def _build_jinja_env_and_render(self, doc_data, issues_list):
        """Build Jinja environment with mock frappe functions and render template.

        Args:
            doc_data: dict with employee_name, employee, department, designation, acknowledgement_date
            issues_list: list of dicts with issue field data

        Returns:
            Rendered HTML string.
        """
        # Build mock doc object
        doc = MagicMock()
        doc.employee_name = doc_data["employee_name"]
        doc.employee = doc_data["employee"]
        doc.department = doc_data["department"]
        doc.designation = doc_data["designation"]
        doc.acknowledgement_date = str(doc_data["acknowledgement_date"])

        # Build child table rows
        rows = []
        issue_docs_map = {}
        for issue_data in issues_list:
            row = MagicMock()
            row.ppe_issue = issue_data["name"]
            rows.append(row)

            # Build a mock PPE Issue doc for frappe.get_doc
            issue_doc = MagicMock()
            issue_doc.ppe_item = issue_data["ppe_item"]
            issue_doc.size = issue_data["size"]
            issue_doc.quantity = issue_data["quantity"]
            issue_doc.issue_date = issue_data["issue_date"]
            issue_doc.expiry_date = issue_data["expiry_date"]
            issue_doc.issue_type = issue_data["issue_type"]
            # MagicMock .get() needs explicit side_effect
            issue_doc.get = lambda key, default=None, _it=issue_data["issue_type"]: (
                _it if key == "issue_type" else default
            )
            issue_docs_map[issue_data["name"]] = issue_doc

        doc.ppe_issues = rows

        # Mock frappe.get_doc
        def mock_get_doc(doctype, name):
            if doctype == "PPE Issue" and name in issue_docs_map:
                return issue_docs_map[name]
            return MagicMock()

        # Mock frappe.format_value — just return str(value) for simplicity
        def mock_format_value(value, args=None):
            if value is None:
                return ""
            return str(value)

        # Build a mock frappe module object
        mock_frappe = MagicMock()
        mock_frappe.get_doc = mock_get_doc
        mock_frappe.format_value = mock_format_value

        # Create Jinja environment with frappe in globals
        env = Environment()
        template = env.from_string(self.template_html)
        rendered = template.render(doc=doc, frappe=mock_frappe)

        return rendered

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_ppe_item_name(self, data):
        """Rendered HTML contains each PPE Issue's ppe_item name.

        **Validates: Requirements 6.3**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            self.assertIn(
                issue["ppe_item"],
                rendered,
                f"PPE Item name '{issue['ppe_item']}' not found in rendered output",
            )

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_quantity(self, data):
        """Rendered HTML contains each PPE Issue's quantity.

        **Validates: Requirements 6.3**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            self.assertIn(
                str(issue["quantity"]),
                rendered,
                f"Quantity '{issue['quantity']}' not found in rendered output",
            )

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_issue_date(self, data):
        """Rendered HTML contains each PPE Issue's issue_date.

        **Validates: Requirements 6.3**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            # frappe.format_value returns str(value), so issue_date appears as str
            self.assertIn(
                str(issue["issue_date"]),
                rendered,
                f"Issue date '{issue['issue_date']}' not found in rendered output",
            )

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_expiry_date_or_na(self, data):
        """Rendered HTML contains each PPE Issue's expiry_date (or "N/A" if None).

        **Validates: Requirements 6.3**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            if issue["expiry_date"]:
                self.assertIn(
                    str(issue["expiry_date"]),
                    rendered,
                    f"Expiry date '{issue['expiry_date']}' not found in rendered output",
                )
            else:
                # Template uses: {{ ... if issue.expiry_date else "N/A" }}
                self.assertIn(
                    "N/A",
                    rendered,
                    "Expected 'N/A' for missing expiry_date not found in rendered output",
                )

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_condition(self, data):
        """Rendered HTML contains correct condition: "Returned" for Casual, "New" otherwise.

        **Validates: Requirements 6.3**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            expected_condition = "Returned" if issue["issue_type"] == "Casual" else "New"
            self.assertIn(
                expected_condition,
                rendered,
                f"Condition '{expected_condition}' not found in rendered output "
                f"(issue_type='{issue['issue_type']}')",
            )

    @given(data=acknowledgement_dataset())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_rendered_output_contains_size_or_na(self, data):
        """Rendered HTML contains each issue's size value or "N/A" if empty.

        **Validates: Requirements 17.7**
        """
        doc_data, issues_list = data
        rendered = self._build_jinja_env_and_render(doc_data, issues_list)

        for issue in issues_list:
            expected_size = issue["size"] if issue["size"] else "N/A"
            self.assertIn(
                expected_size,
                rendered,
                f"Size '{expected_size}' not found in rendered output",
            )


if __name__ == "__main__":
    unittest.main()
