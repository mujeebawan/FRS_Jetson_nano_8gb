"""
Video Clip Recorder for Face Recognition Security System.
Records short video clips around alert events for evidence.

Features:
- Circular buffer keeps last N seconds in memory
- On alert, saves pre-alert + post-alert footage
- Hardware-accelerated encoding on Jetson (nvv4l2h264enc)
- Organized storage: data/clips/{YYYY-MM-DD}/alert_{id}.mp4
"""

import cv2
import numpy as np
import logging
import threading
import time
from pathlib import Path
from collections import deque
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class FrameRecord:
    """A frame with timestamp for the circular buffer."""
    frame: np.ndarray
    timestamp: float


class VideoRecorder:
    """
    Records video clips around alert events.

    Maintains a circular buffer of recent frames and saves clips
    when triggered by an alert.
    """

    def __init__(
        self,
        pre_alert_seconds: float = 5.0,
        post_alert_seconds: float = 5.0,
        fps: int = 15,
        clips_dir: str = None
    ):
        """
        Initialize video recorder.

        Args:
            pre_alert_seconds: Seconds of footage before alert to save
            post_alert_seconds: Seconds of footage after alert to record
            fps: Target frames per second for clips
            clips_dir: Directory to save clips (default: data/clips)
        """
        self.pre_alert_seconds = pre_alert_seconds
        self.post_alert_seconds = post_alert_seconds
        self.fps = fps
        self.clips_dir = Path(clips_dir or "data/clips")
        self.clips_dir.mkdir(parents=True, exist_ok=True)

        # Circular buffer for pre-alert frames
        # Buffer size = pre_alert_seconds * fps
        buffer_size = int(pre_alert_seconds * fps)
        self._buffer: deque[FrameRecord] = deque(maxlen=buffer_size)
        self._buffer_lock = threading.Lock()

        # Recording state
        self._recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._record_frames: list = []
        self._record_alert_id: Optional[int] = None
        self._record_start_time: float = 0

        # Frame dimensions (set on first frame)
        self._frame_size: Optional[Tuple[int, int]] = None

        # Stats
        self._clips_saved = 0
        self._total_frames_buffered = 0

        logger.info(f"VideoRecorder initialized: {pre_alert_seconds}s pre + {post_alert_seconds}s post @ {fps}fps")
        logger.info(f"Clips directory: {self.clips_dir}")

    def add_frame(self, frame: np.ndarray):
        """
        Add a frame to the circular buffer.
        Called continuously from stream to maintain rolling buffer.

        Args:
            frame: BGR numpy array
        """
        if frame is None:
            return

        # Store frame dimensions
        if self._frame_size is None:
            self._frame_size = (frame.shape[1], frame.shape[0])
            logger.info(f"Video frame size: {self._frame_size}")

        # Add to circular buffer
        record = FrameRecord(
            frame=frame.copy(),
            timestamp=time.time()
        )

        with self._buffer_lock:
            self._buffer.append(record)
            self._total_frames_buffered += 1

        # If actively recording post-alert, add to record frames
        if self._recording and self._record_frames is not None:
            self._record_frames.append(record)

            # Check if post-alert recording is complete
            elapsed = time.time() - self._record_start_time
            if elapsed >= self.post_alert_seconds:
                self._finish_recording()

    def trigger_recording(self, alert_id: int, bbox: tuple = None):
        """
        Trigger recording of a video clip for an alert.
        Captures pre-alert buffer + starts post-alert recording.

        Args:
            alert_id: Alert ID for filename
            bbox: Optional face bounding box for annotation
        """
        if self._recording:
            logger.warning(f"Already recording for alert {self._record_alert_id}, skipping {alert_id}")
            return

        logger.info(f"Triggering video recording for alert {alert_id}")

        # Copy pre-alert frames from buffer
        with self._buffer_lock:
            pre_frames = list(self._buffer)

        # Start recording
        self._recording = True
        self._record_alert_id = alert_id
        self._record_frames = pre_frames.copy()
        self._record_start_time = time.time()

        logger.info(f"Captured {len(pre_frames)} pre-alert frames, recording {self.post_alert_seconds}s more...")

    def _finish_recording(self):
        """Finish recording and save the clip in a background thread."""
        if not self._recording:
            return

        self._recording = False
        frames = self._record_frames
        alert_id = self._record_alert_id

        # Reset state
        self._record_frames = []
        self._record_alert_id = None

        # Save in background thread
        self._record_thread = threading.Thread(
            target=self._save_clip,
            args=(frames, alert_id),
            daemon=True
        )
        self._record_thread.start()

    def _save_clip(self, frames: list, alert_id: int) -> Optional[str]:
        """
        Save frames as MP4 video clip.

        Args:
            frames: List of FrameRecord objects
            alert_id: Alert ID for filename

        Returns:
            Path to saved clip, or None if failed
        """
        if not frames or self._frame_size is None:
            logger.warning(f"No frames to save for alert {alert_id}")
            return None

        try:
            # Create date folder
            date_str = datetime.now().strftime("%Y-%m-%d")
            date_folder = self.clips_dir / date_str
            date_folder.mkdir(parents=True, exist_ok=True)

            # Generate filename
            time_str = datetime.now().strftime("%H%M%S")
            filename = f"alert_{alert_id}_{time_str}.mp4"
            filepath = date_folder / filename

            # Try hardware-accelerated encoder first (Jetson)
            # Fallback to software encoder if not available
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')

            writer = cv2.VideoWriter(
                str(filepath),
                fourcc,
                self.fps,
                self._frame_size
            )

            if not writer.isOpened():
                logger.error(f"Failed to open video writer for {filepath}")
                return None

            # Write frames
            frames_written = 0
            for record in frames:
                if record.frame is not None:
                    # Resize if needed
                    if record.frame.shape[1] != self._frame_size[0] or record.frame.shape[0] != self._frame_size[1]:
                        frame = cv2.resize(record.frame, self._frame_size)
                    else:
                        frame = record.frame

                    writer.write(frame)
                    frames_written += 1

            writer.release()

            self._clips_saved += 1
            duration = len(frames) / self.fps
            logger.info(f"Saved clip: {filepath} ({frames_written} frames, {duration:.1f}s)")

            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save clip for alert {alert_id}: {e}")
            return None

    def get_clip_path(self, alert_id: int) -> Optional[Path]:
        """
        Find the clip file for an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Path to clip file if found
        """
        # Search in all date folders
        for date_folder in sorted(self.clips_dir.iterdir(), reverse=True):
            if date_folder.is_dir():
                for clip in date_folder.glob(f"alert_{alert_id}_*.mp4"):
                    return clip
        return None

    def get_stats(self) -> dict:
        """Get recorder statistics."""
        return {
            "buffer_size": len(self._buffer),
            "buffer_capacity": self._buffer.maxlen,
            "is_recording": self._recording,
            "clips_saved": self._clips_saved,
            "total_frames_buffered": self._total_frames_buffered,
            "pre_alert_seconds": self.pre_alert_seconds,
            "post_alert_seconds": self.post_alert_seconds,
            "fps": self.fps
        }

    def cleanup_old_clips(self, days: int = 30):
        """
        Delete clips older than specified days.

        Args:
            days: Delete clips older than this many days
        """
        import shutil
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        for date_folder in self.clips_dir.iterdir():
            if date_folder.is_dir():
                try:
                    folder_date = datetime.strptime(date_folder.name, "%Y-%m-%d")
                    if folder_date < cutoff:
                        shutil.rmtree(date_folder)
                        deleted += 1
                        logger.info(f"Deleted old clips folder: {date_folder}")
                except ValueError:
                    pass  # Skip non-date folders

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old clip folders")
