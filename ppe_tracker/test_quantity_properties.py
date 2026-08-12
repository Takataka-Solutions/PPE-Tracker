# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for PPE Request max quantity validation.

Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity

**Validates: Requirements 24.1, 24.2**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis.strategies import integers, composite, text, sampled_from


@composite
def exceeding_quantity_scenario(draw):
    """Generate a scenario where requested_quantity exceeds the role assignment quantity.

    Returns a dict with:
      - assigned_quantity: the max quantity allowed by PPE Role Assignment Item (1..50)
      - requested_quantity: a quantity strictly greater than assigned_quantity
      - department: a department name
      - designation: a designation name
      - employee_name: an employee identifier
      - ppe_item: a PPE item identifier
      - assignment_names: list of matching PPE Role Assignment names
    """
    assigned_quantity = draw(integers(min_value=1, max_value=50))
    # requested_quantity is always greater than assigned_quantity
    excess = draw(integers(min_value=1, max_value=100))
    requested_quantity = assigned_quantity + excess

    department = f"Department-{draw(integers(min_value=1, max_value=100))}"
    designation = f"Designation-{draw(integers(min_value=1, max_value=100))}"
    employee_name = f"EMP-{draw(integers(min_value=1, max_value=9999)):04d}"
    ppe_item = f"PPE-ITEM-{draw(integers(min_value=1, max_value=50)):03d}"
    assignment_names = [f"PRA-{draw(integers(min_value=1, max_value=9999)):04d}"]

    return {
        "assigned_quantity": assigned_quantity,
        "requested_quantity": requested_quantity,
        "department": department,
        "designation": designation,
        "employee_name": employee_name,
        "ppe_item": ppe_item,
        "assignment_names": assignment_names,
    }


@composite
def within_limit_quantity_scenario(draw):
    """Generate a scenario where requested_quantity is within the role assignment limit.

    Returns a dict with:
      - assigned_quantity: the max quantity allowed by PPE Role Assignment Item (1..50)
      - requested_quantity: a quantity <= assigned_quantity (>= 1)
      - department: a department name
      - designation: a designation name
      - employee_name: an employee identifier
      - ppe_item: a PPE item identifier
      - assignment_names: list of matching PPE Role Assignment names
    """
    assigned_quantity = draw(integers(min_value=1, max_value=50))
    requested_quantity = draw(integers(min_value=1, max_value=assigned_quantity))

    department = f"Department-{draw(integers(min_value=1, max_value=100))}"
    designation = f"Designation-{draw(integers(min_value=1, max_value=100))}"
    employee_name = f"EMP-{draw(integers(min_value=1, max_value=9999)):04d}"
    ppe_item = f"PPE-ITEM-{draw(integers(min_value=1, max_value=50)):03d}"
    assignment_names = [f"PRA-{draw(integers(min_value=1, max_value=9999)):04d}"]

    return {
        "assigned_quantity": assigned_quantity,
        "requested_quantity": requested_quantity,
        "department": department,
        "designation": designation,
        "employee_name": employee_name,
        "ppe_item": ppe_item,
        "assignment_names": assignment_names,
    }


class TestRequestedQuantityCannotExceedRoleAssignment(unittest.TestCase):
    """Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity

    WHEN a PPE Request is saved, THE System SHALL validate that the
    requested_quantity does not exceed the quantity specified in the matching
    PPE Role Assignment Item for that employee's department/designation and PPE Item.

    IF the requested quantity exceeds the assigned quantity, THEN THE System SHALL
    raise a validation error with a message indicating the maximum allowed quantity.

    Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
    **Validates: Requirements 24.1, 24.2**
    """

    @given(scenario=exceeding_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_exceeding_quantity_always_raises_validation_error(self, scenario):
        """For any requested_quantity > assigned_quantity, _validate_max_quantity()
        SHALL call frappe.throw() with an error message indicating the maximum.

        Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.1, 24.2**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

        assigned_qty = scenario["assigned_quantity"]
        requested_qty = scenario["requested_quantity"]
        department = scenario["department"]
        designation = scenario["designation"]
        employee_name = scenario["employee_name"]
        ppe_item = scenario["ppe_item"]
        assignment_names = scenario["assignment_names"]

        # Create a mock PPERequest instance
        mock_self = MagicMock(spec=PPERequest)
        mock_self.employee = employee_name
        mock_self.ppe_item = ppe_item
        mock_self.requested_quantity = requested_qty

        # Mock the employee document with department and designation
        mock_employee = MagicMock()
        mock_employee.department = department
        mock_employee.designation = designation

        # Mock the matching PPE Role Assignment Item rows
        mock_assignment_item = MagicMock()
        mock_assignment_item.quantity = assigned_qty
        matching_items = [mock_assignment_item]

        throw_called = False
        throw_message = ""

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_called, throw_message
            throw_called = True
            throw_message = str(msg)
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe"
        ) as mock_frappe:
            mock_frappe.get_doc.return_value = mock_employee
            mock_frappe.get_all.side_effect = [
                # First call: get matching PPE Role Assignment names
                assignment_names,
                # Second call: get matching PPE Role Assignment Item rows
                matching_items,
            ]
            mock_frappe.throw = mock_throw
            mock_frappe.bold = lambda x: x  # passthrough for frappe.bold

            try:
                PPERequest._validate_max_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: frappe.throw was called — validation error raised
        self.assertTrue(
            throw_called,
            f"Expected frappe.throw() when requested_quantity ({requested_qty}) "
            f"> assigned_quantity ({assigned_qty}), but it was not called.",
        )

        # ASSERTION: Error message mentions the maximum allowed quantity
        self.assertIn(
            str(assigned_qty),
            throw_message,
            f"Error message should mention max allowed quantity ({assigned_qty}). "
            f"Got: {throw_message}",
        )

    @given(scenario=within_limit_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_quantity_within_limit_does_not_raise(self, scenario):
        """For any requested_quantity <= assigned_quantity, _validate_max_quantity()
        SHALL NOT call frappe.throw(). The request is valid.

        Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.1, 24.2**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

        assigned_qty = scenario["assigned_quantity"]
        requested_qty = scenario["requested_quantity"]
        department = scenario["department"]
        designation = scenario["designation"]
        employee_name = scenario["employee_name"]
        ppe_item = scenario["ppe_item"]
        assignment_names = scenario["assignment_names"]

        # Create a mock PPERequest instance
        mock_self = MagicMock(spec=PPERequest)
        mock_self.employee = employee_name
        mock_self.ppe_item = ppe_item
        mock_self.requested_quantity = requested_qty

        # Mock the employee document with department and designation
        mock_employee = MagicMock()
        mock_employee.department = department
        mock_employee.designation = designation

        # Mock the matching PPE Role Assignment Item rows
        mock_assignment_item = MagicMock()
        mock_assignment_item.quantity = assigned_qty
        matching_items = [mock_assignment_item]

        throw_called = False

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_called
            throw_called = True
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe"
        ) as mock_frappe:
            mock_frappe.get_doc.return_value = mock_employee
            mock_frappe.get_all.side_effect = [
                # First call: get matching PPE Role Assignment names
                assignment_names,
                # Second call: get matching PPE Role Assignment Item rows
                matching_items,
            ]
            mock_frappe.throw = mock_throw
            mock_frappe.bold = lambda x: x

            try:
                PPERequest._validate_max_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: frappe.throw was NOT called — request is within limits
        self.assertFalse(
            throw_called,
            f"frappe.throw() should NOT be called when requested_quantity ({requested_qty}) "
            f"<= assigned_quantity ({assigned_qty}), but it was called.",
        )

    @given(scenario=exceeding_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_max_across_multiple_assignments_is_used(self, scenario):
        """When multiple PPE Role Assignment Items match, the maximum quantity
        across all matching rows is used as the cap. If requested_quantity exceeds
        even the highest allowed quantity, validation SHALL fail.

        Feature: tts-ppe-tracker, Property 25: Requested Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.1, 24.2**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

        # Create multiple assignment items, each with quantity <= assigned_quantity
        # The max of all is assigned_quantity (from scenario)
        assigned_qty = scenario["assigned_quantity"]
        requested_qty = scenario["requested_quantity"]
        department = scenario["department"]
        designation = scenario["designation"]
        employee_name = scenario["employee_name"]
        ppe_item = scenario["ppe_item"]

        # Multiple assignment names
        assignment_names = [f"PRA-{i:04d}" for i in range(1, 4)]

        # Multiple matching item rows — the max is assigned_qty
        mock_item_1 = MagicMock()
        mock_item_1.quantity = max(1, assigned_qty - 2)
        mock_item_2 = MagicMock()
        mock_item_2.quantity = assigned_qty  # This is the max
        mock_item_3 = MagicMock()
        mock_item_3.quantity = max(1, assigned_qty - 1)
        matching_items = [mock_item_1, mock_item_2, mock_item_3]

        mock_self = MagicMock(spec=PPERequest)
        mock_self.employee = employee_name
        mock_self.ppe_item = ppe_item
        mock_self.requested_quantity = requested_qty

        mock_employee = MagicMock()
        mock_employee.department = department
        mock_employee.designation = designation

        throw_called = False

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_called
            throw_called = True
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request.frappe"
        ) as mock_frappe:
            mock_frappe.get_doc.return_value = mock_employee
            mock_frappe.get_all.side_effect = [
                assignment_names,
                matching_items,
            ]
            mock_frappe.throw = mock_throw
            mock_frappe.bold = lambda x: x

            try:
                PPERequest._validate_max_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: Even with multiple assignments, exceeding the max still raises
        self.assertTrue(
            throw_called,
            f"Expected frappe.throw() when requested_quantity ({requested_qty}) "
            f"> max assigned_quantity ({assigned_qty}) across multiple assignments.",
        )


# ---------------------------------------------------------------------------
# Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity
# ---------------------------------------------------------------------------

"""
Feature: tts-ppe-tracker, Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity

**Validates: Requirements 24.3, 24.4**
"""


@composite
def exceeding_issued_quantity_scenario(draw):
    """Generate a scenario where existing active issues + new issue quantity exceeds assignment cap.

    Returns a dict with:
      - max_allowed_quantity: the cap from PPE Role Assignment Item (1..50)
      - existing_total: total quantity already actively issued (0..max_allowed_quantity)
      - new_quantity: quantity on the new PPE Issue such that existing_total + new_quantity > max_allowed_quantity
      - department: a department name
      - designation: a designation name
      - employee_name: an employee identifier
      - ppe_item: a PPE item identifier
      - assignment_name: a PPE Role Assignment name
      - issue_name: self.name for the current issue (excluded from existing total query)
    """
    max_allowed_quantity = draw(integers(min_value=1, max_value=50))
    # existing_total can be 0 up to max_allowed_quantity (already issued)
    existing_total = draw(integers(min_value=0, max_value=max_allowed_quantity))
    # remaining capacity
    remaining = max_allowed_quantity - existing_total
    # new_quantity must exceed the remaining capacity
    excess = draw(integers(min_value=1, max_value=100))
    new_quantity = remaining + excess

    department = f"Department-{draw(integers(min_value=1, max_value=100))}"
    designation = f"Designation-{draw(integers(min_value=1, max_value=100))}"
    employee_name = f"EMP-{draw(integers(min_value=1, max_value=9999)):04d}"
    ppe_item = f"PPE-ITEM-{draw(integers(min_value=1, max_value=50)):03d}"
    assignment_name = f"PRA-{draw(integers(min_value=1, max_value=9999)):04d}"
    issue_name = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):04d}"

    return {
        "max_allowed_quantity": max_allowed_quantity,
        "existing_total": existing_total,
        "new_quantity": new_quantity,
        "department": department,
        "designation": designation,
        "employee_name": employee_name,
        "ppe_item": ppe_item,
        "assignment_name": assignment_name,
        "issue_name": issue_name,
    }


@composite
def within_limit_issued_quantity_scenario(draw):
    """Generate a scenario where existing active issues + new issue quantity stays within assignment cap.

    Returns a dict with:
      - max_allowed_quantity: the cap from PPE Role Assignment Item (1..50)
      - existing_total: total quantity already actively issued (0..max_allowed_quantity - 1)
      - new_quantity: quantity on the new PPE Issue such that existing_total + new_quantity <= max_allowed_quantity
      - department: a department name
      - designation: a designation name
      - employee_name: an employee identifier
      - ppe_item: a PPE item identifier
      - assignment_name: a PPE Role Assignment name
      - issue_name: self.name for the current issue (excluded from existing total query)
    """
    max_allowed_quantity = draw(integers(min_value=1, max_value=50))
    # existing_total is 0 to max_allowed_quantity - 1 (at least 1 remaining capacity needed)
    existing_total = draw(integers(min_value=0, max_value=max_allowed_quantity - 1))
    # remaining capacity
    remaining = max_allowed_quantity - existing_total
    # new_quantity is 1 up to remaining (inclusive) so total stays within cap
    new_quantity = draw(integers(min_value=1, max_value=remaining))

    department = f"Department-{draw(integers(min_value=1, max_value=100))}"
    designation = f"Designation-{draw(integers(min_value=1, max_value=100))}"
    employee_name = f"EMP-{draw(integers(min_value=1, max_value=9999)):04d}"
    ppe_item = f"PPE-ITEM-{draw(integers(min_value=1, max_value=50)):03d}"
    assignment_name = f"PRA-{draw(integers(min_value=1, max_value=9999)):04d}"
    issue_name = f"PPE-ISS-{draw(integers(min_value=1, max_value=9999)):04d}"

    return {
        "max_allowed_quantity": max_allowed_quantity,
        "existing_total": existing_total,
        "new_quantity": new_quantity,
        "department": department,
        "designation": designation,
        "employee_name": employee_name,
        "ppe_item": ppe_item,
        "assignment_name": assignment_name,
        "issue_name": issue_name,
    }


class TestTotalIssuedQuantityCannotExceedRoleAssignment(unittest.TestCase):
    """Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity

    WHEN a PPE Issue is submitted, THE System SHALL validate that the total issued
    quantity (current issue + any existing active issues for the same employee and
    PPE Item) does not exceed the assigned quantity from the PPE Role Assignment.

    IF the total would exceed the assigned quantity, THEN THE System SHALL raise a
    validation error and prevent submission.

    Feature: tts-ppe-tracker, Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity
    **Validates: Requirements 24.3, 24.4**
    """

    def _build_mock_issue(self, scenario):
        """Build a mock PPEIssue instance with the required fields."""
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_self = MagicMock(spec=PPEIssue)
        mock_self.employee = scenario["employee_name"]
        mock_self.ppe_item = scenario["ppe_item"]
        mock_self.quantity = scenario["new_quantity"]
        mock_self.name = scenario["issue_name"]
        return mock_self

    def _build_mock_employee(self, scenario):
        """Build a mock Employee document with department and designation."""
        mock_employee = MagicMock()
        mock_employee.get = lambda field: (
            scenario["department"] if field == "department"
            else scenario["designation"] if field == "designation"
            else None
        )
        return mock_employee

    def _build_mock_assignment(self, scenario):
        """Build a mock PPE Role Assignment document with matching required_items."""
        mock_assignment = MagicMock()
        mock_item_row = MagicMock()
        mock_item_row.ppe_item = scenario["ppe_item"]
        mock_item_row.quantity = scenario["max_allowed_quantity"]
        mock_assignment.required_items = [mock_item_row]
        return mock_assignment

    @given(scenario=exceeding_issued_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_exceeding_total_issued_quantity_raises_validation_error(self, scenario):
        """For any existing_total + new_quantity > max_allowed_quantity,
        _validate_max_issued_quantity() SHALL call frappe.throw().

        Feature: tts-ppe-tracker, Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.3, 24.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_self = self._build_mock_issue(scenario)
        mock_employee = self._build_mock_employee(scenario)
        mock_assignment = self._build_mock_assignment(scenario)

        throw_called = False
        throw_message = ""

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_called, throw_message
            throw_called = True
            throw_message = str(msg)
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe"
        ) as mock_frappe, patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue._",
            side_effect=lambda x: x,
        ):
            mock_frappe.get_doc.side_effect = lambda doctype, name: (
                mock_employee if doctype == "Employee"
                else mock_assignment if doctype == "PPE Role Assignment"
                else MagicMock()
            )
            mock_frappe.get_all.return_value = [scenario["assignment_name"]]
            # Mock db.sql to return existing_total
            mock_frappe.db.sql.return_value = [[scenario["existing_total"]]]
            mock_frappe.throw = mock_throw

            try:
                PPEIssue._validate_max_issued_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: frappe.throw was called — validation error raised
        self.assertTrue(
            throw_called,
            f"Expected frappe.throw() when existing_total ({scenario['existing_total']}) + "
            f"new_quantity ({scenario['new_quantity']}) = "
            f"{scenario['existing_total'] + scenario['new_quantity']} > "
            f"max_allowed ({scenario['max_allowed_quantity']}), but it was not called.",
        )

    @given(scenario=within_limit_issued_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_total_within_limit_does_not_raise(self, scenario):
        """For any existing_total + new_quantity <= max_allowed_quantity,
        _validate_max_issued_quantity() SHALL NOT call frappe.throw().

        Feature: tts-ppe-tracker, Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.3, 24.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_self = self._build_mock_issue(scenario)
        mock_employee = self._build_mock_employee(scenario)
        mock_assignment = self._build_mock_assignment(scenario)

        throw_called = False

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_called
            throw_called = True
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe"
        ) as mock_frappe, patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue._",
            side_effect=lambda x: x,
        ):
            mock_frappe.get_doc.side_effect = lambda doctype, name: (
                mock_employee if doctype == "Employee"
                else mock_assignment if doctype == "PPE Role Assignment"
                else MagicMock()
            )
            mock_frappe.get_all.return_value = [scenario["assignment_name"]]
            # Mock db.sql to return existing_total
            mock_frappe.db.sql.return_value = [[scenario["existing_total"]]]
            mock_frappe.throw = mock_throw

            try:
                PPEIssue._validate_max_issued_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: frappe.throw was NOT called — issue is within limit
        self.assertFalse(
            throw_called,
            f"frappe.throw() should NOT be called when existing_total ({scenario['existing_total']}) + "
            f"new_quantity ({scenario['new_quantity']}) = "
            f"{scenario['existing_total'] + scenario['new_quantity']} <= "
            f"max_allowed ({scenario['max_allowed_quantity']}), but it was called.",
        )

    @given(scenario=exceeding_issued_quantity_scenario())
    @settings(max_examples=25, deadline=None)
    def test_error_message_contains_relevant_quantities(self, scenario):
        """When validation fails, the error message SHALL contain the maximum allowed quantity
        so the user knows the limit.

        Feature: tts-ppe-tracker, Property 26: Total Issued Quantity Cannot Exceed Role Assignment Quantity
        **Validates: Requirements 24.3, 24.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import PPEIssue

        mock_self = self._build_mock_issue(scenario)
        mock_employee = self._build_mock_employee(scenario)
        mock_assignment = self._build_mock_assignment(scenario)

        throw_message = ""

        def mock_throw(msg, *args, **kwargs):
            nonlocal throw_message
            throw_message = str(msg)
            raise Exception("ValidationError")

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue.frappe"
        ) as mock_frappe, patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue._",
            side_effect=lambda x: x,
        ):
            mock_frappe.get_doc.side_effect = lambda doctype, name: (
                mock_employee if doctype == "Employee"
                else mock_assignment if doctype == "PPE Role Assignment"
                else MagicMock()
            )
            mock_frappe.get_all.return_value = [scenario["assignment_name"]]
            mock_frappe.db.sql.return_value = [[scenario["existing_total"]]]
            mock_frappe.throw = mock_throw

            try:
                PPEIssue._validate_max_issued_quantity(mock_self)
            except Exception:
                pass

        # ASSERTION: Error message mentions the maximum allowed quantity
        self.assertIn(
            str(scenario["max_allowed_quantity"]),
            throw_message,
            f"Error message should mention max allowed quantity ({scenario['max_allowed_quantity']}). "
            f"Got: {throw_message}",
        )


if __name__ == "__main__":
    unittest.main()
