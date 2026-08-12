# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Issuance Report

Displays all PPE Issue records including Employee, Employee Name, Department,
PPE Item, issue date, expiry date, quantity, and status.
Supports filtering by date range, Employee, Department, PPE Item, and status.

Requirements: 11.1, 11.2, 11.3
"""

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "department", "label": "Department", "fieldtype": "Data", "width": 150},
        {"fieldname": "ppe_item", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 180},
        {"fieldname": "issue_date", "label": "Issue Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "expiry_date", "label": "Expiry Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "quantity", "label": "Qty", "fieldtype": "Int", "width": 80},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    """Query PPE Issue records with filters applied."""
    conditions = {}

    if filters.get("employee"):
        conditions["employee"] = filters["employee"]
    if filters.get("department"):
        conditions["department"] = filters["department"]
    if filters.get("ppe_item"):
        conditions["ppe_item"] = filters["ppe_item"]
    if filters.get("status"):
        conditions["status"] = filters["status"]

    # Date range filter on issue_date
    if filters.get("from_date"):
        conditions["issue_date"] = [">=", filters["from_date"]]
    if filters.get("to_date"):
        if "issue_date" in conditions:
            # Both from_date and to_date specified — use between
            conditions["issue_date"] = ["between", [filters["from_date"], filters["to_date"]]]
        else:
            conditions["issue_date"] = ["<=", filters["to_date"]]

    data = frappe.get_all(
        "PPE Issue",
        filters=conditions,
        fields=[
            "employee",
            "employee_name",
            "department",
            "ppe_item",
            "issue_date",
            "expiry_date",
            "quantity",
            "status",
        ],
        order_by="issue_date desc",
    )

    return data
