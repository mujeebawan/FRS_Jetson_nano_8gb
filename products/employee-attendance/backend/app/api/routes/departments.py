"""
Department management API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ...models.database import Department, Employee, get_db
from ..deps import get_current_active_user, require_admin
from ...models.database import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all departments with employee counts."""
    departments = db.query(Department).order_by(Department.name).all()

    return {
        "departments": [
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "manager_name": d.manager_name,
                "employee_count": len(d.employees),
                "active_employees": len([e for e in d.employees if e.is_active])
            }
            for d in departments
        ]
    }


@router.get("/{dept_id}")
async def get_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get department details."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    return {
        "id": dept.id,
        "name": dept.name,
        "code": dept.code,
        "manager_name": dept.manager_name,
        "employee_count": len(dept.employees),
        "employees": [
            {"id": e.id, "employee_id": e.employee_id, "name": e.name, "position": e.position}
            for e in dept.employees if e.is_active
        ]
    }


@router.post("")
async def create_department(
    name: str,
    code: Optional[str] = None,
    manager_name: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create new department."""
    existing = db.query(Department).filter(Department.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")

    dept = Department(name=name, code=code, manager_name=manager_name)
    db.add(dept)
    db.commit()

    return {"id": dept.id, "name": dept.name, "message": "Department created"}


@router.put("/{dept_id}")
async def update_department(
    dept_id: int,
    name: Optional[str] = None,
    code: Optional[str] = None,
    manager_name: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update department."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    if name:
        dept.name = name
    if code is not None:
        dept.code = code
    if manager_name is not None:
        dept.manager_name = manager_name

    db.commit()
    return {"message": "Department updated"}


@router.delete("/{dept_id}")
async def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete department (employees will have null department)."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Set employees' department to null
    db.query(Employee).filter(Employee.department_id == dept_id).update(
        {"department_id": None}
    )

    db.delete(dept)
    db.commit()

    return {"message": "Department deleted"}
