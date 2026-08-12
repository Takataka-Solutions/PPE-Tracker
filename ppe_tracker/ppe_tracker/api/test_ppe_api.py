# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the ppe_api.py whitelisted API layer.

Tests cover:
- approve_ppe_request from unauthorised role raises PermissionError (Requirement 3.4, 3.8)
- reject_ppe_request with empty reason raises ValidationError (Requirement 3.5)
- approve_ppe_request on non-Submitted request raises error (Requirement 3.4)
- acknowledge_loss from non-linked, non-HR user raises PermissionError (Requirement 6.11)
- get_resolved_lifespan returns correct lifespan and source tag for match and fallback paths (Requirement 4.3, 4.4)
"""

import unittest
from unittest.mock import patch, MagicMock

from frappe.exceptions import ValidationError, PermissionError


class TestApprovePPERequest(unittest.TestCase):
	"""Unit tests for approve_ppe_request API endpoint.

	Requirements: 3.4, 3.8
	"""

	@patch("frappe.get_doc")
	@patch("frappe.get_roles", return_value=["Employee", "All"])
	@patch("frappe.throw", side_effect=PermissionError)
	def test_approve_from_unauthorised_role_raises_permission_error(
		self, mock_throw, mock_get_roles, mock_get_doc
	):
		"""approve_ppe_request() raises PermissionError when caller lacks HR Manager/Safety Officer/HR User role.

		Requirement 3.8: THE System SHALL restrict PPE Request approval to users
		holding the HR Manager, Safety Officer, or HR User role.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import approve_ppe_request

		with self.assertRaises(PermissionError):
			approve_ppe_request("PPE-REQ-2024-0001")

		# Verify frappe.throw was called with PermissionError exc_type
		mock_throw.assert_called_once()
		call_kwargs = mock_throw.call_args
		self.assertEqual(call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("exc"), PermissionError)

		# get_doc should NOT have been called since permission check fails first
		mock_get_doc.assert_not_called()

	@patch("frappe.get_doc")
	@patch("frappe.get_roles", return_value=["HR Manager", "All"])
	@patch("frappe.throw", side_effect=ValidationError)
	def test_approve_non_submitted_request_raises_error(
		self, mock_throw, mock_get_roles, mock_get_doc
	):
		"""approve_ppe_request() raises error when request status is not 'Submitted'.

		Requirement 3.4: Only PPE Requests with status 'Submitted' can be approved.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import approve_ppe_request

		# Mock a PPE Request with status 'Draft' (not Submitted)
		mock_request = MagicMock()
		mock_request.status = "Draft"
		mock_get_doc.return_value = mock_request

		with self.assertRaises(ValidationError):
			approve_ppe_request("PPE-REQ-2024-0002")

		mock_throw.assert_called_once()


class TestRejectPPERequest(unittest.TestCase):
	"""Unit tests for reject_ppe_request API endpoint.

	Requirements: 3.5, 3.8
	"""

	@patch("frappe.get_doc")
	@patch("frappe.get_roles", return_value=["HR Manager", "All"])
	@patch("frappe.throw", side_effect=ValidationError)
	def test_reject_with_empty_reason_raises_validation_error(
		self, mock_throw, mock_get_roles, mock_get_doc
	):
		"""reject_ppe_request() raises ValidationError when rejection_reason is empty.

		Requirement 3.5: WHEN an authorised user rejects a PPE Request, THE System
		SHALL require a rejection reason to be recorded. Rejecting without a reason
		raises a validation error.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import reject_ppe_request

		with self.assertRaises(ValidationError):
			reject_ppe_request("PPE-REQ-2024-0003", "")

		mock_throw.assert_called_once()
		# get_doc should NOT have been called since validation fails first
		mock_get_doc.assert_not_called()

	@patch("frappe.get_doc")
	@patch("frappe.get_roles", return_value=["HR Manager", "All"])
	@patch("frappe.throw", side_effect=ValidationError)
	def test_reject_with_whitespace_only_reason_raises_validation_error(
		self, mock_throw, mock_get_roles, mock_get_doc
	):
		"""reject_ppe_request() raises ValidationError when rejection_reason is only whitespace.

		Requirement 3.5: Empty or whitespace-only reasons are treated as not provided.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import reject_ppe_request

		with self.assertRaises(ValidationError):
			reject_ppe_request("PPE-REQ-2024-0004", "   ")

		mock_throw.assert_called_once()
		mock_get_doc.assert_not_called()


class TestAcknowledgeLoss(unittest.TestCase):
	"""Unit tests for acknowledge_loss API endpoint.

	Requirements: 6.11
	"""

	@patch("frappe.session", MagicMock(user="random_user@example.com"))
	@patch("frappe.db.get_value", return_value="linked_employee@example.com")
	@patch("frappe.get_roles", return_value=["Employee", "All"])
	@patch("frappe.get_doc")
	@patch("frappe.throw", side_effect=PermissionError)
	def test_acknowledge_from_non_linked_non_hr_user_raises_permission_error(
		self, mock_throw, mock_get_doc, mock_get_roles, mock_db_get_value
	):
		"""acknowledge_loss() raises PermissionError when caller is not the linked employee nor HR/Safety Officer.

		Requirement 6.11: THE System SHALL restrict PPE Loss acknowledgement (direct
		path) to the Employee linked on the record or users holding the HR Manager
		or Safety Officer role.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import acknowledge_loss

		# Mock PPE Loss document
		mock_loss_doc = MagicMock()
		mock_loss_doc.employee = "EMP-001"
		mock_get_doc.return_value = mock_loss_doc

		with self.assertRaises(PermissionError):
			acknowledge_loss("PPE-LOSS-2024-0001", "Direct")

		mock_throw.assert_called_once()
		# Verify it was called with PermissionError exc type
		call_args = mock_throw.call_args
		self.assertEqual(call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("exc"), PermissionError)


class TestGetResolvedLifespan(unittest.TestCase):
	"""Unit tests for get_resolved_lifespan API endpoint.

	Requirements: 4.3, 4.4
	"""

	@patch("ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api._determine_lifespan_source", return_value="position_type_match")
	@patch("ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api.resolve_lifespan", return_value=6)
	def test_returns_correct_lifespan_for_position_type_match(
		self, mock_resolve, mock_source
	):
		"""get_resolved_lifespan() returns matched lifespan and 'position_type_match' source.

		Requirement 4.3: WHEN a PPE Issue record is saved, THE System SHALL resolve
		the employee's Position Type from the linked Employee record, look up the
		matching row in the PPE Item Lifespan child table, and use that row's lifespan.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import get_resolved_lifespan

		result = get_resolved_lifespan("PPE-HELMET", "EMP-001")

		self.assertEqual(result["lifespan_months"], 6)
		self.assertEqual(result["source"], "position_type_match")
		mock_resolve.assert_called_once_with("PPE-HELMET", "EMP-001")
		mock_source.assert_called_once_with("PPE-HELMET", "EMP-001")

	@patch("ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api._determine_lifespan_source", return_value="default")
	@patch("ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api.resolve_lifespan", return_value=12)
	def test_returns_default_lifespan_when_no_position_type_match(
		self, mock_resolve, mock_source
	):
		"""get_resolved_lifespan() returns default lifespan and 'default' source when no match.

		Requirement 4.4: IF the employee's Position Type has no matching row in the
		PPE Item Lifespan child table, THEN THE System SHALL fall back to the PPE
		Item default lifespan.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import get_resolved_lifespan

		result = get_resolved_lifespan("PPE-GLOVES", "EMP-002")

		self.assertEqual(result["lifespan_months"], 12)
		self.assertEqual(result["source"], "default")
		mock_resolve.assert_called_once_with("PPE-GLOVES", "EMP-002")
		mock_source.assert_called_once_with("PPE-GLOVES", "EMP-002")

	@patch("frappe.db.get_value", return_value="Heavy Duty")
	@patch("frappe.get_doc")
	def test_determine_lifespan_source_returns_match_when_position_type_found(
		self, mock_get_doc, mock_db_get_value
	):
		"""_determine_lifespan_source() returns 'position_type_match' when a matching row exists.

		Requirement 4.3: The system looks up the matching row in the PPE Item
		Lifespan child table based on the employee's position type.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import _determine_lifespan_source

		# Mock PPE Item with a lifespan_table row matching "Heavy Duty"
		mock_ppe_item = MagicMock()
		mock_row = MagicMock()
		mock_row.position_type = "Heavy Duty"
		mock_ppe_item.lifespan_table = [mock_row]
		mock_get_doc.return_value = mock_ppe_item

		result = _determine_lifespan_source("PPE-HELMET", "EMP-001")

		self.assertEqual(result, "position_type_match")

	@patch("frappe.db.get_value", return_value="Standard")
	@patch("frappe.get_doc")
	def test_determine_lifespan_source_returns_default_when_no_match(
		self, mock_get_doc, mock_db_get_value
	):
		"""_determine_lifespan_source() returns 'default' when no matching position_type row exists.

		Requirement 4.4: Falls back to default lifespan when no lifespan table
		row matches the employee's position type.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api import _determine_lifespan_source

		# Mock PPE Item with a lifespan_table row for "Heavy Duty" only
		mock_ppe_item = MagicMock()
		mock_row = MagicMock()
		mock_row.position_type = "Heavy Duty"
		mock_ppe_item.lifespan_table = [mock_row]
		mock_get_doc.return_value = mock_ppe_item

		# Employee has "Standard" position type — no match in table
		result = _determine_lifespan_source("PPE-HELMET", "EMP-002")

		self.assertEqual(result, "default")


if __name__ == "__main__":
	unittest.main()
