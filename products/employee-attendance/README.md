# Employee Attendance System

**Branch:** `product/employee-attendance`

## Overview

Workforce attendance and time tracking system for offices, factories, and organizations. Built on the FRS Base System V2.

## Features (To Implement)

### Employee Management
- [ ] Employee database with photos and employee ID
- [ ] Department/Team organization
- [ ] Designation and reporting hierarchy
- [ ] Employee profile with attendance history

### Shift Management
- [ ] Multiple shift definitions (day, night, rotational)
- [ ] Shift assignment to employees
- [ ] Flexible timing support
- [ ] Overtime calculation rules

### Time Tracking
- [ ] Check-in / Check-out detection
- [ ] Break time tracking
- [ ] Late arrival with grace period
- [ ] Early departure tracking
- [ ] Total working hours calculation

### Leave Management
- [ ] Leave types (casual, sick, earned, etc.)
- [ ] Leave balance tracking
- [ ] Leave application workflow
- [ ] Manager approval system
- [ ] Holiday calendar

### Notifications & Alerts
- [ ] Late arrival alerts to manager
- [ ] Absence notification
- [ ] Overtime alerts
- [ ] Weekly summary to employees

### Reports & Analytics
- [ ] Daily attendance register
- [ ] Monthly attendance summary
- [ ] Overtime reports
- [ ] Department-wise analytics
- [ ] Payroll integration data
- [ ] Export to Excel/CSV

### Integration
- [ ] HR Management System (HRMS) integration
- [ ] Payroll system integration
- [ ] Biometric system backup
- [ ] Access control integration

## Target Use Cases

- Corporate offices
- Manufacturing plants
- Warehouses and logistics
- Retail stores
- Call centers
- Coworking spaces
- Government offices

## Technical Requirements

- Entry/Exit cameras
- Fast recognition (<500ms)
- High accuracy for all age groups
- Offline capability
- Multi-location support
- High volume (1000+ employees)

## API Additions (Beyond Base)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/employees/` | CRUD | Employee management |
| `/api/employees/{id}/attendance` | GET | Employee attendance history |
| `/api/employees/{id}/photo` | GET/POST | Employee photo |
| `/api/departments/` | CRUD | Department management |
| `/api/shifts/` | CRUD | Shift definitions |
| `/api/shift-assignments/` | CRUD | Assign shifts to employees |
| `/api/attendance/` | GET | Attendance records |
| `/api/attendance/check-in` | POST | Manual check-in |
| `/api/attendance/check-out` | POST | Manual check-out |
| `/api/attendance/regularize` | POST | Regularize attendance |
| `/api/leaves/` | CRUD | Leave management |
| `/api/leaves/{id}/approve` | POST | Approve leave |
| `/api/leaves/{id}/reject` | POST | Reject leave |
| `/api/leave-balance/{employee_id}` | GET | Leave balance |
| `/api/holidays/` | CRUD | Holiday calendar |
| `/api/reports/daily` | GET | Daily attendance report |
| `/api/reports/monthly` | GET | Monthly summary |
| `/api/reports/overtime` | GET | Overtime report |
| `/api/reports/payroll` | GET | Payroll data export |

## Database Additions

### Core Tables
- **Employee** - name, employee_id, department, designation, manager, join_date
- **Department** - name, code, head, location
- **Designation** - name, level, department

### Shift Tables
- **Shift** - name, start_time, end_time, grace_period, break_duration
- **ShiftAssignment** - employee, shift, effective_from, effective_to
- **ShiftRotation** - employee, rotation_pattern

### Attendance Tables
- **AttendanceRecord** - employee, date, check_in, check_out, status, working_hours
- **AttendanceBreak** - attendance_record, break_start, break_end
- **AttendanceRegularization** - attendance_record, reason, approved_by

### Leave Tables
- **LeaveType** - name, code, days_per_year, carry_forward
- **LeaveBalance** - employee, leave_type, year, balance, used
- **LeaveRequest** - employee, leave_type, from_date, to_date, reason, status
- **LeaveApproval** - leave_request, approver, action, remarks

### Holiday Tables
- **Holiday** - date, name, type (public/optional/restricted)
- **HolidayLocation** - holiday, location (for multi-location)

## Frontend Additions

### Dashboard
- Real-time attendance overview
- Today's present/absent count
- Late arrivals list
- On-leave employees
- Pending approvals (for managers)

### Employee Management
- Employee directory with photos
- Employee profile page
- Attendance calendar view
- Individual attendance report

### Attendance Interface
- Check-in/Check-out status
- Manual attendance entry
- Regularization requests
- Overtime entry

### Leave Management
- Leave application form
- Leave calendar
- Leave balance view
- Approval workflow (managers)

### Reports
- Report generation interface
- Date range and filter selection
- Department/Team filters
- Export options (Excel, CSV, PDF)
- Graphical analytics

### Manager Portal
- Team attendance view
- Pending approvals
- Team analytics
- Overtime monitoring

## Attendance Status Types

| Status | Description |
|--------|-------------|
| `present` | Normal working day |
| `absent` | Did not report to work |
| `half_day` | Worked partial day |
| `late` | Arrived after grace period |
| `on_leave` | On approved leave |
| `holiday` | Public/Company holiday |
| `week_off` | Weekly off day |
| `work_from_home` | Remote working |
| `on_duty` | Official duty outside office |

## Overtime Rules

| Rule | Description |
|------|-------------|
| `minimum_ot` | Minimum overtime hours to count (e.g., 30 min) |
| `max_daily_ot` | Maximum overtime per day |
| `ot_multiplier` | Pay multiplier (1.5x, 2x for holidays) |
| `comp_off` | Compensatory off instead of pay |

## Payroll Integration Fields

- Total working days
- Present days
- Absent days (without leave)
- Leave days (paid/unpaid)
- Overtime hours
- Late arrival count
- Early departure count
