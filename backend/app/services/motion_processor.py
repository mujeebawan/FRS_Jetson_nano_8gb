"""
Motion-Triggered Face Detection Processor.

Uses SOFTWARE-BASED frame differencing for motion detection.
This works with ANY camera (Hikvision, Dahua, generic RTSP, etc.)
and is more reliable than camera-specific APIs.

Benefits:
- GPU idle when no motion (saves power, reduces heat)
- Can use larger/more accurate models due to reduced average load
- Works with ANY camera - no vendor-specific API needed
- Better for continuous 24/7 operation
"""

import cv2
import numpy as np
import logging
import threading
from typing import Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class MotionState:
    """Current motion detection state."""
    is_active: bool = False
    last_motion_time: Optional[datetime] = None
    motion_count: int = 0
    motion_score: float = 0.0


class MotionTrigger:
    """
    Software-based motion detection using frame differencing.

    Works with ANY camera by analyzing actual pixel changes.
    Much more reliable than camera-specific APIs.

    Algorithm:
    1. Convert frames to grayscale
    2. Apply Gaussian blur to reduce noise
    3. Compute absolute difference between consecutive frames
    4. Threshold to get binary motion mask
    5. Calculate percentage of pixels that changed
    6. If above threshold, motion is detected
    """

    def __init__(
        self,
        motion_timeout_seconds: float = 3.0,
        motion_threshold: float = 0.1,  # Percentage of pixels changed (0-100) - lowered for sensitivity
        blur_size: int = 21,
        diff_threshold: int = 20,  # Lowered for sensitivity (0-255)
        min_area: int = 300,  # Lowered for detecting smaller movements
        **kwargs  # Ignore unused args like camera, polling_interval
    ):
        """
        Initialize software motion trigger.

        Args:
            motion_timeout_seconds: Continue processing for N seconds after motion stops
            motion_threshold: Percentage of changed pixels to trigger motion (0.1-5.0 typical)
            blur_size: Gaussian blur kernel size (must be odd)
            diff_threshold: Pixel difference threshold (0-255)
            min_area: Minimum contour area to consider as motion
        """
        self.motion_timeout = motion_timeout_seconds
        self.motion_threshold = motion_threshold
        self.blur_size = blur_size
        self.diff_threshold = diff_threshold
        self.min_area = min_area

        # State
        self.state = MotionState()
        self._running = False
        self._lock = threading.Lock()

        # Frame differencing state
        self._prev_frame: Optional[np.ndarray] = None
        self._frame_count = 0
        self._skip_frames = 2  # Skip first few frames for initialization

        # Callbacks
        self._on_motion_start: Optional[Callable] = None
        self._on_motion_stop: Optional[Callable] = None

        # Stats
        self._total_motion_events = 0
        self._processing_saved_frames = 0

        logger.info(f"MotionTrigger initialized (SOFTWARE mode): "
                   f"timeout={motion_timeout_seconds}s, threshold={motion_threshold}%")

    def start(self):
        """Start motion detection (no background thread needed - processes inline)."""
        if self._running:
            return
        self._running = True
        self._prev_frame = None
        self._frame_count = 0
        logger.info("Software motion detection started")

    def stop(self):
        """Stop motion detection."""
        self._running = False
        self._prev_frame = None
        logger.info(f"MotionTrigger stopped. Stats: {self._total_motion_events} events, "
                   f"{self._processing_saved_frames} frames saved from processing")

    def detect_motion(self, frame: np.ndarray) -> bool:
        """
        Detect motion in the given frame using frame differencing.

        Args:
            frame: BGR frame from camera

        Returns:
            True if motion detected, False otherwise
        """
        if frame is None:
            return False

        self._frame_count += 1

        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        gray = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        # Skip first few frames for initialization
        if self._frame_count <= self._skip_frames:
            self._prev_frame = gray
            return True  # Process anyway during init

        # First frame - no comparison possible
        if self._prev_frame is None:
            self._prev_frame = gray
            return True  # Process anyway

        # Compute absolute difference
        frame_delta = cv2.absdiff(self._prev_frame, gray)

        # Threshold the difference
        thresh = cv2.threshold(frame_delta, self.diff_threshold, 255, cv2.THRESH_BINARY)[1]

        # Dilate to fill gaps
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Calculate total motion area
        motion_area = sum(cv2.contourArea(c) for c in contours if cv2.contourArea(c) > self.min_area)
        total_area = frame.shape[0] * frame.shape[1]
        motion_percentage = (motion_area / total_area) * 100

        # Update previous frame (use weighted average for stability)
        self._prev_frame = cv2.addWeighted(gray, 0.5, self._prev_frame, 0.5, 0)

        # Determine if motion detected
        motion_detected = motion_percentage > self.motion_threshold

        with self._lock:
            self.state.motion_score = motion_percentage

            if motion_detected:
                if not self.state.is_active:
                    # New motion event
                    self._total_motion_events += 1
                    logger.debug(f"Motion detected: {motion_percentage:.2f}% (event #{self._total_motion_events})")
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
                        self.state.is_active = False
                        logger.debug(f"Motion ended after {self.state.motion_count} frames")
                        self.state.motion_count = 0
                        if self._on_motion_stop:
                            self._on_motion_stop()

        return motion_detected

    def should_process(self) -> bool:
        """
        Check if face detection should run on current frame.

        Returns:
            True if motion is active or in timeout window
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

    def update_from_frame(self, frame: np.ndarray) -> bool:
        """
        Update motion state from a new frame.
        Should be called for every frame to keep motion detection accurate.

        Args:
            frame: BGR frame from camera

        Returns:
            True if motion detected, False otherwise
        """
        if not self._running:
            return True  # Not running = always process
        return self.detect_motion(frame)

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
                "motion_score": round(self.state.motion_score, 2),
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
