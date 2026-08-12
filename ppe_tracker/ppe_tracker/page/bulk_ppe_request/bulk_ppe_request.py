"""
Bulk PPE Request Page

Server-side handlers for the Bulk PPE Request page.
Provides endpoints to fetch employees filtered by department/designation,
fetch active PPE Items, and create + submit PPE Request records in bulk
after validating against PPE Role Assignment rules.
"""

import json

import frappe
from frappe import _


@frappe.whitelist()
def get_employees(filters=None):
	"""Return employees filtered by department, designation, company, branch, or name search.

	Args:
		filters: Optional JSON string or dict with keys:
			department, designation, company, branch, employee_name

	Returns:
		list[dict]: List of Employee records with relevant fields.
	"""
	frappe.only_for(["HR Manager", "Safety Officer"])

	if isinstance(filters, str):
		filters = json.loads(filters)

	if not filters:
		filters = {}

	conditions = ["emp.status = 'Active'"]
	values = {}

	if filters.get("department"):
		conditions.append("emp.department = %(department)s")
		values["department"] = filters["department"]

	if filters.get("designation"):
		conditions.append("emp.designation = %(designation)s")
		values["designation"] = filters["designation"]

	if filters.get("company"):
		conditions.append("emp.company = %(company)s")
		values["company"] = filters["company"]

	if filters.get("branch"):
		conditions.append("emp.branch = %(branch)s")
		values["branch"] = filters["branch"]

	if filters.get("employee_name"):
		conditions.append("emp.employee_name LIKE %(employee_name)s")
		values["employee_name"] = "%{}%".format(filters["employee_name"])

	where_clause = " AND ".join(conditions)

	employees = frappe.db.sql(
		"""
		SELECT
			emp.name,
			emp.employee_name,
			emp.department,
			emp.designation,
			emp.company,
			emp.branch
		FROM `tabEmployee` emp
		WHERE {where_clause}
		ORDER BY emp.employee_name ASC
		""".format(where_clause=where_clause),
		values,
		as_dict=True,
	)

	return employees


@frappe.whitelist()
def get_ppe_items():
	"""Return all Active PPE Items for multi-select.

	Returns:
		list[dict]: List of PPE Item records with name and item_name.
	"""
	frappe.only_for(["HR Manager", "Safety Officer"])

	items = frappe.get_all(
		"PPE Item",
		filters={"status": "Active"},
		fields=["name", "item_name", "ppe_category"],
		order_by="item_name ASC",
	)

	return items


@frappe.whitelist()
def create_bulk_requests(employees, ppe_items, justification):
	"""Create and submit PPE Request records in bulk.

	For each Employee + PPE Item combination:
	- Validates against PPE Role Assignment rules
	- If not covered → skip with reason
	- If covered → create PPE Request with quantity=1 and given justification, then submit
	- If error → add to failed list

	Args:
		employees: JSON string or list of Employee names.
		ppe_items: JSON string or list of PPE Item names.
		justification: String justification for the requests.

	Returns:
		dict: {"created": [...], "skipped": [...], "failed": [...]}
	"""
	frappe.only_for(["HR Manager", "Safety Officer"])

	if isinstance(employees, str):
		employees = json.loads(employees)

	if isinstance(ppe_items, str):
		ppe_items = json.loads(ppe_items)

	if not employees:
		frappe.throw(_("No employees selected."))

	if not ppe_items:
		frappe.throw(_("No PPE Items selected."))

	if not justification:
		frappe.throw(_("Justification is required."))

	created = []
	skipped = []
	failed = []

	for employee_name in employees:
		# Get employee details
		try:
			employee = frappe.get_doc("Employee", employee_name)
		except Exception:
			failed.append({
				"employee": employee_name,
				"ppe_item": "",
				"error": _("Employee {0} not found.").format(employee_name),
			})
			continue

		for ppe_item_name in ppe_items:
			try:
				# Validate against PPE Role Assignment rules
				if not is_combination_covered(employee, ppe_item_name):
					skipped.append({
						"employee": employee_name,
						"employee_name": employee.employee_name,
						"ppe_item": ppe_item_name,
						"reason": _(
							"No PPE Role Assignment rule covers {0} for employee {1} "
							"(Dept: {2}, Designation: {3})."
						).format(
							ppe_item_name,
							employee.employee_name,
							employee.department or "None",
							employee.designation or "None",
						),
					})
					continue

				# Create PPE Request
				ppe_request = frappe.get_doc({
					"doctype": "PPE Request",
					"employee": employee_name,
					"ppe_item": ppe_item_name,
					"requested_quantity": 1,
					"justification": justification,
				})
				ppe_request.insert(ignore_permissions=True)
				ppe_request.submit()

				created.append({
					"employee": employee_name,
					"employee_name": employee.employee_name,
					"ppe_item": ppe_item_name,
					"request_name": ppe_request.name,
				})

			except Exception as e:
				failed.append({
					"employee": employee_name,
					"employee_name": employee.employee_name,
					"ppe_item": ppe_item_name,
					"error": str(e),
				})

	frappe.db.commit()

	return {"created": created, "skipped": skipped, "failed": failed}


def is_combination_covered(employee, ppe_item_name):
	"""Check if an Employee + PPE Item combination is covered by a PPE Role Assignment rule.

	A combination is "covered" if there exists a PPE Role Assignment where:
	- (assignment.department == employee.department OR assignment.department is empty) AND
	- (assignment.designation == employee.designation OR assignment.designation is empty)
	- AND the PPE Item appears in the assignment's required_items child table

	Args:
		employee: Employee document object.
		ppe_item_name: Name (ID) of the PPE Item to check.

	Returns:
		bool: True if covered, False otherwise.
	"""
	# Build conditions for matching assignments
	conditions = []
	values = {"ppe_item": ppe_item_name}

	# Department match: assignment department equals employee's department OR is empty/null
	dept_condition = "(pa.department = %(emp_department)s OR pa.department IS NULL OR pa.department = '')"
	values["emp_department"] = employee.department or ""

	# Designation match: assignment designation equals employee's designation OR is empty/null
	desig_condition = "(pa.designation = %(emp_designation)s OR pa.designation IS NULL OR pa.designation = '')"
	values["emp_designation"] = employee.designation or ""

	result = frappe.db.sql(
		"""
		SELECT pa.name
		FROM `tabPPE Role Assignment` pa
		INNER JOIN `tabPPE Role Assignment Item` pai ON pai.parent = pa.name
		WHERE {dept_condition}
			AND {desig_condition}
			AND pai.ppe_item = %(ppe_item)s
		LIMIT 1
		""".format(dept_condition=dept_condition, desig_condition=desig_condition),
		values,
		as_dict=True,
	)

	return len(result) > 0
