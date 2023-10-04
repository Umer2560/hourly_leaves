import datetime
from typing import Dict, Optional, Tuple, Union

import frappe
from frappe import _
from frappe.query_builder.functions import Max, Min, Sum
from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import daterange
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	flt,
	formatdate,
	get_fullname,
	get_link_to_form,
	getdate,
	nowdate,
)
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

from hrms.hr.doctype.leave_block_list.leave_block_list import get_applicable_block_dates
from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import create_leave_ledger_entry

from hrms.hr.utils import (
	get_holiday_dates_for_employee,
	get_leave_period,
	set_employee_name,
	share_doc_with_approver,
	validate_active_employee,
	get_earned_leaves,
	get_leave_allocations,
	check_effective_date,
	get_monthly_earned_leave,
	create_additional_leave_ledger_entry,
)


class LeaveApplication(LeaveApplication):

#Function override and changed
	def validate(self):
		validate_active_employee(self.employee)
		set_employee_name(self)
		LeaveApplication.validate_dates(self)
		self.validate_balance_leaves()
		LeaveApplication.validate_leave_overlap(self)
		LeaveApplication.validate_max_days(self)
		LeaveApplication.show_block_day_warning(self)
		LeaveApplication.validate_block_days(self)
		LeaveApplication.validate_salary_processed_days(self)
		LeaveApplication.validate_attendance(self)
		LeaveApplication.set_half_day_date
		
		if frappe.db.get_value("Leave Type", self.leave_type, 'is_optional_leave'):
			LeaveApplication.validate_optional_leave(self)
		LeaveApplication.validate_applicable_after(self)
		self.check_hours_applied()
	def validate_balance_leaves(self):
		if self.from_date and self.to_date:
			self.total_leave_days = get_number_of_leave_days(
				self.employee, self.leave_type, self.from_date, self.to_date, self.half_day, self.half_day_date, self.hours_required, self.specify_hours_date
			)

			if self.total_leave_days <= 0:
				frappe.throw(
					_(
						"The day(s) on which you are applying for leave are holidays. You need not apply for leave."
					)
				)

			if not is_lwp(self.leave_type):
				leave_balance = get_leave_balance_on(
					self.employee,
					self.leave_type,
					self.from_date,
					self.to_date,
					consider_all_leaves_in_the_allocation_period=True,
					for_consumption=True,
				)
				self.leave_balance = leave_balance.get("leave_balance")
				leave_balance_for_consumption = leave_balance.get("leave_balance_for_consumption")

				if self.status != "Rejected" and (
					leave_balance_for_consumption < self.total_leave_days or not leave_balance_for_consumption
				):
					self.show_insufficient_balance_message(leave_balance_for_consumption)
	def check_hours_applied(self):
		get_standard_hours = frappe.db.get_value("HR Settings", None, "standard_working_hours")
		self.hours_day_wise = 0.0
		
		if float(self.available_hours) < float(get_standard_hours):
			self.apply_hours = float(self.available_hours)
		else:
			if self.hours_required:
				if get_standard_hours:
					if float(self.apply_hours) > float(get_standard_hours):
						frappe.throw("Applying Hours must be Less or equal to the Standard Working Hours")
				self.hours_day_wise = (float(self.total_leave_days) - 0.5) * float(get_standard_hours)
			else:
				self.apply_hours = 0.0
				if get_standard_hours:
					self.hours_day_wise = float(self.total_leave_days) * float(get_standard_hours)
		if (float(self.apply_hours) + float(self.hours_day_wise)) > float(self.available_hours):
			frappe.throw("Applying Hours must be Less then Available Hours")
		
		self.total_hours_applied = float(self.hours_day_wise) + float(self.apply_hours)
			
		
	def on_submit(self):
		if self.status in ["Open", "Cancelled"]:
			frappe.throw(
				_("Only Leave Applications with status 'Approved' and 'Rejected' can be submitted")
			)

		LeaveApplication.validate_back_dated_application(self)
		self.update_attendance()

		# notify leave applier about approval
		if frappe.db.get_single_value("HR Settings", "send_leave_notification"):
			LeaveApplication.notify_employee(self)

		self.create_leave_ledger_entry()
		self.reload()
		
	def update_attendance(self):
		if self.status != "Approved":
			return

		holiday_dates = []
		if not frappe.db.get_value("Leave Type", self.leave_type, "include_holiday"):
			holiday_dates = get_holiday_dates_for_employee(self.employee, self.from_date, self.to_date)

		for dt in daterange(getdate(self.from_date), getdate(self.to_date)):
			date = dt.strftime("%Y-%m-%d")
			attendance_name = frappe.db.exists(
				"Attendance", dict(employee=self.employee, attendance_date=date, docstatus=("!=", 2))
			)

			# don't mark attendance for holidays
			# if leave type does not include holidays within leaves as leaves
			if date in holiday_dates:
				if attendance_name:
					# cancel and delete existing attendance for holidays
					attendance = frappe.get_doc("Attendance", attendance_name)
					attendance.flags.ignore_permissions = True
					if attendance.docstatus == 1:
						attendance.cancel()
					frappe.delete_doc("Attendance", attendance_name, force=1)
				continue

			self.create_or_update_attendance(attendance_name, date)

	def create_or_update_attendance(self, attendance_name, date):
		status = (
			"Half Day"
			if (self.half_day_date and getdate(date) == getdate(self.half_day_date)) or (self.specify_hours_date and getdate(date) == getdate(self.specify_hours_date))
			else "On Leave"
		)

		if attendance_name:
			# update existing attendance, change absent to on leave
			doc = frappe.get_doc("Attendance", attendance_name)
			if doc.status != status:
				doc.db_set({"status": status, "leave_type": self.leave_type, "leave_application": self.name})
		else:
			# make new attendance and submit it
			doc = frappe.new_doc("Attendance")
			doc.employee = self.employee
			doc.employee_name = self.employee_name
			doc.attendance_date = date
			doc.company = self.company
			doc.leave_type = self.leave_type
			doc.leave_application = self.name
			doc.status = status
			doc.flags.ignore_validate = True
			doc.insert(ignore_permissions=True)
			doc.submit()	
		
	def create_leave_ledger_entry(self, submit=True):
		if self.status != "Approved" and submit:
			return

		expiry_date = get_allocation_expiry_for_cf_leaves(
			self.employee, self.leave_type, self.to_date, self.from_date
		)
		lwp = frappe.db.get_value("Leave Type", self.leave_type, "is_lwp")

		if expiry_date:
			self.create_ledger_entry_for_intermediate_allocation_expiry(expiry_date, submit, lwp)
		else:
			alloc_on_from_date, alloc_on_to_date = LeaveApplication.get_allocation_based_on_application_dates(self)
			if LeaveApplication.is_separate_ledger_entry_required(self, alloc_on_from_date, alloc_on_to_date):
				LeaveApplication.create_separate_ledger_entries(self, alloc_on_from_date, alloc_on_to_date, submit, lwp)
			else:
				raise_exception = False if frappe.flags.in_patch else True
				args = dict(
					leaves=self.total_leave_days * -1,
					hours= (float(self.apply_hours) + float(self.hours_day_wise)) * -1,
					from_date=self.from_date,
					to_date=self.to_date,
					is_lwp=lwp,
					holiday_list=get_holiday_list_for_employee(self.employee, raise_exception=raise_exception)
					or "",
				)
				create_leave_ledger_entry(self, args, submit)
				
	def create_ledger_entry_for_intermediate_allocation_expiry(self, expiry_date, submit, lwp):
		"""Splits leave application into two ledger entries to consider expiry of allocation"""
		raise_exception = False if frappe.flags.in_patch else True

		leaves = get_number_of_leave_days(
				self.employee, self.leave_type, start_date, self.to_date, self.half_day, self.half_day_date, self.hours_required, self.specify_hours_date
			)

		if leaves:
			args = dict(
				from_date=self.from_date,
				to_date=expiry_date,
				leaves=leaves * -1,
				hours= (float(self.apply_hours) + float(self.hours_day_wise)) * -1,
				is_lwp=lwp,
				holiday_list=get_holiday_list_for_employee(self.employee, raise_exception=raise_exception)
				or "",
			)
			create_leave_ledger_entry(self, args, submit)

		if getdate(expiry_date) != getdate(self.to_date):
			start_date = add_days(expiry_date, 1)
			leaves = get_number_of_leave_days(
				self.employee, self.leave_type, start_date, self.to_date, self.half_day, self.half_day_date, self.hours_required, self.specify_hours_date
			)

			if leaves:
				args.update(dict(from_date=start_date, to_date=self.to_date, leaves=leaves * -1))
				create_leave_ledger_entry(self, args, submit)

def get_allocation_expiry_for_cf_leaves(
	employee: str, leave_type: str, to_date: datetime.date, from_date: datetime.date
) -> str:
	"""Returns expiry of carry forward allocation in leave ledger entry"""
	expiry = frappe.get_all(
		"Leave Ledger Entry",
		filters={
			"employee": employee,
			"leave_type": leave_type,
			"is_carry_forward": 1,
			"transaction_type": "Leave Allocation",
			"to_date": ["between", (from_date, to_date)],
			"docstatus": 1,
		},
		fields=["to_date"],
	)
	return expiry[0]["to_date"] if expiry else ""


@frappe.whitelist()
def get_number_of_leave_days(
	employee: str,
	leave_type: str,
	from_date: datetime.date,
	to_date: datetime.date,
	half_day: Union[int, str, None] = None,
	half_day_date: Union[datetime.date, str, None] = None,
	hours_required: Union[int, str, None] = None,
	specify_hours_date: Union[datetime.date, str, None] = None,
	holiday_list: Optional[str] = None,
) -> float:
	"""Returns number of leave days between 2 dates after considering half day and holidays
	(Based on the include_holiday setting in Leave Type)"""
	number_of_days = 0
	if cint(half_day) == 1:
		if getdate(from_date) == getdate(to_date):
			number_of_days = 0.5
		elif half_day_date and getdate(from_date) <= getdate(half_day_date) <= getdate(to_date):
			frappe.msgprint("elif")
			number_of_days = date_diff(to_date, from_date) + 0.5
		elif specify_hours_date and getdate(from_date) <= getdate(specify_hours_date) <= getdate(to_date):
			number_of_days = date_diff(to_date, from_date) + 0.5
		else:
			number_of_days = date_diff(to_date, from_date) + 1
	elif cint(hours_required) == 1:
		if getdate(from_date) == getdate(to_date):
			number_of_days = 0.5
		elif specify_hours_date and getdate(from_date) <= getdate(specify_hours_date) <= getdate(to_date):
			number_of_days = date_diff(to_date, from_date) + 0.5
		else:
			number_of_days = date_diff(to_date, from_date) + 1
	else:
		number_of_days = date_diff(to_date, from_date) + 1

	if not frappe.db.get_value("Leave Type", leave_type, "include_holiday"):
		number_of_days = flt(number_of_days) - flt(
			get_holidays(employee, from_date, to_date, holiday_list=holiday_list)
		)
	return number_of_days


@frappe.whitelist()
def get_leave_details(employee, date):
	allocation_records = get_leave_allocation_records(employee, date)
	leave_allocation = {}
	for d in allocation_records:
		allocation = allocation_records.get(d, frappe._dict())
		remaining_leaves = get_leave_balance_on(
			employee, d, date, to_date=allocation.to_date, consider_all_leaves_in_the_allocation_period=True
		)
		end_date = allocation.to_date
		leaves_taken = get_leaves_for_period(employee, d, allocation.from_date, end_date)[0] * -1
		leaves_pending = get_leaves_pending_approval_for_period(
			employee, d, allocation.from_date, end_date
		)
		expired_leaves = allocation.total_leaves_allocated - (remaining_leaves['leave_balance'] + leaves_taken)

		leave_allocation[d] = {
			"total_leaves": allocation.total_leaves_allocated,
			"expired_leaves": expired_leaves if expired_leaves > 0 else 0,
			"leaves_taken": leaves_taken,
			"leaves_pending_approval": leaves_pending,
			"remaining_leaves": remaining_leaves['leave_balance'],
			"total_hours": remaining_leaves['total_hours'],
			"remaining_hours": remaining_leaves['remaining_hours'],
			"total_hours_of_leaves_taken": remaining_leaves['total_hours_of_leaves_taken'],
		}

	# is used in set query
	lwp = frappe.get_list("Leave Type", filters={"is_lwp": 1}, pluck="name")

	return {
		"leave_allocation": leave_allocation,
		"leave_approver": get_leave_approver(employee),
		"lwps": lwp,
	}


@frappe.whitelist()
def get_leave_balance_on(
	employee: str,
	leave_type: str,
	date: datetime.date,
	to_date: Union[datetime.date, None] = None,
	consider_all_leaves_in_the_allocation_period: bool = False,
	for_consumption: bool = False,
):
	"""
	Returns leave balance till date
	:param employee: employee name
	:param leave_type: leave type
	:param date: date to check balance on
	:param to_date: future date to check for allocation expiry
	:param consider_all_leaves_in_the_allocation_period: consider all leaves taken till the allocation end date
	:param for_consumption: flag to check if leave balance is required for consumption or display
	        eg: employee has leave balance = 10 but allocation is expiring in 1 day so employee can only consume 1 leave
	        in this case leave_balance = 10 but leave_balance_for_consumption = 1
	        if True, returns a dict eg: {'leave_balance': 10, 'leave_balance_for_consumption': 1}
	        else, returns leave_balance (in this case 10)
	"""

	if not to_date:
		to_date = nowdate()

	allocation_records = get_leave_allocation_records(employee, date, leave_type)
	allocation = allocation_records.get(leave_type, frappe._dict())

	end_date = allocation.to_date if cint(consider_all_leaves_in_the_allocation_period) else date
	cf_expiry = get_allocation_expiry_for_cf_leaves(employee, leave_type, to_date, date)

	leaves_taken = get_leaves_for_period(employee, leave_type, allocation.from_date, end_date)

	remaining_leaves = get_remaining_leaves(allocation, leaves_taken[0], date, cf_expiry)
	remaining_leaves['remaining_hours'] = allocation['total_hours'] + (leaves_taken[1])
	remaining_leaves['total_hours'] = allocation['total_hours']
	remaining_leaves['total_hours_of_leaves_taken'] = allocation['total_hours'] - (allocation['total_hours'] + (leaves_taken[1]))
	
	return remaining_leaves


def get_leave_allocation_records(employee, date, leave_type=None):
	"""Returns the total allocated leaves and carry forwarded leaves based on ledger entries"""
	Ledger = frappe.qb.DocType("Leave Ledger Entry")

	cf_leave_case = (
		frappe.qb.terms.Case().when(Ledger.is_carry_forward == "1", Ledger.leaves).else_(0)
	)
	sum_cf_leaves = Sum(cf_leave_case).as_("cf_leaves")

	new_leaves_case = (
		frappe.qb.terms.Case().when(Ledger.is_carry_forward == "0", Ledger.leaves).else_(0)
	)
	sum_new_leaves = Sum(new_leaves_case).as_("new_leaves")
	sum_total_hours = Sum(Ledger.hours).as_("hours")
	query = (
		frappe.qb.from_(Ledger)
		.select(
			sum_cf_leaves,
			sum_new_leaves,
			Min(Ledger.from_date).as_("from_date"),
			Max(Ledger.to_date).as_("to_date"),
			sum_total_hours,
			Ledger.leave_type,
			Ledger.transaction_name,
		)
		.where(
			(Ledger.from_date <= date)
			& (Ledger.to_date >= date)
			& (Ledger.docstatus == 1)
			& (Ledger.transaction_type == "Leave Allocation")
			& (Ledger.employee == employee)
			& (Ledger.is_expired == 0)
			& (Ledger.is_lwp == 0)
		)
	)

	if leave_type:
		query = query.where((Ledger.leave_type == leave_type))
	query = query.groupby(Ledger.employee, Ledger.leave_type)

	allocation_details = query.run(as_dict=True)
	allocated_leaves = frappe._dict()
	
	for d in allocation_details:
		allocated_leaves.setdefault(
			d.leave_type,
			frappe._dict(
				{
					"from_date": d.from_date,
					"to_date": d.to_date,
					"total_leaves_allocated": flt(d.cf_leaves) + flt(d.new_leaves),
					"unused_leaves": d.cf_leaves,
					"total_hours": d.hours,
					"new_leaves_allocated": d.new_leaves,
					"leave_type": d.leave_type,
				}
			),
		)
	return allocated_leaves


def get_leaves_pending_approval_for_period(
	employee: str, leave_type: str, from_date: datetime.date, to_date: datetime.date
) -> float:
	"""Returns leaves that are pending for approval"""
	leaves = frappe.get_all(
		"Leave Application",
		filters={"employee": employee, "leave_type": leave_type, "status": "Open"},
		or_filters={
			"from_date": ["between", (from_date, to_date)],
			"to_date": ["between", (from_date, to_date)],
		},
		fields=["SUM(total_leave_days) as leaves"],
	)[0]
	return leaves["leaves"] if leaves["leaves"] else 0.0


def get_remaining_leaves(
	allocation: Dict, leaves_taken: float, date: str, cf_expiry: str
) -> Dict[str, float]:
	"""Returns a dict of leave_balance and leave_balance_for_consumption
	leave_balance returns the available leave balance
	leave_balance_for_consumption returns the minimum leaves remaining after comparing with remaining days for allocation expiry
	"""

	def _get_remaining_leaves(remaining_leaves, end_date):
		"""Returns minimum leaves remaining after comparing with remaining days for allocation expiry"""
		if remaining_leaves > 0:
			remaining_days = date_diff(end_date, date) + 1
			remaining_leaves = min(remaining_days, remaining_leaves)

		return remaining_leaves

	leave_balance = leave_balance_for_consumption = flt(allocation.total_leaves_allocated) + flt(
		leaves_taken
	)

	# balance for carry forwarded leaves
	if cf_expiry and allocation.unused_leaves:
		cf_leaves = flt(allocation.unused_leaves) + flt(leaves_taken)
		remaining_cf_leaves = _get_remaining_leaves(cf_leaves, cf_expiry)

		leave_balance = flt(allocation.new_leaves_allocated) + flt(cf_leaves)
		leave_balance_for_consumption = flt(allocation.new_leaves_allocated) + flt(remaining_cf_leaves)

	remaining_leaves = _get_remaining_leaves(leave_balance_for_consumption, allocation.to_date)
	return frappe._dict(leave_balance=leave_balance, leave_balance_for_consumption=remaining_leaves)


def get_leaves_for_period(
	employee: str,
	leave_type: str,
	from_date: datetime.date,
	to_date: datetime.date,
	skip_expired_leaves: bool = True,
) -> float:
	leave_entries = get_leave_entries(employee, leave_type, from_date, to_date)
	leave_days = 0
	leave_hours = 0
	for leave_entry in leave_entries:
		inclusive_period = leave_entry.from_date >= getdate(
			from_date
		) and leave_entry.to_date <= getdate(to_date)

		if inclusive_period and leave_entry.transaction_type == "Leave Encashment":
			leave_days += leave_entry.leaves
			leave_hours += leave_entry.hours

		elif (
			inclusive_period
			and leave_entry.transaction_type == "Leave Allocation"
			and leave_entry.is_expired
			and not skip_expired_leaves
		):
			leave_hours += leave_entry.hours
			leave_days += leave_entry.leaves

		elif leave_entry.transaction_type == "Leave Application":
			leave_hours += leave_entry.hours
			if leave_entry.from_date < getdate(from_date):
				leave_entry.from_date = from_date
			if leave_entry.to_date > getdate(to_date):
				leave_entry.to_date = to_date

			half_day = 0
			hours_required = 0
			specify_hours_date = None
			half_day_date = None
			
			# fetch half day date for leaves with half days
			if leave_entry.leaves % 1:
				half_day = 1
				half_day_date = frappe.db.get_value(
					"Leave Application", {"name": leave_entry.transaction_name}, ["half_day_date"]
				)
				hours_required = 1
				specify_hours_date = frappe.db.get_value(
					"Leave Application", {"name": leave_entry.transaction_name}, ["specify_hours_date"]
				)

			leave_days += (
				get_number_of_leave_days(
					employee,
					leave_type,
					leave_entry.from_date,
					leave_entry.to_date,
					half_day,
					half_day_date,
					hours_required,
					specify_hours_date,
					holiday_list=leave_entry.holiday_list,
				)
				* -1
			)

	return leave_days, leave_hours




def get_leave_entries(employee, leave_type, from_date, to_date):
	"""Returns leave entries between from_date and to_date."""
	return frappe.db.sql(
		"""
		SELECT
			employee, leave_type, from_date, to_date, leaves, hours, transaction_name, transaction_type, holiday_list,
			is_carry_forward, is_expired
		FROM `tabLeave Ledger Entry`
		WHERE employee=%(employee)s AND leave_type=%(leave_type)s
			AND docstatus=1
			AND (leaves<0
				OR is_expired=1)
			AND (from_date between %(from_date)s AND %(to_date)s
				OR to_date between %(from_date)s AND %(to_date)s
				OR (from_date < %(from_date)s AND to_date > %(to_date)s))
	""",
		{"from_date": from_date, "to_date": to_date, "employee": employee, "leave_type": leave_type},
		as_dict=1,
	)


@frappe.whitelist()
def get_holidays(employee, from_date, to_date, holiday_list=None):
	"""get holidays between two dates for the given employee"""
	if not holiday_list:
		holiday_list = get_holiday_list_for_employee(employee)

	holidays = frappe.db.sql(
		"""select count(distinct holiday_date) from `tabHoliday` h1, `tabHoliday List` h2
		where h1.parent = h2.name and h1.holiday_date between %s and %s
		and h2.name = %s""",
		(from_date, to_date, holiday_list),
	)[0][0]

	return holidays


def is_lwp(leave_type):
	lwp = frappe.db.sql("select is_lwp from `tabLeave Type` where name = %s", leave_type)
	return lwp and cint(lwp[0][0]) or 0


@frappe.whitelist()
def get_events(start, end, filters=None):
	from frappe.desk.reportview import get_filters_cond

	events = []

	employee = frappe.db.get_value(
		"Employee", filters={"user_id": frappe.session.user}, fieldname=["name", "company"], as_dict=True
	)

	if employee:
		employee, company = employee.name, employee.company
	else:
		employee = ""
		company = frappe.db.get_value("Global Defaults", None, "default_company")

	conditions = get_filters_cond("Leave Application", filters, [])
	# show department leaves for employee
	if "Employee" in frappe.get_roles():
		add_department_leaves(events, start, end, employee, company)

	add_leaves(events, start, end, conditions)
	add_block_dates(events, start, end, employee, company)
	add_holidays(events, start, end, employee, company)

	return events


def add_department_leaves(events, start, end, employee, company):
	department = frappe.db.get_value("Employee", employee, "department")

	if not department:
		return

	# department leaves
	department_employees = frappe.db.sql_list(
		"""select name from tabEmployee where department=%s
		and company=%s""",
		(department, company),
	)

	filter_conditions = ' and employee in ("%s")' % '", "'.join(department_employees)
	add_leaves(events, start, end, filter_conditions=filter_conditions)


def add_leaves(events, start, end, filter_conditions=None):
	from frappe.desk.reportview import build_match_conditions

	conditions = []

	if not cint(
		frappe.db.get_value("HR Settings", None, "show_leaves_of_all_department_members_in_calendar")
	):
		match_conditions = build_match_conditions("Leave Application")

		if match_conditions:
			conditions.append(match_conditions)

	query = """SELECT
		docstatus,
		name,
		employee,
		employee_name,
		leave_type,
		from_date,
		to_date,
		half_day,
		status,
		color
	FROM `tabLeave Application`
	WHERE
		from_date <= %(end)s AND to_date >= %(start)s <= to_date
		AND docstatus < 2
		AND status in ('Approved', 'Open')
	"""

	if conditions:
		query += " AND " + " AND ".join(conditions)

	if filter_conditions:
		query += filter_conditions

	for d in frappe.db.sql(query, {"start": start, "end": end}, as_dict=True):
		e = {
			"name": d.name,
			"doctype": "Leave Application",
			"from_date": d.from_date,
			"to_date": d.to_date,
			"docstatus": d.docstatus,
			"color": d.color,
			"all_day": int(not d.half_day),
			"title": cstr(d.employee_name)
			+ f" ({cstr(d.leave_type)})"
			+ (" " + _("(Half Day)") if d.half_day else ""),
		}
		if e not in events:
			events.append(e)


def add_block_dates(events, start, end, employee, company):
	# block days
	cnt = 0
	block_dates = get_applicable_block_dates(start, end, employee, company, all_lists=True)

	for block_date in block_dates:
		events.append(
			{
				"doctype": "Leave Block List Date",
				"from_date": block_date.block_date,
				"to_date": block_date.block_date,
				"title": _("Leave Blocked") + ": " + block_date.reason,
				"name": "_" + str(cnt),
			}
		)
		cnt += 1


def add_holidays(events, start, end, employee, company):
	applicable_holiday_list = get_holiday_list_for_employee(employee, company)
	if not applicable_holiday_list:
		return

	for holiday in frappe.db.sql(
		"""select name, holiday_date, description
		from `tabHoliday` where parent=%s and holiday_date between %s and %s""",
		(applicable_holiday_list, start, end),
		as_dict=True,
	):
		events.append(
			{
				"doctype": "Holiday",
				"from_date": holiday.holiday_date,
				"to_date": holiday.holiday_date,
				"title": _("Holiday") + ": " + cstr(holiday.description),
				"name": holiday.name,
			}
		)


@frappe.whitelist()
def get_mandatory_approval(doctype):
	mandatory = ""
	if doctype == "Leave Application":
		mandatory = frappe.db.get_single_value(
			"HR Settings", "leave_approver_mandatory_in_leave_application"
		)
	else:
		mandatory = frappe.db.get_single_value(
			"HR Settings", "expense_approver_mandatory_in_expense_claim"
		)

	return mandatory


def get_approved_leaves_for_period(employee, leave_type, from_date, to_date):
	LeaveApplication = frappe.qb.DocType("Leave Application")
	query = (
		frappe.qb.from_(LeaveApplication)
		.select(
			LeaveApplication.employee,
			LeaveApplication.leave_type,
			LeaveApplication.from_date,
			LeaveApplication.to_date,
			LeaveApplication.total_leave_days,
		)
		.where(
			(LeaveApplication.employee == employee)
			& (LeaveApplication.docstatus == 1)
			& (LeaveApplication.status == "Approved")
			& (
				(LeaveApplication.from_date.between(from_date, to_date))
				| (LeaveApplication.to_date.between(from_date, to_date))
				| ((LeaveApplication.from_date < from_date) & (LeaveApplication.to_date > to_date))
			)
		)
	)

	if leave_type:
		query = query.where(LeaveApplication.leave_type == leave_type)

	leave_applications = query.run(as_dict=True)

	leave_days = 0
	for leave_app in leave_applications:
		if leave_app.from_date >= getdate(from_date) and leave_app.to_date <= getdate(to_date):
			leave_days += leave_app.total_leave_days
		else:
			if leave_app.from_date < getdate(from_date):
				leave_app.from_date = from_date
			if leave_app.to_date > getdate(to_date):
				leave_app.to_date = to_date

			leave_days += get_number_of_leave_days(
				employee, leave_type, leave_app.from_date, leave_app.to_date
			)

	return leave_days


@frappe.whitelist()
def get_leave_approver(employee):
	leave_approver, department = frappe.db.get_value(
		"Employee", employee, ["leave_approver", "department"]
	)

	if not leave_approver and department:
		leave_approver = frappe.db.get_value(
			"Department Approver",
			{"parent": department, "parentfield": "leave_approvers", "idx": 1},
			"approver",
		)

	return leave_approver
	
def allocate_earned_leaves():
	"""Allocate earned leaves to Employees"""
	e_leave_types = get_earned_leaves()
	today = getdate()

	for e_leave_type in e_leave_types:

		leave_allocations = get_leave_allocations(today, e_leave_type.name)

		for allocation in leave_allocations:

			if not allocation.leave_policy_assignment and not allocation.leave_policy:
				continue

			leave_policy = (
				allocation.leave_policy
				if allocation.leave_policy
				else frappe.db.get_value(
					"Leave Policy Assignment", allocation.leave_policy_assignment, ["leave_policy"]
				)
			)

			annual_allocation = frappe.db.get_value(
				"Leave Policy Detail",
				filters={"parent": leave_policy, "leave_type": e_leave_type.name},
				fieldname=["annual_allocation"],
			)

			from_date = allocation.from_date

			if e_leave_type.allocate_on_day == "Date of Joining":
				from_date = frappe.db.get_value("Employee", allocation.employee, "date_of_joining")

			if check_effective_date(
				from_date, today, e_leave_type.earned_leave_frequency, e_leave_type.allocate_on_day
			):
				update_previous_leave_allocation(allocation, annual_allocation, e_leave_type)
				
def update_previous_leave_allocation(allocation, annual_allocation, e_leave_type):
	earned_leaves = get_monthly_earned_leave(
		annual_allocation, e_leave_type.earned_leave_frequency, e_leave_type.rounding
	)

	allocation = frappe.get_doc("Leave Allocation", allocation.name)
	new_allocation = flt(allocation.total_leaves_allocated) + flt(earned_leaves)

	if new_allocation > e_leave_type.max_leaves_allowed and e_leave_type.max_leaves_allowed > 0:
		new_allocation = e_leave_type.max_leaves_allowed

	if new_allocation != allocation.total_leaves_allocated:
		today_date = today()

		allocation.db_set("total_leaves_allocated", new_allocation, update_modified=False)
		#allocation.db_set("hours", new_allocation, update_modified=False)
		create_additional_leave_ledger_entry(allocation, earned_leaves, today_date)

		if e_leave_type.allocate_on_day:
			text = _(
				"Allocated {0} leave(s) via scheduler on {1} based on the 'Allocate on Day' option set to {2}"
			).format(
				frappe.bold(earned_leaves), frappe.bold(formatdate(today_date)), e_leave_type.allocate_on_day
			)

		allocation.add_comment(comment_type="Info", text=text)
