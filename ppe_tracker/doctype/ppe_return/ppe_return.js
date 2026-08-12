// Copyright (c) 2024, Takataka Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPE Return", {
	refresh(frm) {
		// Ensure fetched fields remain read-only on form refresh
		frm.set_df_property("employee", "read_only", 1);
		frm.set_df_property("employee_name", "read_only", 1);
		frm.set_df_property("ppe_item", "read_only", 1);
	},

	ppe_issue(frm) {
		// Auto-fetch employee and ppe_item from linked PPE Issue
		if (frm.doc.ppe_issue) {
			frappe.model.with_doc("PPE Issue", frm.doc.ppe_issue, function () {
				const issue = frappe.model.get_doc("PPE Issue", frm.doc.ppe_issue);
				frm.set_value("employee", issue.employee);
				frm.set_value("ppe_item", issue.ppe_item);
			});
		} else {
			frm.set_value("employee", "");
			frm.set_value("ppe_item", "");
		}
	},
});
