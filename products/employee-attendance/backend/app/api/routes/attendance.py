"""
Attendance API routes.
Handles check-in/out logging and attendance records.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime, date, timedelta
import logging
import csv
import io

from ...models.database import Employee, AttendanceLog, Department, get_db
from ...config import settings
from ..deps import get_current_active_user, require_admin
from ...models.database import User

logger = logging.getLogger(__name__)
router = APIRouter()


def calculate_status(check_in_time: datetime, shift_start, late_threshold: int = 15) -> tuple:
    """
    Calculate attendance status based on check-in time.
    Returns (status, late_minutes)
    """
    if not check_in_time or not shift_start:
        return "present", 0

    # Create datetime for comparison (same date as check-in)
    shift_start_dt = datetime.combine(check_in_time.date(), shift_start)
    late_threshold_dt = shift_start_dt + timedelta(minutes=late_threshold)

    if check_in_time <= shift_start_dt:
        return "present", 0
    elif check_in_time <= late_threshold_dt:
        late_mins = int((check_in_time - shift_start_dt).total_seconds() / 60)
        return "present", late_mins  # Within grace period
    else:
        late_mins = int((check_in_time - shift_start_dt).total_seconds() / 60)
        return "late", late_mins


def calculate_work_hours(check_in: datetime, check_out: datetime, standard_hours: float = 8.0) -> tuple:
    """
    Calculate work hours and overtime.
    Returns (work_hours, overtime_hours)
    """
    if not check_in or not check_out:
        return None, None

    duration = check_out - check_in
    work_hours = duration.total_seconds() / 3600  # Convert to hours

    overtime = max(0, work_hours - standard_hours)

    return round(work_hours, 2), round(overtime, 2)


@router.get("/today")
async def get_today_attendance(
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get today's attendance summary."""
    today = date.today()

    # Get all active employees
    emp_query = db.query(Employee).filter(Employee.is_active == True)
    if department_id:
        emp_query = emp_query.filter(Employee.department_id == department_id)

    total_employees = emp_query.count()
    all_employees = emp_query.all()
    employee_ids = [e.id for e in all_employees]

    # Get today's attendance logs
    logs = db.query(AttendanceLog).filter(
        AttendanceLog.date == today,
        AttendanceLog.employee_id.in_(employee_ids)
    ).all()

    logs_by_employee = {log.employee_id: log for log in logs}

    present = 0
    late = 0
    absent = 0
    checked_out = 0

    attendance_list = []

    for emp in all_employees:
        log = logs_by_employee.get(emp.id)
        if log:
            if log.status == "late":
                late += 1
                present += 1
            else:
                present += 1

            if log.check_out_time:
                checked_out += 1

            attendance_list.append({
                "employee_id": emp.employee_id,
                "name": emp.name,
                "department": emp.department.name if emp.department else None,
                "status": log.status,
                "check_in": log.check_in_time.strftime("%H:%M") if log.check_in_time else None,
                "check_out": log.check_out_time.strftime("%H:%M") if log.check_out_time else None,
                "late_minutes": log.late_minutes,
                "work_hours": log.work_hours
            })
        else:
            absent += 1
            attendance_list.append({
                "employee_id": emp.employee_id,
                "name": emp.name,
                "department": emp.department.name if emp.department else None,
                "status": "absent",
                "check_in": None,
                "check_out": None,
                "late_minutes": None,
                "work_hours": None
            })

    return {
        "date": today.isoformat(),
        "summary": {
            "total": total_employees,
            "present": present,
            "late": late,
            "absent": absent,
            "checked_out": checked_out
        },
        "attendance": sorted(attendance_list, key=lambda x: (x["status"] != "absent", x["name"]))
    }


@router.get("/logs")
async def get_attendance_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    employee_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get attendance logs with filters."""
    query = db.query(AttendanceLog).join(Employee)

    # Date filters
    if start_date:
        try:
            start = date.fromisoformat(start_date)
            query = query.filter(AttendanceLog.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = date.fromisoformat(end_date)
            query = query.filter(AttendanceLog.date <= end)
        except ValueError:
            pass

    if employee_id:
        query = query.filter(AttendanceLog.employee_id == employee_id)

    if department_id:
        query = query.filter(Employee.department_id == department_id)

    if status:
        query = query.filter(AttendanceLog.status == status)

    total = query.count()
    logs = query.order_by(AttendanceLog.date.desc(), AttendanceLog.check_in_time.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "logs": [
            {
                "id": log.id,
                "employee_id": log.employee.employee_id,
                "employee_name": log.employee.name,
                "department": log.employee.department.name if log.employee.department else None,
                "date": log.date.isoformat(),
                "check_in": log.check_in_time.strftime("%H:%M:%S") if log.check_in_time else None,
                "check_out": log.check_out_time.strftime("%H:%M:%S") if log.check_out_time else None,
                "status": log.status,
                "work_hours": log.work_hours,
                "overtime_hours": log.overtime_hours,
                "late_minutes": log.late_minutes
            }
            for log in logs
        ]
    }


@router.post("/manual-check-in/{employee_id}")
async def manual_check_in(
    employee_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Manually check in an employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = date.today()
    now = datetime.now()

    # Check if already checked in today
    existing = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == employee_id,
        AttendanceLog.date == today
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Employee already checked in today")

    # Calculate status
    status, late_mins = calculate_status(now, employee.shift_start, settings.late_threshold_minutes)

    log = AttendanceLog(
        employee_id=employee_id,
        date=today,
        check_in_time=now,
        status=status,
        late_minutes=late_mins,
        notes="Manual check-in"
    )
    db.add(log)
    db.commit()

    return {
        "message": "Check-in recorded",
        "employee": employee.name,
        "time": now.strftime("%H:%M:%S"),
        "status": status
    }


@router.post("/manual-check-out/{employee_id}")
async def manual_check_out(
    employee_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Manually check out an employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = date.today()
    now = datetime.now()

    # Get today's attendance
    log = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == employee_id,
        AttendanceLog.date == today
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="Employee not checked in today")

    if log.check_out_time:
        raise HTTPException(status_code=400, detail="Employee already checked out")

    log.check_out_time = now
    log.work_hours, log.overtime_hours = calculate_work_hours(
        log.check_in_time, now, settings.standard_work_hours
    )
    log.notes = (log.notes or "") + " | Manual check-out"

    db.commit()

    return {
        "message": "Check-out recorded",
        "employee": employee.name,
        "time": now.strftime("%H:%M:%S"),
        "work_hours": log.work_hours
    }


@router.get("/report")
async def get_attendance_report(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    department_id: Optional[int] = None,
    format: str = Query("json", description="Output format: json or csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate attendance report for date range."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    # Get employees
    emp_query = db.query(Employee).filter(Employee.is_active == True)
    if department_id:
        emp_query = emp_query.filter(Employee.department_id == department_id)
    employees = emp_query.all()

    # Get attendance logs for date range
    logs = db.query(AttendanceLog).filter(
        AttendanceLog.date >= start,
        AttendanceLog.date <= end
    ).all()

    # Create lookup
    logs_lookup = {}
    for log in logs:
        key = (log.employee_id, log.date)
        logs_lookup[key] = log

    # Calculate stats per employee
    report_data = []
    total_days = (end - start).days + 1

    for emp in employees:
        present_days = 0
        late_days = 0
        absent_days = 0
        total_hours = 0
        total_overtime = 0

        for day_offset in range(total_days):
            current_date = start + timedelta(days=day_offset)
            # Skip weekends
            if current_date.weekday() >= 5:
                continue

            log = logs_lookup.get((emp.id, current_date))
            if log:
                present_days += 1
                if log.status == "late":
                    late_days += 1
                if log.work_hours:
                    total_hours += log.work_hours
                if log.overtime_hours:
                    total_overtime += log.overtime_hours
            else:
                absent_days += 1

        report_data.append({
            "employee_id": emp.employee_id,
            "name": emp.name,
            "department": emp.department.name if emp.department else "N/A",
            "present_days": present_days,
            "late_days": late_days,
            "absent_days": absent_days,
            "total_work_hours": round(total_hours, 2),
            "total_overtime_hours": round(total_overtime, 2),
            "attendance_percentage": round((present_days / max(1, present_days + absent_days)) * 100, 1)
        })

    if format == "csv":
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "employee_id", "name", "department", "present_days", "late_days",
            "absent_days", "total_work_hours", "total_overtime_hours", "attendance_percentage"
        ])
        writer.writeheader()
        writer.writerows(report_data)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendance_report_{start_date}_{end_date}.csv"}
        )

    return {
        "period": {"start": start_date, "end": end_date},
        "total_employees": len(employees),
        "report": report_data
    }


@router.get("/live-feed")
async def get_recent_checkins(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recent check-ins for live feed display."""
    today = date.today()

    logs = db.query(AttendanceLog).filter(
        AttendanceLog.date == today
    ).order_by(AttendanceLog.updated_at.desc()).limit(limit).all()

    return {
        "recent": [
            {
                "employee_id": log.employee.employee_id,
                "name": log.employee.name,
                "department": log.employee.department.name if log.employee.department else None,
                "action": "check_out" if log.check_out_time and log.check_out_time == log.updated_at else "check_in",
                "time": (log.check_out_time or log.check_in_time).strftime("%H:%M:%S") if log.check_in_time else None,
                "status": log.status,
                "photo_url": f"/api/employees/{log.employee_id}/image"
            }
            for log in logs
        ]
    }
