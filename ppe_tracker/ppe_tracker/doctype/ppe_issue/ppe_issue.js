// Copyright (c) 2024, Takataka Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPE Issue", {
	refresh(frm) {
		// expiry_date, status, and stock_entry are read_only in the schema,
		// but ensure they remain non-editable on form refresh
		frm.set_df_property("expiry_date", "read_only", 1);
		frm.set_df_property("status", "read_only", 1);
		frm.set_df_property("stock_entry", "read_only", 1);

		// Apply issue_type logic on refresh
		frm.trigger("issue_type");
	},

	issue_type(frm) {
		if (frm.doc.issue_type === "Casual") {
			// Filter Employee field to show only casual employees
			frm.set_query("employee", function () {
				return {
					filters: {
						employment_type: "Casual",
					},
				};
			});
			// Default expected_return_date to today if not set
			if (!frm.doc.expected_return_date) {
				frm.set_value("expected_return_date", frappe.datetime.get_today());
			}
		} else {
			// Remove casual employee filter
			frm.set_query("employee", function () {
				return {};
			});
		}
	},

	ppe_request(frm) {
		// Auto-fetch employee and ppe_item from linked PPE Request
		if (frm.doc.ppe_request) {
			frappe.model.with_doc("PPE Request", frm.doc.ppe_request, function () {
				const req = frappe.model.get_doc("PPE Request", frm.doc.ppe_request);
				frm.set_value("employee", req.employee);
				frm.set_value("ppe_item", req.ppe_item);
			});
		} else {
			frm.set_value("employee", "");
			frm.set_value("ppe_item", "");
		}
	},

	issue_date(frm) {
		refreshExpiryPreview(frm);
	},

	ppe_item(frm) {
		refreshExpiryPreview(frm);
	},
});

function refreshExpiryPreview(frm) {
	if (frm.doc.ppe_item && frm.doc.employee && frm.doc.issue_date) {
		frappe.call({
			method: "ppe_tracker.ppe_tracker.ppe_tracker.api.ppe_api.get_resolved_lifespan",
			args: {
				ppe_item: frm.doc.ppe_item,
				employee: frm.doc.employee,
			},
			callback: function (r) {
				if (r.message) {
					const lifespanMonths = r.message.lifespan_months;
					const source = r.message.source;
					const expiryDate = frappe.datetime.add_months(
						frm.doc.issue_date,
						lifespanMonths
					);
					const sourceLabel =
						source === "position_type_match"
							? __("position type")
							: __("default");

					frm.dashboard.set_headline(
						__("Expiry Preview: {0} ({1} months from {2})", [
							frappe.datetime.str_to_user(expiryDate),
							lifespanMonths,
							sourceLabel,
						])
					);
				}
			},
		});
	} else {
		frm.dashboard.clear_headline();
	}
}
