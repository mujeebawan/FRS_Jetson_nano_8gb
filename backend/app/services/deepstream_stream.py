"""
DeepStream Stream Manager - Replaces OpenCV-based stream.py
Uses DeepStream PGIE+SGIE pipeline for GPU-accelerated face detection/recognition.

Features:
- Hardware-accelerated H264 decoding via nvv4l2decoder
- Batched face detection (SCRFD) via PGIE
- Batched face embedding (ArcFace) via SGIE
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
except ImportError:
    PYDS_AVAILABLE = False
    print("WARNING: pyds not available - DeepStream disabled")

from ..config import settings
from ..core.scrfd_parser import SCRFDParser
from ..core.recognizer import FaceRecognizer

logger = logging.getLogger(__name__)

# Config paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
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
    Drop-in replacement for StreamManager with same interface.
    """

    def __init__(
        self,
        camera: "Camera" = None,
        frame_skip: int = 0,
        max_clients: int = 10,
        recognizer: FaceRecognizer = None,
        alert_callback: Optional[Callable] = None
    ):
        """
        Initialize DeepStream manager.

        Args:
            camera: Camera model instance from database
            frame_skip: Detection interval (0 = every frame)
            max_clients: Maximum concurrent viewers
            recognizer: FaceRecognizer for FAISS matching
            alert_callback: Callback for face detection alerts
        """
        if not PYDS_AVAILABLE:
            raise RuntimeError("DeepStream Python bindings (pyds) required")

        self._camera = camera
        self._camera_id = camera.id if camera else 0
        self.frame_skip = frame_skip
        self.max_clients = max_clients
        self.recognizer = recognizer
        self.alert_callback = alert_callback

        # Get RTSP URL from camera
        if camera:
            self.rtsp_url = camera.rtsp_url
        else:
            self.rtsp_url = settings.camera_third_stream

        # Pipeline state
        self.pipeline = None
        self.loop = None
        self._running = False
        self._lock = threading.Lock()

        # Frame distribution
        self._latest_frame: Optional[FrameData] = None
        self._latest_raw_frame: Optional[FrameData] = None
        self._frame_number = 0
        self._subscribers: Set[asyncio.Queue] = set()

        # Detection cache for overlay
        self._last_faces: List[FaceResult] = []

        # SCRFD parser
        self.scrfd_parser = SCRFDParser(
            input_size=(640, 640),
            confidence_threshold=settings.detection_confidence,
            nms_threshold=0.4
        )

        # Stats
        self._fps = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_count = 0
        self._faces_detected = 0
        self._faces_matched = 0

        # Initialize GStreamer
        if not Gst.is_initialized():
            Gst.init(None)

        logger.info(f"DeepStreamManager initialized: camera={camera.name if camera else 'default'}")

    def _create_element(self, factory: str, name: str):
        """Create GStreamer element."""
        elem = Gst.ElementFactory.make(factory, name)
        if not elem:
            raise RuntimeError(f"Failed to create element: {factory}")
        return elem

    def _create_pipeline(self) -> bool:
        """Create DeepStream pipeline with PGIE + SGIE + appsink."""
        try:
            self.pipeline = Gst.Pipeline.new("deepstream-face-pipeline")

            # Source: RTSP stream
            source = self._create_element("rtspsrc", "source")
            source.set_property("location", self.rtsp_url)
            source.set_property("latency", 100)
            source.set_property("drop-on-latency", True)

            # Depay and parse
            depay = self._create_element("rtph264depay", "depay")
            parser = self._create_element("h264parse", "parser")

            # Hardware decoder
            decoder = self._create_element("nvv4l2decoder", "decoder")
            decoder.set_property("enable-max-performance", True)

            # Stream muxer (single camera, but required for nvinfer)
            streammux = self._create_element("nvstreammux", "muxer")
            streammux.set_property("batch-size", 1)
            streammux.set_property("width", 640)
            streammux.set_property("height", 640)
            streammux.set_property("batched-push-timeout", 40000)
            streammux.set_property("live-source", True)

            # PGIE: SCRFD face detection
            pgie = self._create_element("nvinfer", "pgie")
            pgie.set_property("config-file-path", PGIE_CONFIG)

            # Tracker (reduces re-inference)
            tracker = self._create_element("nvtracker", "tracker")
            tracker.set_property("tracker-width", 640)
            tracker.set_property("tracker-height", 384)
            tracker.set_property("ll-lib-file", f"{DS_PATH}/lib/libnvds_nvmultiobjecttracker.so")
            tracker.set_property("ll-config-file", f"{DS_PATH}/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml")

            # SGIE: ArcFace embedding
            sgie = self._create_element("nvinfer", "sgie")
            sgie.set_property("config-file-path", SGIE_CONFIG)

            # Video converter for output
            nvvidconv = self._create_element("nvvideoconvert", "convertor")

            # OSD for bounding boxes
            nvosd = self._create_element("nvdsosd", "osd")
            nvosd.set_property("process-mode", 0)  # CPU mode for text

            # Convert to BGR for appsink
            nvvidconv2 = self._create_element("nvvideoconvert", "convertor2")
            capsfilter = self._create_element("capsfilter", "capsfilter")
            caps = Gst.Caps.from_string("video/x-raw, format=BGR")
            capsfilter.set_property("caps", caps)

            # Appsink for frame access
            appsink = self._create_element("appsink", "appsink")
            appsink.set_property("emit-signals", True)
            appsink.set_property("sync", False)
            appsink.set_property("max-buffers", 1)
            appsink.set_property("drop", True)
            appsink.connect("new-sample", self._on_new_sample)

            # Add elements
            for elem in [source, depay, parser, decoder, streammux, pgie, tracker,
                        sgie, nvvidconv, nvosd, nvvidconv2, capsfilter, appsink]:
                self.pipeline.add(elem)

            # Link source to depay (dynamic pad)
            source.connect("pad-added", self._on_pad_added, depay)

            # Link static elements
            depay.link(parser)
            parser.link(decoder)

            # Link decoder to streammux (need to request pad)
            decoder_src = decoder.get_static_pad("src")
            mux_sink = streammux.request_pad_simple("sink_0")
            decoder_src.link(mux_sink)

            # Link rest of pipeline
            streammux.link(pgie)
            pgie.link(tracker)
            tracker.link(sgie)
            sgie.link(nvvidconv)
            nvvidconv.link(nvosd)
            nvosd.link(nvvidconv2)
            nvvidconv2.link(capsfilter)
            capsfilter.link(appsink)

            # Add probes for detection parsing
            pgie_src = pgie.get_static_pad("src")
            pgie_src.add_probe(Gst.PadProbeType.BUFFER, self._pgie_probe, None)

            sgie_src = sgie.get_static_pad("src")
            sgie_src.add_probe(Gst.PadProbeType.BUFFER, self._sgie_probe, None)

            logger.info("DeepStream pipeline created successfully")
            return True

        except Exception as e:
            logger.error(f"Pipeline creation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

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

            # Create frame data
            frame_data = FrameData(
                frame=frame,
                timestamp=timestamp,
                frame_number=self._frame_number,
                camera_id=self._camera_id,
                has_faces=len(self._last_faces) > 0
            )

            # Store latest frames
            with self._lock:
                self._latest_frame = frame_data
                self._latest_raw_frame = FrameData(
                    frame=frame.copy(),
                    timestamp=timestamp,
                    frame_number=self._frame_number,
                    camera_id=self._camera_id
                )

            # Broadcast to subscribers
            self._broadcast(frame_data)
            self._update_fps()

        return Gst.FlowReturn.OK

    def _pgie_probe(self, pad, info, user_data):
        """Probe after PGIE - parse SCRFD outputs."""
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if not batch_meta:
            return Gst.PadProbeReturn.OK

        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

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
                except Exception:
                    break

                try:
                    l_user = l_user.next
                except StopIteration:
                    break

            # Parse SCRFD outputs
            if len(tensor_outputs) == 9:
                detections = self.scrfd_parser.parse_outputs(
                    tensor_outputs, batch_size=1, original_size=None
                )[0]

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

    def _sgie_probe(self, pad, info, user_data):
        """Probe after SGIE - extract embeddings and match."""
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if not batch_meta:
            return Gst.PadProbeReturn.OK

        faces: List[FaceResult] = []

        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            l_obj = frame_meta.obj_meta_list
            while l_obj is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                except StopIteration:
                    break

                # Extract embedding from SGIE
                embedding = None
                l_user = obj_meta.obj_user_meta_list
                while l_user is not None:
                    try:
                        user_meta = pyds.NvDsUserMeta.cast(l_user.data)
                        if user_meta.base_meta.meta_type == pyds.NvDsMetaType.NVDSINFER_TENSOR_OUTPUT_META:
                            tensor_meta = pyds.NvDsInferTensorMeta.cast(user_meta.user_meta_data)
                            if tensor_meta.num_output_layers > 0:
                                layer = pyds.get_nvds_LayerInfo(tensor_meta, 0)
                                data_ptr = ctypes.cast(
                                    pyds.get_ptr(layer.buffer),
                                    ctypes.POINTER(ctypes.c_float)
                                )
                                embedding = np.ctypeslib.as_array(data_ptr, shape=(512,)).copy()
                    except Exception:
                        pass

                    try:
                        l_user = l_user.next
                    except StopIteration:
                        break

                # Create face result
                rect = obj_meta.rect_params
                face = FaceResult(
                    bbox=(int(rect.left), int(rect.top), int(rect.width), int(rect.height)),
                    confidence=obj_meta.confidence,
                    embedding=embedding,
                    camera_id=self._camera_id
                )

                # Match against FAISS
                if embedding is not None and self.recognizer and self.recognizer.count > 0:
                    result = self.recognizer.identify(embedding)
                    if result and result.is_match:
                        face.person_id = result.person_id
                        face.person_name = result.person_name
                        face.similarity = result.similarity
                        face.is_known = True
                        self._faces_matched += 1

                        # Update OSD text
                        obj_meta.text_params.display_text = f"{result.person_name} ({result.similarity:.2f})"
                        obj_meta.rect_params.border_color.set(0.0, 1.0, 0.0, 1.0)  # Green
                    else:
                        obj_meta.text_params.display_text = "Unknown"
                        obj_meta.rect_params.border_color.set(1.0, 0.0, 0.0, 1.0)  # Red

                faces.append(face)

                # Trigger alert callback
                if self.alert_callback and embedding is not None:
                    self._trigger_alert(face)

                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break

            try:
                l_frame = l_frame.next
            except StopIteration:
                break

        # Cache faces for overlay
        self._last_faces = faces

        return Gst.PadProbeReturn.OK

    def _trigger_alert(self, face: FaceResult):
        """Trigger alert callback for detected face."""
        try:
            # Create detection-like object for alert callback
            from ..core.detector import FaceDetection
            detection = FaceDetection(
                bbox=face.bbox,
                confidence=face.confidence,
                embedding=face.embedding
            )

            # Create frame data for alert
            frame_data = self._latest_raw_frame
            if frame_data:
                self.alert_callback(detection, frame_data)
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
        """Calculate FPS."""
        self._fps_frame_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_fps_time
        if elapsed >= 1.0:
            self._fps = self._fps_frame_count / elapsed
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

        logger.info(f"DeepStream pipeline started: {self.rtsp_url[:50]}...")
        return True

    def stop(self):
        """Stop the pipeline."""
        if not self._running:
            return

        self._running = False

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
        """Get the most recent frame with overlays."""
        with self._lock:
            return self._latest_frame

    def get_latest_raw_frame(self) -> Optional[FrameData]:
        """Get the most recent raw frame."""
        with self._lock:
            return self._latest_raw_frame

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
            "pipeline": "DeepStream PGIE+SGIE"
        }
        if self._camera:
            stats["camera"] = {
                "id": self._camera_id,
                "name": self._camera.name,
                "ip_address": self._camera.ip_address,
                "stream_quality": self._camera.stream_quality
            }
        return stats

    def set_camera(self, camera: "Camera") -> bool:
        """Switch to a different camera."""
        was_running = self._running
        if was_running:
            self.stop()

        self._camera = camera
        self._camera_id = camera.id
        self.rtsp_url = camera.rtsp_url

        logger.info(f"Camera switched to: '{camera.name}'")

        if was_running:
            return self.start()
        return True
