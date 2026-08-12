import frappe


def execute():
    """Rename PPE Assignment → PPE Role Assignment and add quantity column.

    This patch handles upgrades from v1.0 where the DocType was called
    "PPE Assignment". On fresh installs where the old DocType does not
    exist, the patch silently skips.

    Idempotent — safe to run multiple times.
    """

    # Check if old DocType exists; if not, this is a fresh install — skip
    if not frappe.db.exists("DocType", "PPE Assignment"):
        return

    # --- Rename parent DocType ---
    if not frappe.db.exists("DocType", "PPE Role Assignment"):
        frappe.rename_doc("DocType", "PPE Assignment", "PPE Role Assignment", force=True)

    # --- Rename child DocType ---
    if not frappe.db.exists("DocType", "PPE Role Assignment Item"):
        if frappe.db.exists("DocType", "PPE Assignment Item"):
            frappe.rename_doc("DocType", "PPE Assignment Item", "PPE Role Assignment Item", force=True)

    # --- Add quantity column if not already present ---
    table_name = "tabPPE Role Assignment Item"
    if frappe.db.table_exists(table_name):
        columns = frappe.db.get_table_columns(table_name)
        if "quantity" not in columns:
            frappe.db.sql("""
                ALTER TABLE `{table}`
                ADD COLUMN `quantity` INT(11) NOT NULL DEFAULT 1
            """.format(table=table_name))

        # Backfill existing rows that have NULL or 0 quantity
        frappe.db.sql("""
            UPDATE `{table}`
            SET `quantity` = 1
            WHERE `quantity` IS NULL OR `quantity` = 0
        """.format(table=table_name))

    frappe.db.commit()
