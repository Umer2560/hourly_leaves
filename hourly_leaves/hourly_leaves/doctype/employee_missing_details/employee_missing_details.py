# Copyright (c) 2023, umer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EmployeeMissingDetails(Document):
	pass
	
@frappe.whitelist()	
def missing_data():
	return_dict = {"missing_emergency_contact": 0 , "missing_passport_detail": 0, "missing_education_detail": 0, "missing_deposit": 0}
	if frappe.db.exists("Employee", {"user_id":frappe.session.user}):
		employee = frappe.get_doc('Employee', {'user_id': frappe.session.user})
		if employee:
			if not employee.person_to_be_contacted or not employee.emergency_phone_number or not employee.relation:
				return_dict['missing_emergency_contact'] = 1
				
			if not employee.passport_number or not employee.date_of_issue or not employee.valid_upto or not employee.place_of_issue:				
				if not employee.custom_national_identity_card_number or not employee.custom_attach_national_identity_card or not employee.custom_country_of_issue or not employee.custom_date_of_issue:
					return_dict['missing_passport_detail'] = 1
				
			if not employee.education:
				return_dict['missing_education_detail'] = 1
				
				
			if not frappe.db.exists("Direct Deposit Authorization", {"employee": employee.name}):
				return_dict['missing_deposit'] = 1
	return return_dict
