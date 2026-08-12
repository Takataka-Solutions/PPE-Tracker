# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Scheduled tasks for the PPE Tracker app.

This module contains background job functions registered via hooks.py scheduler_events.
Jobs handle automated lifecycle transitions and notification alerts for PPE Issues.
"""

import frappe


def mark_expired_issues():
	"""Transition all Active PPE Issues past their expiry date to Expired status.

	Queries PPE Issue records where status is 'Active' and expiry_date is on or
	before today's date, then bulk-updates each record's status to 'Expired'.

	Validates: Requirements 7.4
	"""
	expired_issues = frappe.get_all(
		"PPE Issue",
		filters={
			"status": "Active",
			"expiry_date": ["<=", frappe.utils.today()],
		},
		pluck="name",
	)

	for issue_name in expired_issues:
		frappe.db.set_value("PPE Issue", issue_name, "status", "Expired")

	frappe.db.commit()


def send_expiry_alerts():
	"""Send daily email alerts for PPE Issues expiring within 30 days.

	1. Query Active PPE Issues with expiry_date <= today + 30 days.
	2. Transition any already-expired (expiry_date <= today) to "Expired" status.
	3. Build supervisor map: group issues by supervisor (employee.reports_to).
	4. Send consolidated email per supervisor using ppe_expiry_alert template.
	5. Send summary email to all HR Manager/Safety Officer role holders.
	6. If no issues found, return silently.
	7. Log error when employee has no reports_to.

	Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
	"""
	today = frappe.utils.today()
	threshold = frappe.utils.add_days(today, 30)

	issues = frappe.get_all(
		"PPE Issue",
		filters={
			"status": "Active",
			"expiry_date": ["<=", threshold],
		},
		fields=["name", "employee", "employee_name", "ppe_item", "issue_date", "expiry_date", "quantity"],
	)

	if not issues:
		return

	# Transition already-expired issues to Expired status
	for issue in issues:
		if str(issue["expiry_date"]) <= today:
			frappe.db.set_value("PPE Issue", issue["name"], "status", "Expired")

	frappe.db.commit()

	# Send consolidated alerts per supervisor
	supervisor_map = _build_supervisor_map(issues)
	for supervisor_email, supervisor_issues in supervisor_map.items():
		_send_alert_email([supervisor_email], supervisor_issues, "ppe_expiry_alert")

	# Send summary to all HR Manager and Safety Officer users
	hr_emails = _get_role_email_list(["HR Manager", "Safety Officer"])
	if hr_emails:
		_send_alert_email(hr_emails, issues, "ppe_expiry_alert")


def _get_role_email_list(roles):
	"""Return unique email addresses of active users holding any of the given roles.

	Filters out disabled users and the Administrator account.

	Args:
		roles: List of role names, e.g. ["HR Manager", "Safety Officer"].

	Returns:
		List of unique user email addresses.

	Validates: Requirements 8.3
	"""
	role_users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", roles]},
		fields=["parent"],
	)

	user_ids = set()
	for entry in role_users:
		user_ids.add(entry.parent)

	# Filter out disabled users and Administrator
	emails = []
	for user_id in user_ids:
		if user_id == "Administrator":
			continue
		user_enabled = frappe.db.get_value("User", user_id, "enabled")
		if user_enabled:
			emails.append(user_id)

	return emails


def _build_supervisor_map(issues):
	"""Group PPE Issues by the supervisor email of each employee.

	For each issue, resolves the employee's reports_to field to find the supervisor,
	then looks up the supervisor's user_id (email). Issues are grouped by supervisor
	email for consolidated alerting.

	If an employee has no reports_to, logs an error via frappe.log_error() and
	skips supervisor grouping for that issue.

	Args:
		issues: List of PPE Issue dicts with at least 'employee' and 'name' fields.

	Returns:
		Dict mapping supervisor email to list of issues they should be alerted about.

	Validates: Requirements 8.2, 8.6
	"""
	supervisor_map = {}

	for issue in issues:
		reports_to = frappe.db.get_value("Employee", issue.employee, "reports_to")

		if not reports_to:
			frappe.log_error(
				message=f"Employee {issue.employee} ({issue.get('employee_name', '')}) has no reports_to set. "
				f"Cannot send supervisor alert for PPE Issue {issue.name}.",
				title="PPE Expiry Alert",
			)
			continue

		supervisor_email = frappe.db.get_value("Employee", reports_to, "user_id")

		if not supervisor_email:
			frappe.log_error(
				message=f"Supervisor {reports_to} for employee {issue.employee} has no user_id. "
				f"Cannot send supervisor alert for PPE Issue {issue.name}.",
				title="PPE Expiry Alert",
			)
			continue

		supervisor_map.setdefault(supervisor_email, []).append(issue)

	return supervisor_map


def _send_alert_email(recipients, issues, template):
	"""Send an email alert to the specified recipients using the given template.

	Args:
		recipients: List of email addresses.
		issues: List of PPE Issue dicts to include in the email context.
		template: Frappe email template name (e.g. "ppe_expiry_alert").

	Validates: Requirements 8.2, 8.3
	"""
	count = len(issues)
	subject = f"PPE Expiry Alert - {count} item{'s' if count != 1 else ''} expiring"

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		template=template,
		args={"issues": issues},
	)


def send_replacement_alerts():
	"""Send daily email alerts for PPE Items due for replacement within 7 days.

	Queries Active PPE Issues with expiry_date between today and today + 7 days.
	Sends consolidated email per supervisor and summary to HR/Safety Officer users.
	Returns silently if no issues found.

	Validates: Requirements 9.1, 9.2, 9.3, 9.4
	"""
	today = frappe.utils.today()
	threshold = frappe.utils.add_days(today, 7)

	due_issues = frappe.get_all(
		"PPE Issue",
		filters={
			"status": "Active",
			"expiry_date": ["between", [today, threshold]],
		},
		fields=["name", "employee", "employee_name", "ppe_item", "issue_date",
				"expiry_date", "quantity"],
	)

	if not due_issues:
		return

	# Send per-supervisor alerts
	supervisor_map = _build_supervisor_map(due_issues)
	for supervisor_email, supervisor_issues in supervisor_map.items():
		_send_alert_email([supervisor_email], supervisor_issues, "ppe_replacement_alert")

	# Send summary to HR/Safety Officers
	hr_emails = _get_role_email_list(["HR Manager", "Safety Officer"])
	if hr_emails:
		_send_alert_email(hr_emails, due_issues, "ppe_replacement_alert")


def send_casual_overdue_alerts():
	"""Identify overdue casual PPE issues and send alert emails.

	Daily scheduled job that:
	1. Queries PPE Issues where issue_type=Casual, status=Active, expected_return_date <= today
	2. Sets is_overdue=1 on each matched record
	3. Sends email alert to HR Manager, HR User, Safety Officer, Storekeeper users

	Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
	"""
	from frappe.utils import today, date_diff

	overdue_issues = frappe.get_all(
		"PPE Issue",
		filters={
			"issue_type": "Casual",
			"status": "Active",
			"expected_return_date": ["<=", today()],
			"docstatus": 1,
		},
		fields=["name", "employee", "employee_name", "ppe_item", "issue_date",
				"expected_return_date"],
	)

	if not overdue_issues:
		return

	# Mark each as overdue
	for issue in overdue_issues:
		frappe.db.set_value("PPE Issue", issue.name, "is_overdue", 1)

	# Calculate days overdue
	for issue in overdue_issues:
		issue["days_overdue"] = date_diff(today(), str(issue.expected_return_date))

	# Get recipients (users with specified roles)
	recipients = get_casual_overdue_alert_recipients()
	if not recipients:
		frappe.db.commit()
		return

	# Send alert email
	subject = f"PPE Overdue Alert: {len(overdue_issues)} Casual PPE Issue(s) Overdue"

	message = "<h3>Overdue Casual PPE Issues</h3>"
	message += "<p>The following casual PPE issues have not been returned by their expected return date:</p>"
	message += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>"
	message += "<tr><th>Employee</th><th>PPE Item</th><th>Issue Date</th><th>Expected Return</th><th>Days Overdue</th></tr>"

	for issue in overdue_issues:
		message += "<tr>"
		message += f"<td>{issue.employee_name}</td>"
		message += f"<td>{issue.ppe_item}</td>"
		message += f"<td>{issue.issue_date}</td>"
		message += f"<td>{issue.expected_return_date}</td>"
		message += f"<td>{issue.days_overdue}</td>"
		message += "</tr>"

	message += "</table>"
	message += "<p>Please follow up with the employees to ensure PPE is returned promptly.</p>"

	frappe.sendmail(
		recipients=recipients,
		subject=subject,
		message=message,
	)

	frappe.db.commit()


def get_casual_overdue_alert_recipients():
	"""Get email addresses of active users with HR Manager, HR User, Safety Officer, or Storekeeper roles.

	Validates: Requirements 10.3
	"""
	roles = ["HR Manager", "HR User", "Safety Officer", "Storekeeper"]

	users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", roles], "parenttype": "User"},
		fields=["parent"],
		distinct=True,
	)

	recipients = []
	for user in users:
		user_email = user.parent
		if user_email == "Administrator":
			continue
		# Check user is enabled
		enabled = frappe.db.get_value("User", user_email, "enabled")
		if enabled:
			recipients.append(user_email)

	return list(set(recipients))
