# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""
Utility functions for PPE Issue Acknowledgement grouping.

Used by the Bulk PPE Issue frontend to group successfully created PPE Issues
by employee, enabling creation of one acknowledgement per employee.
"""


def group_issues_by_employee(issues):
	"""Group a list of PPE Issue dicts by employee.

	Takes a list of dicts (each with 'employee' and 'ppe_issue' keys) and
	returns a dict mapping employee → list of ppe_issue names.

	Args:
		issues: List of dicts, each containing at minimum:
			- employee (str): Employee ID
			- ppe_issue (str): PPE Issue document name

	Returns:
		dict: Mapping of employee ID → list of PPE Issue names belonging
		      to that employee.

	Example:
		>>> issues = [
		...     {"employee": "EMP-001", "ppe_issue": "PPE-ISS-0001"},
		...     {"employee": "EMP-002", "ppe_issue": "PPE-ISS-0002"},
		...     {"employee": "EMP-001", "ppe_issue": "PPE-ISS-0003"},
		... ]
		>>> group_issues_by_employee(issues)
		{'EMP-001': ['PPE-ISS-0001', 'PPE-ISS-0003'], 'EMP-002': ['PPE-ISS-0002']}
	"""
	grouped = {}
	for issue in issues:
		employee = issue.get("employee")
		ppe_issue = issue.get("ppe_issue")
		if employee and ppe_issue:
			if employee not in grouped:
				grouped[employee] = []
			grouped[employee].append(ppe_issue)
	return grouped
