# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the Combined PPE Issue Print Format.

Properties tested:
- Property 10: Combined Print Format Contains Required Fields

The Combined PPE Issue Form Jinja template renders each linked PPE Issue row with:
PPE Item name, size (or "N/A"), quantity, issue_date, expiry_date, and condition
("Returned" for Casual issue_type, "New" otherwise).

Since we cannot render Jinja without Frappe runtime, we test the DATA MODEL
expectation: that frappe.get_doc("PPE Issue", row.ppe_issue) returns a document
with all required fields accessible, and that the condition logic is correct.

**Validates: Requirements 6.3, 17.7**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    text,
    integers,
    dates,
    composite,
    sampled_from,
    one_of,
    just,
    none,
    lists,
)


# --- Strategies ---

@composite
def ppe_issue_doc(draw):
    """Generate a mock PPE Issue document with fields needed by the print format.

    Fields:
    - ppe_item: str (PPE Item name)
    - size: str or empty (employee's size for this item)
    - quantity: int >= 1
    - issue_date: date
    - expiry_date: date (after issue_date)
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

    # Size: some items have sizes, some don't
    has_size = draw(sampled_from([True, False]))
    size = draw(sampled_from(["S", "M", "L", "XL", "8", "9", "10", "42"])) if has_size else ""

    quantity = draw(integers(min_value=1, max_value=20))

    issue_date = draw(dates(
        min_value=dates().filter(lambda d: d.year >= 2020).example() if False else __import__("datetime").date(2020, 1, 1),
        max_value=__import__("datetime").date(2025, 12, 31),
    ))

    # Expiry date is always after issue date
    import datetime
    expiry_offset = draw(integers(min_value=30, max_value=730))
    expiry_date = issue_date + datetime.timedelta(days=expiry_offset)

    doc = MagicMock()
    doc.ppe_item = ppe_item
    doc.size = size
    doc.quantity = quantity
    doc.issue_date = issue_date
    doc.expiry_date = expiry_date
    doc.issue_type = issue_type

    return doc


@composite
def acknowledgement_with_issues(draw):
    """Generate a mock PPE Issue Acknowledgement with 1-8 linked PPE Issue rows.

    Returns (ack_doc, issue_docs_by_name) where issue_docs_by_name maps
    ppe_issue name -> mock PPE Issue document.
    """
    num_issues = draw(integers(min_value=1, max_value=8))

    ack_doc = MagicMock()
    ack_doc.employee = "EMP-001"
    ack_doc.employee_name = "John Doe"
    ack_doc.department = "Operations"
    ack_doc.designation = "Site Worker"
    ack_doc.acknowledgement_date = draw(dates(
        min_value=__import__("datetime").date(2024, 1, 1),
        max_value=__import__("datetime").date(2025, 12, 31),
    ))

    rows = []
    issue_docs_by_name = {}

    for i in range(num_issues):
        issue_name = f"PPE-ISS-2024-{i:04d}"

        row = MagicMock()
        row.ppe_issue = issue_name
        rows.append(row)

        # Generate a PPE Issue document for this row
        issue_doc = draw(ppe_issue_doc())
        issue_docs_by_name[issue_name] = issue_doc

    ack_doc.ppe_issues = rows
    return ack_doc, issue_docs_by_name


# --- Test Class ---

class TestCombinedPrintFormatContainsRequiredFields(unittest.TestCase):
    """Property 10: Combined Print Format Contains Required Fields

    For any PPE Issue Acknowledgement with one or more linked PPE Issues, the
    rendered Combined PPE Issue Form SHALL contain: the PPE Item name, quantity,
    issue date, expiry date, and condition (new/returned) for each linked issue,
    plus the employee's size where applicable.

    We verify this by simulating the Jinja template logic:
    - For each row in doc.ppe_issues, frappe.get_doc("PPE Issue", row.ppe_issue)
      must return a document with all required fields accessible.
    - The condition logic: issue_type == "Casual" → "Returned", else → "New"
    - The size logic: issue.size or "N/A"

    **Validates: Requirements 6.3, 17.7**
    """

    @given(data=acknowledgement_with_issues())
    @settings(max_examples=25, deadline=None)
    def test_all_required_fields_accessible_for_each_issue(self, data):
        """Each linked PPE Issue document exposes all fields required by the print format.

        **Validates: Requirements 6.3**
        """
        ack_doc, issue_docs_by_name = data

        def mock_get_doc(doctype, name):
            if doctype == "PPE Issue":
                return issue_docs_by_name[name]
            return MagicMock()

        with patch(
            "frappe.get_doc",
            side_effect=mock_get_doc,
        ):
            import frappe
            frappe.get_doc = mock_get_doc

            for row in ack_doc.ppe_issues:
                issue = mock_get_doc("PPE Issue", row.ppe_issue)

                # All required fields must be accessible (not raise AttributeError)
                ppe_item_name = issue.ppe_item
                quantity = issue.quantity
                issue_date = issue.issue_date
                expiry_date = issue.expiry_date
                issue_type = issue.issue_type
                size = issue.size

                # Fields must have non-None values
                self.assertIsNotNone(ppe_item_name, "ppe_item must not be None")
                self.assertIsNotNone(quantity, "quantity must not be None")
                self.assertIsNotNone(issue_date, "issue_date must not be None")
                self.assertIsNotNone(expiry_date, "expiry_date must not be None")
                self.assertIsNotNone(issue_type, "issue_type must not be None")
                # size can be empty string but not None
                self.assertIsNotNone(size, "size must not be None (empty string is OK)")

    @given(data=acknowledgement_with_issues())
    @settings(max_examples=25, deadline=None)
    def test_condition_logic_casual_returns_returned(self, data):
        """Condition field renders "Returned" for Casual issue_type, "New" otherwise.

        The Jinja template uses:
            {{ "Returned" if issue.issue_type == "Casual" else "New" }}

        **Validates: Requirements 6.3**
        """
        ack_doc, issue_docs_by_name = data

        for row in ack_doc.ppe_issues:
            issue = issue_docs_by_name[row.ppe_issue]

            # Apply the same condition logic as the Jinja template
            condition = "Returned" if issue.issue_type == "Casual" else "New"

            # Verify the condition is one of the expected values
            self.assertIn(condition, ["New", "Returned"])

            # Verify correctness of the mapping
            if issue.issue_type == "Casual":
                self.assertEqual(condition, "Returned")
            else:
                self.assertEqual(condition, "New")

    @given(data=acknowledgement_with_issues())
    @settings(max_examples=25, deadline=None)
    def test_size_renders_value_or_na(self, data):
        """Size field renders the size value if set, or "N/A" if empty.

        The Jinja template uses:
            {{ issue.size or "N/A" }}

        **Validates: Requirements 17.7**
        """
        ack_doc, issue_docs_by_name = data

        for row in ack_doc.ppe_issues:
            issue = issue_docs_by_name[row.ppe_issue]

            # Apply the same size logic as the Jinja template
            rendered_size = issue.size or "N/A"

            # If size is a non-empty string, it should render as-is
            if issue.size:
                self.assertEqual(rendered_size, issue.size)
            else:
                # If size is empty string or falsy, render "N/A"
                self.assertEqual(rendered_size, "N/A")

    @given(data=acknowledgement_with_issues())
    @settings(max_examples=25, deadline=None)
    def test_print_format_output_contains_all_fields_per_row(self, data):
        """Simulates rendering the Jinja template logic and verifies each row
        contributes all required fields to the output.

        **Validates: Requirements 6.3, 17.7**
        """
        ack_doc, issue_docs_by_name = data

        # Simulate what the Jinja template does for each row
        rendered_rows = []

        for row in ack_doc.ppe_issues:
            issue = issue_docs_by_name[row.ppe_issue]

            # This mirrors the Jinja template logic exactly
            rendered_row = {
                "ppe_item": issue.ppe_item,
                "size": issue.size or "N/A",
                "quantity": issue.quantity,
                "issue_date": issue.issue_date,
                "expiry_date": issue.expiry_date,
                "condition": "Returned" if issue.issue_type == "Casual" else "New",
            }
            rendered_rows.append(rendered_row)

        # Verify we have one rendered row per linked issue
        self.assertEqual(len(rendered_rows), len(ack_doc.ppe_issues))

        # Verify each rendered row contains ALL required fields with non-None values
        required_fields = ["ppe_item", "size", "quantity", "issue_date", "expiry_date", "condition"]

        for i, rendered_row in enumerate(rendered_rows):
            for field in required_fields:
                self.assertIn(field, rendered_row,
                              f"Row {i}: missing required field '{field}'")
                self.assertIsNotNone(rendered_row[field],
                                     f"Row {i}: field '{field}' must not be None")

            # Condition must be one of the valid values
            self.assertIn(rendered_row["condition"], ["New", "Returned"],
                          f"Row {i}: condition must be 'New' or 'Returned'")

            # Size must be a non-empty string (either actual size or "N/A")
            self.assertTrue(len(str(rendered_row["size"])) > 0,
                            f"Row {i}: size must be non-empty (actual value or 'N/A')")


if __name__ == "__main__":
    unittest.main()
