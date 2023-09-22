import frappe
from frappe import _

from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import (
	create_leave_ledger_entry,
	expire_allocation,
)
from frappe.utils import add_days, date_diff, flt, formatdate, getdate
from hrms.hr.doctype.leave_allocation.leave_allocation import LeaveAllocation, get_previous_allocation

from hrms.hr.utils import set_employee_name

class LeaveAllocation(LeaveAllocation):
#function overrride and changed
	def validate(self):
		LeaveAllocation.validate_period(self)
		LeaveAllocation.validate_allocation_overlap(self)
		LeaveAllocation.validate_lwp(self)
		set_employee_name(self)
		LeaveAllocation.set_total_leaves_allocated(self)
		LeaveAllocation.validate_leave_days_and_dates(self)
		
		self.validate_hours()
		
	def on_submit(self):
		self.create_leave_ledger_entry()

		# expire all unused leaves in the ledger on creation of carry forward allocation
		allocation = get_previous_allocation(self.from_date, self.leave_type, self.employee)
		if self.carry_forward and allocation:
			expire_allocation(allocation)
		
	def create_leave_ledger_entry(self, submit=True):
		self.validate_hours()
		if self.unused_leaves:
			expiry_days = frappe.db.get_value(
				"Leave Type", self.leave_type, "expire_carry_forwarded_leaves_after_days"
			)
			end_date = add_days(self.from_date, expiry_days - 1) if expiry_days else self.to_date
			args = dict(
				leaves=self.unused_leaves,
				#hours=self.total_hours,
				from_date=self.from_date,
				to_date=min(getdate(end_date), getdate(self.to_date)),
				is_carry_forward=1,
			)
			create_leave_ledger_entry(self, args, submit)

		args = dict(
			leaves=self.new_leaves_allocated,
			hours=self.total_hours,
			from_date=self.from_date,
			to_date=self.to_date,
			is_carry_forward=0,
		)
		create_leave_ledger_entry(self, args, submit)
		
#custom function
	def validate_hours(self):
		self.total_hours = 0.0
		get_standard_hours = frappe.db.get_value("HR Settings", None, "standard_working_hours")
		if get_standard_hours:
			self.total_hours += float(self.new_leaves_allocated) * float(get_standard_hours)
			if self.unused_leaves:
				self.total_hours += float(self.unused_leaves) * float(get_standard_hours)
