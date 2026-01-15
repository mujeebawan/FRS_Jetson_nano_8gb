"""
Dashboard API routes.
Provides statistics and real-time data for the attendance dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta
import logging

from ...models.database import Employee, AttendanceLog, Department, get_db
from ..deps import get_current_active_user
from ...models.database import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get dashboard statistics."""
    today = date.today()
    now = datetime.now()

    # Total active employees
    total_employees = db.query(Employee).filter(Employee.is_active == True).count()

    # Today's attendance
    today_logs = db.query(AttendanceLog).filter(AttendanceLog.date == today).all()

    present_count = len(today_logs)
    late_count = len([l for l in today_logs if l.status == "late"])
    checked_out_count = len([l for l in today_logs if l.check_out_time])
    absent_count = total_employees - present_count

    # This week stats
    week_start = today - timedelta(days=today.weekday())
    week_logs = db.query(AttendanceLog).filter(
        AttendanceLog.date >= week_start,
        AttendanceLog.date <= today
    ).all()

    week_present = len(set(l.employee_id for l in week_logs))
    week_late_total = len([l for l in week_logs if l.status == "late"])

    # Average work hours this week
    work_hours = [l.work_hours for l in week_logs if l.work_hours]
    avg_work_hours = round(sum(work_hours) / len(work_hours), 1) if work_hours else 0

    # Department breakdown
    departments = db.query(Department).all()
    dept_stats = []
    for dept in departments:
        dept_employees = [e.id for e in dept.employees if e.is_active]
        dept_present = len([l for l in today_logs if l.employee_id in dept_employees])
        dept_stats.append({
            "name": dept.name,
            "code": dept.code,
            "total": len(dept_employees),
            "present": dept_present,
            "absent": len(dept_employees) - dept_present
        })

    return {
        "timestamp": now.isoformat(),
        "today": {
            "date": today.isoformat(),
            "total_employees": total_employees,
            "present": present_count,
            "late": late_count,
            "absent": absent_count,
            "checked_out": checked_out_count,
            "attendance_rate": round((present_count / max(1, total_employees)) * 100, 1)
        },
        "week": {
            "start_date": week_start.isoformat(),
            "employees_attended": week_present,
            "total_late_arrivals": week_late_total,
            "average_work_hours": avg_work_hours
        },
        "departments": sorted(dept_stats, key=lambda x: x["present"], reverse=True)
    }


@router.get("/present")
async def get_present_employees(
    department_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of currently present employees."""
    today = date.today()

    query = db.query(AttendanceLog).join(Employee).filter(
        AttendanceLog.date == today,
        AttendanceLog.check_in_time.isnot(None)
    )

    if department_id:
        query = query.filter(Employee.department_id == department_id)

    logs = query.all()

    # Split into still present and checked out
    still_present = []
    checked_out = []

    for log in logs:
        emp_data = {
            "id": log.employee.id,
            "employee_id": log.employee.employee_id,
            "name": log.employee.name,
            "department": log.employee.department.name if log.employee.department else None,
            "position": log.employee.position,
            "check_in": log.check_in_time.strftime("%H:%M") if log.check_in_time else None,
            "check_out": log.check_out_time.strftime("%H:%M") if log.check_out_time else None,
            "status": log.status,
            "work_hours": log.work_hours,
            "photo_url": f"/api/employees/{log.employee.id}/image"
        }

        if log.check_out_time:
            checked_out.append(emp_data)
        else:
            still_present.append(emp_data)

    return {
        "date": today.isoformat(),
        "still_present": {
            "count": len(still_present),
            "employees": still_present
        },
        "checked_out": {
            "count": len(checked_out),
            "employees": checked_out
        }
    }


@router.get("/late")
async def get_late_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get today's late arrivals."""
    today = date.today()

    logs = db.query(AttendanceLog).join(Employee).filter(
        AttendanceLog.date == today,
        AttendanceLog.status == "late"
    ).order_by(AttendanceLog.late_minutes.desc()).all()

    return {
        "date": today.isoformat(),
        "count": len(logs),
        "employees": [
            {
                "id": log.employee.id,
                "employee_id": log.employee.employee_id,
                "name": log.employee.name,
                "department": log.employee.department.name if log.employee.department else None,
                "check_in": log.check_in_time.strftime("%H:%M") if log.check_in_time else None,
                "late_minutes": log.late_minutes,
                "expected_time": log.employee.shift_start.strftime("%H:%M") if log.employee.shift_start else "09:00"
            }
            for log in logs
        ]
    }


@router.get("/absent")
async def get_absent_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get today's absent employees."""
    today = date.today()

    # Get all active employees
    all_employees = db.query(Employee).filter(Employee.is_active == True).all()

    # Get employees who checked in today
    present_ids = db.query(AttendanceLog.employee_id).filter(
        AttendanceLog.date == today
    ).all()
    present_ids = [p[0] for p in present_ids]

    # Absent = all - present
    absent = [e for e in all_employees if e.id not in present_ids]

    return {
        "date": today.isoformat(),
        "count": len(absent),
        "employees": [
            {
                "id": e.id,
                "employee_id": e.employee_id,
                "name": e.name,
                "department": e.department.name if e.department else None,
                "position": e.position,
                "expected_time": e.shift_start.strftime("%H:%M") if e.shift_start else "09:00"
            }
            for e in absent
        ]
    }


@router.get("/activity")
async def get_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get recent attendance activity for live feed."""
    today = date.today()

    # Get recent logs from today, ordered by last update
    logs = db.query(AttendanceLog).join(Employee).filter(
        AttendanceLog.date == today
    ).order_by(AttendanceLog.updated_at.desc()).limit(limit).all()

    activities = []
    for log in logs:
        # Determine if this was a check-in or check-out based on times
        if log.check_out_time:
            activities.append({
                "type": "check_out",
                "employee_id": log.employee.employee_id,
                "name": log.employee.name,
                "department": log.employee.department.name if log.employee.department else None,
                "time": log.check_out_time.strftime("%H:%M:%S"),
                "timestamp": log.check_out_time.isoformat(),
                "work_hours": log.work_hours
            })

        if log.check_in_time:
            activities.append({
                "type": "check_in",
                "employee_id": log.employee.employee_id,
                "name": log.employee.name,
                "department": log.employee.department.name if log.employee.department else None,
                "time": log.check_in_time.strftime("%H:%M:%S"),
                "timestamp": log.check_in_time.isoformat(),
                "status": log.status,
                "late_minutes": log.late_minutes if log.status == "late" else None
            })

    # Sort by timestamp descending
    activities.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "activities": activities[:limit]
    }
