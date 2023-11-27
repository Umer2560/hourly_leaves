import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}
    columns = get_columns()
    data = get_hourly_leaves(filters)
    return columns, data

def get_columns():
    return [
        _("Employee") + ":Link/Employee:150",
        _("Employee Name") + ":Data:150",
        _("Leave Type") + ":Link/Leave Type:150",
        _("Total Hours") + ":Float:150",
        _("Hours Taken") + ":Float:150",
        _("Hours Remaining") + ":Float:150"
    ]

def get_hourly_leaves(filters):
    cond = get_conditions(filters)
    query = """ select employee, employee_name, sum(hours), leave_type, transaction_type from `tabLeave Ledger Entry` where is_expired = 0 {0} group by employee, leave_type, transaction_type order by employee, leave_type """.format(cond)
    
    leave_applications = frappe.db.sql(query, as_dict = 1)
    #for x in leave_applications:
    consolidated_data = {}

    # Loop through the given data
    for entry in leave_applications:
        employee = entry["employee"]
        leave_type = entry["leave_type"]
        hours = entry["sum(hours)"]

        # Initialize a new entry in the consolidated data if it doesn't exist
        if (employee, leave_type) not in consolidated_data:
            consolidated_data[(employee, leave_type)] = {
                "employee": employee,
                "employee_name": entry["employee_name"],
                "leave_type": leave_type,
                "hours_taken": 0.0,
                "total_hours": 0.0,
                "hours_remaining": 0.0
            }

        # Update total_hours based on the transaction type
        if entry["transaction_type"] == "Leave Allocation":
            consolidated_data[(employee, leave_type)]["total_hours"] += hours
            consolidated_data[(employee, leave_type)]["hours_remaining"] += hours
        elif entry["transaction_type"] == "Leave Application":
            consolidated_data[(employee, leave_type)]["hours_taken"] += hours
            consolidated_data[(employee, leave_type)]["hours_remaining"] += hours

	

    # Convert the dictionary values to a list
    result_list = list(consolidated_data.values())
        
    return result_list
    
def get_conditions(filters):
    conditions = ""
    if filters.get("employee"):
        conditions += " and employee = '{0}' ".format(filters.get("employee"))
    if filters.get("leave_type"):
        conditions += " and leave_type = '{0}' ".format(filters.get("leave_type"))
        
    if filters.get("from_date") and filters.get("to_date"):
        conditions += " and from_date between '{0}' and '{1}' ".format(filters.get("from_date"), filters.get("to_date"))
        
    return conditions
