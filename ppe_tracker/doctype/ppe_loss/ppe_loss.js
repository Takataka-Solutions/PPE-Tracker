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
});
