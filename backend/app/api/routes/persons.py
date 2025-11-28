"""Person management API routes"""

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
from PIL import Image
import io

router = APIRouter()


class PersonCreate(BaseModel):
    name: str


class PersonResponse(BaseModel):
    id: int
    name: str
    embedding_count: int


@router.get("/")
async def list_persons(request: Request) -> List[PersonResponse]:
    """List all enrolled persons."""
    recognizer = request.app.state.recognizer

    # Group by person_id
    persons = {}
    for pid, name in zip(recognizer._person_ids, recognizer._person_names):
        if pid not in persons:
            persons[pid] = {"id": pid, "name": name, "embedding_count": 0}
        persons[pid]["embedding_count"] += 1

    return [PersonResponse(**p) for p in persons.values()]


@router.post("/enroll")
async def enroll_person(
    request: Request,
    name: str,
    image: UploadFile = File(...)
):
    """
    Enroll a new person with face image.

    Args:
        name: Person's name
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

    # Generate new person ID
    existing_ids = set(recognizer._person_ids)
    person_id = max(existing_ids, default=0) + 1

    # Add embedding
    success = recognizer.add_embedding(
        person_id=person_id,
        person_name=name,
        embedding=detection.embedding
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add embedding")

    # Save embeddings
    recognizer.save()

    return {
        "success": True,
        "person_id": person_id,
        "name": name,
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


@router.delete("/{person_id}")
async def delete_person(request: Request, person_id: int):
    """Delete person and all their embeddings."""
    recognizer = request.app.state.recognizer

    if person_id not in recognizer._person_ids:
        raise HTTPException(status_code=404, detail="Person not found")

    success = recognizer.remove_person(person_id)
    if success:
        recognizer.save()

    return {"success": success}


@router.get("/stats")
async def person_stats(request: Request):
    """Get enrollment statistics."""
    recognizer = request.app.state.recognizer
    return {
        "total_embeddings": recognizer.count,
        "total_persons": recognizer.person_count
    }
