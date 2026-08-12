frappe.query_reports["PPE Compliance Summary"] = {
    filters: [
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department"
        },
        {
            fieldname: "designation",
            label: __("Designation"),
            fieldtype: "Link",
            options: "Designation"
        },
        {
            fieldname: "ppe_item",
            label: __("PPE Item"),
            fieldtype: "Link",
            options: "PPE Item"
        },
        {
            fieldname: "reference_date",
            label: __("Reference Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today()
        }
    ]
};
