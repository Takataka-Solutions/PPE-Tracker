"""
Bulk PPE Return API

Whitelisted endpoints for processing multiple PPE Returns in a single batch.
Used by the Bulk PPE Return page to query eligible issues and process returns.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_eligible_returns(filters=None):
	"""Return Active PPE Issues eligible for return, with optional filters.

	Args:
		filters: JSON string or dict with optional keys: employee, department, ppe_item

	Returns:
		List of dicts with: name, employee, employee_name, department, ppe_item,
		                     ppe_item_name, issue_date, expiry_date, quantity
	"""
	frappe.only_for(["HR Manager", "Safety Officer", "Storekeeper"])

	if filters and isinstance(filters, str):
		filters = frappe.parse_json(filters)

	if not filters:
		filters = {}

	query_filters = {
		"status": "Active",
		"docstatus": 1,
	}

	if filters.get("employee"):
		query_filters["employee"] = filters["employee"]

	if filters.get("department"):
		query_filters["department"] = filters["department"]

	if filters.get("ppe_item"):
		query_filters["ppe_item"] = filters["ppe_item"]

	issues = frappe.get_all(
		"PPE Issue",
		filters=query_filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"ppe_item",
			"issue_date",
			"expiry_date",
			"quantity",
		],
		order_by="issue_date desc",
	)

	# Fetch ppe_item_name for display (PPE Item is named by item_name field,
	# so the record name IS the item name, but we include it explicitly for clarity)
	for issue in issues:
		issue["ppe_item_name"] = issue["ppe_item"]

	return issues


@frappe.whitelist()
def process_bulk_returns(items):
	"""Process bulk PPE returns.

	Creates and submits individual PPE Return records for each selected item.
	Continues processing on individual failure and returns a summary.

	Args:
		items: JSON string or list of dicts with keys:
			- ppe_issue (str): PPE Issue name
			- condition (str): "Good", "Damaged", or "Unusable"
			- return_date (str): date string
			- quantity_returned (int, optional): qty to return (defaults to full issued qty)

	Returns:
		dict with 'successes' and 'failures' lists
	"""
	frappe.only_for(["HR Manager", "Safety Officer", "Storekeeper"])

	if items and isinstance(items, str):
		items = frappe.parse_json(items)

	if not items:
		frappe.throw(_("No items provided for bulk return processing."))

	successes = []
	failures = []

	for item in items:
		ppe_issue_name = item.get("ppe_issue")
		if not ppe_issue_name:
			failures.append({
				"ppe_issue": None,
				"error": _("Missing PPE Issue reference in item.")
			})
			continue

		try:
			frappe.db.savepoint("bulk_return_item")

			# Get the PPE Issue details to populate the return
			issue_doc = frappe.get_doc("PPE Issue", ppe_issue_name)

			# Determine quantity to return (default to full issued quantity)
			quantity_returned = item.get("quantity_returned") or issue_doc.quantity

			# Create PPE Return record
			ppe_return = frappe.new_doc("PPE Return")
			ppe_return.ppe_issue = ppe_issue_name
			ppe_return.employee = issue_doc.employee
			ppe_return.ppe_item = issue_doc.ppe_item
			ppe_return.condition = item.get("condition")
			ppe_return.return_date = item.get("return_date")
			ppe_return.quantity_returned = quantity_returned

			ppe_return.insert(ignore_permissions=True)
			ppe_return.submit()

			successes.append({
				"ppe_issue": ppe_issue_name,
				"ppe_return": ppe_return.name,
				"employee": issue_doc.employee,
				"employee_name": issue_doc.employee_name,
				"ppe_item": issue_doc.ppe_item,
			})

		except Exception as e:
			frappe.db.rollback(save_point="bulk_return_item")
			failures.append({
				"ppe_issue": ppe_issue_name,
				"error": str(e),
			})

	# Commit all successful operations
	if successes:
		frappe.db.commit()

	return {
		"successes": successes,
		"failures": failures,
	}
