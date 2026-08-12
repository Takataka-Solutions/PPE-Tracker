frappe.pages["bulk-ppe-return"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bulk PPE Return"),
		single_column: true,
	});

	page.main.addClass("frappe-card");
	page.body = $('<div class="bulk-ppe-return-container"></div>').appendTo(
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

	// Add Fetch button to load data
	page.set_secondary_action(__("Fetch"), function () {
		loadEligibleReturns(page);
	});

	// Add Process Returns primary action
	page.set_primary_action(__("Process Returns"), function () {
		processReturns(page);
	});

	// Store page reference
	wrapper.bulkReturnPage = page;

	// Initial load
	loadEligibleReturns(page);
};

frappe.pages["bulk-ppe-return"].on_page_show = function (wrapper) {
	if (wrapper.bulkReturnPage) {
		loadEligibleReturns(wrapper.bulkReturnPage);
	}
};

function getReturnFilters(page) {
	var filters = {};
	var employee = page.fields_dict.employee.get_value();
	var department = page.fields_dict.department.get_value();
	var ppeItem = page.fields_dict.ppe_item.get_value();

	if (employee) filters.employee = employee;
	if (department) filters.department = department;
	if (ppeItem) filters.ppe_item = ppeItem;

	return filters;
}

function loadEligibleReturns(page) {
	page.body.html(
		'<div class="text-muted text-center" style="padding: 40px;">' +
			__("Loading...") +
			"</div>"
	);

	frappe.call({
		method: "ppe_tracker.ppe_tracker.api.bulk_return.get_eligible_returns",
		args: {
			filters: getReturnFilters(page),
		},
		callback: function (r) {
			if (r.message) {
				renderReturnTable(page, r.message);
			} else {
				renderReturnTable(page, []);
			}
		},
		error: function () {
			page.body.html(
				'<div class="text-muted text-center" style="padding: 40px;">' +
					__("Failed to load data. Please try again.") +
					"</div>"
			);
		},
	});
}

function renderReturnTable(page, data) {
	if (!data || data.length === 0) {
		page.body.html(
			'<div class="text-muted text-center" style="padding: 40px;">' +
				'<p><i class="fa fa-check-circle text-success" style="font-size: 48px;"></i></p>' +
				"<p>" +
				__("No active PPE Issues eligible for return.") +
				"</p>" +
				"</div>"
		);
		return;
	}

	var html = '<div class="bulk-ppe-return-table" style="padding: 15px;">';

	// Summary
	html += '<div class="text-muted small" style="margin-bottom: 10px;">';
	html += __("{0} active issue(s) eligible for return", [data.length]);
	html += "</div>";

	// Controls: Condition, Return Date, Select All
	html += '<div class="row" style="margin-bottom: 15px;">';
	html += '<div class="col-md-3">';
	html += '<label class="control-label">' + __("Condition") + "</label>";
	html += '<select class="form-control return-condition-select">';
	html += '<option value="Good">' + __("Good") + "</option>";
	html += '<option value="Damaged">' + __("Damaged") + "</option>";
	html += '<option value="Unusable">' + __("Unusable") + "</option>";
	html += "</select>";
	html += "</div>";
	html += '<div class="col-md-3">';
	html += '<label class="control-label">' + __("Return Date") + "</label>";
	html +=
		'<input type="date" class="form-control return-date-input" value="' +
		frappe.datetime.get_today() +
		'">';
	html += "</div>";
	html += '<div class="col-md-3" style="padding-top: 24px;">';
	html +=
		'<label><input type="checkbox" class="select-all-checkbox"> ' +
		__("Select All") +
		"</label>";
	html += "</div>";
	html += "</div>";

	// Data table
	html += '<table class="table table-bordered table-hover">';
	html += "<thead><tr>";
	html += '<th style="width: 40px;">' + __("Select") + "</th>";
	html += "<th>" + __("Employee Name") + "</th>";
	html += "<th>" + __("Department") + "</th>";
	html += "<th>" + __("PPE Item") + "</th>";
	html += "<th>" + __("Issue Date") + "</th>";
	html += "<th>" + __("Expiry Date") + "</th>";
	html += "<th>" + __("Qty Issued") + "</th>";
	html += '<th style="width: 100px;">' + __("Qty to Return") + "</th>";
	html += "</tr></thead>";
	html += "<tbody>";

	data.forEach(function (row) {
		var issueDate = frappe.datetime.str_to_user(row.issue_date) || "";
		var expiryDate = frappe.datetime.str_to_user(row.expiry_date) || "";

		html += '<tr data-issue="' + row.name + '">';
		html +=
			'<td><input type="checkbox" class="row-checkbox" data-issue="' +
			row.name +
			'"></td>';
		html +=
			"<td>" +
			frappe.utils.escape_html(row.employee_name || "") +
			"</td>";
		html +=
			"<td>" + frappe.utils.escape_html(row.department || "") + "</td>";
		html +=
			"<td>" +
			frappe.utils.escape_html(row.ppe_item_name || row.ppe_item || "") +
			"</td>";
		html += "<td>" + issueDate + "</td>";
		html += "<td>" + expiryDate + "</td>";
		html += "<td>" + (row.quantity || 0) + "</td>";
		html +=
			'<td><input type="number" class="form-control qty-to-return" ' +
			'data-issue="' +
			row.name +
			'" ' +
			'value="' +
			(row.quantity || 0) +
			'" ' +
			'min="1" max="' +
			(row.quantity || 1) +
			'" ' +
			'style="width: 80px;"></td>';
		html += "</tr>";
	});

	html += "</tbody></table></div>";

	page.body.html(html);

	// Bind select-all checkbox
	page.body.find(".select-all-checkbox").on("change", function () {
		var checked = $(this).prop("checked");
		page.body.find(".row-checkbox").prop("checked", checked);
	});

	// Update select-all when individual checkboxes change
	page.body.find(".row-checkbox").on("change", function () {
		var total = page.body.find(".row-checkbox").length;
		var checked = page.body.find(".row-checkbox:checked").length;
		page.body.find(".select-all-checkbox").prop("checked", total === checked);
	});
}

function processReturns(page) {
	var condition = page.body.find(".return-condition-select").val();
	var returnDate = page.body.find(".return-date-input").val();

	if (!condition) {
		frappe.msgprint(__("Please select a return condition."));
		return;
	}

	if (!returnDate) {
		frappe.msgprint(__("Please select a return date."));
		return;
	}

	// Collect selected items with their quantities
	var selectedItems = [];
	page.body.find(".row-checkbox:checked").each(function () {
		var issueName = $(this).data("issue");
		var qtyInput = page.body.find(
			'.qty-to-return[data-issue="' + issueName + '"]'
		);
		var qtyToReturn = parseInt(qtyInput.val()) || 0;

		if (qtyToReturn > 0) {
			selectedItems.push({
				ppe_issue: issueName,
				condition: condition,
				return_date: returnDate,
				quantity_returned: qtyToReturn,
			});
		}
	});

	if (selectedItems.length === 0) {
		frappe.msgprint(
			__("Please select at least one item to return.")
		);
		return;
	}

	frappe.confirm(
		__(
			"Process returns for {0} selected item(s) with condition '{1}'?",
			[selectedItems.length, condition]
		),
		function () {
			frappe.call({
				method: "ppe_tracker.ppe_tracker.api.bulk_return.process_bulk_returns",
				args: {
					items: selectedItems,
				},
				freeze: true,
				freeze_message: __("Processing returns..."),
				callback: function (r) {
					if (r.message) {
						showReturnResultSummary(page, r.message);
					}
				},
				error: function () {
					frappe.msgprint(
						__(
							"An error occurred while processing. Please try again."
						)
					);
				},
			});
		}
	);
}

function showReturnResultSummary(page, result) {
	var successCount = result.successes ? result.successes.length : 0;
	var failedCount = result.failures ? result.failures.length : 0;

	var html = '<div style="padding: 10px;">';

	if (successCount > 0) {
		html +=
			'<div class="alert alert-success">' +
			'<strong><i class="fa fa-check"></i> ' +
			__("Success") +
			":</strong> " +
			__("{0} PPE Return(s) created and submitted.", [successCount]) +
			"</div>";

		// List successes
		html += "<ul>";
		result.successes.forEach(function (item) {
			html +=
				"<li>" +
				frappe.utils.escape_html(item.employee_name || "") +
				" &mdash; " +
				frappe.utils.escape_html(item.ppe_item || "") +
				" (" +
				frappe.utils.escape_html(item.ppe_return || "") +
				")</li>";
		});
		html += "</ul>";
	}

	if (failedCount > 0) {
		html +=
			'<div class="alert alert-danger">' +
			'<strong><i class="fa fa-times"></i> ' +
			__("Failed") +
			":</strong> " +
			__("{0} return(s) failed.", [failedCount]) +
			"<ul style='margin-top: 8px;'>";

		result.failures.forEach(function (item) {
			html +=
				"<li><strong>" +
				frappe.utils.escape_html(item.ppe_issue || "Unknown") +
				"</strong>: " +
				frappe.utils.escape_html(item.error || "Unknown error") +
				"</li>";
		});

		html += "</ul></div>";
	}

	html += "</div>";

	frappe.msgprint({
		title: __("Bulk Return Result"),
		message: html,
		indicator: failedCount > 0 ? "orange" : "green",
	});

	// Reload table to reflect changes
	loadEligibleReturns(page);
}
