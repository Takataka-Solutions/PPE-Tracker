// Copyright (c) 2024, Takataka Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPE Loss", {
	refresh(frm) {
		// Show attachment field only when method is Supervisor Uploaded
		frm.toggle_display("acknowledgement_attachment",
			frm.doc.acknowledgement_method === "Supervisor Uploaded");
	},

	acknowledgement_method(frm) {
		frm.toggle_display("acknowledgement_attachment",
			frm.doc.acknowledgement_method === "Supervisor Uploaded");
	},

	ppe_issue(frm) {
		if (!frm.doc.ppe_issue) {
			frm.set_value("surcharge_amount", 0);
			return;
		}

		// Chain: PPE Issue → ppe_item → PPE Item → item_code → Item (valuation_rate / standard_rate)
		frappe.db.get_value("PPE Issue", frm.doc.ppe_issue, "ppe_item", (issue) => {
			if (!issue || !issue.ppe_item) return;

			frappe.db.get_value("PPE Item", issue.ppe_item, "item_code", (ppeItem) => {
				if (!ppeItem || !ppeItem.item_code) return;

				frappe.db.get_value("Item", ppeItem.item_code,
					["valuation_rate", "standard_rate"], (item) => {
						if (!item) return;

						// Use valuation_rate first, fall back to standard_rate
						let amount = item.valuation_rate || item.standard_rate || 0;
						frm.set_value("surcharge_amount", amount);
					}
				);
			});
		});
	},
});
