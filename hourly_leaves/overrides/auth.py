import frappe
from frappe import _
import time

def successful_login(login_manager):
	if frappe.db.exists("Employee", {"user_id":frappe.session.user}):
		employee = frappe.get_doc('Employee', {'user_id': frappe.session.user})
		if employee:
			value = 0
			if not employee.person_to_be_contacted or not employee.emergency_phone_number or not employee.relation:
				value = 1
			if (not employee.passport_number or not employee.date_of_issue or not employee.valid_upto or not employee.place_of_issue):
				if (not employee.custom_national_identity_card_number or not employee.custom_attach_national_identity_card or not employee.custom_country_of_issue or not employee.custom_date_of_issue):
					value = 1
			if not employee.education:
				value = 1
				
			if not frappe.db.exists("Direct Deposit Authorization", {"employee": employee.name}):
				value = 1
			if value:
				frappe.local.response["home_page"] = "/app/employee-missing-details"
