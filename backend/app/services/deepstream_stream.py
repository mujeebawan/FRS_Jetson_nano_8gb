"""
DeepStream Stream Manager - Replaces OpenCV-based stream.py
Uses DeepStream for H264 decode + Direct TensorRT for face detection/recognition.

Features:
- Hardware-accelerated H264 decoding via nvv4l2decoder
- Direct TensorRT detection (SCRFD) - ~15-20ms
- Batched TensorRT recognition (ArcFace batch32) - ~3ms/face
- FAISS batch matching for recognition
- Multi-client WebSocket/MJPEG broadcasting
- Database-driven camera configuration
"""

import os
import sys
import logging
import threading
import asyncio
import time
import ctypes
from typing import Optional, Callable, List, Set, Any, Tuple, Dict, TYPE_CHECKING
from dataclasses import dataclass
from queue import Queue, Empty
import numpy as np
import cv2

if TYPE_CHECKING:
    from ..models.database import Camera

# DeepStream environment
DS_PATH = '/opt/nvidia/deepstream/deepstream-7.1'
os.environ['LD_LIBRARY_PATH'] = f'{DS_PATH}/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

try:
    import pyds
    PYDS_AVAILABLE = True
    print("INFO: DeepStream enabled with PGIE+SGIE pipeline")
except ImportError:
    PYDS_AVAILABLE = False
    print("WARNING: pyds not available - DeepStream disabled")

from ..config import settings
from ..core.scrfd_parser import SCRFDParser
from ..core.recognizer import FaceRecognizer

# TensorRT inference engines (use realpath to handle ./  in path)
_THIS_FILE = os.path.realpath(__file__)
TRT_ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE)))), 'data', 'tensorrt_engines')
DET_ENGINE = os.path.join(TRT_ENGINE_DIR, 'det_10g_fp16.engine')
REC_ENGINE = os.path.join(TRT_ENGINE_DIR, 'w600k_r50_batch32_fp16.engine')

# Import TRT process manager (runs TensorRT in separate process)
from .trt_process import TRTProcessManager, DetectionResult

logger = logging.getLogger(__name__)

# Config paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'configs', 'deepstream')
PGIE_CONFIG = os.path.join(CONFIG_DIR, 'scrfd_nvinfer_config.txt')
SGIE_CONFIG = os.path.join(CONFIG_DIR, 'arcface_sgie_config.txt')


@dataclass
class FrameData:
    """Container for a video frame with metadata"""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    camera_id: int = 0
    has_faces: bool = False


@dataclass
class FaceResult:
    """Face detection and recognition result"""
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float
    embedding: Optional[np.ndarray] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    similarity: float = 0.0
    is_known: bool = False
    camera_id: int = 0


class DeepStreamManager:
    """
    DeepStream-based stream manager with face detection/recognition.
    Supports multiple cameras in a single pipeline.
    """

    def __init__(
        self,
        cameras: List["Camera"] = None,
        camera: "Camera" = None,  # Single camera fallback
        frame_skip: int = 0,
        max_clients: int = 10,
        recognizer: FaceRecognizer = None,
        alert_callback: Optional[Callable] = None
    ):
        """
        Initialize DeepStream manager.

        Args:
            cameras: List of Camera model instances (multi-camera)
            camera: Single camera fallback for backwards compatibility
            frame_skip: Detection interval (0 = every frame)
            max_clients: Maximum concurrent viewers
            recognizer: FaceRecognizer for FAISS matching
            alert_callback: Callback for face detection alerts
        """
        if not PYDS_AVAILABLE:
            raise RuntimeError("DeepStream Python bindings (pyds) required")

        # Support both single camera and multi-camera
        if cameras:
            self._cameras = cameras
        elif camera:
            self._cameras = [camera]
        else:
            self._cameras = []

        self._camera = self._cameras[0] if self._cameras else None
        self._camera_id = self._camera.id if self._camera else 0
        self._num_cameras = len(self._cameras)

        self.frame_skip = frame_skip
        self.max_clients = max_clients
        self.recognizer = recognizer
        self.alert_callback = alert_callback

        # Pipeline state
        self.pipeline = None
        self.loop = None
        self._running = False
        self._lock = threading.Lock()

        # Frame distribution (per camera)
        self._latest_frames: Dict[int, FrameData] = {}
        self._latest_frame: Optional[FrameData] = None
        self._latest_raw_frame: Optional[FrameData] = None
        self._frame_number = 0
        self._subscribers: Set[asyncio.Queue] = set()

        # Detection cache for overlay
        self._last_faces: List[FaceResult] = []

        # TensorRT process manager (separate process to avoid CUDA context conflicts)
        self._trt_process: Optional[TRTProcessManager] = None
        self._detection_interval = max(1, frame_skip + 1)
        self._last_detection_frame = 0

        # Result polling thread (checks for detection results from child process)
        self._result_thread = None
        self._result_running = False

        # Timing stats
        self._last_timing = {'detection': 0, 'recognition': 0, 'faiss': 0, 'total': 0, 'faces': 0}

        # Tiler configuration for per-camera frame extraction
        self._tiler_cols = min(self._num_cameras, 2) if self._num_cameras > 0 else 1
        self._tiler_rows = (self._num_cameras + self._tiler_cols - 1) // self._tiler_cols if self._num_cameras > 0 else 1
        self._tile_width = 960
        self._tile_height = 540

        # Stats (per camera)
        self._fps = 0.0
        self._fps_per_camera: Dict[int, float] = {i: 0.0 for i in range(len(self._cameras))}
        self._frame_count_per_camera: Dict[int, int] = {i: 0 for i in range(len(self._cameras))}
        self._faces_per_camera: Dict[int, int] = {i: 0 for i in range(len(self._cameras))}
        self._last_fps_time = time.time()
        self._fps_frame_count = 0
        self._faces_detected = 0
        self._faces_matched = 0

        # Initialize GStreamer
        if not Gst.is_initialized():
            Gst.init(None)

        cam_names = [c.name for c in self._cameras] if self._cameras else ['none']
        logger.info(f"DeepStreamManager initialized: {self._num_cameras} cameras - {cam_names}")

    def _create_element(self, factory: str, name: str):
        """Create GStreamer element."""
        elem = Gst.ElementFactory.make(factory, name)
        if not elem:
            raise RuntimeError(f"Failed to create element: {factory}")
        return elem

    def _create_pipeline(self) -> bool:
        """Create DeepStream pipeline with multi-camera support."""
        try:
            self.pipeline = Gst.Pipeline.new("deepstream-face-pipeline")

            # Stream muxer for batching multiple cameras
            streammux = self._create_element("nvstreammux", "muxer")
            streammux.set_property("batch-size", max(1, self._num_cameras))
            streammux.set_property("width", 640)
            streammux.set_property("height", 640)
            streammux.set_property("batched-push-timeout", 40000)
            streammux.set_property("live-source", True)
            self.pipeline.add(streammux)

            # Create source chain for each camera
            self._sources = {}
            for i, cam in enumerate(self._cameras):
                # Source: RTSP stream
                source = self._create_element("rtspsrc", f"source_{i}")
                source.set_property("location", cam.rtsp_url)
                source.set_property("latency", 100)
                source.set_property("drop-on-latency", True)

                # Depay and parse
                depay = self._create_element("rtph264depay", f"depay_{i}")
                parser = self._create_element("h264parse", f"parser_{i}")

                # Hardware decoder
                decoder = self._create_element("nvv4l2decoder", f"decoder_{i}")
                decoder.set_property("enable-max-performance", True)

                # Add elements
                for elem in [source, depay, parser, decoder]:
                    self.pipeline.add(elem)

                # Link source to depay (dynamic pad)
                source.connect("pad-added", self._on_pad_added, depay)

                # Link static elements
                depay.link(parser)
                parser.link(decoder)

                # Link decoder to streammux
                decoder_src = decoder.get_static_pad("src")
                mux_sink = streammux.request_pad_simple(f"sink_{i}")
                decoder_src.link(mux_sink)

                self._sources[i] = {"source": source, "camera": cam}
                logger.info(f"Added camera {i}: {cam.name} ({cam.ip_address})")

            # NOTE: PGIE disabled - using InsightFace for detection/recognition
            # DeepStream PGIE with custom network-type=100 has caps negotiation issues

            # Multi-stream tiler (combines batched frames into single tiled output)
            tiler = self._create_element("nvmultistreamtiler", "tiler")
            tiler_cols = min(self._num_cameras, 2)
            tiler_rows = (self._num_cameras + tiler_cols - 1) // tiler_cols
            tiler.set_property("rows", tiler_rows)
            tiler.set_property("columns", tiler_cols)
            tiler_width = 960 * tiler_cols
            tiler_height = 540 * tiler_rows
            tiler.set_property("width", tiler_width)
            tiler.set_property("height", tiler_height)
            logger.info(f"Tiler: {tiler_cols}x{tiler_rows} grid, {tiler_width}x{tiler_height}")

            # Video converter (GPU compute mode) - OSD removed, drawing in Python
            nvvidconv = self._create_element("nvvideoconvert", "convertor")
            nvvidconv.set_property("compute-hw", 1)

            capsfilter = self._create_element("capsfilter", "capsfilter")
            caps = Gst.Caps.from_string("video/x-raw, format=BGR")
            capsfilter.set_property("caps", caps)

            # Appsink for frame access
            appsink = self._create_element("appsink", "appsink")
            appsink.set_property("emit-signals", True)
            appsink.set_property("sync", False)
            appsink.set_property("max-buffers", 2 * self._num_cameras)
            appsink.set_property("drop", True)
            appsink.connect("new-sample", self._on_new_sample)

            # Add all elements (decode-only pipeline, detection via InsightFace)
            for elem in [tiler, nvvidconv, capsfilter, appsink]:
                self.pipeline.add(elem)

            # Link pipeline: mux -> tiler -> convert -> caps -> appsink
            # OSD removed - we draw overlays in Python for flexibility
            if not streammux.link(tiler):
                raise RuntimeError("Failed to link streammux -> tiler")
            if not tiler.link(nvvidconv):
                raise RuntimeError("Failed to link tiler -> nvvidconv")
            if not nvvidconv.link(capsfilter):
                raise RuntimeError("Failed to link nvvidconv -> capsfilter")
            if not capsfilter.link(appsink):
                raise RuntimeError("Failed to link capsfilter -> appsink")

            logger.info("DeepStream pipeline created successfully")
            return True

        except Exception as e:
            logger.error(f"Pipeline creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _result_worker(self):
        """
        Worker thread that polls for detection results from TRT child process.
        Runs in main process, just checks the output queue.
        """
        logger.info("Result polling worker started")

        while self._result_running:
            try:
                # Check for results from TRT process (non-blocking)
                if self._trt_process and self._trt_process.is_running:
                    result = self._trt_process.get_result(timeout=0.05)
                    if result:
                        self._process_detection_result(result)
                else:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Result worker error: {e}")
                time.sleep(0.1)

        logger.info("Result polling worker stopped")

    def _process_detection_result(self, result: DetectionResult):
        """Process detection result from TRT child process."""
        t_faiss = 0.0
        faiss_start = time.time()

        new_faces = []
        embeddings_list = []

        # Build face results from detection
        for i, bbox in enumerate(result.boxes):
            x1, y1, x2, y2, score = bbox[:5]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

            embedding = result.embeddings[i] if i < len(result.embeddings) else None

            face_result = FaceResult(
                bbox=(x1, y1, x2 - x1, y2 - y1),
                confidence=float(score),
                embedding=embedding,
                person_name=None,
                similarity=0.0
            )
            new_faces.append(face_result)
            if embedding is not None:
                embeddings_list.append(embedding)

        # FAISS Matching (batch) - runs in main process
        if embeddings_list and self.recognizer:
            embeddings_array = np.array(embeddings_list, dtype=np.float32)
            results = self.recognizer.batch_match(embeddings_array)

            for i, face_result in enumerate(new_faces):
                if face_result.embedding is not None and i < len(results):
                    match = results[i]
                    if match and match.is_match:
                        face_result.person_name = match.person_name
                        face_result.similarity = match.similarity
                        face_result.is_known = True

                if self.alert_callback:
                    self._trigger_alert(face_result)

        t_faiss = (time.time() - faiss_start) * 1000
        total_time = result.detection_time + result.recognition_time + t_faiss

        # Log timing periodically
        if result.frame_num <= 10 or result.frame_num % 100 == 0:
            print(f"[TRT-PROC] Frame #{result.frame_num}: {len(new_faces)} faces", flush=True)
            print(f"  Detection:    {result.detection_time:5.1f}ms", flush=True)
            print(f"  Recognition:  {result.recognition_time:5.1f}ms", flush=True)
            print(f"  FAISS:        {t_faiss:5.1f}ms", flush=True)
            print(f"  TOTAL:        {total_time:5.1f}ms", flush=True)

        # Update state
        self._last_faces = new_faces
        self._faces_detected += len(new_faces)
        self._last_timing = {
            'detection': result.detection_time,
            'recognition': result.recognition_time,
            'faiss': t_faiss,
            'total': total_time,
            'faces': len(new_faces)
        }

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        """Draw bounding boxes and labels on frame."""
        for face in self._last_faces:
            x, y, w, h = face.bbox
            color = (0, 255, 0) if face.is_known else (0, 0, 255)  # Green if known, red if unknown
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # Draw label
            if face.person_name:
                label = f"{face.person_name} ({face.similarity:.2f})"
            else:
                label = "Unknown"

            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return frame

    def _on_pad_added(self, src, pad, depay):
        """Handle dynamic pad from rtspsrc."""
        caps = pad.get_current_caps()
        struct = caps.get_structure(0)
        if struct.get_name().startswith("application/x-rtp"):
            sink_pad = depay.get_static_pad("sink")
            if not sink_pad.is_linked():
                pad.link(sink_pad)

    def _on_new_sample(self, appsink):
        """Handle new frame from appsink."""
        # Debug: print sample count periodically
        self._sample_count = getattr(self, '_sample_count', 0) + 1
        if self._sample_count == 1 or self._sample_count % 500 == 0:
            print(f"[STREAM] Sample #{self._sample_count}, FPS: {self._fps:.1f}", flush=True)

        sample = appsink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.OK

        buf = sample.get_buffer()
        caps = sample.get_caps()

        # Get frame dimensions
        struct = caps.get_structure(0)
        width = struct.get_int("width")[1]
        height = struct.get_int("height")[1]

        # Map buffer and copy to numpy
        success, map_info = buf.map(Gst.MapFlags.READ)
        if success:
            frame = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()
            buf.unmap(map_info)

            self._frame_number += 1
            timestamp = time.time()

            # Store raw frame before overlays
            raw_frame = frame.copy()

            # Submit frame to TRT process for detection
            should_detect = (self._frame_number - self._last_detection_frame >= self._detection_interval)
            if should_detect and self._trt_process and self._trt_process.is_running:
                if self._trt_process.submit_frame(raw_frame, self._frame_number):
                    self._last_detection_frame = self._frame_number

            # Draw overlays from last detection results
            display_frame = self._draw_overlays(frame)

            frame_data = FrameData(
                frame=display_frame,
                timestamp=timestamp,
                frame_number=self._frame_number,
                camera_id=self._camera_id,
                has_faces=len(self._last_faces) > 0
            )

            # Store latest frames
            with self._lock:
                self._latest_frame = frame_data
                self._latest_raw_frame = FrameData(
                    frame=raw_frame,
                    timestamp=timestamp,
                    frame_number=self._frame_number,
                    camera_id=self._camera_id
                )

            # Broadcast to subscribers
            self._broadcast(frame_data)
            self._update_fps()

        return Gst.FlowReturn.OK

    def _sgie_probe(self, pad, info, user_data):
        """
        Probe after SGIE - extract embeddings and do batch FAISS recognition.
        This runs after face detection (PGIE) and tracking.
        """
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if not batch_meta:
            return Gst.PadProbeReturn.OK

        self._sgie_probe_count = getattr(self, '_sgie_probe_count', 0) + 1

        all_faces = []
        all_embeddings = []
        all_obj_metas = []

        # Iterate through frames in batch
        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            source_id = frame_meta.source_id

            # Iterate through detected objects (faces)
            l_obj = frame_meta.obj_meta_list
            while l_obj is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                except StopIteration:
                    break

                # Get bounding box
                rect = obj_meta.rect_params
                x, y, w, h = int(rect.left), int(rect.top), int(rect.width), int(rect.height)
                confidence = obj_meta.confidence
                tracking_id = obj_meta.object_id

                # Extract embedding from SGIE tensor output
                embedding = None
                l_user = obj_meta.obj_user_meta_list
                while l_user is not None:
                    try:
                        user_meta = pyds.NvDsUserMeta.cast(l_user.data)
                        if user_meta.base_meta.meta_type == pyds.NvDsMetaType.NVDSINFER_TENSOR_OUTPUT_META:
                            tensor_meta = pyds.NvDsInferTensorMeta.cast(user_meta.user_meta_data)
                            # ArcFace outputs 512-dim embedding
                            if tensor_meta.num_output_layers > 0:
                                layer = pyds.get_nvds_LayerInfo(tensor_meta, 0)
                                ptr = ctypes.cast(pyds.get_ptr(layer.buffer), ctypes.POINTER(ctypes.c_float))
                                embedding = np.ctypeslib.as_array(ptr, shape=(512,)).copy()
                    except Exception as e:
                        pass
                    try:
                        l_user = l_user.next
                    except StopIteration:
                        break

                face = FaceResult(
                    bbox=(x, y, w, h),
                    confidence=confidence,
                    embedding=embedding,
                    camera_id=source_id
                )
                all_faces.append(face)
                all_obj_metas.append(obj_meta)
                if embedding is not None:
                    all_embeddings.append(embedding)

                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break

            try:
                l_frame = l_frame.next
            except StopIteration:
                break

        # Batch FAISS recognition for all embeddings
        if all_embeddings and self.recognizer:
            embeddings_array = np.array(all_embeddings, dtype=np.float32)
            # Normalize embeddings
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            embeddings_array = embeddings_array / (norms + 1e-10)

            # Batch FAISS search
            results = self.recognizer.batch_match(embeddings_array)

            # Update faces and OSD display
            emb_idx = 0
            for i, face in enumerate(all_faces):
                if face.embedding is not None and emb_idx < len(results):
                    match = results[emb_idx]
                    if match and match.is_match:
                        face.person_name = match.person_name
                        face.person_id = match.person_id
                        face.similarity = match.similarity
                        face.is_known = True
                        # Update OSD text
                        obj_meta = all_obj_metas[i]
                        display_text = pyds.get_string(obj_meta.text_params.display_text)
                        obj_meta.text_params.display_text = f"{match.person_name} ({match.similarity:.2f})"
                        obj_meta.text_params.font_params.font_color.set(0.0, 1.0, 0.0, 1.0)  # Green
                    else:
                        obj_meta = all_obj_metas[i]
                        obj_meta.text_params.display_text = "Unknown"
                        obj_meta.text_params.font_params.font_color.set(1.0, 0.0, 0.0, 1.0)  # Red
                    emb_idx += 1

            # Trigger alerts for recognized faces
            for face in all_faces:
                if self.alert_callback:
                    self._trigger_alert(face)

        # Update stats
        self._last_faces = all_faces
        self._faces_detected += len(all_faces)

        if self._sgie_probe_count % 100 == 1:
            print(f"[SGIE] Batch: {len(all_faces)} faces, {len(all_embeddings)} embeddings", flush=True)

        return Gst.PadProbeReturn.OK

    def _pgie_probe(self, pad, info, user_data):
        """Probe after PGIE - parse SCRFD outputs (for debugging)."""
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if not batch_meta:
            return Gst.PadProbeReturn.OK

        self._pgie_probe_count = getattr(self, '_pgie_probe_count', 0) + 1
        if self._pgie_probe_count % 200 == 1:
            print(f"[PGIE] Probe #{self._pgie_probe_count}", flush=True)

        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            # Track per-camera frame count
            source_id = frame_meta.source_id
            if source_id in self._frame_count_per_camera:
                self._frame_count_per_camera[source_id] += 1

            # Get tensor outputs from PGIE
            l_user = frame_meta.frame_user_meta_list
            tensor_outputs = []

            EXPECTED_SHAPES = [
                (12800, 1), (3200, 1), (800, 1),
                (12800, 4), (3200, 4), (800, 4),
                (12800, 10), (3200, 10), (800, 10),
            ]

            while l_user is not None:
                try:
                    user_meta = pyds.NvDsUserMeta.cast(l_user.data)
                    if user_meta.base_meta.meta_type == pyds.NvDsMetaType.NVDSINFER_TENSOR_OUTPUT_META:
                        tensor_meta = pyds.NvDsInferTensorMeta.cast(user_meta.user_meta_data)

                        # Try to access out_buf_ptrs_host directly
                        try:
                            # Access tensor output via out_buf_ptrs_host
                            for i in range(min(tensor_meta.num_output_layers, 9)):
                                expected_shape = EXPECTED_SHAPES[i]
                                expected_elements = expected_shape[0] * expected_shape[1]

                                # Try out_buf_ptrs_host[i] first
                                try:
                                    host_ptr = tensor_meta.out_buf_ptrs_host[i]
                                    data_ptr = ctypes.cast(
                                        pyds.get_ptr(host_ptr),
                                        ctypes.POINTER(ctypes.c_float)
                                    )
                                except Exception:
                                    # Fallback to layer.buffer
                                    layer = pyds.get_nvds_LayerInfo(tensor_meta, i)
                                    data_ptr = ctypes.cast(
                                        pyds.get_ptr(layer.buffer),
                                        ctypes.POINTER(ctypes.c_float)
                                    )

                                arr = np.ctypeslib.as_array(data_ptr, shape=(expected_elements,))
                                tensor_outputs.append(arr.copy().reshape(expected_shape))

                                if self._pgie_probe_count == 1:
                                    print(f"[DEBUG] Layer {i}: {expected_elements} floats, min={arr.min():.4f}, max={arr.max():.4f}", flush=True)

                        except Exception as inner_e:
                            if self._pgie_probe_count <= 3:
                                print(f"[DEBUG] out_buf_ptrs_host failed: {inner_e}", flush=True)
                            # Fallback to old method
                            for i in range(min(tensor_meta.num_output_layers, 9)):
                                layer = pyds.get_nvds_LayerInfo(tensor_meta, i)
                                expected_shape = EXPECTED_SHAPES[i]
                                expected_elements = expected_shape[0] * expected_shape[1]
                                data_ptr = ctypes.cast(
                                    pyds.get_ptr(layer.buffer),
                                    ctypes.POINTER(ctypes.c_float)
                                )
                                arr = np.ctypeslib.as_array(data_ptr, shape=(expected_elements,))
                                tensor_outputs.append(arr.copy().reshape(expected_shape))

                except Exception as e:
                    if self._pgie_probe_count <= 5:
                        print(f"[DEBUG] Error extracting tensor: {e}", flush=True)
                    break

                try:
                    l_user = l_user.next
                except StopIteration:
                    break

            # Debug: log tensor count
            if self._pgie_probe_count % 200 == 1:
                print(f"[DEBUG]   Found {len(tensor_outputs)} tensor outputs", flush=True)

            # Parse SCRFD outputs
            if len(tensor_outputs) == 9:
                frame_num = frame_meta.frame_num
                # Debug: ALWAYS print on first few parses
                self._parse_count = getattr(self, '_parse_count', 0) + 1
                do_debug = self._parse_count <= 5 or frame_num % 500 == 1

                if do_debug:
                    print(f"[DEBUG] === SCRFD parse #{self._parse_count} frame {frame_num} src {source_id} ===", flush=True)
                    for i, t in enumerate(tensor_outputs):
                        print(f"[DEBUG]   T{i}: shape={t.shape}, min={t.min():.4f}, max={t.max():.4f}", flush=True)

                detections = self.scrfd_parser.parse_outputs(
                    tensor_outputs, batch_size=1, original_size=None
                )[0]

                if do_debug:
                    print(f"[DEBUG]   Parsed {len(detections)} detections", flush=True)
                    if detections:
                        print(f"[DEBUG]   Conf: {min(d.confidence for d in detections):.3f}-{max(d.confidence for d in detections):.3f}", flush=True)
                        for d in detections[:3]:
                            print(f"[DEBUG]   bbox={d.bbox} conf={d.confidence:.3f}", flush=True)

                for det in detections:
                    x, y, w, h = det.bbox
                    if w < 16 or h < 16:
                        continue

                    MUXER_SIZE = 640
                    x = max(0, min(x, MUXER_SIZE - 16))
                    y = max(0, min(y, MUXER_SIZE - 16))
                    w = min(w, MUXER_SIZE - x)
                    h = min(h, MUXER_SIZE - y)

                    if w < 16 or h < 16:
                        continue

                    obj_meta = pyds.nvds_acquire_obj_meta_from_pool(batch_meta)
                    if obj_meta:
                        obj_meta.rect_params.left = float(x)
                        obj_meta.rect_params.top = float(y)
                        obj_meta.rect_params.width = float(w)
                        obj_meta.rect_params.height = float(h)
                        obj_meta.confidence = det.confidence
                        obj_meta.class_id = 0
                        obj_meta.unique_component_id = 1

                        obj_meta.rect_params.border_width = 2
                        obj_meta.rect_params.border_color.set(0.0, 1.0, 0.0, 1.0)

                        pyds.nvds_add_obj_meta_to_frame(frame_meta, obj_meta, None)
                        self._faces_detected += 1

            try:
                l_frame = l_frame.next
            except StopIteration:
                break

        return Gst.PadProbeReturn.OK

    def _trigger_alert(self, face: FaceResult):
        """Trigger alert callback for detected face."""
        try:
            # Pass FaceResult directly with frame data
            frame_data = self._latest_raw_frame
            if frame_data and self.alert_callback:
                self.alert_callback(face, frame_data)
        except Exception as e:
            logger.error(f"Alert trigger error: {e}")

    def _broadcast(self, frame_data: FrameData):
        """Broadcast frame to all subscribers."""
        dead_subscribers = set()
        for queue in self._subscribers:
            try:
                try:
                    queue.get_nowait()
                except:
                    pass
                queue.put_nowait(frame_data)
            except:
                dead_subscribers.add(queue)
        self._subscribers -= dead_subscribers

    def _update_fps(self):
        """Calculate FPS (combined and per-camera)."""
        self._fps_frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        if elapsed >= 1.0:
            self._fps = self._fps_frame_count / elapsed
            # Calculate per-camera FPS from frame counts
            for cam_id in self._frame_count_per_camera:
                self._fps_per_camera[cam_id] = self._frame_count_per_camera[cam_id] / elapsed
                self._frame_count_per_camera[cam_id] = 0
            self._fps_frame_count = 0
            self._last_fps_time = current_time

    def _bus_callback(self, bus, message, loop):
        """Handle GStreamer bus messages."""
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            logger.info("End of stream")
            loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message}")
            loop.quit()
        elif msg_type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Warning: {err.message}")
        return True

    def start(self) -> bool:
        """Start the DeepStream pipeline."""
        if self._running:
            return True

        # Verify TRT engine files exist
        if not os.path.exists(DET_ENGINE):
            logger.error(f"Detection engine not found: {DET_ENGINE}")
            return False
        if not os.path.exists(REC_ENGINE):
            logger.error(f"Recognition engine not found: {REC_ENGINE}")
            return False

        logger.info(f"TRT engines verified:")
        logger.info(f"  Detection: {os.path.basename(DET_ENGINE)}")
        logger.info(f"  Recognition: {os.path.basename(REC_ENGINE)}")

        # Start TRT inference in separate process (avoids CUDA context conflicts)
        self._trt_process = TRTProcessManager(
            det_engine=DET_ENGINE,
            rec_engine=REC_ENGINE,
            conf_threshold=0.5
        )
        if not self._trt_process.start():
            logger.error("Failed to start TRT process")
            return False
        logger.info("TRT process started (separate CUDA context)")

        # Start result polling thread (runs in main process)
        self._result_running = True
        self._result_thread = threading.Thread(target=self._result_worker, daemon=True)
        self._result_thread.start()
        logger.info("Result polling thread started")

        logger.info("Starting DeepStream decode pipeline")

        if not self._create_pipeline():
            return False

        self._running = True

        # Start pipeline
        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_callback, self.loop)

        self.pipeline.set_state(Gst.State.PLAYING)

        # Run loop in thread
        self._loop_thread = threading.Thread(target=self.loop.run, daemon=True)
        self._loop_thread.start()

        cam_info = ", ".join([c.name for c in self._cameras]) if self._cameras else "no cameras"
        logger.info(f"DeepStream pipeline started: {self._num_cameras} cameras ({cam_info})")
        return True

    def stop(self):
        """Stop the pipeline."""
        if not self._running:
            return

        self._running = False

        # Stop result polling thread
        self._result_running = False
        if self._result_thread and self._result_thread.is_alive():
            self._result_thread.join(timeout=2)
            logger.info("Result polling thread stopped")

        # Stop TRT child process
        if self._trt_process:
            self._trt_process.stop()
            logger.info("TRT process stopped")

        if self.loop:
            self.loop.quit()

        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        if hasattr(self, '_loop_thread'):
            self._loop_thread.join(timeout=5)

        logger.info(f"DeepStream stopped. Faces detected: {self._faces_detected}, matched: {self._faces_matched}")

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to frame updates."""
        if len(self._subscribers) >= self.max_clients:
            raise RuntimeError(f"Maximum clients ({self.max_clients}) reached")
        queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Remove subscriber."""
        self._subscribers.discard(queue)

    def get_latest_frame(self) -> Optional[FrameData]:
        """Get the most recent frame with overlays (full tiled view)."""
        with self._lock:
            return self._latest_frame

    def get_latest_raw_frame(self) -> Optional[FrameData]:
        """Get the most recent raw frame (full tiled view)."""
        with self._lock:
            return self._latest_raw_frame

    def get_camera_frame(self, camera_index: int) -> Optional[FrameData]:
        """
        Get frame for a specific camera by cropping from tiled output.

        Args:
            camera_index: Index of camera in the tiled grid (0-based)

        Returns:
            FrameData with cropped single-camera frame, or None if unavailable
        """
        with self._lock:
            if self._latest_frame is None or self._latest_frame.frame is None:
                return None

            if camera_index < 0 or camera_index >= self._num_cameras:
                return self._latest_frame  # Return full frame if invalid index

            # Calculate crop region based on tiler layout
            # Cameras are arranged left-to-right, top-to-bottom
            col = camera_index % self._tiler_cols
            row = camera_index // self._tiler_cols

            x1 = col * self._tile_width
            y1 = row * self._tile_height
            x2 = x1 + self._tile_width
            y2 = y1 + self._tile_height

            # Crop the frame
            full_frame = self._latest_frame.frame
            if y2 > full_frame.shape[0] or x2 > full_frame.shape[1]:
                return self._latest_frame  # Return full if crop out of bounds

            cropped = full_frame[y1:y2, x1:x2].copy()

            return FrameData(
                frame=cropped,
                timestamp=self._latest_frame.timestamp,
                frame_number=self._latest_frame.frame_number,
                camera_id=self._cameras[camera_index].id if camera_index < len(self._cameras) else 0,
                has_faces=self._latest_frame.has_faces
            )

    def get_camera_raw_frame(self, camera_index: int) -> Optional[FrameData]:
        """
        Get RAW frame (without overlays) for a specific camera.
        Used for enrollment to capture clean face images.

        Args:
            camera_index: Index of camera in the tiled grid (0-based)

        Returns:
            FrameData with cropped raw frame (no bounding boxes), or None if unavailable
        """
        with self._lock:
            if self._latest_raw_frame is None or self._latest_raw_frame.frame is None:
                return None

            if camera_index < 0 or camera_index >= self._num_cameras:
                return self._latest_raw_frame  # Return full raw frame if invalid index

            # Calculate crop region based on tiler layout
            col = camera_index % self._tiler_cols
            row = camera_index // self._tiler_cols

            x1 = col * self._tile_width
            y1 = row * self._tile_height
            x2 = x1 + self._tile_width
            y2 = y1 + self._tile_height

            # Crop the raw frame
            full_frame = self._latest_raw_frame.frame
            if y2 > full_frame.shape[0] or x2 > full_frame.shape[1]:
                return self._latest_raw_frame  # Return full if crop out of bounds

            cropped = full_frame[y1:y2, x1:x2].copy()

            return FrameData(
                frame=cropped,
                timestamp=self._latest_raw_frame.timestamp,
                frame_number=self._latest_raw_frame.frame_number,
                camera_id=self._cameras[camera_index].id if camera_index < len(self._cameras) else 0,
                has_faces=False  # Raw frame, no detection info
            )

    def get_camera_index_by_id(self, camera_id: int) -> Optional[int]:
        """Get camera index from camera database ID. Returns None if not found."""
        for i, cam in enumerate(self._cameras):
            if cam.id == camera_id:
                return i
        return None  # Camera not found

    def encode_jpeg(self, frame: np.ndarray, quality: int = 80) -> bytes:
        """Encode frame as JPEG."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return buffer.tobytes()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def motion_active(self) -> bool:
        return True  # DeepStream doesn't use motion detection

    @property
    def motion_stats(self) -> dict:
        return {"enabled": False}

    @property
    def camera(self) -> Optional["Camera"]:
        return self._camera

    @property
    def camera_id(self) -> Optional[int]:
        return self._camera_id

    def get_stats(self) -> dict:
        """Get stream statistics."""
        stats = {
            "fps": self._fps,
            "frame_number": self._frame_number,
            "subscribers": len(self._subscribers),
            "faces_detected": self._faces_detected,
            "faces_matched": self._faces_matched,
            "is_running": self._running,
            "pipeline": "DeepStream Decode + TensorRT (SCRFD + ArcFace batch32)",
            "num_cameras": self._num_cameras,
            "timing": self._last_timing
        }
        # Add all cameras info with per-camera FPS
        cameras_info = []
        for i, cam in enumerate(self._cameras):
            cameras_info.append({
                "id": cam.id,
                "index": i,
                "name": cam.name,
                "ip_address": cam.ip_address,
                "stream_quality": cam.stream_quality,
                "fps": round(self._fps_per_camera.get(i, 0.0), 1),
                "faces": self._faces_per_camera.get(i, 0),
                "connected": True
            })
        stats["cameras"] = cameras_info
        # Keep backward compatibility with single camera field
        if self._camera:
            stats["camera"] = {
                "id": self._camera_id,
                "name": self._camera.name,
                "ip_address": self._camera.ip_address,
                "stream_quality": self._camera.stream_quality
            }
        return stats

    def set_camera(self, camera: "Camera") -> bool:
        """Switch to a different primary camera (replaces first camera)."""
        was_running = self._running
        if was_running:
            self.stop()

        self._camera = camera
        self._camera_id = camera.id
        if self._cameras:
            self._cameras[0] = camera
        else:
            self._cameras = [camera]
            self._num_cameras = 1

        logger.info(f"Camera switched to: '{camera.name}'")

        if was_running:
            return self.start()
        return True
