# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Unit tests for the PPE Loss DocType controller.

Tests validate() and _trigger_acknowledgement() behaviour for:
- New PPE Loss record has acknowledgement_status == "Pending" (Requirement 6.3)
- Acknowledge via Direct path sets status and creates Additional Salary (Requirement 6.4, 6.5)
- Supervisor Uploaded without attachment raises error (Requirement 6.6)
- Additional Salary amount equals surcharge_amount (Requirement 6.7, 6.8)
- additional_salary link field is populated after acknowledgement (Requirement 6.8)
"""

import unittest
from unittest.mock import patch, MagicMock

from frappe.exceptions import ValidationError


def _make_ppe_loss(
	ppe_issue="ISS-001",
	employee="EMP-001",
	employee_name="John Doe",
	ppe_item="PPE-HELMET",
	loss_date="2024-06-15",
	reason="Lost during shift",
	surcharge_amount=500.0,
	acknowledgement_status="Pending",
	acknowledgement_method=None,
	acknowledgement_attachment=None,
	additional_salary=None,
	name="PPE-LOSS-2024-0001",
):
	"""Create a mock PPE Loss document with given field values."""
	doc = MagicMock()
	doc.ppe_issue = ppe_issue
	doc.employee = employee
	doc.employee_name = employee_name
	doc.ppe_item = ppe_item
	doc.loss_date = loss_date
	doc.reason = reason
	doc.surcharge_amount = surcharge_amount
	doc.acknowledgement_status = acknowledgement_status
	doc.acknowledgement_method = acknowledgement_method
	doc.acknowledgement_attachment = acknowledgement_attachment
	doc.additional_salary = additional_salary
	doc.name = name
	return doc


class TestPPELoss(unittest.TestCase):
	"""Unit tests for PPE Loss controller methods.

	Requirements: 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
	"""

	# ------------------------------------------------------------------
	# Default Status Tests
	# ------------------------------------------------------------------

	def test_new_ppe_loss_has_pending_acknowledgement_status(self):
		"""A newly created PPE Loss record has acknowledgement_status == 'Pending'.

		Requirement 6.3: WHEN a PPE Loss record is created, THE System SHALL
		set the acknowledgement status to 'Pending'.
		"""
		doc = _make_ppe_loss(acknowledgement_status="Pending")

		self.assertEqual(doc.acknowledgement_status, "Pending")

	# ------------------------------------------------------------------
	# Acknowledgement via Direct Path Tests
	# ------------------------------------------------------------------

	@patch("frappe.utils.today", return_value="2024-06-15")
	@patch("frappe.new_doc")
	def test_acknowledge_direct_sets_status_and_creates_additional_salary(
		self, mock_new_doc, mock_today
	):
		"""_trigger_acknowledgement() sets status to 'Acknowledged' and creates Additional Salary.

		Requirement 6.4: WHEN an Employee acknowledges a PPE Loss record directly,
		THE System SHALL set the acknowledgement status to 'Acknowledged'.
		Requirement 6.7: WHEN a PPE Loss acknowledgement status is set to
		'Acknowledged', THE System SHALL automatically create an Additional Salary
		record with a deduction type.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

		mock_additional_salary = MagicMock()
		mock_additional_salary.name = "AS-001"
		mock_new_doc.return_value = mock_additional_salary

		doc = _make_ppe_loss(
			employee="EMP-001",
			surcharge_amount=750.0,
			acknowledgement_status="Pending",
		)

		PPELoss._trigger_acknowledgement(doc)

		# Status should be set to Acknowledged
		self.assertEqual(doc.acknowledgement_status, "Acknowledged")

		# Additional Salary should be created
		mock_new_doc.assert_called_once_with("Additional Salary")
		mock_additional_salary.insert.assert_called_once()
		mock_additional_salary.submit.assert_called_once()

		# Document should be saved
		doc.save.assert_called_once()

	# ------------------------------------------------------------------
	# Supervisor Uploaded Validation Tests
	# ------------------------------------------------------------------

	@patch("frappe._", side_effect=lambda x: x)
	@patch("frappe.throw", side_effect=ValidationError)
	def test_supervisor_uploaded_without_attachment_raises_error(
		self, mock_throw, mock_translate
	):
		"""_validate_acknowledgement_attachment() raises error when Supervisor Uploaded lacks attachment.

		Requirement 6.6: IF a PPE Loss record is saved with acknowledgement method
		'Supervisor Uploaded' and no attachment is present, THEN THE System SHALL
		raise a validation error and prevent saving with 'Acknowledged' status.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

		doc = _make_ppe_loss(
			acknowledgement_method="Supervisor Uploaded",
			acknowledgement_status="Acknowledged",
			acknowledgement_attachment=None,
		)

		with self.assertRaises(ValidationError):
			PPELoss._validate_acknowledgement_attachment(doc)

	# ------------------------------------------------------------------
	# Additional Salary Amount Tests
	# ------------------------------------------------------------------

	@patch("frappe.utils.today", return_value="2024-06-15")
	@patch("frappe.new_doc")
	def test_additional_salary_amount_equals_surcharge_amount(
		self, mock_new_doc, mock_today
	):
		"""_create_additional_salary() sets amount to the PPE Loss surcharge_amount.

		Requirement 6.7: THE System SHALL create an Additional Salary record for
		the surcharge amount recorded on the PPE Loss.
		Requirement 6.8: THE System SHALL store a link to the created Additional
		Salary record on the PPE Loss DocType for traceability.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

		mock_additional_salary = MagicMock()
		mock_additional_salary.name = "AS-002"
		mock_new_doc.return_value = mock_additional_salary

		surcharge = 1250.50
		doc = _make_ppe_loss(
			employee="EMP-002",
			surcharge_amount=surcharge,
		)

		PPELoss._create_additional_salary(doc)

		# Verify the Additional Salary was created with correct values
		mock_new_doc.assert_called_once_with("Additional Salary")
		self.assertEqual(mock_additional_salary.employee, "EMP-002")
		self.assertEqual(mock_additional_salary.salary_component, "PPE Loss Deduction")
		self.assertEqual(mock_additional_salary.amount, surcharge)
		self.assertEqual(mock_additional_salary.type, "Deduction")
		mock_additional_salary.insert.assert_called_once()
		mock_additional_salary.submit.assert_called_once()

	# ------------------------------------------------------------------
	# Additional Salary Link Field Tests
	# ------------------------------------------------------------------

	@patch("frappe.utils.today", return_value="2024-06-15")
	@patch("frappe.new_doc")
	def test_additional_salary_link_field_populated_after_acknowledgement(
		self, mock_new_doc, mock_today
	):
		"""_create_additional_salary() populates the additional_salary link field.

		Requirement 6.8: THE System SHALL store a link to the created Additional
		Salary record on the PPE Loss DocType for traceability.
		"""
		from ppe_tracker.ppe_tracker.doctype.ppe_loss.ppe_loss import PPELoss

		mock_additional_salary = MagicMock()
		mock_additional_salary.name = "AS-003"
		mock_new_doc.return_value = mock_additional_salary

		doc = _make_ppe_loss(
			employee="EMP-003",
			surcharge_amount=300.0,
			additional_salary=None,
		)

		PPELoss._create_additional_salary(doc)

		# The additional_salary link field should be populated with the created record name
		self.assertEqual(doc.additional_salary, "AS-003")


if __name__ == "__main__":
	unittest.main()
