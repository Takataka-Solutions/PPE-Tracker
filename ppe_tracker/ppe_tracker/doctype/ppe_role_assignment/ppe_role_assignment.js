// Copyright (c) 2024, Takataka Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('PPE Role Assignment', {
	refresh(frm) {
		// Show intro message if neither department nor designation is selected
		frm.set_intro('');
		if (!frm.doc.department && !frm.doc.designation) {
			frm.set_intro(
				__('Please select at least a Department or Designation.'),
				'yellow'
			);
		}

		// Set filter on ppe_item in child table to show only Active PPE Items
		frm.set_query('ppe_item', 'required_items', function () {
			return {
				filters: {
					status: 'Active'
				}
			};
		});
	},

	department(frm) {
		// Clear intro when a value is selected
		if (frm.doc.department || frm.doc.designation) {
			frm.set_intro('');
		} else {
			frm.set_intro(
				__('Please select at least a Department or Designation.'),
				'yellow'
			);
		}
	},

	designation(frm) {
		// Clear intro when a value is selected
		if (frm.doc.department || frm.doc.designation) {
			frm.set_intro('');
		} else {
			frm.set_intro(
				__('Please select at least a Department or Designation.'),
				'yellow'
			);
		}
	},

	validate(frm) {
		// Client-side validation: at least one of department or designation required
		if (!frm.doc.department && !frm.doc.designation) {
			frappe.msgprint({
				title: __('Validation'),
				indicator: 'red',
				message: __('At least one of Department or Designation must be specified.')
			});
			frappe.validated = false;
		}
	}
});
