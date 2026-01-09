"""Person management API routes"""

from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
import numpy as np
from PIL import Image
import io
import json
import shutil
from pathlib import Path

from ...models.database import get_db, Person, FaceEmbedding
from ...config import settings
from ...core.recognizer import FaceRecognizer

router = APIRouter()

# Available model packs
AVAILABLE_MODELS = ["buffalo_s", "buffalo_l"]


def generate_embeddings_for_all_models(
    detector,
    current_recognizer,
    person_id: int,
    person_name: str,
    image,
    current_embedding
):
    """
    Generate embeddings for all available models, not just the current one.
    This ensures the person is enrolled across all models.

    Args:
        detector: Current detector instance
        current_recognizer: Current recognizer instance
        person_id: Person ID
        person_name: Person name
        image: BGR image array
        current_embedding: Embedding from current model (already extracted)
    """
    import os
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)
    current_model = current_recognizer._model_name

    # Add to current recognizer (already done by caller, but save it)
    # current_recognizer.save() is called by caller

    # Generate for other models
    for model in AVAILABLE_MODELS:
        if model == current_model:
            continue  # Skip current model, already handled

        # Check if model exists
        fp16_path = os.path.expanduser(f"~/.insightface/models/{model}_fp16")
        fp32_path = os.path.expanduser(f"~/.insightface/models/{model}")

        if not os.path.exists(fp16_path) and not os.path.exists(fp32_path):
            logger.info(f"Model {model} not available, skipping")
            continue

        try:
            # Load embeddings file for this model
            embeddings_dir = Path(settings.embeddings_dir)
            embeddings_file = embeddings_dir / f"embeddings_{model}.pkl"

            other_recognizer = FaceRecognizer(
                embeddings_dir=str(embeddings_dir),
                threshold=settings.recognition_threshold,
                use_gpu=settings.faiss_use_gpu,
                model_name=model
            )
            other_recognizer.load()

            # Create a temporary detector with the other model
            # Use same settings as main detector
            from ...core.detector import FaceDetector
            model_name = f"{model}_fp16" if os.path.exists(fp16_path) else model

            other_detector = FaceDetector(
                model_name=model_name,
                min_confidence=settings.detection_confidence,  # Same threshold
                use_gpu=True,
                use_fp16=os.path.exists(fp16_path)
            )
            other_detector.initialize()

            # Detect and extract embedding with other model
            detections = other_detector.detect_with_embeddings(image)

            if detections and detections[0].embedding is not None:
                other_recognizer.add_embedding(person_id, person_name, detections[0].embedding)
                other_recognizer.save()
                logger.info(f"Generated embedding for {person_name} with model {model}")
            else:
                logger.warning(f"Could not detect face for {person_name} with model {model}")

            # Clean up
            del other_detector
            del other_recognizer

        except Exception as e:
            logger.error(f"Failed to generate embedding for model {model}: {e}")

# Persons data file for extended info (name, id_card, case) - legacy, now using DB
PERSONS_DATA_FILE = Path("data/persons.json")


def load_persons_data() -> dict:
    """Load persons metadata from JSON file."""
    if PERSONS_DATA_FILE.exists():
        with open(PERSONS_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_persons_data(data: dict):
    """Save persons metadata to JSON file."""
    PERSONS_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PERSONS_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class PersonCreate(BaseModel):
    name: str
    id_card: Optional[str] = None
    case: Optional[str] = None


class PersonResponse(BaseModel):
    id: int
    name: str
    id_card: Optional[str] = None
    case: Optional[str] = None
    embedding_count: int
    watchlist_status: Optional[str] = None
    threat_level: Optional[str] = None
    created_at: Optional[str] = None


class PersonDetailResponse(BaseModel):
    id: int
    name: str
    id_card: Optional[str] = None
    case: Optional[str] = None
    embedding_count: int
    watchlist_status: Optional[str] = None
    threat_level: Optional[str] = None
    guard_prompt: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    detection_count: int = 0
    last_detection: Optional[str] = None
    has_reference_image: bool = False


@router.get("/")
async def list_persons(request: Request, search: str = None) -> List[PersonResponse]:
    """List all enrolled persons from database with optional search."""
    from ...models.database import Alert
    db = next(get_db())
    try:
        # Get all persons from database with embedding counts
        query = db.query(Person)

        # Apply search filter if provided
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Person.name.ilike(search_term)) |
                (Person.id_number.ilike(search_term))
            )

        persons = query.order_by(Person.created_at.desc()).all()

        result = []
        for person in persons:
            # Count embeddings for this person
            embedding_count = db.query(FaceEmbedding).filter(
                FaceEmbedding.person_id == person.id
            ).count()

            result.append(PersonResponse(
                id=person.id,
                name=person.name,
                id_card=person.id_number,
                case=person.criminal_notes,
                embedding_count=embedding_count,
                watchlist_status=person.watchlist_status,
                threat_level=person.threat_level,
                created_at=person.created_at.isoformat() if person.created_at else None
            ))

        return result
    finally:
        db.close()


@router.post("/enroll")
async def enroll_person(
    request: Request,
    name: str = Form(...),
    id_card: str = Form(None),
    case: str = Form(None),
    watchlist_status: str = Form("normal"),
    threat_level: str = Form("none"),
    guard_prompt: str = Form(None),
    image: UploadFile = File(...)
):
    """
    Enroll a new person with face image.

    Args:
        name: Person's name (required)
        id_card: ID card number (optional)
        case: Case information / criminal notes (optional)
        watchlist_status: Status - normal, criminal, suspect, banned, vip (default: normal)
        threat_level: Threat level - none, low, medium, high, critical (default: none)
        guard_prompt: Custom guard action prompt (optional)
        image: Face image file
    """
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer

    # Read and process image
    contents = await image.read()
    pil_image = Image.open(io.BytesIO(contents)).convert('RGB')
    img_array = np.array(pil_image)
    # Convert RGB to BGR for OpenCV
    img_bgr = img_array[:, :, ::-1].copy()

    # Detect face and extract embedding
    detections = detector.detect_with_embeddings(img_bgr)

    if not detections:
        raise HTTPException(status_code=400, detail="No face detected in image")

    if len(detections) > 1:
        raise HTTPException(status_code=400, detail="Multiple faces detected, use single face image")

    detection = detections[0]
    if detection.embedding is None:
        raise HTTPException(status_code=400, detail="Failed to extract face embedding")

    # Save to database
    db = next(get_db())
    try:
        # Create person in database
        db_person = Person(
            name=name,
            id_number=id_card,
            watchlist_status=watchlist_status,
            threat_level=threat_level,
            criminal_notes=case,
            guard_prompt=guard_prompt
        )
        db.add(db_person)
        db.flush()  # Get the ID

        person_id = db_person.id

        # Save reference image
        ref_images_dir = Path(settings.reference_images_dir)
        ref_images_dir.mkdir(parents=True, exist_ok=True)
        ref_image_path = ref_images_dir / f"person_{person_id}.jpg"
        pil_image.save(str(ref_image_path), "JPEG", quality=90)
        db_person.reference_image_path = str(ref_image_path)

        # Store embedding in database as well
        db_embedding = FaceEmbedding(
            person_id=person_id,
            embedding=detection.embedding.tobytes(),
            source='original',
            confidence=detection.confidence
        )
        db.add(db_embedding)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

    # Add embedding to recognizer (in-memory for fast lookup)
    success = recognizer.add_embedding(
        person_id=person_id,
        person_name=name,
        embedding=detection.embedding
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add embedding to recognizer")

    # Save embeddings to file
    recognizer.save()

    # Generate embeddings for other models (in background-like manner)
    # This ensures the person is enrolled in all available models
    generate_embeddings_for_all_models(
        detector=detector,
        current_recognizer=recognizer,
        person_id=person_id,
        person_name=name,
        image=img_bgr,
        current_embedding=detection.embedding
    )

    # Save extended person data (legacy JSON)
    persons_data = load_persons_data()
    persons_data[str(person_id)] = {
        "name": name,
        "id_card": id_card,
        "case": case
    }
    save_persons_data(persons_data)

    return {
        "success": True,
        "person_id": person_id,
        "name": name,
        "id_card": id_card,
        "case": case,
        "watchlist_status": watchlist_status,
        "threat_level": threat_level,
        "confidence": detection.confidence
    }


@router.post("/{person_id}/add-image")
async def add_person_image(
    request: Request,
    person_id: int,
    image: UploadFile = File(...)
):
    """Add additional face image for existing person."""
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer

    # Check person exists
    if person_id not in recognizer._person_ids:
        raise HTTPException(status_code=404, detail="Person not found")

    # Get person name
    idx = recognizer._person_ids.index(person_id)
    name = recognizer._person_names[idx]

    # Process image
    contents = await image.read()
    pil_image = Image.open(io.BytesIO(contents)).convert('RGB')
    img_array = np.array(pil_image)
    img_bgr = img_array[:, :, ::-1].copy()

    detections = detector.detect_with_embeddings(img_bgr)

    if not detections or detections[0].embedding is None:
        raise HTTPException(status_code=400, detail="No face detected")

    recognizer.add_embedding(person_id, name, detections[0].embedding)
    recognizer.save()

    return {"success": True, "message": f"Added image for {name}"}


def remove_person_from_all_models(person_id: int, current_recognizer):
    """
    Remove a person's embeddings from all model-specific embedding files.

    Args:
        person_id: Person ID to remove
        current_recognizer: Current recognizer instance
    """
    import os
    import logging
    from pathlib import Path

    logger = logging.getLogger(__name__)
    current_model = current_recognizer._model_name

    # Remove from other models
    for model in AVAILABLE_MODELS:
        if model == current_model:
            continue  # Current model handled separately

        try:
            embeddings_dir = Path(settings.embeddings_dir)
            embeddings_file = embeddings_dir / f"embeddings_{model}.pkl"

            if not embeddings_file.exists():
                continue

            # Load recognizer for this model
            other_recognizer = FaceRecognizer(
                embeddings_dir=str(embeddings_dir),
                threshold=settings.recognition_threshold,
                use_gpu=settings.faiss_use_gpu,
                model_name=model
            )
            other_recognizer.load()

            # Remove person if exists
            if person_id in other_recognizer._person_ids:
                other_recognizer.remove_person(person_id)
                other_recognizer.save()
                logger.info(f"Removed person {person_id} from model {model}")

            del other_recognizer

        except Exception as e:
            logger.error(f"Failed to remove person {person_id} from model {model}: {e}")


@router.delete("/{person_id}")
async def delete_person(request: Request, person_id: int):
    """Delete person and all their embeddings from DB and ALL model recognizers."""
    recognizer = request.app.state.recognizer

    # Delete from database first
    db = next(get_db())
    try:
        # Delete embeddings
        db.query(FaceEmbedding).filter(FaceEmbedding.person_id == person_id).delete()

        # Delete person record
        person = db.query(Person).filter(Person.id == person_id).first()
        if person:
            # Delete reference image file if exists
            if person.reference_image_path:
                ref_image = Path(person.reference_image_path)
                if ref_image.exists():
                    ref_image.unlink()
            db.delete(person)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

    # Remove from current in-memory recognizer
    if person_id in recognizer._person_ids:
        success = recognizer.remove_person(person_id)
        if success:
            recognizer.save()
    else:
        success = True  # Already not in memory

    # Remove from ALL other models' embedding files
    remove_person_from_all_models(person_id, recognizer)

    # Remove from legacy JSON
    persons_data = load_persons_data()
    if str(person_id) in persons_data:
        del persons_data[str(person_id)]
        save_persons_data(persons_data)

    return {"success": success, "message": f"Person {person_id} deleted from database and all model recognizers"}


@router.post("/enroll-from-camera")
async def enroll_from_camera(
    request: Request,
    name: str,
    id_card: str = None,
    case: str = None,
    watchlist_status: str = "normal",
    threat_level: str = "none",
    guard_prompt: str = None,
    camera_id: int = None
):
    """
    Enroll a new person by capturing from live camera stream.

    Args:
        name: Person's name (required)
        id_card: ID card number (optional)
        case: Case information / criminal notes (optional)
        watchlist_status: Status - normal, criminal, suspect, banned, vip (default: normal)
        threat_level: Threat level - none, low, medium, high, critical (default: none)
        guard_prompt: Custom guard action prompt (optional)
        camera_id: ID of camera to capture from (optional, default uses first camera)
    """
    stream = request.app.state.stream
    detector = request.app.state.detector
    recognizer = request.app.state.recognizer

    if not stream.is_running:
        raise HTTPException(status_code=400, detail="Stream not running. Start stream first.")

    # Get frame from specific camera or default to first camera
    if camera_id is not None:
        # Get camera index from database ID
        camera_index = stream.get_camera_index_by_id(camera_id)
        if camera_index is None:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        frame_data = stream.get_camera_raw_frame(camera_index)
        if frame_data is None:
            raise HTTPException(status_code=400, detail=f"No frame available from camera {camera_id}")
    else:
        # Default: use first camera (index 0)
        frame_data = stream.get_camera_raw_frame(0)
        if frame_data is None:
            # Fallback to full frame
            frame_data = stream.get_latest_raw_frame()
    if frame_data is None:
        raise HTTPException(status_code=400, detail="No frame available")

    # Detect face and extract embedding
    detections = detector.detect_with_embeddings(frame_data.frame)

    if not detections:
        raise HTTPException(status_code=400, detail="No face detected in frame. Please position face in camera view.")

    if len(detections) > 1:
        raise HTTPException(status_code=400, detail=f"Multiple faces ({len(detections)}) detected. Only one person should be in frame.")

    detection = detections[0]
    if detection.embedding is None:
        raise HTTPException(status_code=400, detail="Failed to extract face embedding")

    # Prepare reference image BEFORE database operations
    import cv2
    ref_images_dir = Path(settings.reference_images_dir)
    ref_images_dir.mkdir(parents=True, exist_ok=True)

    # Crop face region with padding for reference image
    # bbox is (x, y, w, h) format from detector
    bx, by, bw, bh = detection.bbox
    frame_h, frame_w = frame_data.frame.shape[:2]
    pad = 50  # padding around face
    x1 = max(0, int(bx) - pad)
    y1 = max(0, int(by) - pad)
    x2 = min(frame_w, int(bx + bw) + pad)
    y2 = min(frame_h, int(by + bh) + pad)
    face_crop = frame_data.frame[y1:y2, x1:x2]

    if face_crop.size == 0:
        raise HTTPException(status_code=400, detail="Failed to crop face region from frame")

    # Save to database
    db = next(get_db())
    try:
        # Create person in database
        db_person = Person(
            name=name,
            id_number=id_card,
            watchlist_status=watchlist_status,
            threat_level=threat_level,
            criminal_notes=case,
            guard_prompt=guard_prompt
        )
        db.add(db_person)
        db.flush()

        person_id = db_person.id

        # Save reference image
        ref_image_path = ref_images_dir / f"person_{person_id}.jpg"
        success = cv2.imwrite(str(ref_image_path), face_crop)
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to save reference image")

        db_person.reference_image_path = str(ref_image_path)

        # Store embedding in database
        db_embedding = FaceEmbedding(
            person_id=person_id,
            embedding=detection.embedding.tobytes(),
            source='camera_capture',
            confidence=detection.confidence
        )
        db.add(db_embedding)
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

    # Add embedding to recognizer
    success = recognizer.add_embedding(
        person_id=person_id,
        person_name=name,
        embedding=detection.embedding
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add embedding")

    # Save embeddings
    recognizer.save()

    # Generate embeddings for other models
    # Use the full frame for better detection with other models
    generate_embeddings_for_all_models(
        detector=detector,
        current_recognizer=recognizer,
        person_id=person_id,
        person_name=name,
        image=frame_data.frame,
        current_embedding=detection.embedding
    )

    # Save extended person data (legacy)
    persons_data = load_persons_data()
    persons_data[str(person_id)] = {
        "name": name,
        "id_card": id_card,
        "case": case
    }
    save_persons_data(persons_data)

    return {
        "success": True,
        "person_id": person_id,
        "name": name,
        "id_card": id_card,
        "case": case,
        "watchlist_status": watchlist_status,
        "threat_level": threat_level,
        "confidence": float(detection.confidence),
        "bbox": [int(v) for v in detection.bbox]
    }


@router.get("/stats")
async def person_stats(request: Request):
    """Get enrollment statistics."""
    recognizer = request.app.state.recognizer
    return {
        "total_embeddings": recognizer.count,
        "total_persons": recognizer.person_count
    }


@router.get("/{person_id}/image")
async def get_person_image(person_id: int):
    """Get the reference image for a person."""
    from fastapi.responses import Response
    db = next(get_db())
    try:
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        if not person.reference_image_path:
            raise HTTPException(status_code=404, detail="No reference image available")

        image_path = Path(person.reference_image_path)
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")

        # Read image and return with no-cache headers
        with open(image_path, 'rb') as f:
            image_data = f.read()

        return Response(
            content=image_data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    finally:
        db.close()


@router.get("/{person_id}/details")
async def get_person_details(person_id: int) -> PersonDetailResponse:
    """Get detailed information about a person including detection stats."""
    from ...models.database import Alert
    from sqlalchemy import func

    db = next(get_db())
    try:
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        # Count embeddings
        embedding_count = db.query(FaceEmbedding).filter(
            FaceEmbedding.person_id == person_id
        ).count()

        # Count detections (alerts for this person)
        detection_count = db.query(Alert).filter(
            Alert.person_id == person_id
        ).count()

        # Get last detection
        last_alert = db.query(Alert).filter(
            Alert.person_id == person_id
        ).order_by(Alert.timestamp.desc()).first()

        last_detection = last_alert.timestamp.isoformat() if last_alert else None

        # Check if reference image exists
        has_image = False
        if person.reference_image_path:
            has_image = Path(person.reference_image_path).exists()

        return PersonDetailResponse(
            id=person.id,
            name=person.name,
            id_card=person.id_number,
            case=person.criminal_notes,
            embedding_count=embedding_count,
            watchlist_status=person.watchlist_status,
            threat_level=person.threat_level,
            guard_prompt=person.guard_prompt,
            created_at=person.created_at.isoformat() if person.created_at else None,
            updated_at=person.updated_at.isoformat() if person.updated_at else None,
            detection_count=detection_count,
            last_detection=last_detection,
            has_reference_image=has_image
        )
    finally:
        db.close()
