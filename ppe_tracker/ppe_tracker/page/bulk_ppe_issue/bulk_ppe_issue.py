"""
Bulk PPE Issue Page

Server-side handlers for the Bulk PPE Issue page.
Provides endpoints to fetch approved PPE Requests not yet issued,
and to create + submit PPE Issue records in bulk.
"""

import json

import frappe
from frappe import _
from frappe.utils import today


@frappe.whitelist()
def get_approved_requests(filters=None):
	"""Return all Approved PPE Requests that have not yet been issued.

	A PPE Request is considered "not yet issued" if no PPE Issue record
	(with docstatus != 2, i.e., not cancelled) links to it.

	Args:
		filters: Optional JSON string or dict with keys:
			department, designation, ppe_item, employee

	Returns:
		list[dict]: List of PPE Request records with relevant fields.
	"""
	frappe.only_for(["HR Manager", "Safety Officer", "Storekeeper"])

	if isinstance(filters, str):
		filters = json.loads(filters)

	if not filters:
		filters = {}

	conditions = []
	values = {}

	if filters.get("department"):
		conditions.append("pr.department = %(department)s")
		values["department"] = filters["department"]

	if filters.get("designation"):
		conditions.append("pr.designation = %(designation)s")
		values["designation"] = filters["designation"]

	if filters.get("ppe_item"):
		conditions.append("pr.ppe_item = %(ppe_item)s")
		values["ppe_item"] = filters["ppe_item"]

	if filters.get("employee"):
		conditions.append("pr.employee = %(employee)s")
		values["employee"] = filters["employee"]

	extra_conditions = ""
	if conditions:
		extra_conditions = "AND " + " AND ".join(conditions)

	requests = frappe.db.sql(
		"""
		SELECT
			pr.name,
			pr.employee,
			pr.employee_name,
			pr.department,
			pr.designation,
			pr.ppe_item,
			pr.requested_quantity,
			pr.creation AS request_date
		FROM `tabPPE Request` pr
		WHERE pr.status = 'Approved'
			AND pr.docstatus = 1
			AND pr.name NOT IN (
				SELECT pi.ppe_request
				FROM `tabPPE Issue` pi
				WHERE pi.docstatus != 2
			)
			{extra_conditions}
		ORDER BY pr.creation ASC
		""".format(extra_conditions=extra_conditions),
		values,
		as_dict=True,
	)

	return requests


@frappe.whitelist()
def issue_selected(requests):
	"""Create and submit PPE Issue records for the selected PPE Requests.

	Processes each request individually — if one fails, the others continue.

	Args:
		requests: JSON string or list of PPE Request names.

	Returns:
		dict: {"success": [...], "failed": [{"request": name, "error": msg}]}
	"""
	frappe.only_for(["HR Manager", "Safety Officer", "Storekeeper"])

	if isinstance(requests, str):
		requests = json.loads(requests)

	if not requests:
		frappe.throw(_("No requests selected."))

	success = []
	failed = []

	for request_name in requests:
		try:
			ppe_request = frappe.get_doc("PPE Request", request_name)

			# Validate the request is still Approved and not already issued
			if ppe_request.status != "Approved":
				raise ValueError(
					_("PPE Request {0} is no longer in Approved status.").format(request_name)
				)

			# Check if already issued (race condition guard)
			existing_issue = frappe.db.exists(
				"PPE Issue",
				{"ppe_request": request_name, "docstatus": ["!=", 2]},
			)
			if existing_issue:
				raise ValueError(
					_("PPE Request {0} has already been issued.").format(request_name)
				)

			# Create PPE Issue
			ppe_issue = frappe.get_doc(
				{
					"doctype": "PPE Issue",
					"ppe_request": request_name,
					"employee": ppe_request.employee,
					"ppe_item": ppe_request.ppe_item,
					"issue_date": today(),
					"quantity": ppe_request.requested_quantity,
				}
			)
			ppe_issue.insert(ignore_permissions=True)
			ppe_issue.submit()

			success.append({
				"request": request_name,
				"ppe_issue": ppe_issue.name,
				"employee": ppe_request.employee,
				"employee_name": ppe_request.employee_name,
			})

		except Exception as e:
			failed.append({"request": request_name, "error": str(e)})

	frappe.db.commit()

	return {"success": success, "failed": failed}
