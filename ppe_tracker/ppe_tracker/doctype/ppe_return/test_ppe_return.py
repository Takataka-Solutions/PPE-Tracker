# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the PPE Return DocType controller.

Tests validate() and on_submit()/on_cancel() behaviour for:
- Return quantity exceeds issued quantity raises error (Requirement 5.5)
- Return against 'Returned' PPE Issue raises error (Requirement 5.6)
- Return against 'Replaced' PPE Issue raises error (Requirement 5.6)
- Successful submit sets PPE Issue status to 'Returned' (Requirement 5.2)
- Cancel reverts PPE Issue status to 'Active' (Requirement 5.2)
- Condition 'Good' creates Material Receipt Stock Entry (Requirement 5.3)
- Condition 'Damaged' does NOT create Stock Entry (Requirement 5.4)
- Condition 'Unusable' does NOT create Stock Entry (Requirement 5.4)
"""

import unittest
from unittest.mock import patch, MagicMock

from frappe.exceptions import ValidationError


def _make_ppe_return(
	ppe_issue="ISS-001",
	employee="EMP-001",
	ppe_item="PPE-HELMET",
	return_date="2024-06-15",
	quantity_returned=1,
	condition="Good",
	stock_entry=None,
	name="RET-001",
):
	"""Create a mock PPE Return document with given field values."""
	doc = MagicMock()
	doc.ppe_issue = ppe_issue
	doc.employee = employee
	doc.ppe_item = ppe_item
	doc.return_date = return_date
	doc.quantity_returned = quantity_returned
	doc.condition = condition
	doc.stock_entry = stock_entry
	doc.name = name
	return doc


class TestPPEReturn(unittest.TestCase):
	"""Unit tests for PPE Return controller methods.

	Requirements: 5.2, 5.3, 5.4, 5.5, 5.6
	"""

	# ------------------------------------------------------------------
	# Validation Tests
	# ------------------------------------------------------------------

	@patch("frappe.bold", side_effect=lambda x: x)
	@patch("frappe._", side_effect=lambda x: x)
	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value=2)
	def test_return_quantity_exceeds_issued_quantity_raises_error(
		self, mock_get_value, mock_throw, mock_translate, mock_bold
	):
		"""_validate_quantity() raises ValidationError if quantity_returned > issued qty.

		Requirement 5.5: IF the quantity returned on a PPE Return record exceeds
		the original issued quantity on the linked PPE Issue, THEN THE System
		SHALL raise a validation error and prevent submission.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(ppe_issue="ISS-001", quantity_returned=5)

		with self.assertRaises(ValidationError):
			PPEReturn._validate_quantity(doc)

		mock_get_value.assert_called_once_with("PPE Issue", "ISS-001", "quantity")

	@patch("frappe.bold", side_effect=lambda x: x)
	@patch("frappe._", side_effect=lambda x: x)
	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value="Returned")
	def test_return_against_returned_issue_raises_error(
		self, mock_get_value, mock_throw, mock_translate, mock_bold
	):
		"""_validate_issue_status() raises ValidationError if PPE Issue status is 'Returned'.

		Requirement 5.6: IF a PPE Issue record already has a status of 'Returned',
		THEN THE System SHALL prevent the creation of a new PPE Return referencing
		that PPE Issue.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(ppe_issue="ISS-RETURNED")

		with self.assertRaises(ValidationError):
			PPEReturn._validate_issue_status(doc)

		mock_get_value.assert_called_once_with("PPE Issue", "ISS-RETURNED", "status")

	@patch("frappe.bold", side_effect=lambda x: x)
	@patch("frappe._", side_effect=lambda x: x)
	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value="Replaced")
	def test_return_against_replaced_issue_raises_error(
		self, mock_get_value, mock_throw, mock_translate, mock_bold
	):
		"""_validate_issue_status() raises ValidationError if PPE Issue status is 'Replaced'.

		Requirement 5.6: IF a PPE Issue record already has a status of 'Replaced',
		THEN THE System SHALL prevent the creation of a new PPE Return referencing
		that PPE Issue.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(ppe_issue="ISS-REPLACED")

		with self.assertRaises(ValidationError):
			PPEReturn._validate_issue_status(doc)

		mock_get_value.assert_called_once_with("PPE Issue", "ISS-REPLACED", "status")

	# ------------------------------------------------------------------
	# on_submit Tests
	# ------------------------------------------------------------------

	@patch("frappe.db.set_value")
	def test_successful_submit_sets_ppe_issue_status_to_returned(self, mock_set_value):
		"""on_submit() calls _update_issue_status('Returned') on the linked PPE Issue.

		Requirement 5.2: WHEN a PPE Return record is submitted, THE System SHALL
		update the status of the linked PPE Issue record to 'Returned'.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(ppe_issue="ISS-ACTIVE-001")

		PPEReturn._update_issue_status(doc, "Returned")

		mock_set_value.assert_called_once_with(
			"PPE Issue", "ISS-ACTIVE-001", "status", "Returned"
		)

	# ------------------------------------------------------------------
	# on_cancel Tests
	# ------------------------------------------------------------------

	@patch("frappe.db.set_value")
	def test_cancel_reverts_ppe_issue_status_to_active(self, mock_set_value):
		"""on_cancel() reverts the linked PPE Issue status back to 'Active'.

		Requirement 5.2 (inverse): WHEN a PPE Return is cancelled, THE System
		SHALL revert the PPE Issue status to 'Active'.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(ppe_issue="ISS-RETURNED-001", stock_entry=None)

		PPEReturn._update_issue_status(doc, "Active")

		mock_set_value.assert_called_once_with(
			"PPE Issue", "ISS-RETURNED-001", "status", "Active"
		)

	# ------------------------------------------------------------------
	# Stock Entry Creation Tests (condition-based)
	# ------------------------------------------------------------------

	@patch("frappe.db.get_single_value", return_value="Stores - TTS")
	@patch("frappe.db.get_value", return_value="ITEM-HELMET-001")
	@patch("frappe.new_doc")
	def test_condition_good_creates_material_receipt_stock_entry(
		self, mock_new_doc, mock_get_value, mock_get_single_value
	):
		"""_create_material_receipt_stock_entry() creates a Stock Entry when condition is 'Good'.

		Requirement 5.3: WHEN a PPE Return record is submitted with condition 'Good',
		THE System SHALL create a corresponding ERPNext Stock Entry of type
		'Material Receipt' to increment stock for the returned quantity.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		mock_se = MagicMock()
		mock_se.name = "SE-RET-001"
		mock_new_doc.return_value = mock_se

		doc = _make_ppe_return(
			ppe_item="PPE-HELMET",
			quantity_returned=3,
			condition="Good",
		)

		PPEReturn._create_material_receipt_stock_entry(doc)

		# Stock Entry was created
		mock_new_doc.assert_called_once_with("Stock Entry")
		mock_se.append.assert_called_once_with("items", {
			"item_code": "ITEM-HELMET-001",
			"qty": 3,
			"t_warehouse": "Stores - TTS",
		})
		mock_se.insert.assert_called_once()
		mock_se.submit.assert_called_once()
		doc.db_set.assert_called_once_with("stock_entry", "SE-RET-001")

	@patch("frappe.new_doc")
	def test_condition_damaged_does_not_create_stock_entry(self, mock_new_doc):
		"""_create_material_receipt_stock_entry() skips Stock Entry for 'Damaged' condition.

		Requirement 5.4: WHEN a PPE Return record is submitted with condition
		'Damaged', THE System SHALL NOT create a Stock Entry; the item is disposed.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(condition="Damaged")

		PPEReturn._create_material_receipt_stock_entry(doc)

		# No Stock Entry should be created
		mock_new_doc.assert_not_called()

	@patch("frappe.new_doc")
	def test_condition_unusable_does_not_create_stock_entry(self, mock_new_doc):
		"""_create_material_receipt_stock_entry() skips Stock Entry for 'Unusable' condition.

		Requirement 5.4: WHEN a PPE Return record is submitted with condition
		'Unusable', THE System SHALL NOT create a Stock Entry; the item is disposed.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

		doc = _make_ppe_return(condition="Unusable")

		PPEReturn._create_material_receipt_stock_entry(doc)

		# No Stock Entry should be created
		mock_new_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
