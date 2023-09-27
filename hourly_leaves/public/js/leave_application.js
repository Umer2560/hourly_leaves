frappe.ui.form.on('Leave Application', {
	employee: function(frm) {
		frm.trigger("hours_data");
		frm.trigger("dashboard_");
	},
	from_date: function(frm) {
		frm.trigger("hours_data");
		frm.trigger("dashboard_");
		frm.trigger("total_days");
	},
	to_date: function(frm) {
		frm.trigger("hours_data");
		frm.trigger("dashboard_");
		frm.trigger("total_days");
	},
	leave_type: function(frm) {
		frm.trigger("hours_data");
		frm.trigger("dashboard_");
	},
	refresh: function(frm) {
		if (frm.is_new()) {
			frm.trigger("total_days");
		}
	},
	validate: function(frm) {
		if (frm.doc.from_date == frm.doc.to_date && frm.doc.hours_required == 1) {
			frm.doc.specify_hours_date = frm.doc.from_date;
		} else if (frm.doc.hours_required == 0) {
			frm.doc.specify_hours_date = "";
		}
		frm.toggle_reqd("specify_hours_date", frm.doc.hours_required == 1);
	},
	hours_required: function(frm) {
		if (frm.doc.hours_required) {
			if (frm.doc.from_date == frm.doc.to_date) {
				frm.set_value("specify_hours_date", frm.doc.from_date);
			} else {
				frm.trigger("hours_date_datepicker");
			}
		} else {
			frm.set_value("specify_hours_date", "");
		}
		frm.trigger("total_days");
	},
	hours_date_datepicker: function(frm) {
		frm.set_value('specify_hours_date', '');
		var hours_date_datepicker = frm.fields_dict.specify_hours_date.datepicker;
		hours_date_datepicker.update({
			minDate: frappe.datetime.str_to_obj(frm.doc.from_date),
			maxDate: frappe.datetime.str_to_obj(frm.doc.to_date)
		});
	},
	total_days: function(frm) {
		if (frm.doc.from_date && frm.doc.to_date && frm.doc.employee && frm.doc.leave_type) {

			var from_date = Date.parse(frm.doc.from_date);
			var to_date = Date.parse(frm.doc.to_date);

			if (to_date < from_date) {
				frappe.msgprint(__("To Date cannot be less than From Date"));
				frm.set_value('to_date', '');
				return;
			}
			// server call is done to include holidays in leave days calculations
			return frappe.call({
				method: 'hourly_leaves.overrides.leave_application.get_number_of_leave_days',
				args: {
					"employee": frm.doc.employee,
					"leave_type": frm.doc.leave_type,
					"from_date": frm.doc.from_date,
					"to_date": frm.doc.to_date,
					"half_day": frm.doc.half_day,
					"half_day_date": frm.doc.half_day_date,
					"hours_required": frm.doc.hours_required,
					"specify_hours_date": frm.doc.specify_hours_date,
				},
				callback: function(r) {
					console.log(r.message)
					if (r && r.message) {
						frm.set_value('total_leave_days', r.message);
						frm.trigger("hours_data");
					}
				}
			});
		}
	},
	specify_hours_date(frm) {
		frm.trigger("total_days");
	},
	hours_data: function(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.employee && frm.doc.leave_type && frm.doc.from_date && frm.doc.to_date) {
			return frappe.call({
				method: "hourly_leaves.overrides.leave_application.get_leave_balance_on",
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date,
					to_date: frm.doc.to_date,
					leave_type: frm.doc.leave_type,
					consider_all_leaves_in_the_allocation_period: 1
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frm.set_value('available_hours', r.message['remaining_hours']);
						frm.set_value('total_hours', r.message['total_hours']);
						frm.set_value('total_hours_of_leaves_taken', r.message['total_hours_of_leaves_taken']);
					} else {
						frm.set_value('available_hours', "0");
					}
				}
			});
		}
	},
	dashboard_: function(frm) {
		var leave_details;
		let lwps;
		if (frm.doc.employee) {
			frappe.call({
				method: "hourly_leaves.overrides.leave_application.get_leave_details",
				async: false,
				args: {
					employee: frm.doc.employee,
					date: frm.doc.from_date || frm.doc.posting_date
				},
				callback: function(r) {
					if (!r.exc && r.message['leave_allocation']) {
						leave_details = r.message['leave_allocation'];
					}
					if (!r.exc && r.message['leave_approver']) {
						frm.set_value('leave_approver', r.message['leave_approver']);
					}
					lwps = r.message["lwps"];
				}
			});
			$("div").remove(".form-dashboard-section.custom");
			var html_ = `{% if not jQuery.isEmptyObject(data) %}
<table class="table table-bordered small">
	<thead>
		<tr>
			<th style="width: 16%">{{ __("Leave Type") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Total Allocated Leave(s)") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Expired Leave(s)") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Used Leave(s)") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Leave(s) Pending Approval") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Available Leave(s)") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Total Hour(s)") }}</th>
			<th style="width: 16%" class="text-right">{{ __("Remaining Hour(s)") }}</th>
		</tr>
	</thead>
	<tbody>
		{% for(const [key, value] of Object.entries(data)) { %}
			<tr>
				<td> {%= key %} </td>
				<td class="text-right"> {%= value["total_leaves"] %} </td>
				<td class="text-right"> {%= value["expired_leaves"] %} </td>
				<td class="text-right"> {%= value["leaves_taken"] %} </td>
				<td class="text-right"> {%= value["leaves_pending_approval"] %} </td>
				<td class="text-right"> {%= value["remaining_leaves"] %} </td>
				<td class="text-right"> {%= value["total_hours"] %} </td>
				<td class="text-right"> {%= value["remaining_hours"] %} </td>
			</tr>
		{% } %}
	</tbody>
</table>
{% else %}
<p style="margin-top: 30px;"> No Leave has been allocated. </p>
{% endif %}`
			frm.dashboard.add_section(
				frappe.render_template(html_, {
					data: leave_details
				}),
				__("Allocated Leaves")
			);
			frm.dashboard.show();
			let allowed_leave_types = Object.keys(leave_details);

			// lwps should be allowed, lwps don't have any allocation
			allowed_leave_types = allowed_leave_types.concat(lwps);

			frm.set_query('leave_type', function() {
				return {
					filters: [
						['leave_type_name', 'in', allowed_leave_types]
					]
				};
			});
		}
	}
})
