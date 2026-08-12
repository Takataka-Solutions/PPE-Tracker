# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Employee PPE Register

Displays a unified register of all PPE Issue and PPE Return records for a
selected Employee, sorted by date. Supports filtering by Employee and date range.

When a user holds only the Employee role (and no elevated role such as HR Manager,
HR User, Safety Officer, or System Manager), the report automatically restricts
results to that user's own linked Employee record.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

import frappe


# Elevated roles that bypass employee-level restriction
ELEVATED_ROLES = {"HR Manager", "HR User", "Safety Officer", "System Manager"}


def execute(filters=None):
    filters = filters or {}
    get_employee_filter(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_employee_filter(filters):
    """Enforce employee-level access control.

    If the current user only has the Employee role (and none of the elevated
    roles: HR Manager, HR User, Safety Officer, System Manager), override
    the employee filter to restrict results to their own linked Employee record.
    """
    user_roles = set(frappe.get_roles())

    if user_roles & ELEVATED_ROLES:
        # User has at least one elevated role — no restriction
        return

    # User only has Employee role (or other non-elevated roles)
    employee = frappe.db.get_value(
        "Employee", {"user_id": frappe.session.user}, "name"
    )
    if employee:
        filters["employee"] = employee


def get_columns():
    return [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "ppe_item", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 180},
        {"fieldname": "type", "label": "Type", "fieldtype": "Data", "width": 100},
        {"fieldname": "date", "label": "Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "quantity", "label": "Quantity", "fieldtype": "Int", "width": 100},
        {"fieldname": "status_condition", "label": "Status/Condition", "fieldtype": "Data", "width": 140},
    ]


def get_data(filters):
    """Query PPE Issue and PPE Return records, combine into a unified register."""
    data = []

    # --- PPE Issue records ---
    issue_filters = {"docstatus": 1}
    if filters.get("employee"):
        issue_filters["employee"] = filters["employee"]

    issue_date_conditions = ""
    if filters.get("from_date"):
        issue_date_conditions += " AND pi.issue_date >= %(from_date)s"
    if filters.get("to_date"):
        issue_date_conditions += " AND pi.issue_date <= %(to_date)s"

    issue_query = """
        SELECT
            pi.employee,
            pi.employee_name,
            pi.ppe_item,
            'Issue' AS type,
            pi.issue_date AS date,
            pi.quantity,
            pi.status AS status_condition
        FROM `tabPPE Issue` pi
        WHERE pi.docstatus = 1
            {employee_filter}
            {date_conditions}
    """.format(
        employee_filter="AND pi.employee = %(employee)s" if filters.get("employee") else "",
        date_conditions=issue_date_conditions,
    )

    issues = frappe.db.sql(issue_query, filters, as_dict=True)
    data.extend(issues)

    # --- PPE Return records ---
    return_date_conditions = ""
    if filters.get("from_date"):
        return_date_conditions += " AND pr.return_date >= %(from_date)s"
    if filters.get("to_date"):
        return_date_conditions += " AND pr.return_date <= %(to_date)s"

    return_query = """
        SELECT
            pr.employee,
            pr.employee_name,
            pr.ppe_item,
            'Return' AS type,
            pr.return_date AS date,
            pr.quantity_returned AS quantity,
            pr.condition AS status_condition
        FROM `tabPPE Return` pr
        WHERE pr.docstatus = 1
            {employee_filter}
            {date_conditions}
    """.format(
        employee_filter="AND pr.employee = %(employee)s" if filters.get("employee") else "",
        date_conditions=return_date_conditions,
    )

    returns = frappe.db.sql(return_query, filters, as_dict=True)
    data.extend(returns)

    # Sort combined data by date (ascending)
    data.sort(key=lambda row: row.get("date") or "")

    return data
