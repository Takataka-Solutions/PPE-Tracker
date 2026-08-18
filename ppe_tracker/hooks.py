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
# after_install = "ppe_tracker.ppe_tracker.install.after_install"
after_migrate = ["ppe_tracker.ppe_tracker.install.after_migrate"]

# Fixtures
# --------

fixtures = ["Role", "Custom Field", "Workflow", "Print Format"]

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
