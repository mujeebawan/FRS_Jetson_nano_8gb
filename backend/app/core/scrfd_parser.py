"""
SCRFD Post-Processing for DeepStream nvinfer outputs.

Parses raw tensor outputs from SCRFD TensorRT engine and converts them
to face bounding boxes with landmarks.

SCRFD Output Format (9 tensors, 3 scales):
- Stride 8:  scores[N*12800,1], boxes[N*12800,4], kps[N*12800,10]
- Stride 16: scores[N*3200,1],  boxes[N*3200,4],  kps[N*3200,10]
- Stride 32: scores[N*800,1],   boxes[N*800,4],   kps[N*800,10]

Where N = batch size, and anchor counts are for 640x640 input.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


def sigmoid(x):
    """Numerically stable sigmoid function."""
    return np.where(
        x >= 0,
        1 / (1 + np.exp(-x)),
        np.exp(x) / (1 + np.exp(x))
    )


@dataclass
class SCRFDDetection:
    """Single face detection from SCRFD"""
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    landmarks: Optional[np.ndarray] = None  # 5x2 keypoints


class SCRFDParser:
    """
    Parser for SCRFD TensorRT outputs.

    Handles the 9 output tensors and converts them to face detections.
    Compatible with DeepStream nvinfer output-tensor-meta.
    """

    # SCRFD anchor configuration for 640x640 input
    STRIDES = [8, 16, 32]
    ANCHORS_PER_LOCATION = 2

    # Feature map sizes for 640x640 input
    FEAT_SIZES = {
        8: (80, 80),   # 640/8 = 80
        16: (40, 40),  # 640/16 = 40
        32: (20, 20),  # 640/32 = 20
    }

    # Anchors per stride for single batch
    ANCHORS_PER_STRIDE = {
        8: 80 * 80 * 2,   # 12800
        16: 40 * 40 * 2,  # 3200
        32: 20 * 20 * 2,  # 800
    }

    # Output tensor indices (in order from ONNX)
    # 448, 471, 494 = scores for stride 8, 16, 32
    # 451, 474, 497 = boxes for stride 8, 16, 32
    # 454, 477, 500 = keypoints for stride 8, 16, 32
    OUTPUT_ORDER = {
        'scores': [0, 1, 2],    # indices for scores at each stride
        'boxes': [3, 4, 5],     # indices for boxes at each stride
        'kps': [6, 7, 8],       # indices for keypoints at each stride
    }

    def __init__(
        self,
        input_size: Tuple[int, int] = (640, 640),
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4,
        max_detections: int = 100
    ):
        """
        Initialize SCRFD parser.

        Args:
            input_size: Model input size (width, height)
            confidence_threshold: Minimum confidence for detection
            nms_threshold: NMS IoU threshold
            max_detections: Maximum detections per image
        """
        self.input_size = input_size
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.max_detections = max_detections

        # Pre-compute anchor centers for each stride
        self._anchor_centers = {}
        self._generate_anchor_centers()

        logger.info(f"SCRFDParser initialized: input={input_size}, conf={confidence_threshold}, nms={nms_threshold}")

    def _generate_anchor_centers(self):
        """Pre-generate anchor center coordinates for each stride."""
        for stride in self.STRIDES:
            feat_h, feat_w = self.FEAT_SIZES[stride]

            # Generate grid
            y_centers = np.arange(feat_h) * stride + stride // 2
            x_centers = np.arange(feat_w) * stride + stride // 2

            # Create meshgrid
            xx, yy = np.meshgrid(x_centers, y_centers)

            # Flatten and repeat for anchors per location
            centers = np.stack([xx.flatten(), yy.flatten()], axis=1)
            centers = np.repeat(centers, self.ANCHORS_PER_LOCATION, axis=0)

            self._anchor_centers[stride] = centers.astype(np.float32)

    def parse_outputs(
        self,
        outputs: List[np.ndarray],
        batch_size: int = 1,
        original_size: Optional[Tuple[int, int]] = None
    ) -> List[List[SCRFDDetection]]:
        """
        Parse raw SCRFD outputs to detections.

        Args:
            outputs: List of 9 output tensors from TensorRT
            batch_size: Number of images in batch
            original_size: Original image size (width, height) for scaling

        Returns:
            List of detection lists, one per batch item
        """
        if len(outputs) != 9:
            logger.error(f"Expected 9 output tensors, got {len(outputs)}")
            return [[] for _ in range(batch_size)]

        # Scale factors if we need to map back to original size
        scale_x = 1.0
        scale_y = 1.0
        if original_size:
            scale_x = original_size[0] / self.input_size[0]
            scale_y = original_size[1] / self.input_size[1]

        all_detections = []

        for batch_idx in range(batch_size):
            batch_boxes = []
            batch_scores = []
            batch_kps = []

            for stride_idx, stride in enumerate(self.STRIDES):
                anchors_per_batch = self.ANCHORS_PER_STRIDE[stride]

                # Get outputs for this stride
                scores_idx = self.OUTPUT_ORDER['scores'][stride_idx]
                boxes_idx = self.OUTPUT_ORDER['boxes'][stride_idx]
                kps_idx = self.OUTPUT_ORDER['kps'][stride_idx]

                # Extract batch slice
                start = batch_idx * anchors_per_batch
                end = start + anchors_per_batch

                # Handle both 2D and flattened 1D arrays (DeepStream flattens)
                scores_arr = outputs[scores_idx]
                boxes_arr = outputs[boxes_idx]
                kps_arr = outputs[kps_idx]

                # Reshape if flattened
                if scores_arr.ndim == 1:
                    total_anchors = len(scores_arr)
                    scores_arr = scores_arr.reshape(-1, 1)
                if boxes_arr.ndim == 1:
                    boxes_arr = boxes_arr.reshape(-1, 4)
                if kps_arr.ndim == 1:
                    kps_arr = kps_arr.reshape(-1, 10)

                scores_raw = scores_arr[start:end, 0]  # [anchors]
                boxes = boxes_arr[start:end, :]    # [anchors, 4]
                kps = kps_arr[start:end, :]        # [anchors, 10]

                # Apply sigmoid to convert logits to probabilities
                scores = sigmoid(scores_raw)

                # Filter by confidence
                mask = scores > self.confidence_threshold
                if not np.any(mask):
                    continue

                scores = scores[mask]
                boxes = boxes[mask]
                kps = kps[mask]
                anchor_centers = self._anchor_centers[stride][mask]

                # Decode boxes: distance format (left, top, right, bottom) from anchor
                decoded_boxes = self._decode_boxes(boxes, anchor_centers, stride)

                # Decode keypoints
                decoded_kps = self._decode_keypoints(kps, anchor_centers, stride)

                batch_boxes.append(decoded_boxes)
                batch_scores.append(scores)
                batch_kps.append(decoded_kps)

            if not batch_boxes:
                all_detections.append([])
                continue

            # Concatenate all scales
            boxes = np.vstack(batch_boxes)
            scores = np.concatenate(batch_scores)
            kps = np.vstack(batch_kps)

            # Apply NMS
            keep_indices = self._nms(boxes, scores)

            # Limit detections
            keep_indices = keep_indices[:self.max_detections]

            # Create detection objects
            detections = []
            for idx in keep_indices:
                x1, y1, x2, y2 = boxes[idx]

                # Scale to original size
                x1 = int(x1 * scale_x)
                y1 = int(y1 * scale_y)
                x2 = int(x2 * scale_x)
                y2 = int(y2 * scale_y)

                # Scale keypoints
                landmarks = kps[idx].reshape(5, 2)
                landmarks[:, 0] *= scale_x
                landmarks[:, 1] *= scale_y

                det = SCRFDDetection(
                    bbox=(x1, y1, x2 - x1, y2 - y1),
                    confidence=float(scores[idx]),
                    landmarks=landmarks
                )
                detections.append(det)

            all_detections.append(detections)

        return all_detections

    def _decode_boxes(
        self,
        boxes: np.ndarray,
        anchor_centers: np.ndarray,
        stride: int
    ) -> np.ndarray:
        """
        Decode SCRFD box format to x1,y1,x2,y2.

        SCRFD uses distance from anchor center: (left, top, right, bottom)
        Box values are in log-space and need exp() transformation.
        """
        # boxes: [N, 4] as (left, top, right, bottom) distances in log-space
        # anchor_centers: [N, 2] as (cx, cy)

        # Apply exp() to convert from log-space to actual distances
        # Clip to prevent overflow
        boxes_exp = np.exp(np.clip(boxes, -10, 10))

        x1 = anchor_centers[:, 0] - boxes_exp[:, 0] * stride
        y1 = anchor_centers[:, 1] - boxes_exp[:, 1] * stride
        x2 = anchor_centers[:, 0] + boxes_exp[:, 2] * stride
        y2 = anchor_centers[:, 1] + boxes_exp[:, 3] * stride

        # Clip to input size
        x1 = np.clip(x1, 0, self.input_size[0])
        y1 = np.clip(y1, 0, self.input_size[1])
        x2 = np.clip(x2, 0, self.input_size[0])
        y2 = np.clip(y2, 0, self.input_size[1])

        return np.stack([x1, y1, x2, y2], axis=1)

    def _decode_keypoints(
        self,
        kps: np.ndarray,
        anchor_centers: np.ndarray,
        stride: int
    ) -> np.ndarray:
        """
        Decode SCRFD keypoint format.

        Keypoints are offsets from anchor center, scaled by stride.
        Unlike boxes, keypoints are direct offsets (not log-space).
        """
        # kps: [N, 10] as 5 pairs of (dx, dy) - direct offsets
        decoded = np.zeros_like(kps)

        for i in range(5):
            decoded[:, i*2] = anchor_centers[:, 0] + kps[:, i*2] * stride
            decoded[:, i*2+1] = anchor_centers[:, 1] + kps[:, i*2+1] * stride

        return decoded

    def _nms(
        self,
        boxes: np.ndarray,
        scores: np.ndarray
    ) -> List[int]:
        """
        Non-Maximum Suppression.

        Args:
            boxes: [N, 4] boxes as x1,y1,x2,y2
            scores: [N] confidence scores

        Returns:
            Indices of kept boxes
        """
        if len(boxes) == 0:
            return []

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        areas = (x2 - x1) * (y2 - y1)

        # Filter out zero or negative area boxes
        valid_mask = areas > 0
        if not np.any(valid_mask):
            return []

        # Get valid indices
        valid_indices = np.where(valid_mask)[0]
        areas = areas[valid_mask]
        scores_valid = scores[valid_mask]
        x1 = x1[valid_mask]
        y1 = y1[valid_mask]
        x2 = x2[valid_mask]
        y2 = y2[valid_mask]

        order = scores_valid.argsort()[::-1]

        keep = []
        while len(order) > 0:
            i = order[0]
            # Map back to original index
            keep.append(int(valid_indices[i]))

            if len(order) == 1:
                break

            # Compute IoU with remaining boxes
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            intersection = w * h
            union = areas[i] + areas[order[1:]] - intersection
            # Avoid division by zero
            iou = np.where(union > 0, intersection / union, 0)

            # Keep boxes with low IoU
            mask = iou <= self.nms_threshold
            order = order[1:][mask]

        return keep


def parse_deepstream_tensors(
    tensor_meta_list: list,
    batch_size: int,
    parser: SCRFDParser,
    original_size: Tuple[int, int]
) -> List[List[SCRFDDetection]]:
    """
    Parse DeepStream nvinfer output tensor metadata.

    Args:
        tensor_meta_list: List of NvDsInferTensorMeta from probe
        batch_size: Number of frames in batch
        parser: SCRFDParser instance
        original_size: Original frame size (width, height)

    Returns:
        Detections for each batch item
    """
    # Extract numpy arrays from tensor metadata
    outputs = []
    for tensor_meta in tensor_meta_list:
        # Get tensor data as numpy array
        tensor_data = np.ctypeslib.as_array(
            tensor_meta.out_buf_ptrs_host[0],
            shape=tensor_meta.dims.d[:tensor_meta.dims.numDims]
        )
        outputs.append(tensor_data.copy())

    return parser.parse_outputs(outputs, batch_size, original_size)
