frappe.pages["bulk-ppe-issue"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bulk PPE Issue"),
		single_column: true,
	});

	page.main.addClass("frappe-card");
	page.body = $('<div class="bulk-ppe-issue-container"></div>').appendTo(
		page.main
	);

	// Add filters
	page.add_field({
		fieldname: "department",
		label: __("Department"),
		fieldtype: "Link",
		options: "Department",
		change: function () {
			loadData(page);
		},
	});

	page.add_field({
		fieldname: "designation",
		label: __("Designation"),
		fieldtype: "Link",
		options: "Designation",
		change: function () {
			loadData(page);
		},
	});

	page.add_field({
		fieldname: "ppe_item",
		label: __("PPE Item"),
		fieldtype: "Link",
		options: "PPE Item",
		change: function () {
			loadData(page);
		},
	});

	page.add_field({
		fieldname: "employee",
		label: __("Employee"),
		fieldtype: "Link",
		options: "Employee",
		change: function () {
			loadData(page);
		},
	});

	// Add buttons
	page.set_primary_action(__("Issue Selected"), function () {
		issueSelected(page);
	});

	page.add_button(__("Refresh"), function () {
		loadData(page);
	});

	// Store page reference
	wrapper.bulkPpePage = page;

	// Load data on page load
	loadData(page);
};

frappe.pages["bulk-ppe-issue"].on_page_show = function (wrapper) {
	// Reload data when page is shown again
	if (wrapper.bulkPpePage) {
		loadData(wrapper.bulkPpePage);
	}
};

function getFilters(page) {
	var filters = {};
	var department = page.fields_dict.department.get_value();
	var designation = page.fields_dict.designation.get_value();
	var ppe_item = page.fields_dict.ppe_item.get_value();
	var employee = page.fields_dict.employee.get_value();

	if (department) filters.department = department;
	if (designation) filters.designation = designation;
	if (ppe_item) filters.ppe_item = ppe_item;
	if (employee) filters.employee = employee;

	return filters;
}

function loadData(page) {
	page.body.html(
		'<div class="text-muted text-center" style="padding: 40px;">' +
			__("Loading...") +
			"</div>"
	);

	frappe.call({
		method: "ppe_tracker.ppe_tracker.page.bulk_ppe_issue.bulk_ppe_issue.get_approved_requests",
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
			page.body.html(
				'<div class="text-muted text-center" style="padding: 40px;">' +
					__("Failed to load data. Please try again.") +
					"</div>"
			);
		},
	});
}

function renderTable(page, data) {
	if (!data || data.length === 0) {
		page.body.html(
			'<div class="text-muted text-center" style="padding: 40px;">' +
				'<p><i class="fa fa-check-circle text-success" style="font-size: 48px;"></i></p>' +
				"<p>" +
				__("No approved PPE Requests pending issue.") +
				"</p>" +
				"</div>"
		);
		return;
	}

	var html = '<div class="bulk-ppe-issue-table" style="padding: 15px;">';
	html += '<div class="text-muted small" style="margin-bottom: 10px;">';
	html += __("{0} approved request(s) pending issue", [data.length]);
	html += "</div>";
	html += '<table class="table table-bordered table-hover">';
	html += "<thead><tr>";
	html +=
		'<th style="width: 40px;"><input type="checkbox" class="select-all-checkbox" title="' +
		__("Select All") +
		'"></th>';
	html += "<th>" + __("Employee Name") + "</th>";
	html += "<th>" + __("Department") + "</th>";
	html += "<th>" + __("Designation") + "</th>";
	html += "<th>" + __("PPE Item") + "</th>";
	html += "<th>" + __("Qty") + "</th>";
	html += "<th>" + __("Request Date") + "</th>";
	html += "</tr></thead>";
	html += "<tbody>";

	data.forEach(function (row) {
		var requestDate = frappe.datetime.str_to_user(row.request_date);
		html += '<tr data-request="' + row.name + '">';
		html +=
			'<td><input type="checkbox" class="row-checkbox" data-request="' +
			row.name +
			'"></td>';
		html += "<td>" + frappe.utils.escape_html(row.employee_name || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(row.department || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(row.designation || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(row.ppe_item || "") + "</td>";
		html += "<td>" + (row.requested_quantity || 0) + "</td>";
		html += "<td>" + (requestDate || "") + "</td>";
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

function issueSelected(page) {
	var selectedRequests = [];
	page.body.find(".row-checkbox:checked").each(function () {
		selectedRequests.push($(this).data("request"));
	});

	if (selectedRequests.length === 0) {
		frappe.msgprint(__("Please select at least one request to issue."));
		return;
	}

	frappe.confirm(
		__("Issue PPE for {0} selected request(s)?", [selectedRequests.length]),
		function () {
			frappe.call({
				method: "ppe_tracker.ppe_tracker.page.bulk_ppe_issue.bulk_ppe_issue.issue_selected",
				args: {
					requests: selectedRequests,
				},
				freeze: true,
				freeze_message: __("Issuing PPE..."),
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
	var successCount = result.success ? result.success.length : 0;
	var failedCount = result.failed ? result.failed.length : 0;

	var html = '<div style="padding: 10px;">';

	if (successCount > 0) {
		html +=
			'<div class="alert alert-success">' +
			'<strong><i class="fa fa-check"></i> ' +
			__("Success") +
			":</strong> " +
			__("{0} PPE Issue(s) created and submitted.", [successCount]) +
			"</div>";
	}

	if (failedCount > 0) {
		html +=
			'<div class="alert alert-danger">' +
			'<strong><i class="fa fa-times"></i> ' +
			__("Failed") +
			":</strong> " +
			__("{0} request(s) failed.", [failedCount]) +
			"<ul style='margin-top: 8px;'>";

		result.failed.forEach(function (item) {
			html +=
				"<li><strong>" +
				frappe.utils.escape_html(item.request) +
				"</strong>: " +
				frappe.utils.escape_html(item.error) +
				"</li>";
		});

		html += "</ul></div>";
	}

	html += "</div>";

	frappe.msgprint({
		title: __("Bulk Issue Result"),
		message: html,
		indicator: failedCount > 0 ? "orange" : "green",
	});

	// Reload table to reflect changes
	loadData(page);

	// Offer to create PPE Issue Acknowledgement(s) for successful issues
	offerAcknowledgement(result.success);
}

function offerAcknowledgement(successes) {
	if (!successes || successes.length === 0) return;

	// Group by employee
	var byEmployee = {};
	successes.forEach(function (item) {
		var emp = item.employee;
		if (!byEmployee[emp]) {
			byEmployee[emp] = {
				employee: emp,
				employee_name: item.employee_name,
				issues: [],
			};
		}
		byEmployee[emp].issues.push(item.ppe_issue);
	});

	var employeeCount = Object.keys(byEmployee).length;
	var message =
		employeeCount === 1
			? __("Create PPE Issue Acknowledgement for {0}?", [
					Object.values(byEmployee)[0].employee_name,
				])
			: __("Create PPE Issue Acknowledgements for {0} employees?", [
					employeeCount,
				]);

	frappe.confirm(message, function () {
		createAcknowledgements(byEmployee);
	});
}

function createAcknowledgements(byEmployee) {
	var employees = Object.keys(byEmployee);

	if (employees.length === 1) {
		// Single employee - create one acknowledgement and navigate to it
		var empData = byEmployee[employees[0]];
		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: {
					doctype: "PPE Issue Acknowledgement",
					employee: empData.employee,
					acknowledgement_date: frappe.datetime.get_today(),
					ppe_issues: empData.issues.map(function (issue) {
						return { ppe_issue: issue };
					}),
				},
			},
			freeze: true,
			freeze_message: __("Creating Acknowledgement..."),
			callback: function (r) {
				if (r.message) {
					frappe.set_route(
						"Form",
						"PPE Issue Acknowledgement",
						r.message.name
					);
				}
			},
		});
	} else {
		// Multiple employees - create one acknowledgement per employee
		var promises = employees.map(function (emp) {
			var empData = byEmployee[emp];
			return frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "PPE Issue Acknowledgement",
						employee: empData.employee,
						acknowledgement_date: frappe.datetime.get_today(),
						ppe_issues: empData.issues.map(function (issue) {
							return { ppe_issue: issue };
						}),
					},
				},
			});
		});

		Promise.all(promises).then(function (results) {
			frappe.msgprint(
				__(
					"{0} Acknowledgement(s) created. Navigate to PPE Issue Acknowledgement list to review.",
					[results.length]
				)
			);
			frappe.set_route("List", "PPE Issue Acknowledgement");
		});
	}
}
