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

        # Alert configuration
        self.alert_on_unknown = settings.alert_on_unknown
        self.alert_on_known = settings.alert_on_known
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

    def save_alert_snapshot(self, frame, alert_id: int) -> Optional[str]:
        """
        Save frame snapshot for alert in date-wise folder.

        Structure: data/snapshots/{YYYY-MM-DD}/alert_{id}_{HHMMSS}.jpg

        Args:
            frame: OpenCV frame (BGR numpy array)
            alert_id: Alert database ID

        Returns:
            Path to saved snapshot, or None if failed
        """
        if frame is None:
            return None

        try:
            date_folder = self._get_date_folder()
            time_str = datetime.now().strftime("%H%M%S")
            filename = f"alert_{alert_id}_{time_str}.jpg"
            filepath = date_folder / filename

            cv2.imwrite(str(filepath), frame)
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
            return False

        # Check configuration
        if person is None:
            # Unknown person
            return self.alert_on_unknown

        # Known person - check their status
        status = person.watchlist_status

        # Only alert on watchlist persons (criminal, suspect, banned, etc.)
        # NOT on normal persons - we only want criminal detection alerts
        if status in ['criminal', 'most_wanted', 'suspect', 'person_of_interest', 'banned']:
            return True

        # VIP alerts (optional, controlled by config)
        if status == 'vip' and self.alert_on_known:
            return True

        # Normal persons - NO alert (this is a security system for criminals)
        return False

    def create_alert(
        self,
        db: Session,
        event_type: str,
        person: Optional[Person] = None,
        confidence: Optional[float] = None,
        similarity_score: Optional[float] = None,
        frame=None
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

            # Save snapshot
            if self.save_snapshot and frame is not None:
                snapshot_path = self.save_alert_snapshot(frame, alert.id)
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
