"""
Bulk PPE Loss API Module

Whitelisted API endpoints for the Bulk PPE Loss tool.
Allows HR Managers and Safety Officers to record multiple PPE Losses
in a single batch operation.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_eligible_losses(filters=None):
	"""Return Active PPE Issues eligible for loss recording.

	Args:
		filters: JSON string or dict with optional keys: employee, department, ppe_item

	Returns:
		List of dicts with: name, employee, employee_name, department, ppe_item,
		                    ppe_item_name, issue_date, quantity

	Validates: Requirements 4.2, 4.3
	"""
	frappe.only_for(["HR Manager", "Safety Officer"])

	if filters and isinstance(filters, str):
		filters = frappe.parse_json(filters)

	query_filters = {
		"status": "Active",
		"docstatus": 1,
	}

	if filters:
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
			"quantity",
		],
		order_by="issue_date desc",
	)

	# Fetch ppe_item_name for each issue from the PPE Item DocType
	for issue in issues:
		issue["ppe_item_name"] = frappe.db.get_value(
			"PPE Item", issue["ppe_item"], "item_name"
		) or issue["ppe_item"]

	return issues


@frappe.whitelist()
def process_bulk_losses(items):
	"""Process bulk PPE losses.

	For each selected PPE Issue, creates a PPE Loss record with the specified
	loss date and reason. Surcharge amount is auto-populated from the linked
	ERPNext Item's valuation rate. Acknowledgement status is set to "Pending".

	Continues processing on individual failure and returns a summary.

	Args:
		items: JSON string or list of dicts with keys:
			- ppe_issue (str): PPE Issue name
			- loss_date (str): date string
			- reason (str): loss reason text

	Returns:
		dict with 'successes' and 'failures' lists

	Validates: Requirements 4.5, 4.6, 4.7, 4.8
	"""
	frappe.only_for(["HR Manager", "Safety Officer"])

	if isinstance(items, str):
		items = frappe.parse_json(items)

	successes = []
	failures = []

	for item in items:
		ppe_issue_name = item.get("ppe_issue")
		loss_date = item.get("loss_date")
		reason = item.get("reason")

		# Use savepoint so individual failures don't roll back the entire batch
		savepoint = f"bulk_loss_{ppe_issue_name}"
		try:
			frappe.db.savepoint(savepoint)

			if not ppe_issue_name or not loss_date or not reason:
				frappe.throw(_("ppe_issue, loss_date, and reason are required for each item."))

			# Get PPE Issue record details
			ppe_issue = frappe.get_doc("PPE Issue", ppe_issue_name)

			# Get the item_code from PPE Item
			item_code = frappe.db.get_value("PPE Item", ppe_issue.ppe_item, "item_code")
			if not item_code:
				frappe.throw(
					_("PPE Item {0} does not have a linked Item Code.").format(ppe_issue.ppe_item)
				)

			# Get valuation_rate from ERPNext Item, fallback to Bin
			valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
			if not valuation_rate:
				valuation_rate = frappe.db.get_value(
					"Bin", {"item_code": item_code}, "valuation_rate"
				)
			if not valuation_rate:
				valuation_rate = 0

			# Calculate surcharge amount
			surcharge_amount = valuation_rate * (ppe_issue.quantity or 1)

			# Create PPE Loss record
			loss_doc = frappe.new_doc("PPE Loss")
			loss_doc.ppe_issue = ppe_issue_name
			loss_doc.employee = ppe_issue.employee
			loss_doc.ppe_item = ppe_issue.ppe_item
			loss_doc.loss_date = loss_date
			loss_doc.reason = reason
			loss_doc.surcharge_amount = surcharge_amount
			loss_doc.acknowledgement_status = "Pending"
			loss_doc.insert(ignore_permissions=True)

			successes.append({
				"ppe_issue": ppe_issue_name,
				"ppe_loss": loss_doc.name,
				"employee": ppe_issue.employee,
				"employee_name": ppe_issue.employee_name,
				"surcharge_amount": surcharge_amount,
			})

		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
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
