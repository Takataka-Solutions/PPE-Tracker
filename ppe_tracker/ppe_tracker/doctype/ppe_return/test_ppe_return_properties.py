# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Property-based tests for the PPE Return DocType.

Feature: tts-ppe-tracker, Property 13: Return Quantity Cannot Exceed Issued Quantity

**Validates: Requirements 5.4**
"""

import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis.strategies import integers, text

from frappe.exceptions import ValidationError


class TestReturnQuantityCannotExceedIssuedQuantity(unittest.TestCase):
    """Property 13: Return Quantity Cannot Exceed Issued Quantity

    For any PPE Return where quantity_returned exceeds the issued quantity
    on the linked PPE Issue, _validate_quantity() SHALL raise a ValidationError.

    Feature: tts-ppe-tracker, Property 13: Return Quantity Cannot Exceed Issued Quantity
    **Validates: Requirements 5.4**
    """

    @given(
        issued_qty=integers(min_value=1, max_value=100),
        excess=integers(min_value=1, max_value=100),
    )
    @settings(max_examples=25)
    def test_quantity_returned_exceeding_issued_raises_validation_error(
        self, issued_qty, excess
    ):
        """For any quantity_returned > issued quantity, _validate_quantity()
        always raises ValidationError.

        Feature: tts-ppe-tracker, Property 13: Return Quantity Cannot Exceed Issued Quantity
        **Validates: Requirements 5.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        quantity_returned = issued_qty + excess  # Always exceeds

        # Create a mock PPE Return document
        mock_doc = MagicMock()
        mock_doc.ppe_issue = "PPE-ISS-001"
        mock_doc.quantity_returned = quantity_returned

        # Mock frappe.db.get_value to return the issued quantity
        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.db.get_value",
            return_value=issued_qty,
        ) as mock_get_value:
            # Mock frappe.throw to raise ValidationError
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.throw",
                side_effect=ValidationError,
            ) as mock_throw:
                with self.assertRaises(ValidationError):
                    PPEReturn._validate_quantity(mock_doc)

                # Verify frappe.db.get_value was called for the PPE Issue quantity
                mock_get_value.assert_called_once_with(
                    "PPE Issue", "PPE-ISS-001", "quantity"
                )

                # Verify frappe.throw was called (validation triggered)
                mock_throw.assert_called_once()

    @given(
        issued_qty=integers(min_value=1, max_value=100),
    )
    @settings(max_examples=25)
    def test_quantity_returned_equal_to_issued_does_not_raise(self, issued_qty):
        """For quantity_returned == issued quantity, _validate_quantity()
        does NOT raise ValidationError (boundary case — exact return is valid).

        Feature: tts-ppe-tracker, Property 13: Return Quantity Cannot Exceed Issued Quantity
        **Validates: Requirements 5.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        # Create a mock PPE Return document with quantity_returned == issued_qty
        mock_doc = MagicMock()
        mock_doc.ppe_issue = "PPE-ISS-001"
        mock_doc.quantity_returned = issued_qty

        # Mock frappe.db.get_value to return the issued quantity
        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.db.get_value",
            return_value=issued_qty,
        ) as mock_get_value:
            # Mock frappe.throw — should NOT be called
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.throw",
                side_effect=ValidationError,
            ) as mock_throw:
                # Should not raise
                PPEReturn._validate_quantity(mock_doc)

                # Verify frappe.throw was NOT called
                mock_throw.assert_not_called()

    @given(
        issued_qty=integers(min_value=2, max_value=100),
    )
    @settings(max_examples=25)
    def test_quantity_returned_less_than_issued_does_not_raise(self, issued_qty):
        """For quantity_returned < issued quantity, _validate_quantity()
        does NOT raise ValidationError (partial return is valid).

        Feature: tts-ppe-tracker, Property 13: Return Quantity Cannot Exceed Issued Quantity
        **Validates: Requirements 5.4**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        # Create a mock PPE Return document with quantity_returned < issued_qty
        mock_doc = MagicMock()
        mock_doc.ppe_issue = "PPE-ISS-001"
        mock_doc.quantity_returned = issued_qty - 1  # Always less than issued

        # Mock frappe.db.get_value to return the issued quantity
        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.db.get_value",
            return_value=issued_qty,
        ) as mock_get_value:
            # Mock frappe.throw — should NOT be called
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.throw",
                side_effect=ValidationError,
            ) as mock_throw:
                # Should not raise
                PPEReturn._validate_quantity(mock_doc)

                # Verify frappe.throw was NOT called
                mock_throw.assert_not_called()


class TestCancellationCreatesReverseStockEntry(unittest.TestCase):
    """Property 24: Cancellation Creates Reverse Stock Entry

    When a PPE Return is cancelled, if a linked Stock Entry exists, the system
    SHALL cancel it (creating a reverse entry, net stock change = 0). If no
    Stock Entry is linked (Damaged/Unusable returns), cancellation should still
    revert the PPE Issue status to 'Active' without attempting Stock Entry cancellation.

    Feature: tts-ppe-tracker, Property 24: Cancellation Creates Reverse Stock Entry
    **Validates: Requirements 17.6**
    """

    @given(stock_entry_name=text(min_size=5, max_size=20))
    @settings(max_examples=25)
    def test_cancel_with_stock_entry_cancels_linked_stock_entry(
        self, stock_entry_name
    ):
        """For any PPE Return with a linked Stock Entry, on_cancel() SHALL
        cancel the Stock Entry (net stock change = 0) and revert PPE Issue
        status to 'Active'.

        Feature: tts-ppe-tracker, Property 24: Cancellation Creates Reverse Stock Entry
        **Validates: Requirements 17.6**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        # Create a mock PPE Return document with a linked stock_entry
        mock_doc = MagicMock()
        mock_doc.stock_entry = stock_entry_name
        mock_doc.ppe_issue = "PPE-ISS-001"

        # Create a mock Stock Entry that will be fetched
        mock_se = MagicMock()

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.get_doc",
            return_value=mock_se,
        ) as mock_get_doc:
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.db.set_value",
            ) as mock_set_value:
                PPEReturn.on_cancel(mock_doc)

                # Assert frappe.get_doc was called with the Stock Entry name
                mock_get_doc.assert_called_once_with(
                    "Stock Entry", stock_entry_name
                )

                # Assert the Stock Entry's cancel() method was called
                mock_se.cancel.assert_called_once()

                # Assert PPE Issue status reverted to 'Active'
                mock_set_value.assert_called_once_with(
                    "PPE Issue", "PPE-ISS-001", "status", "Active"
                )

    @given(stock_entry_name=text(min_size=5, max_size=20))
    @settings(max_examples=25)
    def test_cancel_without_stock_entry_does_not_cancel_any_stock_entry(
        self, stock_entry_name
    ):
        """For any PPE Return WITHOUT a linked Stock Entry (Damaged/Unusable
        returns where stock_entry is None/empty), on_cancel() SHALL NOT
        attempt to cancel any Stock Entry but SHALL still revert PPE Issue
        status to 'Active'.

        Feature: tts-ppe-tracker, Property 24: Cancellation Creates Reverse Stock Entry
        **Validates: Requirements 17.6**
        """
        from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return import PPEReturn

        # Create a mock PPE Return document with NO linked stock_entry
        mock_doc = MagicMock()
        mock_doc.stock_entry = None  # Damaged/Unusable — no Stock Entry created
        mock_doc.ppe_issue = "PPE-ISS-002"

        with patch(
            "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.get_doc",
        ) as mock_get_doc:
            with patch(
                "ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_return.ppe_return.frappe.db.set_value",
            ) as mock_set_value:
                PPEReturn.on_cancel(mock_doc)

                # Assert frappe.get_doc was NOT called (no Stock Entry to cancel)
                mock_get_doc.assert_not_called()

                # Assert PPE Issue status STILL reverted to 'Active'
                mock_set_value.assert_called_once_with(
                    "PPE Issue", "PPE-ISS-002", "status", "Active"
                )


if __name__ == "__main__":
    unittest.main()
