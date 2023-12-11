import frappe
from frappe import _
from frappe.model.document import Document

from hourly_leaves.hourly_leaves.utils import update_employee_work_history

class EmployeePromotion(Document):
	def on_submit(self):
		employee = frappe.get_doc("Employee", self.employee)
		employee = update_employee_work_history(
			employee, self.promotion_details, date=self.promotion_date
		)

		if self.revised_ctc:
			employee.ctc = self.revised_ctc

		employee.save()

	def on_cancel(self):
		employee = frappe.get_doc("Employee", self.employee)
		employee = update_employee_work_history(employee, self.promotion_details, cancel=True)

		if self.revised_ctc:
			employee.ctc = self.current_ctc

		employee.save()


@frappe.whitelist()
def update_emp_promotion():
	get_info = frappe.db.sql(""" select name from `tabEmployee Promotion` where docstatus = 0 and promotion_date = %s """,(frappe.utils.nowdate()))
	if get_info:
		for pro in get_info:
			doc = frappe.get_doc("Employee Promotion", str(pro[0]))
			doc.submit()
			
			
			

