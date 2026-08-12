// Copyright (c) 2024, Takataka Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('PPE Item', {
	setup(frm) {
		// Filter item_code Link field to only show Items with item_group = "PPE"
		frm.set_query('item_code', function () {
			return {
				filters: {
					item_group: 'PPE'
				}
			};
		});
	},

	refresh(frm) {
		// Refresh lifespan_table child table grid display
		if (frm.fields_dict.lifespan_table) {
			frm.fields_dict.lifespan_table.grid.refresh();
		}
	}
});
