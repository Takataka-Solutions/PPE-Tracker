# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Unit tests for PPE Tracker Settings DocType.

Tests cover:
- Valid configuration saves successfully (Requirements 1.1)
- Duplicate warehouse references raise validation error (Requirements 1.2)
- Non-existent warehouse reference raises validation error (Requirements 1.7)
- Disabled warehouse reference raises validation error (Requirements 1.7)
- Permission enforcement — System Manager and HR Manager access (Requirements 1.3)
"""

import unittest
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPPETrackerSettings(FrappeTestCase):
	"""Unit tests for PPE Tracker Settings Single DocType.

	Validates: Requirements 1.1, 1.2, 1.3, 1.7
	"""

	def _get_settings_doc(self):
		"""Return the PPE Tracker Settings singleton document."""
		return frappe.get_doc("PPE Tracker Settings")

	@patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe.db.get_value")
	def test_valid_configuration_saves_successfully(self, mock_get_value):
		"""Three distinct existing active warehouses should save without error.

		Validates: Requirements 1.1
		"""
		# Mock: all three warehouses exist and are active (disabled=0)
		def side_effect(doctype, name, fields, as_dict=False):
			if doctype == "Warehouse":
				return {"name": name, "disabled": 0}
			return None

		mock_get_value.side_effect = side_effect

		doc = self._get_settings_doc()
		doc.returned_ppe_warehouse = "Warehouse-A"
		doc.default_issue_warehouse = "Warehouse-B"
		doc.wornout_ppe_warehouse = "Warehouse-C"

		# Should not raise any exception
		doc.validate()

	@patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe.db.get_value")
	def test_duplicate_warehouses_raise_validation_error(self, mock_get_value):
		"""Same warehouse in two or more fields should raise frappe.ValidationError.

		Validates: Requirements 1.2
		"""
		# Mock: warehouses exist and are active (validation for duplicates runs first)
		def side_effect(doctype, name, fields, as_dict=False):
			if doctype == "Warehouse":
				return {"name": name, "disabled": 0}
			return None

		mock_get_value.side_effect = side_effect

		doc = self._get_settings_doc()
		doc.returned_ppe_warehouse = "Warehouse-A"
		doc.default_issue_warehouse = "Warehouse-A"  # Duplicate!
		doc.wornout_ppe_warehouse = "Warehouse-C"

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	@patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe.db.get_value")
	def test_all_three_same_warehouses_raise_validation_error(self, mock_get_value):
		"""All three fields set to the same warehouse should raise validation error.

		Validates: Requirements 1.2
		"""
		def side_effect(doctype, name, fields, as_dict=False):
			if doctype == "Warehouse":
				return {"name": name, "disabled": 0}
			return None

		mock_get_value.side_effect = side_effect

		doc = self._get_settings_doc()
		doc.returned_ppe_warehouse = "Warehouse-X"
		doc.default_issue_warehouse = "Warehouse-X"
		doc.wornout_ppe_warehouse = "Warehouse-X"

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	@patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe.db.get_value")
	def test_nonexistent_warehouse_raises_validation_error(self, mock_get_value):
		"""A warehouse name that doesn't exist in the DB should raise error.

		Validates: Requirements 1.7
		"""
		# Mock: first warehouse does not exist (returns None), others exist
		def side_effect(doctype, name, fields, as_dict=False):
			if doctype == "Warehouse":
				if name == "Non-Existent-Warehouse":
					return None  # Does not exist
				return {"name": name, "disabled": 0}
			return None

		mock_get_value.side_effect = side_effect

		doc = self._get_settings_doc()
		doc.returned_ppe_warehouse = "Non-Existent-Warehouse"
		doc.default_issue_warehouse = "Warehouse-B"
		doc.wornout_ppe_warehouse = "Warehouse-C"

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	@patch("ppe_tracker.ppe_tracker.doctype.ppe_tracker_settings.ppe_tracker_settings.frappe.db.get_value")
	def test_disabled_warehouse_raises_validation_error(self, mock_get_value):
		"""A warehouse that exists but has disabled=1 should raise error.

		Validates: Requirements 1.7
		"""
		# Mock: wornout warehouse exists but is disabled
		def side_effect(doctype, name, fields, as_dict=False):
			if doctype == "Warehouse":
				if name == "Disabled-Warehouse":
					return {"name": name, "disabled": 1}  # Disabled
				return {"name": name, "disabled": 0}
			return None

		mock_get_value.side_effect = side_effect

		doc = self._get_settings_doc()
		doc.returned_ppe_warehouse = "Warehouse-A"
		doc.default_issue_warehouse = "Warehouse-B"
		doc.wornout_ppe_warehouse = "Disabled-Warehouse"

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_permission_enforcement(self):
		"""Only System Manager and HR Manager should have access.

		Validates: Requirements 1.3
		"""
		meta = frappe.get_meta("PPE Tracker Settings")
		permissions = meta.permissions

		# Extract roles that have read access
		roles_with_access = [p.role for p in permissions if p.read]

		self.assertIn("System Manager", roles_with_access)
		self.assertIn("HR Manager", roles_with_access)

		# System Manager should have full CRUD
		sm_perms = [p for p in permissions if p.role == "System Manager"][0]
		self.assertTrue(sm_perms.read)
		self.assertTrue(sm_perms.write)
		self.assertTrue(sm_perms.create)
		self.assertTrue(sm_perms.delete)

		# HR Manager should have read/write but not create/delete
		hr_perms = [p for p in permissions if p.role == "HR Manager"][0]
		self.assertTrue(hr_perms.read)
		self.assertTrue(hr_perms.write)
		self.assertFalse(hr_perms.create)
		self.assertFalse(hr_perms.delete)

		# No other roles should have access
		self.assertEqual(len(roles_with_access), 2)


if __name__ == "__main__":
	unittest.main()
