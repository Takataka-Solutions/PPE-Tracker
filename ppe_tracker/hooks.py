app_name = "ppe_tracker"
app_title = "PPE Tracker"
app_publisher = "Takataka Solutions"
app_description = "Personal Protective Equipment lifecycle management for ERPNext"
app_email = "info@takatakasolutions.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ppe_tracker/css/ppe_tracker.css"
# app_include_js = "/assets/ppe_tracker/js/ppe_tracker.js"

# include js, css files in header of web template
# web_include_css = "/assets/ppe_tracker/css/ppe_tracker.css"
# web_include_js = "/assets/ppe_tracker/js/ppe_tracker.js"

# Installation
# ------------

# before_install = "ppe_tracker.ppe_tracker.install.before_install"
after_install = "ppe_tracker.ppe_tracker.install.after_install"
after_migrate = ["ppe_tracker.ppe_tracker.install.after_migrate"]

# Fixtures
# --------
# Every entry MUST carry an explicit filter. A bare DocType name means "every
# record of this type on the site", and this app shares a site with
# takataka_solutions, which also exports Custom Field, Workflow and Print Format
# unfiltered. Without filters, `bench export-fixtures` for either app captures
# the other's records and `bench migrate` sync order decides which survives.
# See docs/02_Blocker_Register.md BLOCK-002.
#
# Deliberately NOT fixtures:
#   Role         - seeded idempotently in install.py. Roles are global, and an
#                  unfiltered Role export drags in every role on the site.
#   Print Format - "Combined PPE Issue Form" is a standard (file-based) print
#                  format living in ppe_tracker/print_format/, so it syncs like
#                  a DocType. A fixture entry would be redundant.

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    # Custom Field autonames as "{dt}-{fieldname}"
                    "Employee-custom_position_type",
                    "Stock Entry-custom_ppe_issue",
                    "Stock Entry-custom_ppe_return",
                    "Additional Salary-custom_ppe_loss",
                ],
            ]
        ],
    },
    {
        "dt": "Workflow",
        # Required as a fixture: there is no Workflow JSON in the module tree.
        "filters": [["name", "in", ["PPE Request Approval"]]],
    },
]

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "ppe_tracker.ppe_tracker.tasks.mark_expired_issues",
        "ppe_tracker.ppe_tracker.tasks.send_expiry_alerts",
        "ppe_tracker.ppe_tracker.tasks.send_replacement_alerts",
        "ppe_tracker.ppe_tracker.tasks.send_casual_overdue_alerts",
    ],
}

# Document Events
# ---------------

doc_events = {}

# Permissions
# -----------

# permission_query_conditions = {}
# has_permission = {}
