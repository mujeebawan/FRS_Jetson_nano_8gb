"""
Person Enrollment Service for Face Recognition Security System.
Handles person registration with proper folder structure and embedding management.
"""

import logging
import cv2
import numpy as np
import os
import shutil
from datetime import datetime
from typing import Optional, List, Tuple
from pathlib import Path
from sqlalchemy.orm import Session
import pickle

from ..config import settings
from ..models.database import Person, FaceEmbedding

logger = logging.getLogger(__name__)


class EnrollmentService:
    """
    Manages person enrollment with organized folder structure.

    Folder structure:
        data/persons/{person_uuid}/
            profile.jpg          # Primary reference image
            images/              # Additional images
            embeddings/          # Cached embeddings
            metadata.json        # Person metadata
    """

    def __init__(self, detector=None, recognizer=None):
        """
        Initialize enrollment service.

        Args:
            detector: FaceDetector instance for face detection
            recognizer: FaceRecognizer instance for embedding extraction
        """
        self.persons_dir = Path("data/persons")
        self.persons_dir.mkdir(parents=True, exist_ok=True)

        self.detector = detector
        self.recognizer = recognizer

        logger.info(f"EnrollmentService initialized. Persons dir: {self.persons_dir}")

    def set_detector(self, detector):
        """Set face detector instance."""
        self.detector = detector

    def set_recognizer(self, recognizer):
        """Set face recognizer instance."""
        self.recognizer = recognizer

    def _get_person_folder(self, person_uuid: str) -> Path:
        """Get or create person's folder."""
        folder = self.persons_dir / person_uuid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "images").mkdir(exist_ok=True)
        (folder / "embeddings").mkdir(exist_ok=True)
        return folder

    def enroll_person(
        self,
        db: Session,
        name: str,
        image: np.ndarray,
        id_number: Optional[str] = None,
        watchlist_status: str = 'normal',
        threat_level: str = 'none',
        criminal_notes: Optional[str] = None,
        guard_prompt: Optional[str] = None
    ) -> Tuple[Optional[Person], str]:
        """
        Enroll a new person with face image.

        Args:
            db: Database session
            name: Person's name
            image: Face image (BGR numpy array)
            id_number: Optional ID (CNIC, passport, etc.)
            watchlist_status: Status category
            threat_level: Threat level
            criminal_notes: Notes for watchlist persons
            guard_prompt: Custom guard prompt

        Returns:
            Tuple of (Person object or None, status message)
        """
        if self.detector is None:
            return None, "Detector not initialized"

        try:
            # Detect face in image
            detections = self.detector.detect_with_embeddings(image)

            if not detections:
                return None, "No face detected in image"

            if len(detections) > 1:
                return None, f"Multiple faces ({len(detections)}) detected. Please provide image with single face."

            detection = detections[0]
            if detection.embedding is None:
                return None, "Failed to extract face embedding"

            # Check for duplicate ID number
            if id_number:
                existing = db.query(Person).filter(Person.id_number == id_number).first()
                if existing:
                    return None, f"Person with ID {id_number} already exists: {existing.name}"

            # Create person record
            person = Person(
                name=name,
                id_number=id_number,
                watchlist_status=watchlist_status,
                threat_level=threat_level,
                criminal_notes=criminal_notes,
                guard_prompt=guard_prompt
            )

            if watchlist_status != 'normal':
                person.added_to_watchlist_at = datetime.utcnow()

            db.add(person)
            db.flush()  # Get UUID

            # Create person folder
            folder = self._get_person_folder(person.uuid)
            person.folder_path = str(folder.relative_to(self.persons_dir))

            # Save reference image
            profile_path = folder / "profile.jpg"
            cv2.imwrite(str(profile_path), image)
            person.reference_image_path = str(profile_path)

            # Save embedding to database
            embedding_blob = pickle.dumps(detection.embedding)
            face_embedding = FaceEmbedding(
                person_id=person.id,
                embedding=embedding_blob,
                source='original',
                source_image_path=str(profile_path),
                confidence=detection.confidence
            )
            db.add(face_embedding)

            # Also save embedding to file for backup
            emb_path = folder / "embeddings" / "original.pkl"
            with open(emb_path, 'wb') as f:
                pickle.dump(detection.embedding, f)

            # Add to recognizer's index if available
            if self.recognizer:
                self.recognizer.add_embedding(person.id, person.name, detection.embedding)

            db.commit()
            db.refresh(person)

            logger.info(f"Person enrolled: {person.name} (UUID: {person.uuid}, Status: {watchlist_status})")
            return person, "Person enrolled successfully"

        except Exception as e:
            logger.error(f"Enrollment failed: {e}")
            db.rollback()
            return None, f"Enrollment failed: {str(e)}"

    def add_face_image(
        self,
        db: Session,
        person_id: int,
        image: np.ndarray,
        source: str = 'additional'
    ) -> Tuple[bool, str]:
        """
        Add additional face image for existing person.

        Args:
            db: Database session
            person_id: Person ID
            image: Face image
            source: Image source type

        Returns:
            Tuple of (success, message)
        """
        if self.detector is None:
            return False, "Detector not initialized"

        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return False, "Person not found"

            # Detect face
            detections = self.detector.detect_with_embeddings(image)
            if not detections:
                return False, "No face detected"

            detection = detections[0]
            if detection.embedding is None:
                return False, "Failed to extract embedding"

            # Save image
            folder = self._get_person_folder(person.uuid)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_path = folder / "images" / f"{source}_{timestamp}.jpg"
            cv2.imwrite(str(img_path), image)

            # Save embedding
            embedding_blob = pickle.dumps(detection.embedding)
            face_embedding = FaceEmbedding(
                person_id=person.id,
                embedding=embedding_blob,
                source=source,
                source_image_path=str(img_path),
                confidence=detection.confidence
            )
            db.add(face_embedding)

            # Update recognizer
            if self.recognizer:
                self.recognizer.add_embedding(person.id, person.name, detection.embedding)

            db.commit()

            logger.info(f"Added face image for {person.name}: {img_path}")
            return True, "Face image added successfully"

        except Exception as e:
            logger.error(f"Failed to add face image: {e}")
            db.rollback()
            return False, f"Failed: {str(e)}"

    def update_person(
        self,
        db: Session,
        person_id: int,
        name: Optional[str] = None,
        watchlist_status: Optional[str] = None,
        threat_level: Optional[str] = None,
        criminal_notes: Optional[str] = None,
        guard_prompt: Optional[str] = None
    ) -> Tuple[Optional[Person], str]:
        """Update person information."""
        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return None, "Person not found"

            if name:
                person.name = name
            if watchlist_status:
                if watchlist_status != 'normal' and person.watchlist_status == 'normal':
                    person.added_to_watchlist_at = datetime.utcnow()
                person.watchlist_status = watchlist_status
            if threat_level:
                person.threat_level = threat_level
            if criminal_notes is not None:
                person.criminal_notes = criminal_notes
            if guard_prompt is not None:
                person.guard_prompt = guard_prompt

            db.commit()
            db.refresh(person)

            # Update recognizer if name changed
            if name and self.recognizer:
                self.recognizer.update_person_name(person.id, name)

            logger.info(f"Person updated: {person.name}")
            return person, "Person updated successfully"

        except Exception as e:
            logger.error(f"Failed to update person: {e}")
            db.rollback()
            return None, f"Failed: {str(e)}"

    def delete_person(self, db: Session, person_id: int) -> Tuple[bool, str]:
        """
        Delete person and all associated data.

        Args:
            db: Database session
            person_id: Person ID

        Returns:
            Tuple of (success, message)
        """
        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return False, "Person not found"

            # Remove folder
            if person.folder_path:
                folder = self.persons_dir / person.folder_path
                if folder.exists():
                    shutil.rmtree(folder)

            # Remove from recognizer
            if self.recognizer:
                self.recognizer.remove_person(person.id)

            # Delete from database (cascade deletes embeddings)
            db.delete(person)
            db.commit()

            logger.info(f"Person deleted: {person.name}")
            return True, "Person deleted successfully"

        except Exception as e:
            logger.error(f"Failed to delete person: {e}")
            db.rollback()
            return False, f"Failed: {str(e)}"

    def get_person(self, db: Session, person_id: int) -> Optional[Person]:
        """Get person by ID."""
        return db.query(Person).filter(Person.id == person_id).first()

    def get_all_persons(
        self,
        db: Session,
        watchlist_only: bool = False,
        limit: int = 100
    ) -> List[Person]:
        """Get all persons, optionally filtered to watchlist."""
        query = db.query(Person)

        if watchlist_only:
            query = query.filter(Person.watchlist_status != 'normal')

        return query.order_by(Person.name).limit(limit).all()

    def get_criminals(self, db: Session, limit: int = 100) -> List[Person]:
        """Get all criminals/watchlist persons."""
        return (
            db.query(Person)
            .filter(Person.watchlist_status.in_(['criminal', 'most_wanted', 'suspect']))
            .order_by(Person.threat_level.desc(), Person.name)
            .limit(limit)
            .all()
        )

    def load_all_embeddings(self, db: Session) -> int:
        """
        Load all embeddings from database into recognizer.

        Returns:
            Number of embeddings loaded
        """
        if self.recognizer is None:
            logger.warning("No recognizer set, cannot load embeddings")
            return 0

        count = 0
        persons = db.query(Person).all()

        for person in persons:
            embeddings = db.query(FaceEmbedding).filter(
                FaceEmbedding.person_id == person.id
            ).all()

            for emb_record in embeddings:
                try:
                    embedding = pickle.loads(emb_record.embedding)
                    self.recognizer.add_embedding(person.id, person.name, embedding)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to load embedding {emb_record.id}: {e}")

        logger.info(f"Loaded {count} embeddings for {len(persons)} persons")
        return count

    def get_person_stats(self, db: Session) -> dict:
        """Get enrollment statistics."""
        total = db.query(Person).count()
        criminals = db.query(Person).filter(
            Person.watchlist_status.in_(['criminal', 'most_wanted'])
        ).count()
        suspects = db.query(Person).filter(Person.watchlist_status == 'suspect').count()
        vips = db.query(Person).filter(Person.watchlist_status == 'vip').count()
        normal = db.query(Person).filter(Person.watchlist_status == 'normal').count()

        return {
            "total_enrolled": total,
            "criminals": criminals,
            "suspects": suspects,
            "vips": vips,
            "normal": normal
        }

    def regenerate_all_embeddings(self, db: Session, model_name: str) -> Tuple[int, int, List[str]]:
        """
        Regenerate embeddings for all persons using the current detector model.
        This is called when switching models to ensure embeddings match the new model.

        Args:
            db: Database session
            model_name: Name of the model being used (for logging)

        Returns:
            Tuple of (success_count, fail_count, error_messages)
        """
        if self.detector is None:
            logger.error("Detector not initialized for embedding regeneration")
            return 0, 0, ["Detector not initialized"]

        if self.recognizer is None:
            logger.error("Recognizer not initialized for embedding regeneration")
            return 0, 0, ["Recognizer not initialized"]

        # Clear current embeddings in recognizer
        self.recognizer._embeddings = []
        self.recognizer._person_ids = []
        self.recognizer._person_names = []
        self.recognizer._faiss_initialized = False
        self.recognizer._index = None

        persons = db.query(Person).all()
        success_count = 0
        fail_count = 0
        errors = []

        logger.info(f"Regenerating embeddings for {len(persons)} persons with model {model_name}")

        for person in persons:
            try:
                # Find reference image
                image_path = None

                # Try reference_image_path first
                if person.reference_image_path and os.path.exists(person.reference_image_path):
                    image_path = person.reference_image_path
                # Try folder structure
                elif person.folder_path:
                    folder = self.persons_dir / person.folder_path
                    profile_path = folder / "profile.jpg"
                    if profile_path.exists():
                        image_path = str(profile_path)
                # Try legacy data/images/person_X.jpg
                else:
                    legacy_path = Path("data/images") / f"person_{person.id}.jpg"
                    if legacy_path.exists():
                        image_path = str(legacy_path)

                if not image_path:
                    errors.append(f"No image found for {person.name} (ID: {person.id})")
                    fail_count += 1
                    continue

                # Load image
                image = cv2.imread(image_path)
                if image is None:
                    errors.append(f"Failed to load image for {person.name}: {image_path}")
                    fail_count += 1
                    continue

                # Detect face and extract embedding
                detections = self.detector.detect_with_embeddings(image)

                if not detections:
                    errors.append(f"No face detected for {person.name}")
                    fail_count += 1
                    continue

                detection = detections[0]
                if detection.embedding is None:
                    errors.append(f"Failed to extract embedding for {person.name}")
                    fail_count += 1
                    continue

                # Add to recognizer
                self.recognizer.add_embedding(person.id, person.name, detection.embedding)
                success_count += 1

                logger.debug(f"Regenerated embedding for {person.name}")

            except Exception as e:
                errors.append(f"Error processing {person.name}: {str(e)}")
                fail_count += 1
                logger.error(f"Failed to regenerate embedding for {person.name}: {e}")

        # Save the new embeddings
        self.recognizer.save()

        logger.info(f"Embedding regeneration complete: {success_count} success, {fail_count} failed")
        return success_count, fail_count, errors
