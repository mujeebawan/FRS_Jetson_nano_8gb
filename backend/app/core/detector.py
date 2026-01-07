"""
Face Detector using SCRFD from InsightFace.
Optimized for Jetson Orin Nano 8GB with TensorRT FP16 acceleration.
"""

import cv2
import numpy as np
import logging
import os
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# TensorRT engine cache directory
TENSORRT_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'tensorrt_engines')


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
        model_name: str = None,  # Uses config if not specified
        min_confidence: float = 0.5,
        det_size: tuple = (640, 640),  # Full size for GPU processing
        use_gpu: bool = None,  # Uses config if not specified
        use_fp16: bool = None,  # Uses config if not specified
        use_tensorrt: bool = None,  # Uses config if not specified
        tensorrt_cache_dir: str = None
    ):
        """
        Initialize face detector.

        Args:
            model_name: InsightFace model pack (buffalo_s or buffalo_l)
            min_confidence: Minimum detection confidence threshold
            det_size: Detection input size
            use_gpu: Whether to use GPU acceleration
            use_fp16: Whether to use FP16 models (faster, lower memory)
            use_tensorrt: Whether to use TensorRT Execution Provider (10x speedup)
            tensorrt_cache_dir: Directory to cache TensorRT engines
        """
        # Get settings from config if not specified
        from ..config import settings
        base_model = model_name or settings.recognition_model
        use_gpu = use_gpu if use_gpu is not None else settings.use_gpu
        use_fp16 = use_fp16 if use_fp16 is not None else settings.use_fp16
        use_tensorrt = use_tensorrt if use_tensorrt is not None else settings.use_tensorrt

        self.min_confidence = min_confidence
        self.det_size = det_size
        self.use_gpu = use_gpu
        self.use_fp16 = use_fp16
        self.use_tensorrt = use_tensorrt
        self.tensorrt_cache_dir = tensorrt_cache_dir or TENSORRT_CACHE_DIR
        self._app = None
        self._initialized = False

        # Use FP16 model pack if available and enabled
        if use_fp16:
            fp16_model = f"{base_model}_fp16"
            fp16_path = os.path.expanduser(f"~/.insightface/models/{fp16_model}")
            if os.path.exists(fp16_path):
                self.model_name = fp16_model
                logger.info(f"Using FP16 models from {fp16_model}")
            else:
                self.model_name = base_model
                logger.info(f"FP16 models not found, using FP32: {base_model}")
        else:
            self.model_name = base_model

        # Ensure cache directory exists
        os.makedirs(self.tensorrt_cache_dir, exist_ok=True)

        logger.info(f"FaceDetector configured: model={self.model_name}, det_size={det_size}, GPU={use_gpu}, FP16={use_fp16}, TensorRT={use_tensorrt}")

    def _build_providers(self) -> list:
        """Build ONNX Runtime execution providers with optional TensorRT acceleration."""
        providers = []

        if self.use_gpu:
            if self.use_tensorrt:
                # TensorRT Execution Provider (10x faster than CUDA EP)
                # Uses FP16 internally for speed while accepting FP32 input
                trt_options = {
                    'device_id': 0,
                    'trt_fp16_enable': True,  # Use FP16 for faster inference
                    'trt_engine_cache_enable': True,  # Cache TRT engines
                    'trt_engine_cache_path': self.tensorrt_cache_dir,
                }
                providers.append(('TensorrtExecutionProvider', trt_options))
                logger.info(f"TensorRT EP enabled with FP16, cache: {self.tensorrt_cache_dir}")

            # CUDA provider (fallback if TensorRT enabled, primary otherwise)
            cuda_options = {
                'device_id': 0,
                'arena_extend_strategy': 'kNextPowerOfTwo',
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            }
            providers.append(('CUDAExecutionProvider', cuda_options))
            if not self.use_tensorrt:
                logger.info("CUDA EP enabled (TensorRT disabled)")

        # CPU fallback
        providers.append('CPUExecutionProvider')
        return providers

    def initialize(self) -> bool:
        """Initialize the detector model (lazy loading)."""
        if self._initialized:
            return True

        try:
            from insightface.app import FaceAnalysis

            providers = self._build_providers()
            logger.info(f"Initializing FaceAnalysis with providers: {[p[0] if isinstance(p, tuple) else p for p in providers]}")

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
            logger.info(f"FaceDetector initialized successfully (GPU={self.use_gpu}, FP16={self.use_fp16})")
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
