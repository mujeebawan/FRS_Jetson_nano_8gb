"""
Frame processor for face detection and recognition.
Processes video frames and draws detection boxes.
"""

import cv2
import numpy as np
import logging
from typing import Optional, List, Callable
from dataclasses import dataclass

from .stream import FrameData
from ..core.detector import FaceDetector, FaceDetection
from ..core.recognizer import FaceRecognizer, MatchResult

logger = logging.getLogger(__name__)


class FrameProcessor:
    """
    Processes video frames for face detection and recognition.
    Draws bounding boxes and labels on frames.
    Keeps last detection overlay for smooth display between detections.
    """

    def __init__(
        self,
        detector: FaceDetector,
        recognizer: FaceRecognizer,
        alert_callback: Optional[Callable] = None
    ):
        """
        Initialize frame processor.

        Args:
            detector: Face detector instance
            recognizer: Face recognizer instance
            alert_callback: Optional callback for alerts (unknown faces)
        """
        self.detector = detector
        self.recognizer = recognizer
        self.alert_callback = alert_callback
        self._frame_count = 0

        # Cache last detection results for smooth display
        self._last_detections: List[FaceDetection] = []
        self._last_names: List[str] = []
        self._last_colors: List[tuple] = []

        logger.info("FrameProcessor initialized")

    def process(self, frame_data: FrameData, detect: bool = True) -> FrameData:
        """
        Process a frame for face detection and recognition.

        Args:
            frame_data: Input frame data
            detect: If True, run detection. If False, only draw cached boxes.

        Returns:
            Processed frame data with annotations
        """
        if frame_data.frame is None:
            return frame_data

        self._frame_count += 1

        if detect:
            # Detect faces (with embeddings only when we have enrolled persons)
            has_enrolled = self.recognizer.count > 0
            detections = self.detector.detect_with_embeddings(frame_data.frame) if has_enrolled else self.detector.detect(frame_data.frame)

            if detections:
                # New detections - update cache
                names = []
                colors = []
                for det in detections:
                    if det.embedding is not None:
                        result = self.recognizer.identify(det.embedding)
                        if result and result.is_match:
                            names.append(f"{result.person_name} ({result.similarity:.2f})")
                            colors.append((0, 255, 0))  # Green for known
                        else:
                            names.append("Unknown")
                            colors.append((0, 0, 255))  # Red for unknown
                        # Trigger alert callback for ALL detections (AlertManager handles filtering)
                        if self.alert_callback:
                            self.alert_callback(det, frame_data)
                    else:
                        names.append(f"{det.confidence:.2f}")
                        colors.append((255, 255, 0))  # Yellow for no embedding

                # Cache for smooth display
                self._last_detections = detections
                self._last_names = names
                self._last_colors = colors
            else:
                # No detections - clear cache
                self._last_detections = []
                self._last_names = []
                self._last_colors = []

        # Draw cached detections (even if no new detections this frame)
        if self._last_detections:
            frame_data.frame = self._draw_detections(
                frame_data.frame, self._last_detections, self._last_names, self._last_colors
            )

        return frame_data

    def draw_overlay(self, frame_data: FrameData) -> FrameData:
        """Draw cached detection boxes without running detection (fast)."""
        if frame_data.frame is None:
            return frame_data

        if self._last_detections:
            # Draw directly on frame (in-place) for maximum speed
            self._draw_detections_inplace(
                frame_data.frame, self._last_detections, self._last_names, self._last_colors
            )
        return frame_data

    def _draw_detections_inplace(
        self,
        image: np.ndarray,
        detections: List[FaceDetection],
        names: List[str],
        colors: List[tuple]
    ) -> None:
        """Draw detection boxes directly on image (in-place, no copy)."""
        for i, det in enumerate(detections):
            x, y, w, h = det.bbox
            color = colors[i] if i < len(colors) else (0, 255, 0)

            # Draw bounding box
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)

            # Draw label
            label = names[i] if i < len(names) else ""
            if label:
                (label_w, label_h), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )
                label_y = y - 10 if y > 30 else y + h + 20
                cv2.rectangle(
                    image,
                    (x, label_y - label_h - baseline - 5),
                    (x + label_w + 10, label_y + 5),
                    color, -1
                )
                cv2.putText(
                    image, label, (x + 5, label_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                )

    def _draw_detections(
        self,
        image: np.ndarray,
        detections: List[FaceDetection],
        names: List[str],
        colors: List[tuple]
    ) -> np.ndarray:
        """Draw detection boxes with custom colors (returns copy)."""
        output = image.copy()

        for i, det in enumerate(detections):
            x, y, w, h = det.bbox
            color = colors[i] if i < len(colors) else (0, 255, 0)

            # Draw bounding box
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # Draw label background
            label = names[i] if i < len(names) else ""
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            label_y = y - 10 if y > 30 else y + h + 20

            cv2.rectangle(
                output,
                (x, label_y - label_h - baseline - 5),
                (x + label_w + 10, label_y + 5),
                color, -1
            )

            # Draw label text
            cv2.putText(
                output, label, (x + 5, label_y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )

            # Draw landmarks if available
            if det.landmarks is not None:
                for lm in det.landmarks:
                    cv2.circle(output, (int(lm[0]), int(lm[1])), 2, (0, 255, 255), -1)

        return output


def create_frame_processor(
    detector: FaceDetector,
    recognizer: FaceRecognizer,
    alert_callback: Optional[Callable] = None
) -> Callable[[FrameData], FrameData]:
    """
    Create a frame processor function for the stream manager.

    Args:
        detector: Face detector instance
        recognizer: Face recognizer instance
        alert_callback: Optional callback for alerts

    Returns:
        Processor function compatible with StreamManager.set_processor()
    """
    processor = FrameProcessor(detector, recognizer, alert_callback)
    return processor.process
