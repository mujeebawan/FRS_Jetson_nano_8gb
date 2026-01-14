"""
Direct TensorRT inference for face detection and recognition.
Bypasses ONNX Runtime for maximum performance on Jetson.
"""

import os
import time
import numpy as np
import tensorrt as trt
import pycuda.driver as cuda
# NOTE: Do NOT import pycuda.autoinit - context is managed by detection worker thread
from typing import List, Tuple, Optional
import cv2
import logging

logger = logging.getLogger(__name__)

# TensorRT logger
TRT_LOGGER = trt.Logger(trt.Logger.WARNING)


class TRTInference:
    """Base class for TensorRT inference."""

    def __init__(self, engine_path: str):
        """Load TensorRT engine from file."""
        self.engine_path = engine_path
        self.engine = None
        self.context = None
        self.bindings = []
        self.inputs = []
        self.outputs = []
        self.stream = None

        self._load_engine()

    def _load_engine(self):
        """Load the TensorRT engine."""
        if not os.path.exists(self.engine_path):
            raise FileNotFoundError(f"Engine not found: {self.engine_path}")

        runtime = trt.Runtime(TRT_LOGGER)
        with open(self.engine_path, 'rb') as f:
            self.engine = runtime.deserialize_cuda_engine(f.read())

        if self.engine is None:
            raise RuntimeError(f"Failed to load engine: {self.engine_path}")

        self.context = self.engine.create_execution_context()
        self.stream = cuda.Stream()

        # Allocate buffers with max size for dynamic shapes
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            shape = list(self.engine.get_tensor_shape(name))
            dtype = trt.nptype(self.engine.get_tensor_dtype(name))

            # Handle dynamic shapes - allocate based on tensor type
            is_input = self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT

            if is_input:
                # Input: max batch4 * 640*640*3 = ~5M elements
                max_elements = 4 * 640 * 640 * 3
            else:
                # Output: SCRFD batch4 has max 51200*10 = 512K per tensor
                max_elements = 512 * 1024

            host_mem = cuda.pagelocked_empty(max_elements, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            self.bindings.append(int(device_mem))

            if is_input:
                self.inputs.append({'name': name, 'host': host_mem, 'device': device_mem, 'shape': shape, 'dtype': dtype})
            else:
                self.outputs.append({'name': name, 'host': host_mem, 'device': device_mem, 'shape': shape, 'dtype': dtype})

        logger.info(f"Loaded TensorRT engine: {os.path.basename(self.engine_path)}")
        logger.info(f"  Inputs: {[(i['name'], i['shape']) for i in self.inputs]}")
        logger.info(f"  Outputs: {[(o['name'], o['shape']) for o in self.outputs]}")

    def __del__(self):
        """Cleanup CUDA memory."""
        pass  # pycuda handles cleanup


class SCRFDDetector(TRTInference):
    """SCRFD face detector using TensorRT."""

    def __init__(
        self,
        engine_path: str,
        input_size: Tuple[int, int] = (640, 640),
        conf_threshold: float = 0.3,
        nms_threshold: float = 0.4
    ):
        super().__init__(engine_path)
        self.input_size = input_size  # (width, height)
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold

        # SCRFD anchor strides
        self.feat_strides = [8, 16, 32]
        self.num_anchors = 2

        # Pre-compute anchor centers
        self._init_anchors()

    def _init_anchors(self):
        """Pre-compute anchor centers for all feature map scales."""
        self.anchor_centers = {}
        h, w = self.input_size[1], self.input_size[0]

        for stride in self.feat_strides:
            fh, fw = h // stride, w // stride
            y, x = np.meshgrid(np.arange(fh), np.arange(fw), indexing='ij')
            centers = np.stack([x.flatten(), y.flatten()], axis=1)
            centers = (centers * stride + stride // 2).astype(np.float32)
            # Repeat for num_anchors
            centers = np.repeat(centers, self.num_anchors, axis=0)
            self.anchor_centers[stride] = centers

    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """Preprocess image for SCRFD."""
        h, w = image.shape[:2]
        target_w, target_h = self.input_size

        # Calculate scale maintaining aspect ratio
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        # Resize
        resized = cv2.resize(image, (new_w, new_h))

        # Pad to target size
        padded = np.zeros((target_h, target_w, 3), dtype=np.float32)
        padded[:new_h, :new_w] = resized

        # Normalize and transpose
        padded = (padded - 127.5) / 128.0
        padded = padded.transpose(2, 0, 1)  # HWC -> CHW
        padded = np.expand_dims(padded, 0).astype(np.float32)  # Add batch dim

        return padded, scale, (0, 0)  # pad_x, pad_y both 0 for top-left padding

    def _postprocess(
        self,
        outputs: List[np.ndarray],
        scale: float,
        orig_size: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Post-process SCRFD outputs."""
        # SCRFD outputs: 9 tensors (3 scales x (scores, boxes, landmarks))
        # Order: score_8, score_16, score_32, bbox_8, bbox_16, bbox_32, kps_8, kps_16, kps_32

        all_scores = []
        all_boxes = []
        all_kps = []

        for i, stride in enumerate(self.feat_strides):
            # Get outputs for this scale
            scores = outputs[i].reshape(-1)
            boxes = outputs[i + 3].reshape(-1, 4)
            kps = outputs[i + 6].reshape(-1, 10) if len(outputs) > 6 else None

            # Get anchor centers for this stride
            anchor_centers = self.anchor_centers[stride]

            # Filter by confidence
            mask = scores > self.conf_threshold
            if not np.any(mask):
                continue

            scores = scores[mask]
            boxes = boxes[mask]
            anchor_centers = anchor_centers[mask]
            if kps is not None:
                kps = kps[mask]

            # Decode boxes: distance from anchor center
            # boxes are [left, top, right, bottom] distances
            x1 = anchor_centers[:, 0] - boxes[:, 0] * stride
            y1 = anchor_centers[:, 1] - boxes[:, 1] * stride
            x2 = anchor_centers[:, 0] + boxes[:, 2] * stride
            y2 = anchor_centers[:, 1] + boxes[:, 3] * stride

            # Scale back to original image
            x1 = x1 / scale
            y1 = y1 / scale
            x2 = x2 / scale
            y2 = y2 / scale

            boxes_decoded = np.stack([x1, y1, x2, y2, scores], axis=1)
            all_boxes.append(boxes_decoded)

            # Decode keypoints if available
            if kps is not None:
                kps_decoded = np.zeros((len(kps), 5, 2), dtype=np.float32)
                for j in range(5):
                    kps_decoded[:, j, 0] = (anchor_centers[:, 0] + kps[:, j*2] * stride) / scale
                    kps_decoded[:, j, 1] = (anchor_centers[:, 1] + kps[:, j*2+1] * stride) / scale
                all_kps.append(kps_decoded)

        if not all_boxes:
            return np.array([]), np.array([])

        all_boxes = np.vstack(all_boxes)
        all_kps = np.vstack(all_kps) if all_kps else np.array([])

        # NMS
        keep = self._nms(all_boxes, self.nms_threshold)
        boxes = all_boxes[keep]
        kps = all_kps[keep] if len(all_kps) > 0 else np.array([])

        return boxes, kps

    def _nms(self, boxes: np.ndarray, threshold: float) -> List[int]:
        """Non-maximum suppression."""
        if len(boxes) == 0:
            return []

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]
        scores = boxes[:, 4]

        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)

            if len(order) == 1:
                break

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            inter = w * h

            iou = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1]

        return keep

    def detect(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect faces in single image.

        Args:
            image: BGR image (H, W, 3)

        Returns:
            boxes: (N, 5) array of [x1, y1, x2, y2, score]
            keypoints: (N, 5, 2) array of facial landmarks
        """
        # Use batch detection with single image
        results = self.detect_batch([image])
        return results[0]

    def detect_batch(self, images: List[np.ndarray]) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Detect faces in multiple images with single batched inference.

        Args:
            images: List of BGR images (H, W, 3)

        Returns:
            List of (boxes, keypoints) tuples per image
        """
        if not images:
            return []

        batch_size = len(images)
        orig_sizes = [(img.shape[1], img.shape[0]) for img in images]
        scales = []

        # Preprocess all images
        batch_data = np.zeros((batch_size, 3, self.input_size[1], self.input_size[0]), dtype=np.float32)
        for i, image in enumerate(images):
            preprocessed, scale, _ = self._preprocess(image)
            batch_data[i] = preprocessed[0]  # Remove batch dim from single preprocess
            scales.append(scale)

        # Set input shape for batch
        input_shape = batch_data.shape
        self.context.set_input_shape(self.inputs[0]['name'], input_shape)

        # Copy input to device
        input_flat = batch_data.ravel()
        if len(self.inputs[0]['host']) < len(input_flat):
            self.inputs[0]['host'] = cuda.pagelocked_empty(len(input_flat), np.float32)
            self.inputs[0]['device'] = cuda.mem_alloc(len(input_flat) * 4)

        np.copyto(self.inputs[0]['host'][:len(input_flat)], input_flat)
        cuda.memcpy_htod_async(self.inputs[0]['device'], self.inputs[0]['host'][:len(input_flat)], self.stream)

        # Set tensor addresses
        for inp in self.inputs:
            self.context.set_tensor_address(inp['name'], int(inp['device']))
        for out in self.outputs:
            self.context.set_tensor_address(out['name'], int(out['device']))

        # Execute
        self.context.execute_async_v3(self.stream.handle)

        # Get outputs
        outputs = []
        for out in self.outputs:
            actual_shape = self.context.get_tensor_shape(out['name'])
            actual_size = int(np.prod(actual_shape))
            if actual_size > 0:
                cuda.memcpy_dtoh_async(out['host'][:actual_size], out['device'], self.stream)

        self.stream.synchronize()

        for out in self.outputs:
            actual_shape = self.context.get_tensor_shape(out['name'])
            actual_size = int(np.prod(actual_shape))
            if actual_size > 0:
                data = out['host'][:actual_size].copy().reshape(actual_shape)
            else:
                data = np.array([])
            outputs.append(data)

        # Postprocess per image
        results = []
        for img_idx in range(batch_size):
            boxes, kps = self._postprocess_batch_item(outputs, img_idx, batch_size, scales[img_idx], orig_sizes[img_idx])
            results.append((boxes, kps))

        return results

    def _postprocess_batch_item(
        self,
        outputs: List[np.ndarray],
        img_idx: int,
        batch_size: int,
        scale: float,
        orig_size: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Post-process SCRFD outputs for one image in batch."""
        all_boxes = []
        all_kps = []

        # Anchors per image at each scale
        anchors_per_scale = [len(self.anchor_centers[s]) for s in self.feat_strides]

        for i, stride in enumerate(self.feat_strides):
            n_anchors = anchors_per_scale[i]

            # Extract this image's portion from batched output
            # Output shape is (batch*n_anchors, channels)
            start_idx = img_idx * n_anchors
            end_idx = start_idx + n_anchors

            scores = outputs[i][start_idx:end_idx].flatten()
            boxes = outputs[i + 3][start_idx:end_idx]
            kps = outputs[i + 6][start_idx:end_idx]

            if len(scores) == 0:
                continue

            mask = scores > self.conf_threshold
            if not np.any(mask):
                continue

            scores = scores[mask]
            boxes = boxes[mask]
            kps = kps[mask] if len(kps) > 0 else np.array([])
            anchor_centers = self.anchor_centers[stride][mask]

            # Decode boxes
            x1 = anchor_centers[:, 0] - boxes[:, 0] * stride
            y1 = anchor_centers[:, 1] - boxes[:, 1] * stride
            x2 = anchor_centers[:, 0] + boxes[:, 2] * stride
            y2 = anchor_centers[:, 1] + boxes[:, 3] * stride

            # Scale back
            x1, y1, x2, y2 = x1 / scale, y1 / scale, x2 / scale, y2 / scale

            boxes_scaled = np.stack([x1, y1, x2, y2, scores], axis=1)
            all_boxes.append(boxes_scaled)

            if len(kps) > 0:
                kps_scaled = np.zeros((len(kps), 5, 2), dtype=np.float32)
                for j in range(5):
                    kps_scaled[:, j, 0] = (anchor_centers[:, 0] + kps[:, j * 2] * stride) / scale
                    kps_scaled[:, j, 1] = (anchor_centers[:, 1] + kps[:, j * 2 + 1] * stride) / scale
                all_kps.append(kps_scaled)

        if not all_boxes:
            return np.array([]), np.array([])

        all_boxes = np.vstack(all_boxes)
        all_kps = np.vstack(all_kps) if all_kps else np.array([])

        # NMS
        if len(all_boxes) > 0:
            keep = self._nms(all_boxes, self.nms_threshold)
            all_boxes = all_boxes[keep]
            all_kps = all_kps[keep] if len(all_kps) > 0 else np.array([])

        return all_boxes, all_kps

class ArcFaceRecognizer(TRTInference):
    """ArcFace face recognizer using TensorRT with batched inference."""

    def __init__(self, engine_path: str, batch_size: int = 32):
        # w600k_r50_batch32_fp16.engine has profile [1,3,112,112]..[32,3,112,112]
        # Optimal batch is 16, max is 32
        self.batch_size = batch_size
        super().__init__(engine_path)

    def _align_face(self, image: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """Align face using 5-point landmarks."""
        # Reference landmarks for 112x112 face
        ref_pts = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)

        # Estimate affine transform
        kps = kps.astype(np.float32)
        M = cv2.estimateAffinePartial2D(kps, ref_pts, method=cv2.LMEDS)[0]

        if M is None:
            # Fallback: simple crop and resize
            x1, y1 = kps.min(axis=0) - 20
            x2, y2 = kps.max(axis=0) + 20
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(image.shape[1], int(x2)), min(image.shape[0], int(y2))
            face = image[y1:y2, x1:x2]
            aligned = cv2.resize(face, (112, 112))
        else:
            aligned = cv2.warpAffine(image, M, (112, 112))

        return aligned

    def _preprocess_batch(self, faces: List[np.ndarray]) -> np.ndarray:
        """Preprocess batch of aligned face images."""
        batch = np.zeros((len(faces), 3, 112, 112), dtype=np.float32)

        for i, face in enumerate(faces):
            # BGR -> RGB, normalize
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            face = (face.astype(np.float32) - 127.5) / 127.5
            face = face.transpose(2, 0, 1)  # HWC -> CHW
            batch[i] = face

        return batch

    def get_embeddings(self, image: np.ndarray, keypoints: np.ndarray) -> np.ndarray:
        """
        Extract embeddings for multiple faces in one batched inference call.

        Args:
            image: Original BGR image
            keypoints: (N, 5, 2) array of facial landmarks

        Returns:
            embeddings: (N, 512) array of normalized embeddings
        """
        if len(keypoints) == 0:
            return np.array([])

        # Align faces
        aligned_faces = []
        for kps in keypoints:
            aligned = self._align_face(image, kps)
            aligned_faces.append(aligned)

        # Process in batches
        all_embeddings = []

        for batch_start in range(0, len(aligned_faces), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(aligned_faces))
            batch_faces = aligned_faces[batch_start:batch_end]

            # Preprocess batch
            input_batch = self._preprocess_batch(batch_faces)

            # Set dynamic batch size
            input_shape = (len(batch_faces), 3, 112, 112)
            self.context.set_input_shape(self.inputs[0]['name'], input_shape)

            # Reallocate output buffer if needed
            output_size = len(batch_faces) * 512
            if len(self.outputs[0]['host']) < output_size:
                self.outputs[0]['host'] = cuda.pagelocked_empty(output_size, np.float32)
                self.outputs[0]['device'] = cuda.mem_alloc(output_size * 4)

            # Copy input to device
            input_flat = input_batch.ravel().astype(np.float32)
            if len(self.inputs[0]['host']) < len(input_flat):
                self.inputs[0]['host'] = cuda.pagelocked_empty(len(input_flat), np.float32)
                self.inputs[0]['device'] = cuda.mem_alloc(len(input_flat) * 4)

            np.copyto(self.inputs[0]['host'][:len(input_flat)], input_flat)
            cuda.memcpy_htod_async(self.inputs[0]['device'], self.inputs[0]['host'][:len(input_flat)], self.stream)

            # Set tensor addresses
            for inp in self.inputs:
                self.context.set_tensor_address(inp['name'], int(inp['device']))
            for out in self.outputs:
                self.context.set_tensor_address(out['name'], int(out['device']))

            # Execute
            self.context.execute_async_v3(self.stream.handle)

            # Copy output
            cuda.memcpy_dtoh_async(self.outputs[0]['host'][:output_size], self.outputs[0]['device'], self.stream)
            self.stream.synchronize()

            # Extract embeddings
            batch_embeddings = self.outputs[0]['host'][:output_size].reshape(-1, 512).copy()

            # Normalize
            norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
            batch_embeddings = batch_embeddings / (norms + 1e-10)

            all_embeddings.append(batch_embeddings)

        return np.vstack(all_embeddings) if all_embeddings else np.array([])


class TRTFaceProcessor:
    """
    Combined face detection + recognition using TensorRT.
    DeepStream handles video decoding, this handles AI inference.
    """

    def __init__(
        self,
        detector_engine: str,
        recognizer_engine: str,
        det_size: Tuple[int, int] = (640, 640),
        conf_threshold: float = 0.5,
        batch_size: int = 32
    ):
        logger.info("Initializing TensorRT Face Processor...")

        self.detector = SCRFDDetector(
            detector_engine,
            input_size=det_size,
            conf_threshold=conf_threshold
        )

        self.recognizer = ArcFaceRecognizer(
            recognizer_engine,
            batch_size=batch_size
        )

        logger.info("TensorRT Face Processor ready")

    def process(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Process image: detect faces and extract embeddings.

        Args:
            image: BGR image

        Returns:
            boxes: (N, 5) [x1, y1, x2, y2, score]
            keypoints: (N, 5, 2) facial landmarks
            embeddings: (N, 512) normalized embeddings
        """
        # Detection
        det_start = time.time()
        boxes, kps = self.detector.detect(image)
        det_time = (time.time() - det_start) * 1000

        if len(boxes) == 0:
            return np.array([]), np.array([]), np.array([])

        # Recognition (batched)
        rec_start = time.time()
        embeddings = self.recognizer.get_embeddings(image, kps)
        rec_time = (time.time() - rec_start) * 1000

        logger.debug(f"TRT: {len(boxes)} faces - Det:{det_time:.1f}ms Rec:{rec_time:.1f}ms")

        return boxes, kps, embeddings


# Test function
if __name__ == "__main__":
    import sys

    # Engine paths
    PROJECT_ROOT = '/home/tempuser/Downloads/Frs_sec'
    DET_ENGINE = os.path.join(PROJECT_ROOT, 'data/tensorrt_engines/det_10g_fp16.engine')
    REC_ENGINE = os.path.join(PROJECT_ROOT, 'data/tensorrt_engines/w600k_r50_fp16.engine')

    print("Testing TensorRT Face Processor...")
    print(f"  Detector: {DET_ENGINE}")
    print(f"  Recognizer: {REC_ENGINE}")

    processor = TRTFaceProcessor(DET_ENGINE, REC_ENGINE)

    # Test image
    test_img = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

    # Warmup
    print("\nWarmup...")
    for _ in range(5):
        processor.process(test_img)

    # Timing
    print("\nTiming (10 runs)...")
    times = []
    for i in range(10):
        start = time.time()
        boxes, kps, emb = processor.process(test_img)
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.1f}ms, {len(boxes)} faces")

    print(f"\nAverage: {np.mean(times):.1f}ms")
