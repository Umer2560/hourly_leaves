// Copyright (c) 2024, umer and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employee Balance Carry Forward', {
	refresh: function(frm) {
		frm.disable_save();
		frm.fields_dict.get_allocations.$input.addClass(' btn btn-primary');
		frm.fields_dict.carry_forward.$input.addClass(' btn btn-primary');
	},
	get_allocations:(frm)=>{
		erpnext.get_employees.get_employees_data(frm);
	},
	carry_forward:(frm)=>{
		erpnext.carry_forwards.create_fun(frm);
	}
});

erpnext.get_employees = {
	get_employees_data: function (frm) {

		frm.set_value("carry_forward_details" ,"");
		frappe.call({
			method: "hourly_leaves.hourly_leaves.doctype.employee_balance_carry_forward.employee_balance_carry_forward.get_employees_data",
			async: false,
			args:{
				"company":frm.doc.company,
				"leave_type":frm.doc.leave_type,
				"from_date":frm.doc.from_date,
				"to_date":frm.doc.to_date,
			},
			callback: function (response) {
				if (response.message) {
					$.each(response.message, function(i, d) {
						var row = frappe.model.add_child(frm.doc, "Carry Forward Table", "carry_forward_details");
						row.leave_allocation = d[0];
						row.employee = d[1];
					});
				}
				refresh_field("carry_forward_details");
			}
		});
	}
},

erpnext.carry_forwards = {
	create_fun: function (frm) {
		if (frm.doc.carry_forward_details)
		{
			frappe.call({
				method: "hourly_leaves.hourly_leaves.doctype.employee_balance_carry_forward.employee_balance_carry_forward.allot_leaves",
				async: false,
				args:{
					"carry_forward_details": frm.doc.carry_forward_details,
					"leave_type":frm.doc.leave_type,
				}
			});
		}
	}
}

