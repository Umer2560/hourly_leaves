import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def update_emp_promotion():
	get_info = frappe.db.sql(""" select name from `tabEmployee Promotion` where docstatus = 0 and promotion_date = %s """,(frappe.utils.nowdate()))
	if get_info:
		for pro in get_info:
			doc = frappe.get_doc("Employee Promotion", str(pro[0]))
			doc.submit()
