import frappe
from frappe import _
from frappe.model.document import Document
from hrms.hr.utils import update_to_date_in_work_history

def update_employee_work_history(employee, details, date=None, cancel=False):
	if not employee.internal_work_history and not cancel:
		employee.append(
			"internal_work_history",
			{
				"branch": employee.branch,
				"designation": employee.designation,
				"department": employee.department,
				"position_number": employee.position_number,
				"from_date": employee.date_of_joining,
			},
		)

	internal_work_history = {}
	for item in details:
		field = frappe.get_meta("Employee").get_field(item.fieldname)
		if not field:
			continue
		fieldtype = field.fieldtype
		new_data = item.new if not cancel else item.current
		if fieldtype == "Date" and new_data:
			new_data = getdate(new_data)
		elif fieldtype == "Datetime" and new_data:
			new_data = get_datetime(new_data)
		setattr(employee, item.fieldname, new_data)
		if item.fieldname in ["department", "designation", "branch", "position_number"]:
			internal_work_history[item.fieldname] = item.new

	if internal_work_history and not cancel:
		internal_work_history["from_date"] = date
		employee.append("internal_work_history", internal_work_history)

	if cancel:
		delete_employee_work_history(details, employee, date)

	update_to_date_in_work_history(employee, cancel)

	return employee
	

def delete_employee_work_history(details, employee, date):
	filters = {}
	for d in details:
		for history in employee.internal_work_history:
			if d.property == "Department" and history.department == d.new:
				department = d.new
				filters["department"] = department
			if d.property == "Designation" and history.designation == d.new:
				designation = d.new
				filters["designation"] = designation
			if d.property == "Branch" and history.branch == d.new:
				branch = d.new
				filters["branch"] = branch
			if d.property == "Position Number" and history.position_number == d.new:
				position_number = d.new
				filters["position_number"] = position_number
			if date and date == history.from_date:
				filters["from_date"] = date
	if filters:
		frappe.db.delete("Employee Internal Work History", filters)
		employee.save()
