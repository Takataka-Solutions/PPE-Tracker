# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Inventory Report

Displays current PPE stock levels per item across three configured warehouses:
Default Issue Warehouse, Returned PPE Warehouse, and Wornout PPE Warehouse.
Shows per-warehouse stock columns with dynamic labels from PPE Tracker Settings,
a total stock column, and active issued quantity.

Supports filtering by PPE Item, PPE Category, and optional Warehouse override.

Requirements: 2.4, 7.4, 8.3
"""

import frappe


def execute(filters=None):
    # Fetch warehouse configuration from PPE Tracker Settings
    default_wh = frappe.db.get_single_value("PPE Tracker Settings", "default_issue_warehouse")
    returned_wh = frappe.db.get_single_value("PPE Tracker Settings", "returned_ppe_warehouse")
    wornout_wh = frappe.db.get_single_value("PPE Tracker Settings", "wornout_ppe_warehouse")

    columns = get_columns(default_wh, returned_wh, wornout_wh)
    data = get_data(filters, default_wh, returned_wh, wornout_wh)
    return columns, data


def get_columns(default_wh=None, returned_wh=None, wornout_wh=None):
    """Build report columns with dynamic warehouse labels from Settings."""
    default_label = default_wh or "Default Issue Warehouse"
    returned_label = returned_wh or "Returned PPE Warehouse"
    wornout_label = wornout_wh or "Wornout PPE Warehouse"

    return [
        {"fieldname": "item_name", "label": "PPE Item", "fieldtype": "Link", "options": "PPE Item", "width": 200},
        {"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "ppe_category", "label": "Category", "fieldtype": "Data", "width": 150},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 100},
        {"fieldname": "default_wh_stock", "label": default_label, "fieldtype": "Int", "width": 150},
        {"fieldname": "returned_wh_stock", "label": returned_label, "fieldtype": "Int", "width": 150},
        {"fieldname": "wornout_wh_stock", "label": wornout_label, "fieldtype": "Int", "width": 150},
        {"fieldname": "total_stock", "label": "Total Stock", "fieldtype": "Int", "width": 100},
        {"fieldname": "active_issued", "label": "Active Issued", "fieldtype": "Int", "width": 120},
    ]


def get_data(filters, default_wh=None, returned_wh=None, wornout_wh=None):
    """Query PPE Items with per-warehouse stock and active issuance data."""
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
        # Get stock qty per warehouse
        default_stock = get_stock_qty(item.item_code, default_wh) if default_wh else 0
        returned_stock = get_stock_qty(item.item_code, returned_wh) if returned_wh else 0
        wornout_stock = get_stock_qty(item.item_code, wornout_wh) if wornout_wh else 0

        # If a specific warehouse filter is applied, show that warehouse's stock in total
        if filters.get("warehouse"):
            total_stock = get_stock_qty(item.item_code, filters["warehouse"])
        else:
            total_stock = default_stock + returned_stock + wornout_stock

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
                "default_wh_stock": default_stock,
                "returned_wh_stock": returned_stock,
                "wornout_wh_stock": wornout_stock,
                "total_stock": total_stock,
                "active_issued": active_issued,
            }
        )

    return data


def get_stock_qty(item_code, warehouse=None):
    """Fetch actual_qty from Bin for the given item_code and optional warehouse."""
    if not item_code:
        return 0

    filters = {"item_code": item_code}
    if warehouse:
        filters["warehouse"] = warehouse

    bins = frappe.get_all("Bin", filters=filters, fields=["actual_qty"])
    return sum(b.actual_qty for b in bins) if bins else 0
