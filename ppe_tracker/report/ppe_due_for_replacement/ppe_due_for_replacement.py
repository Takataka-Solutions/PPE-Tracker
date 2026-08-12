# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Due for Replacement Report

Lists all Active PPE Issue records whose expiry date falls within a
user-specified number of days (default 30) from the current date.
Enriches each record with Department and Designation from the Employee
DocType and computes days remaining until expiry.

Filters: days_window, Department, Designation, PPE Item
Roles: HR Manager, Safety Officer, System Manager

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5
"""

import frappe
from frappe.utils import today, add_days, date_diff


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "department", "label": "Department", "fieldtype": "Link", "options": "Department", "width": 150},
        {"fieldname": "designation", "label": "Designation", "fieldtype": "Link", "options": "Designation", "width": 150},
        {"fieldname": "ppe_item", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 150},
        {"fieldname": "issue_date", "label": "Issue Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "expiry_date", "label": "Expiry Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "days_remaining", "label": "Days Remaining", "fieldtype": "Int", "width": 120},
        {"fieldname": "quantity", "label": "Quantity", "fieldtype": "Int", "width": 90},
    ]


def get_data(filters):
    """Query Active PPE Issues expiring within the specified days window."""
    days_window = filters.get("days_window") or 30
    current_date = today()
    threshold = add_days(current_date, days_window)

    # Use list-style filters to support multiple conditions on expiry_date
    issue_conditions = [
        ["PPE Issue", "status", "=", "Active"],
        ["PPE Issue", "expiry_date", "<=", threshold],
        ["PPE Issue", "expiry_date", ">=", current_date],
    ]

    if filters.get("ppe_item"):
        issue_conditions.append(["PPE Issue", "ppe_item", "=", filters["ppe_item"]])

    issues = frappe.get_all(
        "PPE Issue",
        filters=issue_conditions,
        fields=["name", "employee", "employee_name", "ppe_item", "issue_date", "expiry_date", "quantity"],
    )

    data = []
    for issue in issues:
        # Enrich with Department and Designation from Employee DocType
        employee_details = frappe.db.get_value(
            "Employee",
            issue.employee,
            ["department", "designation"],
            as_dict=True,
        ) or {}

        department = employee_details.get("department", "")
        designation = employee_details.get("designation", "")

        # Apply optional department filter
        if filters.get("department") and department != filters["department"]:
            continue

        # Apply optional designation filter
        if filters.get("designation") and designation != filters["designation"]:
            continue

        # Compute days remaining until expiry
        days_remaining = date_diff(issue.expiry_date, current_date)

        data.append({
            "employee": issue.employee,
            "employee_name": issue.employee_name,
            "department": department,
            "designation": designation,
            "ppe_item": issue.ppe_item,
            "issue_date": issue.issue_date,
            "expiry_date": issue.expiry_date,
            "days_remaining": days_remaining,
            "quantity": issue.quantity,
        })

    # Sort by days remaining (most urgent first)
    data.sort(key=lambda x: x["days_remaining"])

    return data
