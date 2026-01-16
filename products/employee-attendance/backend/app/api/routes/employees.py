"""
Employee management API routes.
Handles CRUD operations for employees and face enrollment.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date, time
import os
import uuid
import shutil
import logging

from ...models.database import Employee, Department, FaceEmbedding, AttendanceLog, get_db
from ...config import settings
from ..deps import get_current_active_user, require_admin
from ...models.database import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def list_employees(
    department_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all employees with optional filters."""
    query = db.query(Employee)

    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Employee.name.ilike(search_term)) |
            (Employee.employee_id.ilike(search_term)) |
            (Employee.email.ilike(search_term))
        )

    total = query.count()
    employees = query.order_by(Employee.name).offset(skip).limit(limit).all()

    return {
        "total": total,
        "employees": [
            {
                "id": e.id,
                "employee_id": e.employee_id,
                "name": e.name,
                "email": e.email,
                "phone": e.phone,
                "department_id": e.department_id,
                "department_name": e.department.name if e.department else None,
                "position": e.position,
                "shift_start": e.shift_start.strftime("%H:%M") if e.shift_start else "09:00",
                "shift_end": e.shift_end.strftime("%H:%M") if e.shift_end else "18:00",
                "is_active": e.is_active,
                "has_face": len(e.embeddings) > 0,
                "reference_image_path": e.reference_image_path,
                "join_date": e.join_date.isoformat() if e.join_date else None,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in employees
        ]
    }


@router.get("/{employee_id}")
async def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get single employee by ID."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Get today's attendance
    today = date.today()
    today_attendance = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == employee_id,
        AttendanceLog.date == today
    ).first()

    return {
        "id": employee.id,
        "uuid": employee.uuid,
        "employee_id": employee.employee_id,
        "name": employee.name,
        "email": employee.email,
        "phone": employee.phone,
        "department_id": employee.department_id,
        "department_name": employee.department.name if employee.department else None,
        "position": employee.position,
        "shift_start": employee.shift_start.strftime("%H:%M") if employee.shift_start else "09:00",
        "shift_end": employee.shift_end.strftime("%H:%M") if employee.shift_end else "18:00",
        "is_active": employee.is_active,
        "has_face": len(employee.embeddings) > 0,
        "embedding_count": len(employee.embeddings),
        "reference_image_path": employee.reference_image_path,
        "join_date": employee.join_date.isoformat() if employee.join_date else None,
        "created_at": employee.created_at.isoformat() if employee.created_at else None,
        "today_attendance": {
            "status": today_attendance.status if today_attendance else "absent",
            "check_in": today_attendance.check_in_time.isoformat() if today_attendance and today_attendance.check_in_time else None,
            "check_out": today_attendance.check_out_time.isoformat() if today_attendance and today_attendance.check_out_time else None,
        } if today_attendance else None
    }


@router.post("")
async def create_employee(
    employee_id: str = Form(...),
    name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    position: Optional[str] = Form(None),
    shift_start: Optional[str] = Form("09:00"),
    shift_end: Optional[str] = Form("18:00"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create new employee with optional face enrollment."""
    # Check if employee_id already exists
    existing = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    # Parse shift times
    try:
        start_time = time.fromisoformat(shift_start) if shift_start else time(9, 0)
        end_time = time.fromisoformat(shift_end) if shift_end else time(18, 0)
    except ValueError:
        start_time = time(9, 0)
        end_time = time(18, 0)

    # Create employee
    employee = Employee(
        employee_id=employee_id,
        name=name,
        email=email,
        phone=phone,
        department_id=department_id,
        position=position,
        shift_start=start_time,
        shift_end=end_time,
        is_active=True,
        join_date=date.today()
    )
    db.add(employee)
    db.flush()  # Get ID

    # Handle image upload and face enrollment
    if image and image.filename:
        try:
            # Create employee folder
            employee_folder = os.path.join(settings.reference_images_dir, str(employee.id))
            os.makedirs(employee_folder, exist_ok=True)

            # Save image
            image_path = os.path.join(employee_folder, f"reference_{uuid.uuid4().hex[:8]}.jpg")
            with open(image_path, "wb") as f:
                content = await image.read()
                f.write(content)

            employee.reference_image_path = image_path
            employee.folder_path = employee_folder

            # Try to extract face embedding using detector
            try:
                import cv2
                from ...main import app

                # Load image
                img = cv2.imread(image_path)
                if img is not None:
                    # Use app's detector to get face embedding
                    detector = app.state.detector
                    detections = detector.detect_with_embeddings(img)

                    if detections and detections[0].embedding is not None:
                        face_embedding = FaceEmbedding(
                            employee_id=employee.id,
                            embedding=detections[0].embedding.tobytes(),
                            source="enrollment",
                            source_image_path=image_path,
                            confidence=detections[0].confidence
                        )
                        db.add(face_embedding)
                        logger.info(f"Face enrolled for employee {employee_id} with confidence {detections[0].confidence:.2f}")

                        # Reload recognizer to include new embedding
                        recognizer = app.state.recognizer
                        recognizer.add_embedding(
                            detections[0].embedding,
                            employee.id,
                            employee.name
                        )
                    else:
                        logger.warning(f"No face detected in uploaded image for {employee_id}")
                else:
                    logger.warning(f"Could not load image: {image_path}")
            except Exception as e:
                logger.warning(f"Could not extract face embedding: {e}")

        except Exception as e:
            logger.error(f"Error saving employee image: {e}")

    db.commit()

    return {
        "id": employee.id,
        "employee_id": employee.employee_id,
        "name": employee.name,
        "message": "Employee created successfully"
    }


@router.put("/{employee_id}")
async def update_employee(
    employee_id: int,
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    position: Optional[str] = Form(None),
    shift_start: Optional[str] = Form(None),
    shift_end: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update employee details."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Update fields
    if name is not None:
        employee.name = name
    if email is not None:
        employee.email = email
    if phone is not None:
        employee.phone = phone
    if department_id is not None:
        employee.department_id = department_id
    if position is not None:
        employee.position = position
    if is_active is not None:
        employee.is_active = is_active

    if shift_start:
        try:
            employee.shift_start = time.fromisoformat(shift_start)
        except ValueError:
            pass
    if shift_end:
        try:
            employee.shift_end = time.fromisoformat(shift_end)
        except ValueError:
            pass

    # Handle new image
    if image and image.filename:
        try:
            employee_folder = os.path.join(settings.reference_images_dir, str(employee.id))
            os.makedirs(employee_folder, exist_ok=True)

            image_path = os.path.join(employee_folder, f"reference_{uuid.uuid4().hex[:8]}.jpg")
            with open(image_path, "wb") as f:
                content = await image.read()
                f.write(content)

            employee.reference_image_path = image_path

            # Re-enroll face using detector
            try:
                import cv2
                from ...main import app

                img = cv2.imread(image_path)
                if img is not None:
                    detector = app.state.detector
                    detections = detector.detect_with_embeddings(img)

                    if detections and detections[0].embedding is not None:
                        # Remove old embeddings from DB and recognizer
                        db.query(FaceEmbedding).filter(FaceEmbedding.employee_id == employee.id).delete()

                        # Add new embedding
                        face_embedding = FaceEmbedding(
                            employee_id=employee.id,
                            embedding=detections[0].embedding.tobytes(),
                            source="enrollment",
                            source_image_path=image_path,
                            confidence=detections[0].confidence
                        )
                        db.add(face_embedding)

                        # Update recognizer
                        recognizer = app.state.recognizer
                        recognizer.remove_person(employee.id)
                        recognizer.add_embedding(
                            detections[0].embedding,
                            employee.id,
                            employee.name
                        )
                        logger.info(f"Face re-enrolled for employee {employee.employee_id}")
                    else:
                        logger.warning(f"No face detected in updated image")
            except Exception as e:
                logger.warning(f"Could not extract face embedding: {e}")

        except Exception as e:
            logger.error(f"Error updating employee image: {e}")

    db.commit()

    return {"message": "Employee updated successfully", "id": employee.id}


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete employee and their data."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Delete employee folder
    if employee.folder_path and os.path.exists(employee.folder_path):
        try:
            shutil.rmtree(employee.folder_path)
        except Exception as e:
            logger.error(f"Error deleting employee folder: {e}")

    db.delete(employee)
    db.commit()

    return {"message": "Employee deleted successfully"}


@router.get("/{employee_id}/image")
async def get_employee_image(
    employee_id: int,
    db: Session = Depends(get_db)
):
    """Get employee reference image."""
    from fastapi.responses import FileResponse

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.reference_image_path:
        raise HTTPException(status_code=404, detail="Image not found")

    if not os.path.exists(employee.reference_image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(employee.reference_image_path, media_type="image/jpeg")


@router.post("/enroll-from-camera")
async def enroll_from_camera(
    employee_id: str = Form(...),
    name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    position: Optional[str] = Form(None),
    shift_start: Optional[str] = Form("09:00"),
    shift_end: Optional[str] = Form("18:00"),
    camera_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create employee with face captured from camera."""
    from fastapi import Request
    import numpy as np

    # Check if employee_id already exists
    existing = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    # Get current frame from stream
    from ...main import app
    stream = app.state.stream

    if not stream.is_running:
        raise HTTPException(status_code=400, detail="Stream not running. Start the stream first.")

    # Get raw frame (without overlays) for enrollment
    if camera_id:
        camera_index = stream.get_camera_index_by_id(camera_id)
        if camera_index is None:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        frame_data = stream.get_camera_raw_frame(camera_index)
    else:
        frame_data = stream.get_latest_raw_frame()

    if frame_data is None or frame_data.frame is None:
        raise HTTPException(status_code=400, detail="No frame available from camera")

    frame = frame_data.frame

    # Detect face and get embedding
    detector = app.state.detector
    recognizer = app.state.recognizer

    detections = detector.detect_with_embeddings(frame)
    if not detections:
        raise HTTPException(status_code=400, detail="No face detected in frame. Please position face clearly.")

    # Use the largest face (closest to camera)
    best_det = max(detections, key=lambda d: d.bbox[2] * d.bbox[3])

    if best_det.embedding is None:
        raise HTTPException(status_code=400, detail="Could not extract face embedding. Try again.")

    # Parse shift times
    try:
        start_time = time.fromisoformat(shift_start) if shift_start else time(9, 0)
        end_time = time.fromisoformat(shift_end) if shift_end else time(18, 0)
    except ValueError:
        start_time = time(9, 0)
        end_time = time(18, 0)

    # Create employee
    employee = Employee(
        employee_id=employee_id,
        name=name,
        email=email,
        phone=phone,
        department_id=department_id,
        position=position,
        shift_start=start_time,
        shift_end=end_time,
        is_active=True,
        join_date=date.today()
    )
    db.add(employee)
    db.flush()

    # Save captured face image
    import cv2
    employee_folder = os.path.join(settings.reference_images_dir, str(employee.id))
    os.makedirs(employee_folder, exist_ok=True)

    # Crop face with padding
    x, y, w, h = best_det.bbox
    padding = 50
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(frame.shape[1], x + w + padding)
    y2 = min(frame.shape[0], y + h + padding)
    face_crop = frame[y1:y2, x1:x2]

    image_path = os.path.join(employee_folder, f"reference_{uuid.uuid4().hex[:8]}.jpg")
    cv2.imwrite(image_path, face_crop)

    employee.reference_image_path = image_path
    employee.folder_path = employee_folder

    # Save embedding
    face_embedding = FaceEmbedding(
        employee_id=employee.id,
        embedding=best_det.embedding.tobytes(),
        source="camera_enrollment",
        source_image_path=image_path,
        confidence=best_det.confidence
    )
    db.add(face_embedding)

    db.commit()

    # Reload recognizer to include new employee
    recognizer.load()

    logger.info(f"Employee {employee_id} enrolled from camera with face embedding")

    return {
        "id": employee.id,
        "employee_id": employee.employee_id,
        "name": employee.name,
        "message": "Employee enrolled from camera successfully",
        "face_confidence": best_det.confidence
    }


@router.get("/{employee_id}/attendance")
async def get_employee_attendance(
    employee_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get attendance history for an employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    query = db.query(AttendanceLog).filter(AttendanceLog.employee_id == employee_id)

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

    logs = query.order_by(AttendanceLog.date.desc()).limit(30).all()

    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.name,
        "attendance": [
            {
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
