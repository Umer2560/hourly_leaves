import frappe
from frappe import _
import time

def successful_login(login_manager):
	if frappe.db.exists("Employee", {"user_id":frappe.session.user}):
		employee = frappe.get_doc('Employee', {'user_id': frappe.session.user})
		if employee:
			if not employee.person_to_be_contacted or not employee.emergency_phone_number or not employee.relation:
				frappe.msgprint("<b>Please fill in your emergency contact details.</b>")
				
			if not employee.passport_number or not employee.date_of_issue or not employee.valid_upto or not employee.place_of_issue:
				frappe.msgprint("<b>Please fill in your Passport details.</b>")
				
			if not employee.education:
				frappe.msgprint("<b>Please fill in your Education details.</b>")
				
				
			if not frappe.db.exists("Direct Deposit Authorization", {"employee": employee.name}):
				frappe.msgprint("<b>Please fill in Direct Deposit Authorization Form</b>")
