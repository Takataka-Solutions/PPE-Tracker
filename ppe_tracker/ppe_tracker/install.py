"""
PPE Tracker install/migrate hooks.

Sets up permissions for custom roles on standard ERPNext DocTypes
that cannot be modified via fixture JSON files directly.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

# Roles this app owns. Seeded here rather than shipped as a fixture: Role is a
# global DocType, and an unfiltered Role fixture on a shared site captures every
# role present, including takataka_solutions' own. See BLOCK-002.
#
# desk_access mirrors the previous fixtures/role.json exactly, so behaviour is
# unchanged. Only MRF User set it explicitly there; the other two are left to
# Frappe's default. Confirm during UAT that Safety Officer has the desk access it
# needs to action the PPE Request Approval workflow.
PPE_ROLES = (
    {"role_name": "Safety Officer", "is_custom": 1},
    {"role_name": "Storekeeper", "is_custom": 1},
    {"role_name": "MRF User", "is_custom": 1, "desk_access": 1},
)


def after_install():
    """Run once on bench install-app.

    Wired so a fresh install does not depend on a later `bench migrate` to
    become usable. Everything called here is idempotent, so the overlap with
    after_migrate is harmless.
    """
    after_migrate()


def after_migrate():
    """Run after every bench migrate to ensure roles and permissions are in place."""
    ensure_roles()
    setup_mrf_user_permissions()
    frappe.db.commit()


def ensure_roles():
    """Create this app's roles if absent. Idempotent; never modifies existing roles.

    Existing roles are left untouched on purpose. On a shared site a role may
    already exist and be in use by another app, and silently rewriting its
    properties would be a cross-app side effect.
    """
    for role in PPE_ROLES:
        if frappe.db.exists("Role", role["role_name"]):
            continue
        doc = frappe.new_doc("Role")
        doc.update(role)
        doc.insert(ignore_permissions=True)


def setup_mrf_user_permissions():
    """
    Configure MRF User role permissions on Stock Entry and Warehouse DocTypes.

    MRF User needs:
    - Read/Write access to Warehouse (filtered to Wornout PPE Warehouse via User Permission at runtime)
    - Read/Write/Create permission on Stock Entry (to create Material Issue for disposal/sale)

    Note: The actual warehouse-level filtering (restricting MRF User to only the Wornout PPE
    Warehouse) is done at runtime via User Permissions assigned by the admin. This setup only
    grants the base DocType-level permissions that the role requires.
    """
    _setup_warehouse_permissions()
    _setup_stock_entry_permissions()


def _setup_warehouse_permissions():
    """Grant MRF User read/write access to Warehouse DocType."""
    role = "MRF User"
    doctype = "Warehouse"

    if not _role_has_permission(doctype, role):
        add_permission(doctype, role, permlevel=0)

    # Set read and write permissions
    update_permission_property(doctype, role, permlevel=0, ptype="read", value=1)
    update_permission_property(doctype, role, permlevel=0, ptype="write", value=1)

    # MRF User should not create/delete warehouses
    update_permission_property(doctype, role, permlevel=0, ptype="create", value=0)
    update_permission_property(doctype, role, permlevel=0, ptype="delete", value=0)

    # Enable User Permission filtering so MRF User only sees warehouses
    # they are explicitly granted access to (i.e., Wornout PPE Warehouse)
    update_permission_property(
        doctype, role, permlevel=0, ptype="if_owner", value=0
    )


def _setup_stock_entry_permissions():
    """Grant MRF User read/write/create access to Stock Entry DocType."""
    role = "MRF User"
    doctype = "Stock Entry"

    if not _role_has_permission(doctype, role):
        add_permission(doctype, role, permlevel=0)

    # MRF User can read, write, create, and submit Stock Entries
    update_permission_property(doctype, role, permlevel=0, ptype="read", value=1)
    update_permission_property(doctype, role, permlevel=0, ptype="write", value=1)
    update_permission_property(doctype, role, permlevel=0, ptype="create", value=1)
    update_permission_property(doctype, role, permlevel=0, ptype="submit", value=1)
    update_permission_property(doctype, role, permlevel=0, ptype="cancel", value=1)

    # MRF User should not delete Stock Entries
    update_permission_property(doctype, role, permlevel=0, ptype="delete", value=0)


def _role_has_permission(doctype, role):
    """Check if a role already has any permission entry for a DocType."""
    return frappe.db.exists(
        "Custom DocPerm",
        {"parent": doctype, "role": role}
    ) or frappe.db.exists(
        "DocPerm",
        {"parent": doctype, "role": role}
    )
