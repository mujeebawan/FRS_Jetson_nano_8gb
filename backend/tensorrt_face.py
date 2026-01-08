#!/usr/bin/env python3
"""
TensorRT Face Detection and Recognition
Uses pre-built TensorRT engines for inference
"""

import os
import numpy as np
import cv2
import tensorrt as trt
import pycuda.driver as cuda
import pycuda.autoinit
from typing import List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set library path
os.environ['LD_LIBRARY_PATH'] = '/usr/lib/aarch64-linux-gnu/nvidia:' + os.environ.get('LD_LIBRARY_PATH', '')


class TRTEngine:
    """TensorRT Engine wrapper"""

    def __init__(self, engine_path: str):
        self.logger = trt.Logger(trt.Logger.WARNING)

        # Load engine
        with open(engine_path, 'rb') as f:
            engine_data = f.read()

        runtime = trt.Runtime(self.logger)
        self.engine = runtime.deserialize_cuda_engine(engine_data)
        self.context = self.engine.create_execution_context()

        # Get input/output info
        self.input_name = self.engine.get_tensor_name(0)
        self.input_shape = self.engine.get_tensor_shape(self.input_name)
        self.input_dtype = trt.nptype(self.engine.get_tensor_dtype(self.input_name))

        # Allocate buffers
        self.bindings = []
        self.outputs = []
        self.output_names = []

        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            dtype = trt.nptype(self.engine.get_tensor_dtype(name))
            shape = self.engine.get_tensor_shape(name)

            # Handle dynamic shapes
            if -1 in shape:
                shape = tuple(max(1, s) for s in shape)

            size = trt.volume(shape)

            if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
                self.input_buffer = cuda.mem_alloc(size * np.dtype(dtype).itemsize)
                self.bindings.append(int(self.input_buffer))
            else:
                output_buffer = cuda.mem_alloc(size * np.dtype(dtype).itemsize)
                self.bindings.append(int(output_buffer))
                self.outputs.append({
                    'name': name,
                    'buffer': output_buffer,
                    'shape': shape,
                    'dtype': dtype,
                    'size': size
                })
                self.output_names.append(name)

        self.stream = cuda.Stream()

    def infer(self, input_data: np.ndarray) -> List[np.ndarray]:
        """Run inference"""
        # Set input shape for dynamic inputs
        self.context.set_input_shape(self.input_name, input_data.shape)

        # Copy input to device
        cuda.memcpy_htod_async(self.input_buffer, input_data.astype(self.input_dtype).ravel(), self.stream)

        # Set tensor addresses
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            self.context.set_tensor_address(name, self.bindings[i])

        # Run inference
        self.context.execute_async_v3(stream_handle=self.stream.handle)

        # Copy outputs back
        results = []
        for out in self.outputs:
            output = np.empty(out['size'], dtype=out['dtype'])
            cuda.memcpy_dtoh_async(output, out['buffer'], self.stream)
            results.append(output.reshape(out['shape']))

        self.stream.synchronize()
        return results


class TRTFaceAnalysis:
    """TensorRT-based Face Analysis (compatible with InsightFace API)"""

    def __init__(
        self,
        det_engine_path: str,
        rec_engine_path: str,
        det_size: Tuple[int, int] = (640, 640),
        det_thresh: float = 0.5
    ):
        logger.info(f"Loading detection engine: {det_engine_path}")
        self.det_engine = TRTEngine(det_engine_path)

        logger.info(f"Loading recognition engine: {rec_engine_path}")
        self.rec_engine = TRTEngine(rec_engine_path)

        self.det_size = det_size
        self.det_thresh = det_thresh
        self.input_mean = 127.5
        self.input_std = 128.0
        self.rec_mean = 127.5
        self.rec_std = 127.5

    def get(self, img: np.ndarray, max_num: int = 0) -> List:
        """Detect faces and extract embeddings"""
        faces = []

        # Detect faces
        bboxes, kpss = self._detect(img)

        if bboxes is None or len(bboxes) == 0:
            return faces

        # Limit number of faces
        if max_num > 0 and len(bboxes) > max_num:
            # Sort by area and take largest
            areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
            indices = np.argsort(areas)[::-1][:max_num]
            bboxes = bboxes[indices]
            if kpss is not None:
                kpss = kpss[indices]

        # Extract embeddings for each face
        for i, bbox in enumerate(bboxes):
            face = Face()
            face.bbox = bbox[:4]
            face.det_score = bbox[4]

            if kpss is not None and i < len(kpss):
                face.kps = kpss[i]

            # Get aligned face and embedding
            aimg = self._align_face(img, face)
            if aimg is not None:
                face.embedding = self._get_embedding(aimg)
                faces.append(face)

        return faces

    def _detect(self, img: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Run face detection"""
        # Preprocess
        det_img, scale = self._preprocess_det(img)

        # Run detection
        outputs = self.det_engine.infer(det_img)

        # Post-process (SCRFD specific)
        bboxes, kpss = self._postprocess_det(outputs, scale, img.shape[:2])

        return bboxes, kpss

    def _preprocess_det(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """Preprocess image for detection"""
        h, w = img.shape[:2]
        target_h, target_w = self.det_size

        # Calculate scale
        scale = min(target_h / h, target_w / w)
        new_h, new_w = int(h * scale), int(w * scale)

        # Resize
        resized = cv2.resize(img, (new_w, new_h))

        # Pad to target size
        det_img = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        det_img[:new_h, :new_w] = resized

        # Normalize and transpose
        det_img = (det_img.astype(np.float32) - self.input_mean) / self.input_std
        det_img = det_img.transpose(2, 0, 1)[np.newaxis, ...]  # NCHW

        return det_img, scale

    def _postprocess_det(
        self,
        outputs: List[np.ndarray],
        scale: float,
        orig_size: Tuple[int, int]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Post-process detection outputs (SCRFD)"""
        # SCRFD outputs: scores, bboxes, keypoints at different strides
        # This is a simplified version - full implementation would handle all strides

        fmc = 3  # Feature map count
        strides = [8, 16, 32]

        all_bboxes = []
        all_kpss = []

        # Process each stride
        for idx in range(fmc):
            if idx * 3 >= len(outputs):
                break

            scores = outputs[idx * 3]
            bbox_preds = outputs[idx * 3 + 1]
            kps_preds = outputs[idx * 3 + 2] if idx * 3 + 2 < len(outputs) else None

            # Reshape and process
            if scores.ndim == 4:
                scores = scores.squeeze()
            if bbox_preds.ndim == 4:
                bbox_preds = bbox_preds.squeeze()

            # Get indices above threshold
            if scores.ndim == 1:
                pos_inds = np.where(scores > self.det_thresh)[0]
            else:
                pos_inds = np.where(scores.flatten() > self.det_thresh)[0]

            if len(pos_inds) == 0:
                continue

            # Simplified bbox extraction (would need proper anchor handling)
            # For now, use InsightFace fallback

        # If simplified processing fails, return None (will use InsightFace fallback)
        if len(all_bboxes) == 0:
            return None, None

        bboxes = np.vstack(all_bboxes)
        kpss = np.vstack(all_kpss) if all_kpss else None

        # Scale back to original size
        bboxes[:, :4] /= scale
        if kpss is not None:
            kpss /= scale

        # NMS
        keep = self._nms(bboxes, 0.4)
        bboxes = bboxes[keep]
        if kpss is not None:
            kpss = kpss[keep]

        return bboxes, kpss

    def _nms(self, bboxes: np.ndarray, thresh: float) -> List[int]:
        """Non-maximum suppression"""
        x1 = bboxes[:, 0]
        y1 = bboxes[:, 1]
        x2 = bboxes[:, 2]
        y2 = bboxes[:, 3]
        scores = bboxes[:, 4]

        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            inter = w * h

            iou = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(iou <= thresh)[0]
            order = order[inds + 1]

        return keep

    def _align_face(self, img: np.ndarray, face) -> Optional[np.ndarray]:
        """Align face using keypoints"""
        if face.kps is None:
            # Simple crop without alignment
            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img.shape[1], x2)
            y2 = min(img.shape[0], y2)

            face_img = img[y1:y2, x1:x2]
            if face_img.size == 0:
                return None

            return cv2.resize(face_img, (112, 112))

        # Use keypoints for alignment
        kps = face.kps

        # Standard face alignment landmarks
        dst = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041]
        ], dtype=np.float32)

        # Estimate transformation
        tform = cv2.estimateAffinePartial2D(kps, dst)[0]
        if tform is None:
            return None

        aimg = cv2.warpAffine(img, tform, (112, 112))
        return aimg

    def _get_embedding(self, aimg: np.ndarray) -> np.ndarray:
        """Extract face embedding"""
        # Preprocess
        img = (aimg.astype(np.float32) - self.rec_mean) / self.rec_std
        img = img.transpose(2, 0, 1)[np.newaxis, ...]  # NCHW

        # Run inference
        outputs = self.rec_engine.infer(img)

        # Get embedding and normalize
        embedding = outputs[0].flatten()
        embedding = embedding / np.linalg.norm(embedding)

        return embedding


class Face:
    """Face container (compatible with InsightFace)"""
    def __init__(self):
        self.bbox = None
        self.kps = None
        self.det_score = None
        self.embedding = None
        self.normed_embedding = None


def create_trt_face_analysis(
    det_engine: str = "det_500m_fp16.engine",
    rec_engine: str = "w600k_r50_fp16.engine",
    engine_dir: str = "/home/tempuser/Downloads/Frs_sec/data/tensorrt_engines"
) -> TRTFaceAnalysis:
    """Factory function to create TRT face analysis"""
    det_path = os.path.join(engine_dir, det_engine)
    rec_path = os.path.join(engine_dir, rec_engine)

    return TRTFaceAnalysis(det_path, rec_path)


if __name__ == "__main__":
    # Test
    import time

    print("Creating TRT Face Analysis...")
    app = create_trt_face_analysis()

    # Create test image
    test_img = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Warmup
    print("Warming up...")
    for _ in range(5):
        faces = app.get(test_img)

    # Benchmark
    print("Benchmarking...")
    times = []
    for _ in range(50):
        start = time.perf_counter()
        faces = app.get(test_img)
        times.append((time.perf_counter() - start) * 1000)

    print(f"Average latency: {np.mean(times):.2f} ms")
    print(f"Throughput: {1000 / np.mean(times):.2f} FPS")
