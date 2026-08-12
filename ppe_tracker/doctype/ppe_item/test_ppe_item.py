# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the PPE Item DocType controller.

Tests validate() behaviour for:
- Non-PPE item group raises ValidationError (Requirement 1.2)
- Zero/invalid default_lifespan raises ValidationError (Requirement 1.5)
- Duplicate position_type in Lifespan table raises ValidationError (Requirement 1.4)
- Valid PPE Item with two unique Lifespan rows saves successfully (Requirements 1.5, 1.6)
"""

import unittest
from unittest.mock import patch, MagicMock

from frappe.exceptions import ValidationError


def _make_ppe_item(item_code="TEST-PPE-001", default_lifespan=6, lifespan_table=None):
	"""Create a mock PPE Item document with given field values."""
	doc = MagicMock()
	doc.item_code = item_code
	doc.default_lifespan = default_lifespan
	doc.lifespan_table = lifespan_table or []
	return doc


def _make_lifespan_row(position_type, lifespan, idx=1):
	"""Create a mock PPE Item Lifespan child row."""
	row = MagicMock()
	row.position_type = position_type
	row.lifespan = lifespan
	row.idx = idx
	return row


class TestPPEItem(unittest.TestCase):
	"""Unit tests for PPE Item validate() method.

	Requirements: 1.2, 1.4, 1.5, 1.6
	"""

	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value="General")
	def test_non_ppe_item_group_raises_error(self, mock_get_value, mock_throw):
		"""Save with non-PPE item group raises ValidationError.

		Requirement 1.2: The linked Item must belong to item group 'PPE';
		if not, the system raises a validation error and prevents saving.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

		doc = _make_ppe_item(item_code="ITEM-GENERAL-001", default_lifespan=6)

		with self.assertRaises(ValidationError):
			PPEItem.validate(doc)

		mock_get_value.assert_called_once_with("Item", "ITEM-GENERAL-001", "item_group")

	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value="PPE")
	def test_zero_default_lifespan_raises_error(self, mock_get_value, mock_throw):
		"""Save with default_lifespan = 0 raises ValidationError.

		Requirement 1.5: A PPE Item with default lifespan less than 1
		must raise a validation error and prevent saving.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

		doc = _make_ppe_item(default_lifespan=0)

		with self.assertRaises(ValidationError):
			PPEItem.validate(doc)

	@patch("frappe.throw", side_effect=ValidationError)
	@patch("frappe.db.get_value", return_value="PPE")
	def test_duplicate_position_type_raises_error(self, mock_get_value, mock_throw):
		"""Save with duplicate position_type in Lifespan table raises ValidationError.

		Requirement 1.4: No two rows in the PPE Item Lifespan child table
		can share the same Position Type value.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

		row1 = _make_lifespan_row(position_type="Heavy Duty", lifespan=3, idx=1)
		row2 = _make_lifespan_row(position_type="Heavy Duty", lifespan=6, idx=2)
		doc = _make_ppe_item(default_lifespan=6, lifespan_table=[row1, row2])

		with self.assertRaises(ValidationError):
			PPEItem.validate(doc)

	@patch("frappe.throw")
	@patch("frappe.db.get_value", return_value="PPE")
	def test_valid_ppe_item_with_two_lifespan_rows(self, mock_get_value, mock_throw):
		"""Valid PPE Item with two unique Lifespan rows saves successfully.

		Requirements 1.2, 1.4, 1.5, 1.6: A PPE Item with item_group='PPE',
		valid default_lifespan (>= 1), and unique position types in the
		lifespan table should pass validate() without raising any error.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_item.ppe_item import PPEItem

		row1 = _make_lifespan_row(position_type="Heavy Duty", lifespan=6, idx=1)
		row2 = _make_lifespan_row(position_type="Standard", lifespan=12, idx=2)
		doc = _make_ppe_item(default_lifespan=12, lifespan_table=[row1, row2])

		# Should NOT raise any exception
		PPEItem.validate(doc)

		# frappe.throw should never have been called
		mock_throw.assert_not_called()


if __name__ == "__main__":
	unittest.main()
