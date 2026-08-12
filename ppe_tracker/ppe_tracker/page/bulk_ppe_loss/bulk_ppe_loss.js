frappe.pages["bulk-ppe-loss"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bulk PPE Loss"),
		single_column: true,
	});

	page.main.addClass("frappe-card");
	page.body = $('<div class="bulk-ppe-loss-container"></div>').appendTo(
		page.main
	);

	// Add filter fields
	page.add_field({
		fieldname: "employee",
		label: __("Employee"),
		fieldtype: "Link",
		options: "Employee",
	});

	page.add_field({
		fieldname: "department",
		label: __("Department"),
		fieldtype: "Link",
		options: "Department",
	});

	page.add_field({
		fieldname: "ppe_item",
		label: __("PPE Item"),
		fieldtype: "Link",
		options: "PPE Item",
	});

	// Add Fetch button in the filter area
	page.add_button(__("Fetch"), function () {
		loadData(page);
	});

	// Add primary action button
	page.set_primary_action(__("Record Losses"), function () {
		recordLosses(page);
	});

	// Store page reference
	wrapper.bulkPpeLossPage = page;

	// Render the controls section (loss date, reason) and empty table
	renderControls(page);
};

frappe.pages["bulk-ppe-loss"].on_page_show = function (wrapper) {
	// Reload data when page is shown again
	if (wrapper.bulkPpeLossPage) {
		renderControls(wrapper.bulkPpeLossPage);
	}
};

function getFilters(page) {
	var filters = {};
	var employee = page.fields_dict.employee.get_value();
	var department = page.fields_dict.department.get_value();
	var ppeItem = page.fields_dict.ppe_item.get_value();

	if (employee) filters.employee = employee;
	if (department) filters.department = department;
	if (ppeItem) filters.ppe_item = ppeItem;

	return filters;
}

function renderControls(page) {
	var html = '<div class="bulk-ppe-loss-controls" style="padding: 15px;">';

	// Loss Date and Reason fields
	html += '<div class="row" style="margin-bottom: 15px;">';
	html += '<div class="col-md-4">';
	html += '<label class="control-label">' + __("Loss Date") + ' <span class="text-danger">*</span></label>';
	html += '<input type="date" class="form-control loss-date-input" value="' + frappe.datetime.get_today() + '">';
	html += '</div>';
	html += '<div class="col-md-8">';
	html += '<label class="control-label">' + __("Reason") + ' <span class="text-danger">*</span></label>';
	html += '<input type="text" class="form-control loss-reason-input" placeholder="' + __("Enter reason for loss (e.g., theft, damage during transport)") + '">';
	html += '</div>';
	html += '</div>';

	// Table placeholder
	html += '<div class="bulk-ppe-loss-table-area">';
	html += '<div class="text-muted text-center" style="padding: 40px;">';
	html += '<p><i class="fa fa-search" style="font-size: 48px;"></i></p>';
	html += '<p>' + __("Use the filters above and click Fetch to load eligible PPE Issues.") + '</p>';
	html += '</div>';
	html += '</div>';

	html += '</div>';

	page.body.html(html);
}

function loadData(page) {
	var tableArea = page.body.find(".bulk-ppe-loss-table-area");
	tableArea.html(
		'<div class="text-muted text-center" style="padding: 40px;">' +
			__("Loading...") +
			"</div>"
	);

	frappe.call({
		method: "ppe_tracker.ppe_tracker.api.bulk_loss.get_eligible_losses",
		args: {
			filters: getFilters(page),
		},
		callback: function (r) {
			if (r.message) {
				renderTable(page, r.message);
			} else {
				renderTable(page, []);
			}
		},
		error: function () {
			tableArea.html(
				'<div class="text-muted text-center" style="padding: 40px;">' +
					__("Failed to load data. Please try again.") +
					"</div>"
			);
		},
	});
}

function renderTable(page, data) {
	var tableArea = page.body.find(".bulk-ppe-loss-table-area");

	if (!data || data.length === 0) {
		tableArea.html(
			'<div class="text-muted text-center" style="padding: 40px;">' +
				'<p><i class="fa fa-check-circle text-success" style="font-size: 48px;"></i></p>' +
				"<p>" +
				__("No active PPE Issues found matching the filters.") +
				"</p>" +
				"</div>"
		);
		return;
	}

	var html = '';
	html += '<div class="text-muted small" style="margin-bottom: 10px;">';
	html += __("{0} active issue(s) eligible for loss recording", [data.length]);
	html += "</div>";
	html += '<table class="table table-bordered table-hover">';
	html += "<thead><tr>";
	html +=
		'<th style="width: 40px;"><input type="checkbox" class="select-all-checkbox" title="' +
		__("Select All") +
		'"></th>';
	html += "<th>" + __("Employee Name") + "</th>";
	html += "<th>" + __("Department") + "</th>";
	html += "<th>" + __("PPE Item") + "</th>";
	html += "<th>" + __("Issue Date") + "</th>";
	html += "<th>" + __("Qty Issued") + "</th>";
	html += "<th>" + __("PPE Issue ID") + "</th>";
	html += "</tr></thead>";
	html += "<tbody>";

	data.forEach(function (row) {
		var issueDate = frappe.datetime.str_to_user(row.issue_date);
		html += '<tr data-issue="' + row.name + '">';
		html +=
			'<td><input type="checkbox" class="row-checkbox" data-issue="' +
			row.name +
			'"></td>';
		html += "<td>" + frappe.utils.escape_html(row.employee_name || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(row.department || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(row.ppe_item_name || row.ppe_item || "") + "</td>";
		html += "<td>" + (issueDate || "") + "</td>";
		html += "<td>" + (row.quantity || 0) + "</td>";
		html += '<td><a href="/app/ppe-issue/' + row.name + '">' + frappe.utils.escape_html(row.name) + "</a></td>";
		html += "</tr>";
	});

	html += "</tbody></table>";

	tableArea.html(html);

	// Bind select-all checkbox
	tableArea.find(".select-all-checkbox").on("change", function () {
		var checked = $(this).prop("checked");
		tableArea.find(".row-checkbox").prop("checked", checked);
	});

	// Update select-all when individual checkboxes change
	tableArea.find(".row-checkbox").on("change", function () {
		var total = tableArea.find(".row-checkbox").length;
		var checked = tableArea.find(".row-checkbox:checked").length;
		tableArea.find(".select-all-checkbox").prop("checked", total === checked);
	});
}

function recordLosses(page) {
	// Gather selected items
	var selectedIssues = [];
	page.body.find(".row-checkbox:checked").each(function () {
		selectedIssues.push($(this).data("issue"));
	});

	if (selectedIssues.length === 0) {
		frappe.msgprint(__("Please select at least one PPE Issue to record a loss."));
		return;
	}

	// Get loss date and reason
	var lossDate = page.body.find(".loss-date-input").val();
	var reason = page.body.find(".loss-reason-input").val();

	if (!lossDate) {
		frappe.msgprint(__("Please enter a Loss Date."));
		return;
	}

	if (!reason || !reason.trim()) {
		frappe.msgprint(__("Please enter a Reason for the loss."));
		return;
	}

	// Build items payload
	var items = selectedIssues.map(function (issueName) {
		return {
			ppe_issue: issueName,
			loss_date: lossDate,
			reason: reason.trim(),
		};
	});

	frappe.confirm(
		__("Record losses for {0} selected PPE Issue(s)?", [selectedIssues.length]),
		function () {
			frappe.call({
				method: "ppe_tracker.ppe_tracker.api.bulk_loss.process_bulk_losses",
				args: {
					items: items,
				},
				freeze: true,
				freeze_message: __("Recording PPE Losses..."),
				callback: function (r) {
					if (r.message) {
						showResultSummary(page, r.message);
					}
				},
				error: function () {
					frappe.msgprint(
						__("An error occurred while processing. Please try again.")
					);
				},
			});
		}
	);
}

function showResultSummary(page, result) {
	var successCount = result.successes ? result.successes.length : 0;
	var failedCount = result.failures ? result.failures.length : 0;

	var html = '<div style="padding: 10px;">';

	if (successCount > 0) {
		html +=
			'<div class="alert alert-success">' +
			'<strong><i class="fa fa-check"></i> ' +
			__("Success") +
			":</strong> " +
			__("{0} PPE Loss record(s) created.", [successCount]) +
			"<ul style='margin-top: 8px;'>";

		result.successes.forEach(function (item) {
			html +=
				"<li>" +
				frappe.utils.escape_html(item.employee_name || item.employee || "") +
				" — " +
				frappe.utils.escape_html(item.ppe_issue) +
				" → <a href='/app/ppe-loss/" + item.ppe_loss + "'>" +
				frappe.utils.escape_html(item.ppe_loss) +
				"</a> (Surcharge: " +
				format_currency(item.surcharge_amount || 0) +
				")</li>";
		});

		html += "</ul></div>";
	}

	if (failedCount > 0) {
		html +=
			'<div class="alert alert-danger">' +
			'<strong><i class="fa fa-times"></i> ' +
			__("Failed") +
			":</strong> " +
			__("{0} record(s) failed.", [failedCount]) +
			"<ul style='margin-top: 8px;'>";

		result.failures.forEach(function (item) {
			html +=
				"<li><strong>" +
				frappe.utils.escape_html(item.ppe_issue || "") +
				"</strong>: " +
				frappe.utils.escape_html(item.error || "") +
				"</li>";
		});

		html += "</ul></div>";
	}

	html += "</div>";

	frappe.msgprint({
		title: __("Bulk PPE Loss Result"),
		message: html,
		indicator: failedCount > 0 ? "orange" : "green",
	});

	// Reload table to reflect changes
	loadData(page);
}
