"""
Motion-Triggered Face Detection Processor.

Uses Hikvision camera's built-in Video Motion Detection (VMD) via ISAPI
to optimize processing - only run face detection when motion is detected.

This significantly reduces GPU usage and allows for higher quality models.
"""

import logging
import asyncio
import threading
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..config import settings
from .camera import CameraService, MotionEvent

logger = logging.getLogger(__name__)


@dataclass
class MotionState:
    """Current motion detection state."""
    is_active: bool = False
    last_motion_time: Optional[datetime] = None
    motion_count: int = 0
    last_poll_time: Optional[datetime] = None


class MotionTrigger:
    """
    Integrates with Hikvision camera's VMD to trigger face detection only when needed.

    Two modes:
    1. Polling mode: Periodically check motion status (reliable, ~100ms latency)
    2. Event stream mode: Subscribe to alertStream (real-time, but may disconnect)

    Benefits:
    - GPU idle when no motion (saves power, reduces heat)
    - Can use larger/more accurate models due to reduced average load
    - Better for continuous 24/7 operation
    """

    def __init__(
        self,
        camera: Optional[CameraService] = None,
        motion_timeout_seconds: float = 3.0,
        polling_interval: float = 0.5,
        use_event_stream: bool = False
    ):
        """
        Initialize motion trigger.

        Args:
            camera: CameraService instance for ISAPI access
            motion_timeout_seconds: Continue processing for N seconds after motion stops
            polling_interval: How often to poll motion status (seconds)
            use_event_stream: Use alertStream instead of polling (experimental)
        """
        self.camera = camera or CameraService()
        self.motion_timeout = motion_timeout_seconds
        self.polling_interval = polling_interval
        self.use_event_stream = use_event_stream

        # State
        self.state = MotionState()
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._event_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

        # Callbacks
        self._on_motion_start: Optional[Callable] = None
        self._on_motion_stop: Optional[Callable] = None

        # Stats
        self._total_motion_events = 0
        self._processing_saved_frames = 0

        logger.info(f"MotionTrigger initialized (timeout={motion_timeout_seconds}s, polling={polling_interval}s)")

    def start(self):
        """Start motion monitoring."""
        if self._running:
            return

        self._running = True

        if self.use_event_stream:
            # Start async event stream listener
            logger.info("Starting motion event stream listener...")
            # This needs to run in the event loop
        else:
            # Start polling thread
            self._poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
            self._poll_thread.start()
            logger.info("Started motion polling thread")

    def stop(self):
        """Stop motion monitoring."""
        self._running = False

        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None

        if self._event_task:
            self._event_task.cancel()

        logger.info(f"MotionTrigger stopped. Stats: {self._total_motion_events} events, "
                   f"{self._processing_saved_frames} frames saved from processing")

    def _polling_loop(self):
        """Background thread that polls motion status via ISAPI."""
        import time
        import httpx

        # Create sync client for polling
        client = httpx.Client(
            auth=httpx.DigestAuth(self.camera.username, self.camera.password),
            timeout=5.0
        )

        url = f"{self.camera.base_url}/ISAPI/Event/triggers/VMD-1/status"

        while self._running:
            try:
                response = client.get(url)

                if response.status_code == 200:
                    # Parse motion status from XML
                    text = response.text.lower()
                    motion_detected = '<eventstate>active</eventstate>' in text

                    with self._lock:
                        self.state.last_poll_time = datetime.now()

                        if motion_detected:
                            # Motion detected
                            if not self.state.is_active:
                                # New motion event
                                self._total_motion_events += 1
                                logger.info(f"Motion detected (event #{self._total_motion_events})")
                                if self._on_motion_start:
                                    self._on_motion_start()

                            self.state.is_active = True
                            self.state.last_motion_time = datetime.now()
                            self.state.motion_count += 1

                        else:
                            # No motion - check timeout
                            if self.state.is_active and self.state.last_motion_time:
                                elapsed = (datetime.now() - self.state.last_motion_time).total_seconds()

                                if elapsed > self.motion_timeout:
                                    # Motion timeout - stop processing
                                    self.state.is_active = False
                                    logger.info(f"Motion ended (was active for {self.state.motion_count} polls)")
                                    self.state.motion_count = 0

                                    if self._on_motion_stop:
                                        self._on_motion_stop()

                else:
                    logger.debug(f"Motion status check failed: {response.status_code}")

            except Exception as e:
                logger.debug(f"Motion polling error: {e}")

            time.sleep(self.polling_interval)

        client.close()

    async def _event_stream_loop(self):
        """Async task that listens to alertStream for real-time events."""
        while self._running:
            try:
                await self.camera.subscribe_motion_events(self._handle_motion_event)
            except Exception as e:
                logger.error(f"Event stream error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5.0)

    async def _handle_motion_event(self, event: MotionEvent):
        """Handle motion event from alertStream."""
        with self._lock:
            if event.active:
                if not self.state.is_active:
                    self._total_motion_events += 1
                    logger.info(f"Motion event received (#{self._total_motion_events})")

                self.state.is_active = True
                self.state.last_motion_time = datetime.now()

                if self._on_motion_start:
                    self._on_motion_start()
            else:
                # Inactive event - start timeout
                pass  # Let polling handle timeout

    def should_process(self) -> bool:
        """
        Check if face detection should run on current frame.

        Returns:
            True if motion is active and frame should be processed
        """
        if not settings.enable_motion_trigger:
            # Motion trigger disabled - always process
            return True

        with self._lock:
            # Always process if motion is currently active
            if self.state.is_active:
                return True

            # Check if we're in the timeout window after motion stopped
            if self.state.last_motion_time:
                elapsed = (datetime.now() - self.state.last_motion_time).total_seconds()
                if elapsed <= self.motion_timeout:
                    return True

            # No motion - track saved frames
            self._processing_saved_frames += 1
            return False

    def on_motion_start(self, callback: Callable):
        """Register callback for when motion starts."""
        self._on_motion_start = callback

    def on_motion_stop(self, callback: Callable):
        """Register callback for when motion stops."""
        self._on_motion_stop = callback

    @property
    def is_motion_active(self) -> bool:
        """Check if motion is currently detected."""
        with self._lock:
            return self.state.is_active

    @property
    def last_motion_time(self) -> Optional[datetime]:
        """Get timestamp of last motion detection."""
        with self._lock:
            return self.state.last_motion_time

    def get_stats(self) -> dict:
        """Get motion detection statistics."""
        with self._lock:
            return {
                "is_active": self.state.is_active,
                "total_events": self._total_motion_events,
                "frames_saved": self._processing_saved_frames,
                "last_motion": self.state.last_motion_time.isoformat() if self.state.last_motion_time else None,
                "motion_timeout_sec": self.motion_timeout,
                "enabled": settings.enable_motion_trigger
            }


class MotionAwareProcessor:
    """
    Wraps the face processor to only run detection when motion is detected.

    This is a decorator pattern that adds motion-awareness to any processor.
    """

    def __init__(self, processor: Any, motion_trigger: MotionTrigger):
        """
        Initialize motion-aware processor.

        Args:
            processor: The actual FrameProcessor that does face detection
            motion_trigger: MotionTrigger instance for checking motion
        """
        self.processor = processor
        self.motion_trigger = motion_trigger

        # Cache last detections for overlay when not processing
        self._last_detections = []
        self._last_detection_time: Optional[datetime] = None
        self._overlay_cache_seconds = 2.0  # Show last detections for 2s after motion stops

    def process(self, frame_data, detect: bool = True):
        """
        Process frame with motion awareness.

        Args:
            frame_data: FrameData object
            detect: Whether to run detection (may be overridden by motion state)

        Returns:
            Processed FrameData
        """
        # Check if motion is detected
        should_detect = detect and self.motion_trigger.should_process()

        if should_detect:
            # Run full detection and recognition
            result = self.processor.process(frame_data, detect=True)

            # Cache detections for overlay
            if hasattr(self.processor, '_last_detections'):
                self._last_detections = self.processor._last_detections
            self._last_detection_time = datetime.now()

            return result
        else:
            # No motion - just draw cached overlay if recent
            if self._should_draw_cached_overlay():
                return self.processor.draw_overlay(frame_data)
            else:
                # No overlay needed - return frame as-is
                frame_data.has_motion = False
                return frame_data

    def _should_draw_cached_overlay(self) -> bool:
        """Check if we should draw cached detection overlay."""
        if not self._last_detection_time:
            return False

        elapsed = (datetime.now() - self._last_detection_time).total_seconds()
        return elapsed <= self._overlay_cache_seconds

    def draw_overlay(self, frame_data):
        """Draw overlay (pass through to processor)."""
        return self.processor.draw_overlay(frame_data)

    def get_stats(self) -> dict:
        """Get combined stats from processor and motion trigger."""
        stats = {}

        # Add processor stats if available
        if hasattr(self.processor, 'get_stats'):
            stats['processor'] = self.processor.get_stats()

        # Add motion stats
        stats['motion'] = self.motion_trigger.get_stats()

        return stats
