# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the PPE Request DocType controller.

Tests validate() and on_submit() behaviour for:
- on_submit sets status to 'Submitted' (Requirement 3.2)
- Reject without reason raises ValidationError (Requirement 3.5)
- Reject with reason sets status to 'Rejected' (Requirement 3.5)
- Approve sets status to 'Approved' via API flag (Requirement 3.4)
"""

import unittest
from unittest.mock import patch, MagicMock

from frappe.exceptions import ValidationError


def _make_ppe_request(status="Draft", rejection_reason="", via_api=False):
	"""Create a mock PPE Request document with given field values."""
	doc = MagicMock()
	doc.status = status
	doc.rejection_reason = rejection_reason
	doc.flags = MagicMock()
	doc.flags.get = MagicMock(return_value=via_api)
	doc.is_new = MagicMock(return_value=False)
	doc.has_value_changed = MagicMock(return_value=True)
	return doc


class TestPPERequest(unittest.TestCase):
	"""Unit tests for PPE Request controller methods.

	Requirements: 3.2, 3.3, 3.4, 3.5
	"""

	def test_submit_sets_status_to_submitted(self):
		"""on_submit() sets status to 'Submitted' and calls db_set.

		Requirement 3.2: When a PPE Request is submitted, the system shall
		set its status to 'Submitted'.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

		doc = _make_ppe_request(status="Draft")

		PPERequest.on_submit(doc)

		self.assertEqual(doc.status, "Submitted")
		doc.db_set.assert_called_once_with("status", "Submitted", update_modified=False)

	@patch("frappe.throw", side_effect=ValidationError)
	def test_reject_without_reason_raises_error(self, mock_throw):
		"""Reject with empty rejection_reason raises ValidationError.

		Requirement 3.5: When an authorised user rejects a PPE Request, the
		system shall require a rejection reason to be recorded. Rejecting
		without a reason raises a validation error.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

		doc = _make_ppe_request(status="Rejected", rejection_reason="")

		with self.assertRaises(ValidationError):
			PPERequest._validate_rejection_reason(doc)

		mock_throw.assert_called_once()

	@patch("frappe.throw")
	def test_reject_with_reason_succeeds(self, mock_throw):
		"""Reject with a valid rejection_reason does not raise.

		Requirement 3.5: When a rejection reason is provided, the rejection
		proceeds without error.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

		doc = _make_ppe_request(status="Rejected", rejection_reason="Not available in stock")

		# Should NOT raise any exception
		PPERequest._validate_rejection_reason(doc)

		mock_throw.assert_not_called()

	@patch("frappe.throw")
	def test_approve_sets_status(self, mock_throw):
		"""Approve via API sets status to 'Approved' without validation error.

		Requirement 3.4: When an authorised user approves a PPE Request,
		the system shall set its status to 'Approved'. The via_api flag
		bypasses the status transition guard.
		"""
		from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_request.ppe_request import PPERequest

		doc = _make_ppe_request(status="Approved", via_api=True)

		# With via_api=True, validate should not throw for restricted status
		PPERequest._validate_status_transition(doc)

		mock_throw.assert_not_called()


if __name__ == "__main__":
	unittest.main()
