frappe.pages["bulk-ppe-request"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Bulk PPE Request"),
		single_column: true,
	});

	page.main.addClass("frappe-card");
	page.body = $('<div class="bulk-ppe-request-container"></div>').appendTo(
		page.main
	);

	// Add filters for employee selection
	page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		change: function () {
			loadEmployees(page);
		},
	});

	page.add_field({
		fieldname: "department",
		label: __("Department"),
		fieldtype: "Link",
		options: "Department",
		change: function () {
			loadEmployees(page);
		},
	});

	page.add_field({
		fieldname: "designation",
		label: __("Designation"),
		fieldtype: "Link",
		options: "Designation",
		change: function () {
			loadEmployees(page);
		},
	});

	page.add_field({
		fieldname: "branch",
		label: __("Branch"),
		fieldtype: "Link",
		options: "Branch",
		change: function () {
			loadEmployees(page);
		},
	});

	page.add_field({
		fieldname: "employee_name",
		label: __("Employee Name"),
		fieldtype: "Data",
		placeholder: __("Search by name..."),
		change: function () {
			loadEmployees(page);
		},
	});

	page.add_field({
		fieldname: "justification",
		label: __("Justification"),
		fieldtype: "Select",
		options: [
			"New Employee",
			"New Requirement",
			"Lost (Cost Charged to Employee)",
			"Worn Out Before Lifespan End (Cost Charged to Employee)",
			"Exceeded Lifespan",
		].join("\n"),
		reqd: 1,
	});

	// Add primary action button
	page.set_primary_action(__("Create Requests"), function () {
		createRequests(page);
	});

	page.add_button(__("Refresh"), function () {
		loadEmployees(page);
		loadPpeItems(page);
	});

	// Store page reference
	wrapper.bulkPpeRequestPage = page;

	// Initial data load
	loadEmployees(page);
	loadPpeItems(page);
};

frappe.pages["bulk-ppe-request"].on_page_show = function (wrapper) {
	if (wrapper.bulkPpeRequestPage) {
		loadEmployees(wrapper.bulkPpeRequestPage);
		loadPpeItems(wrapper.bulkPpeRequestPage);
	}
};

function getEmployeeFilters(page) {
	var filters = {};
	var company = page.fields_dict.company.get_value();
	var department = page.fields_dict.department.get_value();
	var designation = page.fields_dict.designation.get_value();
	var branch = page.fields_dict.branch.get_value();
	var employee_name = page.fields_dict.employee_name.get_value();

	if (company) filters.company = company;
	if (department) filters.department = department;
	if (designation) filters.designation = designation;
	if (branch) filters.branch = branch;
	if (employee_name) filters.employee_name = employee_name;

	return filters;
}

function loadEmployees(page) {
	frappe.call({
		method: "ppe_tracker.ppe_tracker.page.bulk_ppe_request.bulk_ppe_request.get_employees",
		args: {
			filters: getEmployeeFilters(page),
		},
		callback: function (r) {
			renderEmployeeTable(page, r.message || []);
		},
		error: function () {
			page.body.find(".employee-section").html(
				'<div class="text-muted text-center" style="padding: 20px;">' +
					__("Failed to load employees.") +
					"</div>"
			);
		},
	});
}

function loadPpeItems(page) {
	frappe.call({
		method: "ppe_tracker.ppe_tracker.page.bulk_ppe_request.bulk_ppe_request.get_ppe_items",
		callback: function (r) {
			renderPpeItemTable(page, r.message || []);
		},
		error: function () {
			page.body.find(".ppe-items-section").html(
				'<div class="text-muted text-center" style="padding: 20px;">' +
					__("Failed to load PPE Items.") +
					"</div>"
			);
		},
	});
}

function renderEmployeeTable(page, employees) {
	var $section = page.body.find(".employee-section");
	if (!$section.length) {
		page.body.html(
			'<div class="employee-section" style="padding: 15px;"></div>' +
				'<div class="ppe-items-section" style="padding: 15px;"></div>'
		);
		$section = page.body.find(".employee-section");
	}

	if (!employees || employees.length === 0) {
		$section.html(
			'<h5>' + __("Employees") + "</h5>" +
				'<div class="text-muted text-center" style="padding: 20px;">' +
				__("No active employees found matching the selected filters.") +
				"</div>"
		);
		return;
	}

	var html = "<h5>" + __("Employees") + " (" + employees.length + ")</h5>";
	html += '<div class="text-muted small" style="margin-bottom: 8px;">';
	html += __("Select employees to create PPE Requests for.");
	html += "</div>";
	html += '<table class="table table-bordered table-hover">';
	html += "<thead><tr>";
	html +=
		'<th style="width: 40px;"><input type="checkbox" class="select-all-employees" title="' +
		__("Select All") +
		'"></th>';
	html += "<th>" + __("Employee Name") + "</th>";
	html += "<th>" + __("Department") + "</th>";
	html += "<th>" + __("Designation") + "</th>";
	html += "<th>" + __("Branch") + "</th>";
	html += "</tr></thead>";
	html += "<tbody>";

	employees.forEach(function (emp) {
		html += '<tr data-employee="' + emp.name + '">';
		html +=
			'<td><input type="checkbox" class="employee-checkbox" data-employee="' +
			emp.name +
			'"></td>';
		html += "<td>" + frappe.utils.escape_html(emp.employee_name || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(emp.department || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(emp.designation || "") + "</td>";
		html += "<td>" + frappe.utils.escape_html(emp.branch || "") + "</td>";
		html += "</tr>";
	});

	html += "</tbody></table>";

	$section.html(html);

	// Bind select-all checkbox
	$section.find(".select-all-employees").on("change", function () {
		var checked = $(this).prop("checked");
		$section.find(".employee-checkbox").prop("checked", checked);
	});

	$section.find(".employee-checkbox").on("change", function () {
		var total = $section.find(".employee-checkbox").length;
		var checked = $section.find(".employee-checkbox:checked").length;
		$section.find(".select-all-employees").prop("checked", total === checked);
	});
}

function renderPpeItemTable(page, items) {
	var $section = page.body.find(".ppe-items-section");
	if (!$section.length) {
		page.body.append('<div class="ppe-items-section" style="padding: 15px;"></div>');
		$section = page.body.find(".ppe-items-section");
	}

	if (!items || items.length === 0) {
		$section.html(
			'<h5>' + __("PPE Items") + "</h5>" +
				'<div class="text-muted text-center" style="padding: 20px;">' +
				__("No active PPE Items found.") +
				"</div>"
		);
		return;
	}

	var html = "<h5>" + __("PPE Items") + " (" + items.length + ")</h5>";
	html += '<div class="text-muted small" style="margin-bottom: 8px;">';
	html += __("Select PPE Items to request for the selected employees.");
	html += "</div>";
	html += '<table class="table table-bordered table-hover">';
	html += "<thead><tr>";
	html +=
		'<th style="width: 40px;"><input type="checkbox" class="select-all-items" title="' +
		__("Select All") +
		'"></th>';
	html += "<th>" + __("PPE Item") + "</th>";
	html += "<th>" + __("Category") + "</th>";
	html += "</tr></thead>";
	html += "<tbody>";

	items.forEach(function (item) {
		html += '<tr data-item="' + item.name + '">';
		html +=
			'<td><input type="checkbox" class="item-checkbox" data-item="' +
			item.name +
			'"></td>';
		html += "<td>" + frappe.utils.escape_html(item.ppe_item_name || item.name) + "</td>";
		html += "<td>" + frappe.utils.escape_html(item.category || "") + "</td>";
		html += "</tr>";
	});

	html += "</tbody></table>";

	$section.html(html);

	// Bind select-all checkbox
	$section.find(".select-all-items").on("change", function () {
		var checked = $(this).prop("checked");
		$section.find(".item-checkbox").prop("checked", checked);
	});

	$section.find(".item-checkbox").on("change", function () {
		var total = $section.find(".item-checkbox").length;
		var checked = $section.find(".item-checkbox:checked").length;
		$section.find(".select-all-items").prop("checked", total === checked);
	});
}

function createRequests(page) {
	// Gather selected employees
	var selectedEmployees = [];
	page.body.find(".employee-checkbox:checked").each(function () {
		selectedEmployees.push($(this).data("employee"));
	});

	// Gather selected PPE items
	var selectedItems = [];
	page.body.find(".item-checkbox:checked").each(function () {
		selectedItems.push($(this).data("item"));
	});

	// Get justification
	var justification = page.fields_dict.justification.get_value();

	// Validate selections
	if (selectedEmployees.length === 0) {
		frappe.msgprint(__("Please select at least one employee."));
		return;
	}

	if (selectedItems.length === 0) {
		frappe.msgprint(__("Please select at least one PPE Item."));
		return;
	}

	if (!justification) {
		frappe.msgprint(__("Please select a justification."));
		return;
	}

	var totalCombinations = selectedEmployees.length * selectedItems.length;

	frappe.confirm(
		__(
			"Create PPE Requests for {0} employee(s) × {1} PPE item(s) = {2} request(s)?",
			[selectedEmployees.length, selectedItems.length, totalCombinations]
		),
		function () {
			frappe.call({
				method: "ppe_tracker.ppe_tracker.page.bulk_ppe_request.bulk_ppe_request.create_bulk_requests",
				args: {
					employees: selectedEmployees,
					ppe_items: selectedItems,
					justification: justification,
				},
				freeze: true,
				freeze_message: __("Creating PPE Requests..."),
				callback: function (r) {
					if (r.message) {
						showSummary(page, r.message);
					}
				},
				error: function () {
					frappe.msgprint(
						__("An error occurred while creating requests. Please try again.")
					);
				},
			});
		}
	);
}

function showSummary(page, result) {
	var created = result.created || [];
	var skipped = result.skipped || [];
	var failed = result.failed || [];

	var html = '<div style="padding: 15px;">';
	html += "<h5>" + __("Bulk PPE Request Summary") + "</h5>";

	// Success count
	html +=
		'<div class="alert alert-success">' +
		'<strong>' + __("Created:") + "</strong> " +
		created.length +
		" " +
		__("request(s) successfully created and submitted.") +
		"</div>";

	// Skipped count
	if (skipped.length > 0) {
		html +=
			'<div class="alert alert-warning">' +
			'<strong>' + __("Skipped:") + "</strong> " +
			skipped.length +
			" " +
			__("combination(s) not covered by PPE Role Assignment rules.") +
			"<ul style='margin-top: 8px;'>";
		skipped.forEach(function (s) {
			html +=
				"<li>" +
				frappe.utils.escape_html(s.employee_name || s.employee) +
				" — " +
				frappe.utils.escape_html(s.ppe_item) +
				": " +
				frappe.utils.escape_html(s.reason) +
				"</li>";
		});
		html += "</ul></div>";
	}

	// Failed count
	if (failed.length > 0) {
		html +=
			'<div class="alert alert-danger">' +
			'<strong>' + __("Failed:") + "</strong> " +
			failed.length +
			" " +
			__("request(s) failed to create.") +
			"<ul style='margin-top: 8px;'>";
		failed.forEach(function (f) {
			html +=
				"<li>" +
				frappe.utils.escape_html(f.employee_name || f.employee) +
				" — " +
				frappe.utils.escape_html(f.ppe_item) +
				": " +
				frappe.utils.escape_html(f.error) +
				"</li>";
		});
		html += "</ul></div>";
	}

	html += "</div>";

	frappe.msgprint({
		title: __("Bulk PPE Request Results"),
		indicator: failed.length > 0 ? "orange" : "green",
		message: html,
	});

	// Refresh the page data
	loadEmployees(page);
	loadPpeItems(page);
}
