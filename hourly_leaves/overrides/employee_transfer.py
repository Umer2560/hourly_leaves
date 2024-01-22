import frappe
from frappe import _
from frappe.model.document import Document
from hourly_leaves.hourly_leaves.utils import update_employee_work_history
from hrms.hr.doctype.employee_transfer.employee_transfer import EmployeeTransfer

class EmployeeTransfer(EmployeeTransfer):
	def on_submit(self):
		employee = frappe.get_doc("Employee", self.employee)
		for x in self.transfer_details:
			if x.fieldname == "position_number":
				new_des = frappe.db.get_value("Position Number", x.new, "designation")
				if new_des:
					row = self.append("transfer_details", {})
					row.property = 'Designation'
					row.current = employee.designation
					row.new = new_des
					row.fieldname = 'designation'
		
		if self.create_new_employee_id:
			new_employee = frappe.copy_doc(employee)
			new_employee.name = None
			new_employee.employee_number = None
			new_employee = update_employee_work_history(
				new_employee, self.transfer_details, date=self.transfer_date
			)
			if self.new_company and self.company != self.new_company:
				new_employee.internal_work_history = []
				new_employee.date_of_joining = self.transfer_date
				new_employee.company = self.new_company
			# move user_id to new employee before insert
			if employee.user_id and not EmployeeTransfer.validate_user_in_details(self):
				new_employee.user_id = employee.user_id
				employee.db_set("user_id", "")
			new_employee.insert()
			self.db_set("new_employee_id", new_employee.name)
			# relieve the old employee
			employee.db_set("relieving_date", self.transfer_date)
			employee.db_set("status", "Left")
		else:
			employee = update_employee_work_history(
				employee, self.transfer_details, date=self.transfer_date
			)
			if self.new_company and self.company != self.new_company:
				employee.company = self.new_company
				employee.date_of_joining = self.transfer_date
			employee.save()


@frappe.whitelist()
def update_emp_transfer():
	get_info = frappe.db.sql(""" select name from `tabEmployee Transfer` where docstatus = 0 and transfer_date = %s """,(frappe.utils.nowdate()))
	if get_info:
		for transfer in get_info:
			doc = frappe.get_doc("Employee Transfer", str(transfer[0]))
			doc.submit()
