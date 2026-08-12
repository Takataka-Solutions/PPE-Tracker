# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for Employee PPE Size controller validations.

Feature: ppe-tracker-enhancements-v2, Properties 20-24: Employee PPE Size Validation

**Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7**
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    composite,
    sampled_from,
    text,
    integers,
    lists,
    booleans,
    just,
)


MODULE_PATH = "ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@composite
def size_validation_scenario(draw):
    """Generate a scenario for testing size value validation.

    Returns a tuple of:
      - ppe_item: PPE Item name
      - item_code: linked ERPNext Item template code
      - attributes: list of attribute names on the template
      - valid_values_by_attr: dict mapping attribute name -> list of valid values
      - entered_size: the size value entered by user (may or may not be valid)
    """
    ppe_item = draw(text(min_size=3, max_size=15, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-"))
    item_code = draw(text(min_size=3, max_size=15, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"))

    # Generate 1-3 attributes
    num_attrs = draw(integers(min_value=1, max_value=3))
    attributes = [f"Attr-{i}" for i in range(num_attrs)]

    # Generate valid values for each attribute (2-5 values each)
    valid_values_by_attr = {}
    all_valid_values = []
    for attr in attributes:
        num_values = draw(integers(min_value=2, max_value=5))
        values = [f"{attr}-Val-{j}" for j in range(num_values)]
        valid_values_by_attr[attr] = values
        all_valid_values.extend(values)

    # Decide if entered_size is valid or invalid
    is_valid = draw(booleans())
    if is_valid and all_valid_values:
        entered_size = draw(sampled_from(all_valid_values))
    else:
        entered_size = draw(text(min_size=1, max_size=10, alphabet="xyz0123456789"))
        # Ensure it's truly invalid
        assume(entered_size not in all_valid_values)

    return (ppe_item, item_code, attributes, valid_values_by_attr, entered_size)


@composite
def variant_resolution_scenario(draw):
    """Generate a scenario for testing item variant auto-resolution.

    Returns a tuple of:
      - item_template: item code for the template
      - attribute: the size attribute name
      - size_value: the size value to resolve
      - variants: list of variant names
      - matching_variant: which variant matches (or None if none match)
    """
    item_template = draw(text(min_size=3, max_size=15, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"))
    attribute = draw(sampled_from(["Size", "Boot Size", "Glove Size", "Overall Size"]))
    size_value = draw(sampled_from(["S", "M", "L", "XL", "8", "9", "10", "11", "42", "44"]))

    # Generate 1-5 variants
    num_variants = draw(integers(min_value=1, max_value=5))
    variants = [f"{item_template}-{i:03d}" for i in range(num_variants)]

    # Decide which variant matches (always exactly one for this scenario)
    matching_idx = draw(integers(min_value=0, max_value=num_variants - 1))
    matching_variant = variants[matching_idx]

    return (item_template, attribute, size_value, variants, matching_variant, matching_idx)


@composite
def duplicate_ppe_items_scenario(draw):
    """Generate a child table with potential duplicate PPE Items.

    Returns a tuple of:
      - rows: list of dicts with ppe_item and idx
      - has_duplicates: whether any duplicates exist
    """
    # Generate 2-8 PPE Item names
    num_unique = draw(integers(min_value=2, max_value=6))
    unique_items = [f"PPE-ITEM-{i:03d}" for i in range(num_unique)]

    # Decide if we introduce duplicates
    has_duplicates = draw(booleans())

    if has_duplicates:
        # Pick a random number of rows (must be > num_unique to guarantee a dup)
        num_rows = draw(integers(min_value=num_unique + 1, max_value=num_unique + 4))
        rows = []
        for i in range(num_rows):
            if i < num_unique:
                ppe_item = unique_items[i]
            else:
                # Force a duplicate from the existing items
                ppe_item = draw(sampled_from(unique_items))
            rows.append({"ppe_item": ppe_item, "idx": i + 1})
    else:
        # All unique
        rows = [{"ppe_item": item, "idx": i + 1} for i, item in enumerate(unique_items)]

    # Recheck: confirm duplicates status
    seen = set()
    actual_has_duplicates = False
    for row in rows:
        if row["ppe_item"] in seen:
            actual_has_duplicates = True
            break
        seen.add(row["ppe_item"])

    return (rows, actual_has_duplicates)


@composite
def one_record_per_employee_scenario(draw):
    """Generate a scenario for testing one-record-per-employee constraint.

    Returns a tuple of:
      - employee: employee ID
      - is_new: whether the document is new
      - existing_record: whether an existing record already exists for this employee
    """
    employee = draw(text(min_size=5, max_size=15, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"))
    is_new = draw(booleans())
    existing_record = draw(booleans())

    return (employee, is_new, existing_record)


@composite
def prepopulate_scenario(draw):
    """Generate a scenario for testing pre-population from Role Assignment.

    Returns a tuple of:
      - employee_name: employee ID
      - department: department name (or None)
      - designation: designation name (or None)
      - assignments: list of assignment names
      - assignment_items: dict mapping assignment_name -> list of (ppe_item, has_sizes) tuples
    """
    employee_name = draw(text(min_size=5, max_size=12, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789"))

    # At least one of department/designation must be set for prepopulation to work
    has_dept = draw(booleans())
    has_desig = draw(booleans())
    assume(has_dept or has_desig)

    department = f"DEPT-{draw(text(min_size=2, max_size=5, alphabet='ABCDEFGH'))}" if has_dept else None
    designation = f"DESIG-{draw(text(min_size=2, max_size=5, alphabet='ABCDEFGH'))}" if has_desig else None

    # Generate 1-3 matching assignments
    num_assignments = draw(integers(min_value=1, max_value=3))
    assignments = [f"PRA-{i:03d}" for i in range(num_assignments)]

    # Generate items for each assignment (2-4 items per assignment)
    assignment_items = {}
    for assignment_name in assignments:
        num_items = draw(integers(min_value=2, max_value=4))
        items = []
        for j in range(num_items):
            ppe_item = f"PPE-{assignment_name}-{j:02d}"
            has_sizes = draw(booleans())
            items.append((ppe_item, has_sizes))
        assignment_items[assignment_name] = items

    return (employee_name, department, designation, assignments, assignment_items)


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

class TestSizeValueMustMatchTemplateAttribute(unittest.TestCase):
    """Property 20: Size Value Must Match Template Attribute

    For any PPE Size Item row, the entered size value SHALL match one of the valid
    attribute values defined on the linked PPE Item's ERPNext Item Template; if the
    size does not match any attribute value, the system SHALL reject with a validation error.

    Feature: ppe-tracker-enhancements-v2, Property 20: Size Value Must Match Template Attribute
    **Validates: Requirements 16.3**
    """

    @given(scenario=size_validation_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_size_value_validation(self, scenario):
        """Size must match a valid attribute value on the template; reject otherwise.

        Feature: ppe-tracker-enhancements-v2, Property 20: Size Value Must Match Template Attribute
        **Validates: Requirements 16.3**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size import EmployeePPESize

        ppe_item, item_code, attributes, valid_values_by_attr, entered_size = scenario

        # Compute all valid values and expected result
        all_valid_values = []
        for attr_values in valid_values_by_attr.values():
            all_valid_values.extend(attr_values)
        size_is_valid = entered_size in all_valid_values

        # Build mock self
        mock_self = MagicMock(spec=EmployeePPESize)
        mock_row = MagicMock()
        mock_row.ppe_item = ppe_item
        mock_row.size = entered_size
        mock_row.idx = 1
        mock_row.item_variant = None
        mock_self.ppe_size_items = [mock_row]

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            # Mock frappe.db.get_value to return item_code for the PPE Item
            mock_frappe.db.get_value.return_value = item_code

            # Mock frappe.get_all for Item Variant Attribute (attributes on template)
            attr_records = [MagicMock(attribute=attr) for attr in attributes]
            # Mock frappe.get_all for Item Attribute Value (valid values per attribute)
            attr_value_lists = [valid_values_by_attr[attr] for attr in attributes]

            # frappe.get_all is called multiple times:
            # 1. For Item Variant Attribute (attributes list)
            # 2. For Item Attribute Value (for each attribute)
            call_count = [0]

            def mock_get_all(doctype, **kwargs):
                call_count[0] += 1
                if doctype == "Item Variant Attribute":
                    return attr_records
                elif doctype == "Item Attribute Value":
                    # Determine which attribute is being queried
                    parent_attr = kwargs.get("filters", {}).get("parent", "")
                    if parent_attr in valid_values_by_attr:
                        return valid_values_by_attr[parent_attr]
                    return []
                elif doctype == "Item":
                    # For variant resolution (called if size is valid)
                    return []
                return []

            mock_frappe.get_all.side_effect = mock_get_all
            mock_frappe.throw = MagicMock(side_effect=Exception("validation_error"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold = lambda x: f"<b>{x}</b>"

            # Mock _get_item_variant for valid sizes (it will be called if size passes validation)
            mock_self._get_item_variant = MagicMock(return_value="VARIANT-001")

            if size_is_valid:
                # Should NOT throw for invalid size — proceed to variant resolution
                try:
                    EmployeePPESize._validate_and_resolve_sizes(mock_self)
                    # If it gets here, no throw happened for size validation
                except Exception:
                    # It might throw for variant resolution (no variant found)
                    # but we only care that it didn't throw for size mismatch
                    pass
                # Verify throw was not called for size mismatch
                # (it might be called for missing variant, which is a different check)
                for call_args in mock_frappe.throw.call_args_list:
                    msg = str(call_args)
                    self.assertNotIn("is not a valid option", msg)
            else:
                # Should throw because size doesn't match any valid attribute value
                with self.assertRaises(Exception):
                    EmployeePPESize._validate_and_resolve_sizes(mock_self)
                # Verify throw was called
                mock_frappe.throw.assert_called()


class TestItemVariantAutoResolution(unittest.TestCase):
    """Property 21: Item Variant Auto-Resolution

    For any valid combination of PPE Item (with has_sizes=1) and a size value matching
    a template attribute, the system SHALL resolve and populate the item_variant field
    with the ERPNext Item Variant that matches the template + size attribute value.

    Feature: ppe-tracker-enhancements-v2, Property 21: Item Variant Auto-Resolution
    **Validates: Requirements 16.4**
    """

    @given(scenario=variant_resolution_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_item_variant_auto_resolution(self, scenario):
        """Resolve correct Item Variant for valid PPE Item + size combination.

        Feature: ppe-tracker-enhancements-v2, Property 21: Item Variant Auto-Resolution
        **Validates: Requirements 16.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size import EmployeePPESize

        item_template, attribute, size_value, variants, matching_variant, matching_idx = scenario

        # Build mock self
        mock_self = MagicMock(spec=EmployeePPESize)

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            # Mock frappe.get_all for Item variants query
            mock_frappe.get_all.return_value = variants

            # Mock frappe.db.exists to return True only for the matching variant
            def mock_db_exists(doctype, filters):
                if doctype == "Item Variant Attribute":
                    parent = filters.get("parent", "")
                    attr = filters.get("attribute", "")
                    value = filters.get("attribute_value", "")
                    if parent == matching_variant and attr == attribute and value == size_value:
                        return True
                return False

            mock_frappe.db.exists.side_effect = mock_db_exists
            mock_frappe.throw = MagicMock(side_effect=Exception("validation_error"))
            mock_frappe._ = lambda x: x

            # Call _get_item_variant
            result = EmployeePPESize._get_item_variant(mock_self, item_template, attribute, size_value)

            # ASSERTION: The correct variant should be returned
            self.assertEqual(result, matching_variant)

            # ASSERTION: frappe.throw should NOT be called (valid resolution)
            mock_frappe.throw.assert_not_called()


class TestPPEItemUniquenessInEmployeePPESize(unittest.TestCase):
    """Property 22: PPE Item Uniqueness in Employee PPE Size

    For any Employee PPE Size record, the system SHALL reject saving if the child table
    contains duplicate PPE Item entries, and accept when all PPE Items are unique.

    Feature: ppe-tracker-enhancements-v2, Property 22: PPE Item Uniqueness in Employee PPE Size
    **Validates: Requirements 16.5**
    """

    @given(scenario=duplicate_ppe_items_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_duplicate_ppe_items_rejected(self, scenario):
        """Reject if child table contains duplicate PPE Items; accept if all unique.

        Feature: ppe-tracker-enhancements-v2, Property 22: PPE Item Uniqueness in Employee PPE Size
        **Validates: Requirements 16.5**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size import EmployeePPESize

        rows, has_duplicates = scenario

        # Build mock self with child table rows
        mock_self = MagicMock(spec=EmployeePPESize)
        mock_rows = []
        for row in rows:
            mock_row = MagicMock()
            mock_row.ppe_item = row["ppe_item"]
            mock_row.idx = row["idx"]
            mock_rows.append(mock_row)
        mock_self.ppe_size_items = mock_rows

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("validation_error"))
            mock_frappe._ = lambda x: x

            if has_duplicates:
                # ASSERTION: frappe.throw MUST be called for duplicates
                with self.assertRaises(Exception):
                    EmployeePPESize._validate_no_duplicate_ppe_items(mock_self)
                mock_frappe.throw.assert_called_once()
            else:
                # ASSERTION: frappe.throw should NOT be called for unique items
                EmployeePPESize._validate_no_duplicate_ppe_items(mock_self)
                mock_frappe.throw.assert_not_called()


class TestOneEmployeePPESizeRecordPerEmployee(unittest.TestCase):
    """Property 23: One Employee PPE Size Record Per Employee

    For any Employee, the system SHALL prevent creation of more than one Employee PPE Size
    record — rejecting creation if a record already exists for that employee.

    Feature: ppe-tracker-enhancements-v2, Property 23: One Employee PPE Size Record Per Employee
    **Validates: Requirements 16.6**
    """

    @given(scenario=one_record_per_employee_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_one_record_per_employee(self, scenario):
        """Prevent creation of duplicate records for same employee.

        Feature: ppe-tracker-enhancements-v2, Property 23: One Employee PPE Size Record Per Employee
        **Validates: Requirements 16.6**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size import EmployeePPESize

        employee, is_new, existing_record = scenario

        # Build mock self (don't use spec= because is_new() is inherited from Document)
        mock_self = MagicMock()
        mock_self.employee = employee
        mock_self.name = f"EPS-{employee}"
        mock_self.is_new.return_value = is_new

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            mock_frappe.throw = MagicMock(side_effect=Exception("validation_error"))
            mock_frappe._ = lambda x: x
            mock_frappe.bold.return_value = f"<b>{employee}</b>"

            # Mock frappe.db.exists
            if existing_record:
                mock_frappe.db.exists.return_value = f"EPS-EXISTING-{employee}"
            else:
                mock_frappe.db.exists.return_value = None

            should_throw = is_new and existing_record

            if should_throw:
                # ASSERTION: frappe.throw MUST be called when new + existing record
                with self.assertRaises(Exception):
                    EmployeePPESize._validate_one_record_per_employee(mock_self)
                mock_frappe.throw.assert_called_once()
            else:
                # ASSERTION: frappe.throw should NOT be called
                EmployeePPESize._validate_one_record_per_employee(mock_self)
                mock_frappe.throw.assert_not_called()


class TestPrePopulateSizedItemsFromRoleAssignment(unittest.TestCase):
    """Property 24: Pre-Populate Sized Items From Role Assignment

    For any new Employee PPE Size record, the system SHALL pre-populate the child table
    with PPE Items that are required for the employee's designation per PPE Role Assignment
    AND have has_sizes = 1 enabled.

    Feature: ppe-tracker-enhancements-v2, Property 24: Pre-Populate Sized Items From Role Assignment
    **Validates: Requirements 16.7**
    """

    @given(scenario=prepopulate_scenario())
    @settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_prepopulate_from_role_assignment(self, scenario):
        """New Employee PPE Size record pre-populates with required sized PPE Items.

        Feature: ppe-tracker-enhancements-v2, Property 24: Pre-Populate Sized Items From Role Assignment
        **Validates: Requirements 16.7**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.employee_ppe_size.employee_ppe_size import EmployeePPESize

        employee_name, department, designation, assignments, assignment_items = scenario

        # Build mock self
        mock_self = MagicMock(spec=EmployeePPESize)
        mock_self.employee = employee_name
        appended_items = []

        def mock_append(table_name, row_dict):
            appended_items.append(row_dict)

        mock_self.append = mock_append

        with patch(f"{MODULE_PATH}.frappe") as mock_frappe:
            # Mock frappe.get_doc for Employee
            mock_employee = MagicMock()
            mock_employee.get.side_effect = lambda field: department if field == "department" else designation if field == "designation" else None

            # Mock frappe.get_doc to return employee or assignment docs
            def mock_get_doc(doctype, name=None):
                if doctype == "Employee":
                    return mock_employee
                elif doctype == "PPE Role Assignment":
                    mock_assignment = MagicMock()
                    items = assignment_items.get(name, [])
                    mock_items = []
                    for ppe_item, has_sizes in items:
                        mock_item = MagicMock()
                        mock_item.ppe_item = ppe_item
                        mock_items.append(mock_item)
                    mock_assignment.required_items = mock_items
                    return mock_assignment
                return MagicMock()

            mock_frappe.get_doc.side_effect = mock_get_doc

            # Mock frappe.get_all for PPE Role Assignments
            mock_frappe.get_all.return_value = assignments

            # Mock frappe.db.get_value for PPE Item has_sizes
            def mock_get_value(doctype, name, field):
                if doctype == "PPE Item" and field == "has_sizes":
                    # Look up has_sizes from our test data
                    for assignment_name, items in assignment_items.items():
                        for ppe_item, has_sizes in items:
                            if ppe_item == name:
                                return has_sizes
                return None

            mock_frappe.db.get_value.side_effect = mock_get_value

            # Call the method
            EmployeePPESize._prepopulate_from_role_assignment(mock_self)

            # Compute expected: unique PPE Items with has_sizes=1 across all assignments
            expected_sized_items = set()
            for assignment_name in assignments:
                for ppe_item, has_sizes in assignment_items[assignment_name]:
                    if has_sizes:
                        expected_sized_items.add(ppe_item)

            # ASSERTION 1: Number of appended rows equals number of unique sized items
            self.assertEqual(len(appended_items), len(expected_sized_items))

            # ASSERTION 2: All appended items are from the expected set
            appended_ppe_items = {row["ppe_item"] for row in appended_items}
            self.assertEqual(appended_ppe_items, expected_sized_items)

            # ASSERTION 3: Each appended row has the correct structure
            for row in appended_items:
                self.assertIn("ppe_item", row)
                self.assertIn(row["ppe_item"], expected_sized_items)


if __name__ == "__main__":
    unittest.main()
