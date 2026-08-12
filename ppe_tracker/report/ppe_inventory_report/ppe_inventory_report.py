# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Inventory Report

Displays current PPE stock levels per item, including ERPNext Item code,
warehouse stock quantity (from Bin), and active issued quantity.
Supports filtering by PPE Item, PPE Category, and Warehouse.

Requirements: 10.1, 10.2, 10.3
"""

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"fieldname": "item_name", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 200},
        {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "ppe_category", "label": "Category", "fieldtype": "Data", "width": 150},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
        {"fieldname": "stock_qty", "label": "Stock Qty", "fieldtype": "Int", "width": 100},
        {"fieldname": "active_issued", "label": "Active Issued", "fieldtype": "Int", "width": 120},
    ]


def get_data(filters):
    """Query PPE Items with stock and active issuance data."""
    conditions = {}
    if filters.get("ppe_item"):
        conditions["name"] = filters["ppe_item"]
    if filters.get("ppe_category"):
        conditions["ppe_category"] = filters["ppe_category"]

    ppe_items = frappe.get_all(
        "PPE Item",
        filters=conditions,
        fields=["name", "item_name", "item_code", "ppe_category", "status"],
    )

    data = []
    for item in ppe_items:
        # Get stock qty from Bin
        stock_qty = get_stock_qty(item.item_code, filters.get("warehouse"))

        # Count active issued PPE Issues for this item
        active_issued = frappe.db.count(
            "PPE Issue", filters={"ppe_item": item.name, "status": "Active"}
        )

        data.append(
            {
                "item_name": item.name,
                "item_code": item.item_code,
                "ppe_category": item.ppe_category,
                "status": item.status,
                "stock_qty": stock_qty,
                "active_issued": active_issued,
            }
        )

    return data


def get_stock_qty(item_code, warehouse=None):
    """Fetch actual_qty from Bin for the given item_code and optional warehouse."""
    filters = {"item_code": item_code}
    if warehouse:
        filters["warehouse"] = warehouse

    bins = frappe.get_all("Bin", filters=filters, fields=["actual_qty"])
    return sum(b.actual_qty for b in bins) if bins else 0
