"""
Stream Manager for handling video streams with multi-client broadcast.
Optimized for Jetson Orin Nano 8GB.

Features:
- GStreamer hardware-accelerated decoding (nvv4l2decoder)
- Motion-triggered face detection (via Hikvision ISAPI VMD)
- Multi-client WebSocket broadcasting
- Minimal latency pipeline
- ASYNC processing: Detection runs in separate thread, never blocks stream
"""

import cv2
import numpy as np
import logging
import asyncio
import threading
from typing import Optional, Callable, List, Set, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .processor import FrameProcessor
from dataclasses import dataclass
from queue import Queue, Empty
import time

from ..config import settings
from .motion_processor import MotionTrigger

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """Container for a video frame with metadata"""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    has_motion: bool = False


class StreamManager:
    """
    Manages video stream capture and multi-client broadcasting.
    Single capture thread serves multiple WebSocket/HTTP clients.

    Features:
    - Hardware-accelerated H264 decoding via GStreamer/nvv4l2decoder
    - Motion-triggered face detection (only process when camera detects movement)
    - Multi-client WebSocket broadcasting with minimal latency
    """

    def __init__(
        self,
        rtsp_url: str = None,
        frame_skip: int = 2,
        max_clients: int = 10,
        enable_motion_trigger: bool = None
    ):
        """
        Initialize stream manager.

        Args:
            rtsp_url: RTSP stream URL
            frame_skip: Process every Nth frame
            max_clients: Maximum concurrent viewers
            enable_motion_trigger: Enable motion-based processing (default from settings)
        """
        self.rtsp_url = rtsp_url or self._get_default_stream()
        self.frame_skip = frame_skip
        self.max_clients = max_clients

        # Motion trigger (uses camera's built-in VMD via ISAPI)
        self._enable_motion_trigger = enable_motion_trigger if enable_motion_trigger is not None else settings.enable_motion_trigger
        self._motion_trigger: Optional[MotionTrigger] = None

        if self._enable_motion_trigger:
            self._motion_trigger = MotionTrigger(
                motion_timeout_seconds=3.0,  # Continue processing 3s after motion stops
                polling_interval=0.3  # Poll motion status every 300ms
            )

        # Stream state
        self._capture: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Frame distribution
        self._latest_frame: Optional[FrameData] = None
        self._latest_raw_frame: Optional[FrameData] = None  # Clean frame without overlays (for enrollment)
        self._frame_number = 0
        self._subscribers: Set[asyncio.Queue] = set()

        # Processing callback - can be function or FrameProcessor object
        self._processor: Optional[Any] = None
        self._processor_obj: Optional["FrameProcessor"] = None

        # Video recorder reference (set externally)
        self._video_recorder: Optional[Any] = None

        # Async processing - separate thread for detection (never blocks stream)
        self._process_thread: Optional[threading.Thread] = None
        self._process_queue: Queue = Queue(maxsize=2)  # Only keep latest frames
        self._process_counter = 0

        # Stats
        self._fps = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_count = 0
        self._processed_frames = 0
        self._skipped_frames = 0

        logger.info(f"StreamManager initialized: url={self.rtsp_url[:50]}...")
        logger.info(f"Motion trigger: {'enabled' if self._enable_motion_trigger else 'disabled'}")

    def _get_default_stream(self) -> str:
        """Get default stream URL based on settings."""
        stream = settings.process_stream
        if stream == "main":
            return settings.camera_main_stream
        elif stream == "sub":
            return settings.camera_sub_stream
        else:
            return settings.camera_third_stream

    def start(self) -> bool:
        """Start stream capture thread and motion trigger."""
        if self._running:
            return True

        try:
            # Try GStreamer hardware-accelerated pipeline first (Jetson optimized)
            gst_pipeline = self._build_gstreamer_pipeline()
            self._capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

            if not self._capture.isOpened():
                logger.info("GStreamer failed, trying FFMPEG...")
                # Fallback to FFMPEG with TCP transport
                self._capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self._capture.isOpened():
                logger.error("Failed to open video stream")
                return False

            # Start motion trigger if enabled
            if self._motion_trigger:
                self._motion_trigger.start()
                logger.info("Motion trigger started")

            self._running = True

            # Start capture thread (fast, never blocks)
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            # Start processing thread (separate, handles detection)
            self._process_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self._process_thread.start()

            logger.info("Stream capture started (async processing enabled)")
            return True

        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False

    def _build_gstreamer_pipeline(self) -> str:
        """Build GStreamer pipeline for hardware-accelerated decoding with minimal latency."""
        # Ultra-low latency pipeline for real-time streaming
        # - latency=0: Minimum RTSP buffering
        # - drop-on-latency=true: Drop frames if behind
        # - nvv4l2decoder: Hardware H264 decoding
        # - appsink: sync=false (no clock sync), max-buffers=1 (only latest frame), drop=true
        return (
            f"rtspsrc location={self.rtsp_url} latency=0 drop-on-latency=true ! "
            "rtph264depay ! h264parse ! "
            "nvv4l2decoder enable-max-performance=true ! "
            "nvvidconv ! "
            "video/x-raw,format=BGRx ! "
            "videoconvert ! "
            "video/x-raw,format=BGR ! "
            "appsink sync=false max-buffers=1 drop=true"
        )

    def _capture_loop(self):
        """
        Main capture loop - FAST, never blocks.
        Only captures frames, draws cached overlays, and broadcasts.
        Detection happens in separate _processing_loop thread.
        """
        while self._running:
            try:
                ret, frame = self._capture.read()

                if not ret:
                    logger.warning("Frame read failed, reconnecting...")
                    time.sleep(0.5)
                    self._reconnect()
                    continue

                self._frame_number += 1
                self._process_counter += 1

                # Run software motion detection on EVERY frame (updates internal state)
                # Then check if we should process based on motion state + timeout
                has_motion = True  # Default: always process
                if self._motion_trigger:
                    # Update motion detection with current frame (this analyzes pixels)
                    self._motion_trigger.update_from_frame(frame)
                    # Then check if we should process (motion active or in timeout window)
                    has_motion = self._motion_trigger.should_process()

                # Create frame data
                frame_data = FrameData(
                    frame=frame,
                    timestamp=time.time(),
                    frame_number=self._frame_number,
                    has_motion=has_motion
                )

                # Queue frame for async processing (non-blocking)
                should_process = (
                    self._processor_obj and
                    self._process_counter >= self.frame_skip and
                    has_motion
                )

                if should_process:
                    self._process_counter = 0
                    # Non-blocking put - drop old frames if queue full
                    try:
                        # Clear old frame if queue full
                        if self._process_queue.full():
                            try:
                                self._process_queue.get_nowait()
                                self._skipped_frames += 1
                            except Empty:
                                pass
                        # Queue new frame (copy for thread safety)
                        self._process_queue.put_nowait(FrameData(
                            frame=frame.copy(),
                            timestamp=frame_data.timestamp,
                            frame_number=frame_data.frame_number,
                            has_motion=has_motion
                        ))
                    except:
                        pass  # Queue full, skip this frame

                # Save raw frame (without overlays) for enrollment
                with self._lock:
                    self._latest_raw_frame = FrameData(
                        frame=frame.copy(),
                        timestamp=frame_data.timestamp,
                        frame_number=frame_data.frame_number,
                        has_motion=has_motion
                    )

                # Feed frame to video recorder buffer (for alert clips)
                if self._video_recorder and self._frame_number % 2 == 0:  # Every other frame = ~15fps
                    try:
                        self._video_recorder.add_frame(frame)
                    except Exception:
                        pass  # Ignore recorder errors

                # Draw cached overlays (very fast, ~1ms)
                if self._processor_obj:
                    try:
                        frame_data = self._processor_obj.draw_overlay(frame_data)
                    except Exception as e:
                        pass  # Ignore overlay errors

                # Update latest frame (with overlays for display)
                with self._lock:
                    self._latest_frame = frame_data

                # Broadcast to subscribers (all frames for smooth video)
                self._broadcast(frame_data)

                # Update FPS
                self._update_fps()

            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                time.sleep(0.01)

    def _processing_loop(self):
        """
        Separate processing thread for face detection/recognition.
        Runs independently, never blocks the capture loop.
        """
        logger.info("Processing thread started")

        while self._running:
            try:
                # Wait for frame with timeout
                try:
                    frame_data = self._process_queue.get(timeout=0.1)
                except Empty:
                    continue

                # Process frame (detection + recognition)
                if self._processor_obj:
                    try:
                        self._processor_obj.process(frame_data, detect=True)
                        self._processed_frames += 1
                    except Exception as e:
                        logger.error(f"Frame processor error: {e}")

            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                time.sleep(0.01)

        logger.info("Processing thread stopped")

    def _reconnect(self):
        """Attempt to reconnect to stream."""
        try:
            if self._capture:
                self._capture.release()

            self._capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if not self._capture.isOpened():
                gst_pipeline = self._build_gstreamer_pipeline()
                self._capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

    def _broadcast(self, frame_data: FrameData):
        """Broadcast frame to all subscribers with minimal latency."""
        dead_subscribers = set()

        for queue in self._subscribers:
            try:
                # Clear old frame and put new one - always show latest
                try:
                    queue.get_nowait()  # Remove old frame if exists
                except:
                    pass
                queue.put_nowait(frame_data)  # Put latest frame
            except:
                dead_subscribers.add(queue)

        # Clean up dead subscribers
        self._subscribers -= dead_subscribers

    def _update_fps(self):
        """Calculate current FPS."""
        self._fps_frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time

        if elapsed >= 1.0:
            self._fps = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._last_fps_time = current_time

    def stop(self):
        """Stop stream capture, processing thread, and motion trigger."""
        self._running = False

        # Stop motion trigger
        if self._motion_trigger:
            self._motion_trigger.stop()

        # Stop processing thread
        if self._process_thread:
            self._process_thread.join(timeout=2.0)
            self._process_thread = None

        # Stop capture thread
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._capture:
            self._capture.release()
            self._capture = None

        # Clear queue
        while not self._process_queue.empty():
            try:
                self._process_queue.get_nowait()
            except Empty:
                break

        logger.info(f"Stream capture stopped. Processed: {self._processed_frames}, Skipped: {self._skipped_frames}")

    def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to frame updates.

        Returns:
            Queue that will receive FrameData objects
        """
        if len(self._subscribers) >= self.max_clients:
            raise RuntimeError(f"Maximum clients ({self.max_clients}) reached")

        # maxsize=1: Only keep latest frame, discard old ones for low latency
        queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        logger.debug(f"New subscriber, total: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove subscriber."""
        self._subscribers.discard(queue)
        logger.debug(f"Subscriber removed, total: {len(self._subscribers)}")

    def set_processor(self, processor: Any):
        """
        Set frame processor - can be function or FrameProcessor object.

        Args:
            processor: FrameProcessor object or function that takes FrameData
        """
        # Check if it's a FrameProcessor object (has draw_overlay method)
        if hasattr(processor, 'draw_overlay') and hasattr(processor, 'process'):
            self._processor_obj = processor
            self._processor = None
            logger.info(f"FrameProcessor connected: {type(processor).__name__}")
        else:
            # Legacy function-based processor
            self._processor = processor
            self._processor_obj = None
            logger.info(f"Legacy processor function connected")

    def set_video_recorder(self, recorder: Any):
        """
        Set video recorder for alert clips.

        Args:
            recorder: VideoRecorder instance
        """
        self._video_recorder = recorder
        logger.info("VideoRecorder connected to stream")

    def get_latest_frame(self) -> Optional[FrameData]:
        """Get the most recent frame (with overlays for display)."""
        with self._lock:
            return self._latest_frame

    def get_latest_raw_frame(self) -> Optional[FrameData]:
        """Get the most recent raw frame (without overlays, for enrollment)."""
        with self._lock:
            return self._latest_raw_frame

    def encode_jpeg(self, frame: np.ndarray, quality: int = 80) -> bytes:
        """Encode frame as JPEG."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return buffer.tobytes()

    @property
    def fps(self) -> float:
        """Current frames per second."""
        return self._fps

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)

    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        return self._running

    @property
    def motion_active(self) -> bool:
        """Check if motion is currently detected."""
        if self._motion_trigger:
            return self._motion_trigger.is_motion_active
        return True  # Always "active" if motion trigger disabled

    @property
    def motion_stats(self) -> dict:
        """Get motion detection statistics."""
        if self._motion_trigger:
            return self._motion_trigger.get_stats()
        return {
            "enabled": False,
            "is_active": True,
            "total_events": 0,
            "frames_saved": 0
        }

    def get_stats(self) -> dict:
        """Get comprehensive stream statistics."""
        stats = {
            "fps": self._fps,
            "frame_number": self._frame_number,
            "subscribers": len(self._subscribers),
            "processed_frames": self._processed_frames,
            "skipped_frames": self._skipped_frames,
            "is_running": self._running
        }

        # Add motion stats
        if self._motion_trigger:
            stats["motion"] = self._motion_trigger.get_stats()

        return stats
