import frappe
from frappe import _
from frappe.model.document import Document


@frappe.whitelist()
def update_emp_transfer():
	get_info = frappe.db.sql(""" select name from `tabEmployee Transfer` where docstatus = 0 and transfer_date = %s """,(frappe.utils.nowdate()))
	if get_info:
		for transfer in get_info:
			doc = frappe.get_doc("Employee Transfer", str(transfer[0]))
			doc.submit()
