# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""PPE Compliance Summary Report

Displays total PPE demand for active employees versus what has been requested,
issued, and what stock is available. Helps plan procurement and identify
compliance gaps.

Columns: PPE Item, PPE Category, Required Qty, Requested Qty, Issued Qty,
         Available Stock, Gap

Logic per PPE Item:
  - Required Qty: count active employees matching each PPE Role Assignment's
    dept/designation × the assignment quantity for that item
  - Requested Qty: sum of quantities from pending/approved/submitted PPE Requests
  - Issued Qty: sum of quantities from active PPE Issues (docstatus=1, status=Active)
  - Available Stock: actual_qty from ERPNext Bin for the linked Item code
  - Gap: Required - Issued - Available Stock (positive = shortfall)

Sorted by Gap descending (biggest shortfall first).

Filters: Department, Designation, PPE Item, Reference Date
Roles: HR Manager, Safety Officer, Storekeeper, System Manager

Requirements: 25.1, 25.2, 25.3, 25.4
"""

import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": _("PPE Item"), "fieldname": "ppe_item", "fieldtype": "Link", "options": "PPE Item", "width": 200},
        {"label": _("PPE Category"), "fieldname": "ppe_category", "fieldtype": "Data", "width": 150},
        {"label": _("Required Qty"), "fieldname": "required_qty", "fieldtype": "Int", "width": 110},
        {"label": _("Requested Qty"), "fieldname": "requested_qty", "fieldtype": "Int", "width": 120},
        {"label": _("Issued Qty"), "fieldname": "issued_qty", "fieldtype": "Int", "width": 110},
        {"label": _("Available Stock"), "fieldname": "available_stock", "fieldtype": "Float", "width": 130},
        {"label": _("Gap"), "fieldname": "gap", "fieldtype": "Float", "width": 100},
    ]


def get_data(filters):
    """Build compliance summary data grouped by PPE Item."""
    if not filters:
        filters = {}

    reference_date = filters.get("reference_date") or today()

    # Step 1: Fetch PPE Role Assignments (filtered by dept/designation)
    assignment_conditions = []
    assignment_values = {}

    if filters.get("department"):
        assignment_conditions.append("pra.department = %(department)s")
        assignment_values["department"] = filters["department"]

    if filters.get("designation"):
        assignment_conditions.append("pra.designation = %(designation)s")
        assignment_values["designation"] = filters["designation"]

    assignment_where = " AND ".join(assignment_conditions) if assignment_conditions else "1=1"

    assignments = frappe.db.sql("""
        SELECT
            pra.name AS assignment_name,
            pra.department,
            pra.designation,
            prai.ppe_item,
            prai.quantity
        FROM `tabPPE Role Assignment` pra
        INNER JOIN `tabPPE Role Assignment Item` prai
            ON prai.parent = pra.name AND prai.parenttype = 'PPE Role Assignment'
        WHERE {where_clause}
    """.format(where_clause=assignment_where), assignment_values, as_dict=True)

    if not assignments:
        return []

    # Step 2: For each unique PPE Item, calculate required qty
    # Required = count of active employees matching dept/designation × quantity
    ppe_item_required = {}  # {ppe_item: total_required}

    for assignment in assignments:
        emp_conditions = ["emp.status = %(emp_status)s"]
        emp_values = {"emp_status": "Active"}

        # Employee must have been active as of reference_date
        emp_conditions.append(
            "(emp.date_of_joining IS NULL OR emp.date_of_joining <= %(reference_date)s)"
        )
        emp_values["reference_date"] = reference_date

        # Employees who have left before reference_date should be excluded
        emp_conditions.append(
            "(emp.relieving_date IS NULL OR emp.relieving_date > %(reference_date)s)"
        )

        if assignment.department:
            emp_conditions.append("emp.department = %(department)s")
            emp_values["department"] = assignment.department

        if assignment.designation:
            emp_conditions.append("emp.designation = %(designation)s")
            emp_values["designation"] = assignment.designation

        emp_where = " AND ".join(emp_conditions)

        emp_count_result = frappe.db.sql("""
            SELECT COUNT(emp.name) AS cnt
            FROM `tabEmployee` emp
            WHERE {where_clause}
        """.format(where_clause=emp_where), emp_values, as_dict=True)

        emp_count = emp_count_result[0].cnt if emp_count_result else 0

        required = emp_count * (assignment.quantity or 1)

        ppe_item = assignment.ppe_item
        ppe_item_required[ppe_item] = ppe_item_required.get(ppe_item, 0) + required

    # Apply ppe_item filter if specified
    if filters.get("ppe_item"):
        filter_item = filters["ppe_item"]
        if filter_item in ppe_item_required:
            ppe_item_required = {filter_item: ppe_item_required[filter_item]}
        else:
            return []

    # Step 3: For each PPE Item, get requested qty, issued qty, available stock
    data = []
    for ppe_item, required_qty in ppe_item_required.items():
        # Get PPE Item category and item_code
        ppe_item_details = frappe.db.get_value(
            "PPE Item", ppe_item, ["ppe_category", "item_code"], as_dict=True
        )
        if not ppe_item_details:
            continue

        ppe_category = ppe_item_details.ppe_category or ""
        item_code = ppe_item_details.item_code

        # Requested Qty: sum qty from PPE Requests with status in (Pending Approval, Approved, Submitted)
        requested_qty = get_requested_qty(ppe_item)

        # Issued Qty: sum qty from active PPE Issues (docstatus=1, status=Active)
        issued_qty = get_issued_qty(ppe_item)

        # Available Stock: actual_qty from ERPNext Bin
        available_stock = get_available_stock(item_code)

        # Gap: Required - Issued - Available Stock
        gap = required_qty - issued_qty - available_stock

        data.append({
            "ppe_item": ppe_item,
            "ppe_category": ppe_category,
            "required_qty": required_qty,
            "requested_qty": requested_qty,
            "issued_qty": issued_qty,
            "available_stock": available_stock,
            "gap": gap,
        })

    # Sort by gap descending (biggest shortfall first)
    data.sort(key=lambda x: x["gap"], reverse=True)

    return data


def get_requested_qty(ppe_item):
    """Sum requested_quantity from PPE Requests with pending/approved/submitted status."""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(pr.requested_quantity), 0) AS total
        FROM `tabPPE Request` pr
        WHERE pr.ppe_item = %(ppe_item)s
            AND pr.status IN ('Pending Approval', 'Approved', 'Submitted')
            AND pr.docstatus < 2
    """, {"ppe_item": ppe_item}, as_dict=True)

    return result[0].total if result else 0


def get_issued_qty(ppe_item):
    """Sum quantity from active PPE Issues (docstatus=1, status=Active)."""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(pi.quantity), 0) AS total
        FROM `tabPPE Issue` pi
        WHERE pi.ppe_item = %(ppe_item)s
            AND pi.docstatus = 1
            AND pi.status = 'Active'
    """, {"ppe_item": ppe_item}, as_dict=True)

    return result[0].total if result else 0


def get_available_stock(item_code):
    """Fetch total actual_qty from ERPNext Bin for the given item_code."""
    if not item_code:
        return 0

    result = frappe.db.sql("""
        SELECT COALESCE(SUM(b.actual_qty), 0) AS total
        FROM `tabBin` b
        WHERE b.item_code = %(item_code)s
    """, {"item_code": item_code}, as_dict=True)

    return result[0].total if result else 0
