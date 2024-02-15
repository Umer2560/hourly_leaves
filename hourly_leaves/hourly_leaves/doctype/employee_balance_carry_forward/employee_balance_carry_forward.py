# Copyright (c) 2024, umer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
class EmployeeBalanceCarryForward(Document):
	pass
	
@frappe.whitelist()
def get_employees_data(company=None, leave_type=None, from_date=None, to_date=None):
	where = ""
	if company and company!=" ":
		where = " and company = '" + company + "'"

	if not leave_type:
		frappe.throw("Please Select Leave Type First")

	if leave_type and leave_type !=" ":
		where += " and leave_type = '" + leave_type + "'"

	if not from_date:
		frappe.throw("Please Select From Date First")
		
	if from_date and from_date !=" ":
		where += " and from_date >= '" + from_date + "'"

	if not to_date:
		frappe.throw("Please Select To Date First")
		
	if to_date and to_date !=" ":
		where += " and to_date <= '" + to_date + "'"
		

	query_e = """select name, employee from `tabLeave Allocation` where docstatus != 2 {0}""".format(where)

	employee_list = frappe.db.sql(query_e)

	return employee_list
	
@frappe.whitelist()
def allot_leaves(carry_forward_details , leave_type=None):
	employees_list = json.loads(carry_forward_details)
	if employees_list:
		for emp in employees_list:
			doc = frappe.new_doc("Leave Ledger Entry")
			doc.employee = emp["employee"]
			doc.leave_type = leave_type
			doc.transaction_type = 'Leave Allocation'
			doc.transaction_name = emp["leave_allocation"]
			
			doc.from_date = frappe.db.get_value("Leave Allocation", str(emp["leave_allocation"]), "from_date")
			doc.to_date = frappe.db.get_value("Leave Allocation", str(emp["leave_allocation"]), "to_date")
			
			doc.hours = emp["balance"]
			doc.leaves = float(emp["balance"])/8.0
			doc.save()
			doc.submit()
		frappe.msgprint("Balance Updated")

