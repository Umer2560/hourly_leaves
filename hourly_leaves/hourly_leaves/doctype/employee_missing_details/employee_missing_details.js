// Copyright (c) 2023, umer and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employee Missing Details', {
	onload: function (frm) {
		frm.disable_save()
		frappe.call({
		    method: "hourly_leaves.hourly_leaves.doctype.employee_missing_details.employee_missing_details.missing_data",
		    callback: function (r) {
		        var emp_id = r.message.employee
		        var checklistHtml = '<ul>';
		        if (r.message.missing_emergency_contact) {
		            checklistHtml += '<li><h3>Please <a href = "/app/employee/' + emp_id +'"> <b style="color: red;">Click here</b></a> to fill in your Emergency Contact details in your employee profile</h3></li>';
		        }
		        if (r.message.missing_passport_detail) {
		            checklistHtml += '<li><h3>Please <a href = "/app/employee/' + emp_id +'"> <b style="color: red;">Click here</b></a> to fill in your Passport details or National Identity Card Details in your employee profile</h3></li>';
		        }
		        if (r.message.missing_education_detail) {
		            checklistHtml += '<li><h3>Please <a href = "/app/employee/' + emp_id +'"> <b style="color: red;">Click here</b></a> to fill in your Education details in your employee profile</h3></li>';
		        }
		        if (r.message.missing_deposit) {
		            checklistHtml += '<li><h3>Please <a href = "/app/direct-deposit-authorization/new-direct-deposit-authorization"> <b style="color: red;">Click here</b></a> to fill in Direct Deposit Authorization Form </h3></li>';
		        }
		        checklistHtml += '</ul>';

		        $(checklistHtml).appendTo(frm.fields_dict.missing_detail.wrapper);
		    },
		});
    },
});
