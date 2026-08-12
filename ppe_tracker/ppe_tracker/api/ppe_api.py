"""
PPE Tracker API Module

Whitelisted API endpoints for the PPE Tracker application.
Provides REST-accessible helper functions for PPE management operations.
"""

import frappe
from frappe import _

from ppe_tracker.ppe_tracker.ppe_tracker.doctype.ppe_issue.ppe_issue import resolve_lifespan


@frappe.whitelist()
def get_resolved_lifespan(ppe_item: str, employee: str) -> dict:
	"""Resolve the applicable lifespan for a PPE Item + Employee combination.

	Calls resolve_lifespan() and determines whether the result came from a
	position_type match in the PPE Item's lifespan_table or from the default.

	Args:
		ppe_item: The name (ID) of the PPE Item record.
		employee: The name (ID) of the Employee record.

	Returns:
		dict: {"lifespan_months": int, "source": str}
			- source is "position_type_match" if a matching row was found,
			  or "default" if the PPE Item's default_lifespan was used.

	Validates: Requirements 4.3, 4.4
	"""
	lifespan_months = resolve_lifespan(ppe_item, employee)
	source = _determine_lifespan_source(ppe_item, employee)
	return {"lifespan_months": lifespan_months, "source": source}


def _determine_lifespan_source(ppe_item_name: str, employee_name: str) -> str:
	"""Determine whether the resolved lifespan matched a position_type row or fell back to default."""
	position_type = frappe.db.get_value("Employee", employee_name, "custom_position_type")

	if position_type:
		ppe_item = frappe.get_doc("PPE Item", ppe_item_name)
		for row in ppe_item.lifespan_table:
			if row.position_type == position_type:
				return "position_type_match"

	return "default"
