"""
Alert Manager for Face Recognition Security System.
Handles criminal detection alerts, guard prompts, and notifications.
"""

import logging
import cv2
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
from sqlalchemy.orm import Session

from ..config import settings
from ..models.database import Alert, Person

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages security alerts for criminal/person detection.
    Organizes snapshots in date-wise folders.
    """

    def __init__(self):
        """Initialize alert manager."""
        self.alerts_dir = Path(settings.snapshots_dir)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

        # Cooldown tracking to prevent alert spam
        self._last_alert_times: Dict[str, datetime] = {}
        self._cooldown_seconds = settings.alert_cooldown_seconds

        # Alert configuration - read dynamically from settings
        self.save_snapshot = settings.alert_save_snapshot

        logger.info(f"AlertManager initialized. Snapshots dir: {self.alerts_dir}")

    def _get_date_folder(self) -> Path:
        """Get or create today's date folder for snapshots."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_folder = self.alerts_dir / date_str
        date_folder.mkdir(parents=True, exist_ok=True)
        return date_folder

    def _check_cooldown(self, person_id: Optional[int], event_type: str) -> bool:
        """
        Check if enough time has passed since last alert for this person/event.

        Returns:
            True if alert should proceed, False if in cooldown
        """
        cooldown_key = f"{event_type}_{person_id}" if person_id else f"{event_type}_unknown"
        last_time = self._last_alert_times.get(cooldown_key)

        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self._cooldown_seconds:
                logger.debug(f"Alert cooldown active: {cooldown_key} ({elapsed:.1f}s < {self._cooldown_seconds}s)")
                return False

        # Update last alert time
        self._last_alert_times[cooldown_key] = datetime.now()
        return True

    def save_alert_snapshot(
        self,
        frame,
        alert_id: int,
        bbox: Optional[tuple] = None,
        person_name: Optional[str] = None,
        threat_level: Optional[str] = None
    ) -> Optional[str]:
        """
        Save full frame snapshot with face highlighted for alert.

        Structure: data/snapshots/{YYYY-MM-DD}/alert_{id}_{HHMMSS}.jpg

        Args:
            frame: OpenCV frame (BGR numpy array)
            alert_id: Alert database ID
            bbox: Face bounding box (x, y, width, height) to highlight
            person_name: Name to display on the box
            threat_level: Threat level for color coding

        Returns:
            Path to saved snapshot, or None if failed
        """
        if frame is None:
            return None

        try:
            # Make a copy to draw on
            annotated_frame = frame.copy()

            # Draw face highlight box if bbox provided
            if bbox is not None:
                x, y, w, h = bbox

                # Color based on threat level (BGR format)
                if threat_level == 'critical':
                    color = (0, 0, 255)  # Red
                    thickness = 4
                elif threat_level == 'high':
                    color = (0, 128, 255)  # Orange
                    thickness = 3
                elif threat_level in ['medium', 'low']:
                    color = (0, 255, 255)  # Yellow
                    thickness = 2
                else:
                    color = (0, 255, 0)  # Green for unknown/normal
                    thickness = 2

                # Draw rectangle around face
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, thickness)

                # Draw label background and text
                label = person_name or "Unknown"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.8
                label_thickness = 2

                # Get text size for background
                (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, label_thickness)

                # Draw filled rectangle behind text
                label_y = max(y - 10, text_h + 10)
                cv2.rectangle(
                    annotated_frame,
                    (x, label_y - text_h - 5),
                    (x + text_w + 10, label_y + 5),
                    color,
                    -1  # Filled
                )

                # Draw text
                cv2.putText(
                    annotated_frame,
                    label,
                    (x + 5, label_y),
                    font,
                    font_scale,
                    (255, 255, 255),  # White text
                    label_thickness
                )

            date_folder = self._get_date_folder()
            time_str = datetime.now().strftime("%H%M%S")
            filename = f"alert_{alert_id}_{time_str}.jpg"
            filepath = date_folder / filename

            cv2.imwrite(str(filepath), annotated_frame)
            logger.info(f"Alert snapshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save alert snapshot: {e}")
            return None

    def generate_guard_prompt(self, person: Person) -> str:
        """
        Generate action prompt for security guard based on person's status.

        Args:
            person: Person database object

        Returns:
            Guard action prompt string
        """
        if person.guard_prompt:
            return person.guard_prompt

        # Generate default prompt based on status
        status = person.watchlist_status
        threat = person.threat_level
        name = person.name

        if status == 'criminal' or status == 'most_wanted':
            if threat == 'critical':
                return f"CRITICAL ALERT: {name} detected. DO NOT APPROACH. Call police immediately: 15. Secure all exits."
            elif threat == 'high':
                return f"HIGH ALERT: {name} detected. Exercise extreme caution. Notify supervisor and call authorities: 15."
            else:
                return f"ALERT: Criminal {name} detected. Notify security supervisor immediately."

        elif status == 'suspect':
            return f"SUSPECT ALERT: {name} detected. Monitor closely and report to supervisor. Do not confront."

        elif status == 'person_of_interest':
            return f"NOTICE: Person of interest {name} detected. Log sighting and continue monitoring."

        elif status == 'banned':
            return f"ACCESS DENIED: {name} is banned from premises. Escort out immediately and document incident."

        elif status == 'vip':
            return f"VIP ALERT: {name} detected. Notify management. Ensure premium service."

        else:
            return f"Person detected: {name}"

    def should_create_alert(
        self,
        person: Optional[Person],
        confidence: float,
        event_type: str
    ) -> bool:
        """
        Determine if an alert should be created based on configuration.

        Args:
            person: Person object if matched, None if unknown
            confidence: Recognition confidence
            event_type: Type of event

        Returns:
            True if alert should be created
        """
        # Check cooldown
        person_id = person.id if person else None
        if not self._check_cooldown(person_id, event_type):
            logger.debug(f"Alert skipped (cooldown): person_id={person_id}")
            return False

        # Check configuration - read dynamically from settings
        if person is None:
            # Unknown person - no alert (we only care about known persons)
            logger.debug(f"Alert skipped (unknown person): alert_on_unknown={settings.alert_on_unknown}")
            return settings.alert_on_unknown

        # Known person - check their status
        status = person.watchlist_status
        logger.info(f"Checking alert for {person.name}: status={status}, threat={person.threat_level}")

        # Only alert on watchlist persons (criminal, suspect, banned, etc.)
        # NOT on normal persons - we only want criminal detection alerts
        if status in ['criminal', 'most_wanted', 'suspect', 'person_of_interest', 'banned']:
            logger.info(f"Alert APPROVED for {person.name} (watchlist: {status})")
            return True

        # VIP alerts (optional, controlled by config)
        if status == 'vip' and settings.alert_on_known:
            logger.info(f"Alert APPROVED for VIP {person.name}")
            return True

        # Normal persons - NO alert (this is a security system for criminals)
        logger.debug(f"Alert skipped (normal person): {person.name}")
        return False

    def create_alert(
        self,
        db: Session,
        event_type: str,
        person: Optional[Person] = None,
        confidence: Optional[float] = None,
        similarity_score: Optional[float] = None,
        frame=None,
        bbox: Optional[tuple] = None
    ) -> Optional[Alert]:
        """
        Create and save alert to database.

        Args:
            db: Database session
            event_type: Type of event
            person: Matched person (None for unknown)
            confidence: Detection confidence
            similarity_score: Face similarity score
            frame: Video frame for snapshot
            bbox: Face bounding box (x, y, w, h) for highlighting

        Returns:
            Created Alert object, or None if not created
        """
        try:
            # Determine if we should create alert
            if not self.should_create_alert(person, confidence or 0, event_type):
                return None

            # Generate guard prompt
            displayed_prompt = None
            threat_level = None
            watchlist_status = None

            if person:
                displayed_prompt = self.generate_guard_prompt(person)
                threat_level = person.threat_level
                watchlist_status = person.watchlist_status

            # Create alert record
            alert = Alert(
                event_type=event_type,
                person_id=person.id if person else None,
                person_name=person.name if person else "Unknown",
                confidence=confidence,
                similarity_score=similarity_score,
                threat_level=threat_level,
                watchlist_status=watchlist_status,
                displayed_prompt=displayed_prompt,
                guard_verified=False,
                acknowledged=False
            )

            db.add(alert)
            db.flush()  # Get ID before committing

            # Save snapshot with face highlight
            if self.save_snapshot and frame is not None:
                snapshot_path = self.save_alert_snapshot(
                    frame,
                    alert.id,
                    bbox=bbox,
                    person_name=person.name if person else "Unknown",
                    threat_level=threat_level
                )
                alert.snapshot_path = snapshot_path

            db.commit()
            db.refresh(alert)

            # Log alert
            if threat_level in ['critical', 'high']:
                logger.warning(f"HIGH PRIORITY ALERT: {alert}")
            else:
                logger.info(f"Alert created: {alert}")

            return alert

        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            db.rollback()
            return None

    def get_active_alerts(
        self,
        db: Session,
        threat_level: Optional[str] = None,
        limit: int = 50
    ) -> List[Alert]:
        """
        Get unacknowledged alerts, optionally filtered by threat level.

        Args:
            db: Database session
            threat_level: Optional filter by threat level
            limit: Maximum alerts to return

        Returns:
            List of Alert objects
        """
        query = db.query(Alert).filter(Alert.acknowledged == False)

        if threat_level:
            query = query.filter(Alert.threat_level == threat_level)

        return query.order_by(Alert.timestamp.desc()).limit(limit).all()

    def get_recent_alerts(
        self,
        db: Session,
        hours: int = 24,
        limit: int = 100
    ) -> List[Alert]:
        """Get alerts from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return (
            db.query(Alert)
            .filter(Alert.timestamp >= cutoff)
            .order_by(Alert.timestamp.desc())
            .limit(limit)
            .all()
        )

    def verify_alert(
        self,
        db: Session,
        alert_id: int,
        guard_action: str,
        verified_by: str,
        notes: Optional[str] = None
    ) -> Optional[Alert]:
        """
        Record guard verification of an alert.

        Args:
            db: Database session
            alert_id: Alert ID
            guard_action: Action taken (confirmed, false_alarm, etc.)
            verified_by: Guard username
            notes: Optional notes

        Returns:
            Updated Alert object
        """
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return None

            alert.guard_verified = True
            alert.guard_action = guard_action
            alert.guard_verified_by = verified_by
            alert.guard_verified_at = datetime.now()
            alert.action_notes = notes

            db.commit()
            db.refresh(alert)

            logger.info(f"Alert {alert_id} verified: {guard_action} by {verified_by}")
            return alert

        except Exception as e:
            logger.error(f"Failed to verify alert: {e}")
            db.rollback()
            return None

    def acknowledge_alert(
        self,
        db: Session,
        alert_id: int,
        acknowledged_by: str
    ) -> Optional[Alert]:
        """Mark alert as acknowledged by admin."""
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return None

            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.acknowledged_at = datetime.now()

            db.commit()
            db.refresh(alert)

            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return alert

        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            db.rollback()
            return None

    def get_alert_statistics(self, db: Session, hours: int = 24) -> Dict[str, Any]:
        """Get alert statistics for dashboard."""
        cutoff = datetime.now() - timedelta(hours=hours)

        total = db.query(Alert).filter(Alert.timestamp >= cutoff).count()
        critical = db.query(Alert).filter(
            Alert.timestamp >= cutoff,
            Alert.threat_level == 'critical'
        ).count()
        high = db.query(Alert).filter(
            Alert.timestamp >= cutoff,
            Alert.threat_level == 'high'
        ).count()
        unverified = db.query(Alert).filter(
            Alert.timestamp >= cutoff,
            Alert.guard_verified == False
        ).count()

        return {
            "period_hours": hours,
            "total_alerts": total,
            "critical_alerts": critical,
            "high_alerts": high,
            "unverified": unverified,
            "verified": total - unverified
        }
