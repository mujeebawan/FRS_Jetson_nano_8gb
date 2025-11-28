"""
Face Detector using SCRFD from InsightFace.
Optimized for Jetson Orin Nano 8GB.
"""

import cv2
import numpy as np
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    """Face detection result"""
    bbox: tuple  # (x, y, width, height)
    confidence: float
    landmarks: Optional[np.ndarray] = None  # 5 facial keypoints
    embedding: Optional[np.ndarray] = None  # 512-D vector (if extracted)


class FaceDetector:
    """
    Face detector using SCRFD from InsightFace.
    Uses SCRFD_2.5G_KPS for optimal balance on Jetson Orin Nano 8GB.
    """

    def __init__(
        self,
        model_name: str = "buffalo_s",
        min_confidence: float = 0.5,
        det_size: tuple = (640, 640),
        use_gpu: bool = True
    ):
        """
        Initialize face detector.

        Args:
            model_name: InsightFace model pack (buffalo_s recommended for 8GB)
            min_confidence: Minimum detection confidence threshold
            det_size: Detection input size
            use_gpu: Whether to use GPU acceleration
        """
        self.min_confidence = min_confidence
        self.det_size = det_size
        self.model_name = model_name
        self._app = None
        self._initialized = False
        self.use_gpu = use_gpu

        logger.info(f"FaceDetector configured: model={model_name}, det_size={det_size}")

    def initialize(self) -> bool:
        """Initialize the detector model (lazy loading)."""
        if self._initialized:
            return True

        try:
            from insightface.app import FaceAnalysis

            providers = []
            if self.use_gpu:
                providers.append(('CUDAExecutionProvider', {
                    'device_id': 0,
                    'arena_extend_strategy': 'kNextPowerOfTwo',
                    'cudnn_conv_algo_search': 'DEFAULT',  # EXHAUSTIVE uses more memory
                    'do_copy_in_default_stream': True,
                }))
            providers.append('CPUExecutionProvider')

            self._app = FaceAnalysis(
                name=self.model_name,
                providers=providers
            )

            self._app.prepare(
                ctx_id=0 if self.use_gpu else -1,
                det_size=self.det_size,
                det_thresh=self.min_confidence
            )

            self._initialized = True
            logger.info(f"FaceDetector initialized successfully (GPU={self.use_gpu})")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize FaceDetector: {e}")
            return False

    def detect(self, image: np.ndarray, extract_embedding: bool = False) -> List[FaceDetection]:
        """
        Detect faces in image.

        Args:
            image: BGR image from OpenCV
            extract_embedding: Also extract face embeddings

        Returns:
            List of FaceDetection objects
        """
        if not self._initialized:
            if not self.initialize():
                return []

        if image is None or image.size == 0:
            return []

        try:
            faces = self._app.get(image)
            detections = []

            height, width = image.shape[:2]

            for face in faces:
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox

                # Clamp to image bounds
                x = max(0, x1)
                y = max(0, y1)
                w = min(x2 - x1, width - x)
                h = min(y2 - y1, height - y)

                detection = FaceDetection(
                    bbox=(x, y, w, h),
                    confidence=float(face.det_score),
                    landmarks=face.kps if hasattr(face, 'kps') else None,
                    embedding=face.embedding if extract_embedding and hasattr(face, 'embedding') else None
                )
                detections.append(detection)

            logger.debug(f"Detected {len(detections)} face(s)")
            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def detect_with_embeddings(self, image: np.ndarray) -> List[FaceDetection]:
        """Detect faces and extract embeddings in one pass."""
        return self.detect(image, extract_embedding=True)

    def crop_face(
        self,
        image: np.ndarray,
        detection: FaceDetection,
        padding: float = 0.2
    ) -> Optional[np.ndarray]:
        """
        Crop face region with padding.

        Args:
            image: Source image
            detection: Face detection result
            padding: Padding ratio (0.2 = 20%)

        Returns:
            Cropped face image or None
        """
        if image is None:
            return None

        x, y, w, h = detection.bbox
        height, width = image.shape[:2]

        pad_w = int(w * padding)
        pad_h = int(h * padding)

        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(width, x + w + pad_w)
        y2 = min(height, y + h + pad_h)

        crop = image[y1:y2, x1:x2]
        return crop if crop.size > 0 else None

    def draw_detections(
        self,
        image: np.ndarray,
        detections: List[FaceDetection],
        names: Optional[List[str]] = None,
        draw_landmarks: bool = False
    ) -> np.ndarray:
        """
        Draw detection boxes and optional labels on image.

        Args:
            image: Source image
            detections: List of detections
            names: Optional list of names for each detection
            draw_landmarks: Whether to draw facial landmarks

        Returns:
            Annotated image
        """
        output = image.copy()

        for i, det in enumerate(detections):
            x, y, w, h = det.bbox
            color = (0, 255, 0)  # Green for known, red for unknown

            # Draw bounding box
            cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)

            # Draw label
            if names and i < len(names):
                label = f"{names[i]} ({det.confidence:.2f})"
            else:
                label = f"{det.confidence:.2f}"

            label_y = y - 10 if y > 20 else y + h + 20
            cv2.putText(output, label, (x, label_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Draw landmarks
            if draw_landmarks and det.landmarks is not None:
                for lm in det.landmarks:
                    cv2.circle(output, (int(lm[0]), int(lm[1])), 2, (0, 0, 255), -1)

        return output
