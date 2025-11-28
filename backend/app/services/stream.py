"""
Stream Manager for handling video streams with multi-client broadcast.
Optimized for Jetson Orin Nano 8GB.
"""

import cv2
import numpy as np
import logging
import asyncio
import threading
from typing import Optional, Callable, List, Set
from dataclasses import dataclass
from queue import Queue
import time

from ..config import settings

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
    """

    def __init__(
        self,
        rtsp_url: str = None,
        frame_skip: int = 2,
        max_clients: int = 10
    ):
        """
        Initialize stream manager.

        Args:
            rtsp_url: RTSP stream URL
            frame_skip: Process every Nth frame
            max_clients: Maximum concurrent viewers
        """
        self.rtsp_url = rtsp_url or self._get_default_stream()
        self.frame_skip = frame_skip
        self.max_clients = max_clients

        # Stream state
        self._capture: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Frame distribution
        self._latest_frame: Optional[FrameData] = None
        self._frame_number = 0
        self._subscribers: Set[asyncio.Queue] = set()

        # Processing callback
        self._processor: Optional[Callable] = None

        # Stats
        self._fps = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_count = 0

        logger.info(f"StreamManager initialized: url={self.rtsp_url[:50]}...")

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
        """Start stream capture thread."""
        if self._running:
            return True

        try:
            # Initialize capture
            self._capture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

            if not self._capture.isOpened():
                # Try with GStreamer pipeline
                gst_pipeline = self._build_gstreamer_pipeline()
                self._capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

            if not self._capture.isOpened():
                logger.error("Failed to open video stream")
                return False

            # Set buffer size to reduce latency
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)

            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()

            logger.info("Stream capture started")
            return True

        except Exception as e:
            logger.error(f"Failed to start stream: {e}")
            return False

    def _build_gstreamer_pipeline(self) -> str:
        """Build GStreamer pipeline for hardware-accelerated decoding."""
        # Parse RTSP URL components
        return (
            f"rtspsrc location={self.rtsp_url} latency=100 ! "
            "rtph264depay ! h264parse ! "
            "nvv4l2decoder ! "
            "nvvidconv ! "
            "video/x-raw,format=BGRx ! "
            "videoconvert ! "
            "video/x-raw,format=BGR ! "
            "appsink drop=1"
        )

    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        skip_counter = 0

        while self._running:
            try:
                ret, frame = self._capture.read()

                if not ret:
                    logger.warning("Frame read failed, reconnecting...")
                    time.sleep(1)
                    self._reconnect()
                    continue

                skip_counter += 1
                if skip_counter <= self.frame_skip:
                    continue
                skip_counter = 0

                self._frame_number += 1

                # Create frame data
                frame_data = FrameData(
                    frame=frame,
                    timestamp=time.time(),
                    frame_number=self._frame_number
                )

                # Process frame if processor is set
                if self._processor:
                    try:
                        frame_data = self._processor(frame_data)
                    except Exception as e:
                        logger.error(f"Frame processor error: {e}")

                # Update latest frame
                with self._lock:
                    self._latest_frame = frame_data

                # Broadcast to subscribers
                self._broadcast(frame_data)

                # Update FPS
                self._update_fps()

            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                time.sleep(0.1)

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
        """Broadcast frame to all subscribers."""
        dead_subscribers = set()

        for queue in self._subscribers:
            try:
                # Non-blocking put, drop if queue is full
                if queue.qsize() < 2:
                    queue.put_nowait(frame_data)
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
        """Stop stream capture."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._capture:
            self._capture.release()
            self._capture = None

        logger.info("Stream capture stopped")

    def subscribe(self) -> asyncio.Queue:
        """
        Subscribe to frame updates.

        Returns:
            Queue that will receive FrameData objects
        """
        if len(self._subscribers) >= self.max_clients:
            raise RuntimeError(f"Maximum clients ({self.max_clients}) reached")

        queue = asyncio.Queue(maxsize=2)
        self._subscribers.add(queue)
        logger.debug(f"New subscriber, total: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove subscriber."""
        self._subscribers.discard(queue)
        logger.debug(f"Subscriber removed, total: {len(self._subscribers)}")

    def set_processor(self, processor: Callable):
        """
        Set frame processor function.

        Args:
            processor: Function that takes FrameData and returns processed FrameData
        """
        self._processor = processor

    def get_latest_frame(self) -> Optional[FrameData]:
        """Get the most recent frame."""
        with self._lock:
            return self._latest_frame

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
