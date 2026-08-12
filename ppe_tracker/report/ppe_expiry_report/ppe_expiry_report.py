# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Expiry Report

Displays all PPE Issue records with status Active or Expired, showing
days until expiry (negative values indicate already-expired items).
Supports filtering by PPE Item, Employee, Department, and expiry date range.

Requirements: 12.1, 12.2, 12.3
"""

import frappe
from frappe.utils import date_diff, today


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "department", "label": "Department", "fieldtype": "Link", "options": "Department", "width": 150},
        {"fieldname": "ppe_item", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 180},
        {"fieldname": "issue_date", "label": "Issue Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "expiry_date", "label": "Expiry Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "days_until_expiry", "label": "Days Until Expiry", "fieldtype": "Int", "width": 140},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    """Query PPE Issue records with Active or Expired status and compute days until expiry."""
    conditions = {"status": ["in", ["Active", "Expired"]]}

    if filters.get("ppe_item"):
        conditions["ppe_item"] = filters["ppe_item"]
    if filters.get("employee"):
        conditions["employee"] = filters["employee"]
    if filters.get("department"):
        conditions["department"] = filters["department"]
    if filters.get("from_date"):
        conditions.setdefault("expiry_date", [])
        if isinstance(conditions["expiry_date"], list):
            conditions["expiry_date"] = [">=", filters["from_date"]]
        else:
            conditions["expiry_date"] = [">=", filters["from_date"]]
    if filters.get("to_date"):
        if filters.get("from_date"):
            conditions["expiry_date"] = ["between", [filters["from_date"], filters["to_date"]]]
        else:
            conditions["expiry_date"] = ["<=", filters["to_date"]]

    issues = frappe.get_all(
        "PPE Issue",
        filters=conditions,
        fields=[
            "employee",
            "employee_name",
            "department",
            "ppe_item",
            "issue_date",
            "expiry_date",
            "status",
        ],
        order_by="expiry_date asc",
    )

    current_date = today()
    data = []
    for issue in issues:
        days_until_expiry = date_diff(issue.expiry_date, current_date)
        data.append(
            {
                "employee": issue.employee,
                "employee_name": issue.employee_name,
                "department": issue.department,
                "ppe_item": issue.ppe_item,
                "issue_date": issue.issue_date,
                "expiry_date": issue.expiry_date,
                "days_until_expiry": days_until_expiry,
                "status": issue.status,
            }
        )

    return data
