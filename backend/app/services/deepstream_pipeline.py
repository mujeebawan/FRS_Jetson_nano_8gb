"""
DeepStream Pipeline Service for Face Recognition System

Provides GPU-accelerated video decode with zero-copy frame extraction.
Uses DeepStream for decode, InsightFace (TensorRT) for face detection/recognition.

Architecture:
    RTSP Source → nvv4l2decoder → nvvideoconvert → appsink (probe) → InsightFace → FAISS

Benefits:
    - Zero-copy GPU decode (nvv4l2decoder)
    - Hardware-accelerated color conversion (nvvideoconvert)
    - Direct GPU buffer access via pyds
    - Compatible with existing InsightFace + TensorRT EP pipeline
"""

import os
import sys
import logging
import threading
import queue
import time
from typing import Callable, Optional, Tuple
import numpy as np

# Set DeepStream library path
os.environ['LD_LIBRARY_PATH'] = '/opt/nvidia/deepstream/deepstream-7.1/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

import pyds

logger = logging.getLogger(__name__)


class DeepStreamPipeline:
    """
    DeepStream-based video pipeline for face recognition.

    Uses nvv4l2decoder for hardware decode and nvvideoconvert for
    GPU-based color conversion. Frames are extracted via buffer probe
    for processing with InsightFace.
    """

    def __init__(
        self,
        rtsp_url: str,
        frame_callback: Optional[Callable[[np.ndarray, int], None]] = None,
        width: int = 1280,
        height: int = 720,
        fps: int = 25
    ):
        """
        Initialize DeepStream pipeline.

        Args:
            rtsp_url: RTSP stream URL
            frame_callback: Callback function(frame, frame_number) for each frame
            width: Output frame width
            height: Output frame height
            fps: Target frame rate
        """
        self.rtsp_url = rtsp_url
        self.frame_callback = frame_callback
        self.width = width
        self.height = height
        self.fps = fps

        self.pipeline = None
        self.loop = None
        self.loop_thread = None
        self.running = False

        self.frame_queue = queue.Queue(maxsize=2)
        self.frame_count = 0
        self.last_frame_time = 0

        # Performance metrics
        self.decode_times = []
        self.total_frames = 0

        # Initialize GStreamer
        if not Gst.is_initialized():
            Gst.init(None)

        logger.info(f"DeepStreamPipeline initialized: {width}x{height}@{fps}fps")

    def _create_pipeline(self) -> bool:
        """Create GStreamer pipeline with DeepStream elements."""
        try:
            # Create pipeline
            self.pipeline = Gst.Pipeline.new("deepstream-face-pipeline")

            # Create elements
            source = Gst.ElementFactory.make("rtspsrc", "rtsp-source")
            depay = Gst.ElementFactory.make("rtph264depay", "h264-depay")
            parse = Gst.ElementFactory.make("h264parse", "h264-parse")
            decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
            nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nv-vidconv")
            capsfilter = Gst.ElementFactory.make("capsfilter", "caps-filter")
            appsink = Gst.ElementFactory.make("appsink", "app-sink")

            if not all([source, depay, parse, decoder, nvvidconv, capsfilter, appsink]):
                logger.error("Failed to create pipeline elements")
                return False

            # Configure source
            source.set_property("location", self.rtsp_url)
            source.set_property("latency", 0)
            source.set_property("drop-on-latency", True)
            source.set_property("protocols", "tcp")

            # Configure decoder for max performance
            decoder.set_property("enable-max-performance", True)

            # Configure video converter
            # Output RGBA for easy numpy conversion
            caps = Gst.Caps.from_string(
                f"video/x-raw(memory:NVMM),format=RGBA,width={self.width},height={self.height}"
            )
            capsfilter.set_property("caps", caps)

            # Configure appsink
            appsink.set_property("emit-signals", True)
            appsink.set_property("sync", False)
            appsink.set_property("max-buffers", 1)
            appsink.set_property("drop", True)

            # Add elements to pipeline
            for element in [source, depay, parse, decoder, nvvidconv, capsfilter, appsink]:
                self.pipeline.add(element)

            # Link static elements (depay onwards)
            if not depay.link(parse):
                logger.error("Failed to link depay -> parse")
                return False
            if not parse.link(decoder):
                logger.error("Failed to link parse -> decoder")
                return False
            if not decoder.link(nvvidconv):
                logger.error("Failed to link decoder -> nvvidconv")
                return False
            if not nvvidconv.link(capsfilter):
                logger.error("Failed to link nvvidconv -> capsfilter")
                return False
            if not capsfilter.link(appsink):
                logger.error("Failed to link capsfilter -> appsink")
                return False

            # Connect source pad-added signal (RTSP source creates pads dynamically)
            source.connect("pad-added", self._on_pad_added, depay)

            # Add probe to appsink
            appsink_pad = appsink.get_static_pad("sink")
            appsink_pad.add_probe(
                Gst.PadProbeType.BUFFER,
                self._appsink_buffer_probe,
                None
            )

            logger.info("DeepStream pipeline created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create pipeline: {e}")
            return False

    def _on_pad_added(self, src, new_pad, depay):
        """Handle dynamic pad creation from rtspsrc."""
        caps = new_pad.get_current_caps()
        struct = caps.get_structure(0)
        name = struct.get_name()

        if name.startswith("application/x-rtp"):
            sink_pad = depay.get_static_pad("sink")
            if not sink_pad.is_linked():
                new_pad.link(sink_pad)
                logger.info("RTSP source pad linked to depay")

    def _appsink_buffer_probe(self, pad, info, user_data):
        """
        Buffer probe callback - extracts frames from GPU buffer.

        Uses pyds.get_nvds_buf_surface() for zero-copy GPU buffer access.
        """
        try:
            gst_buffer = info.get_buffer()
            if not gst_buffer:
                return Gst.PadProbeReturn.OK

            start_time = time.perf_counter()

            # Get surface from buffer (this maps GPU memory to CPU)
            # For NVMM memory, use pyds functions
            caps = pad.get_current_caps()
            struct = caps.get_structure(0)

            # Map buffer to get data
            success, map_info = gst_buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.PadProbeReturn.OK

            # Create numpy array from buffer data
            # RGBA format: 4 bytes per pixel
            frame = np.ndarray(
                (self.height, self.width, 4),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()  # Copy to prevent memory issues after unmap

            gst_buffer.unmap(map_info)

            # Convert RGBA to BGR for OpenCV/InsightFace
            import cv2
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

            decode_time = (time.perf_counter() - start_time) * 1000
            self.decode_times.append(decode_time)
            self.frame_count += 1
            self.total_frames += 1

            # Put frame in queue (non-blocking)
            try:
                self.frame_queue.put_nowait((frame_bgr, self.frame_count))
            except queue.Full:
                pass  # Drop frame if queue is full

            # Call callback if provided
            if self.frame_callback:
                self.frame_callback(frame_bgr, self.frame_count)

            # Log performance periodically
            if self.total_frames % 100 == 0:
                avg_decode = np.mean(self.decode_times[-100:])
                logger.info(f"DeepStream: {self.total_frames} frames, avg decode: {avg_decode:.2f}ms")

        except Exception as e:
            logger.error(f"Buffer probe error: {e}")

        return Gst.PadProbeReturn.OK

    def _bus_call(self, bus, message, loop):
        """Handle GStreamer bus messages."""
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            logger.info("End of stream")
            loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message}")
            logger.debug(f"Debug info: {debug}")
            loop.quit()
        elif msg_type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {err.message}")
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old, new, pending = message.parse_state_changed()
                logger.debug(f"Pipeline state: {old.value_nick} -> {new.value_nick}")

        return True

    def start(self) -> bool:
        """Start the DeepStream pipeline."""
        if self.running:
            logger.warning("Pipeline already running")
            return True

        if not self._create_pipeline():
            return False

        # Create and start main loop in separate thread
        self.loop = GLib.MainLoop()

        # Add bus watch
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_call, self.loop)

        # Set pipeline to playing state
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to set pipeline to PLAYING state")
            return False

        self.running = True

        # Start main loop in thread
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()

        logger.info("DeepStream pipeline started")
        return True

    def _run_loop(self):
        """Run GLib main loop."""
        try:
            self.loop.run()
        except Exception as e:
            logger.error(f"Main loop error: {e}")
        finally:
            self.running = False

    def stop(self):
        """Stop the DeepStream pipeline."""
        if not self.running:
            return

        logger.info("Stopping DeepStream pipeline...")

        # Stop pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        # Quit main loop
        if self.loop and self.loop.is_running():
            self.loop.quit()

        # Wait for thread to finish
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=5)

        self.running = False
        logger.info("DeepStream pipeline stopped")

    def get_frame(self, timeout: float = 1.0) -> Optional[Tuple[np.ndarray, int]]:
        """
        Get the latest frame from the pipeline.

        Args:
            timeout: Maximum time to wait for a frame

        Returns:
            Tuple of (frame, frame_number) or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_performance_stats(self) -> dict:
        """Get performance statistics."""
        if not self.decode_times:
            return {}

        recent = self.decode_times[-100:] if len(self.decode_times) > 100 else self.decode_times
        return {
            'total_frames': self.total_frames,
            'avg_decode_ms': np.mean(recent),
            'min_decode_ms': np.min(recent),
            'max_decode_ms': np.max(recent),
            'decode_fps': 1000 / np.mean(recent) if recent else 0
        }

    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self.running


class DeepStreamFaceProcessor:
    """
    Face processor using DeepStream pipeline + InsightFace.

    Combines DeepStream for efficient video decode with existing
    InsightFace (TensorRT EP) pipeline for face detection and recognition.
    """

    def __init__(
        self,
        rtsp_url: str,
        detector,  # FaceDetector instance
        recognizer,  # FaceRecognizer instance
        on_detection: Optional[Callable] = None,
        width: int = 1280,
        height: int = 720
    ):
        """
        Initialize face processor.

        Args:
            rtsp_url: RTSP stream URL
            detector: FaceDetector instance (with TensorRT EP)
            recognizer: FaceRecognizer instance
            on_detection: Callback for face detections
            width: Frame width
            height: Frame height
        """
        self.detector = detector
        self.recognizer = recognizer
        self.on_detection = on_detection

        self.pipeline = DeepStreamPipeline(
            rtsp_url=rtsp_url,
            frame_callback=self._process_frame,
            width=width,
            height=height
        )

        self.processing = False
        self.process_every_n = 1  # Process every Nth frame
        self.frame_count = 0

        # Performance tracking
        self.detect_times = []
        self.total_detections = 0

        logger.info("DeepStreamFaceProcessor initialized")

    def _process_frame(self, frame: np.ndarray, frame_number: int):
        """Process a frame for face detection/recognition."""
        if not self.processing:
            return

        self.frame_count += 1
        if self.frame_count % self.process_every_n != 0:
            return

        try:
            start_time = time.perf_counter()

            # Detect faces
            detections = self.detector.detect_with_embeddings(frame)

            detect_time = (time.perf_counter() - start_time) * 1000
            self.detect_times.append(detect_time)

            # Recognize faces
            results = []
            for detection in detections:
                if detection.embedding is not None:
                    match = self.recognizer.identify(detection.embedding)
                    results.append({
                        'detection': detection,
                        'match': match,
                        'frame_number': frame_number
                    })
                    self.total_detections += 1

            # Callback
            if self.on_detection and results:
                self.on_detection(frame, results)

            # Log performance periodically
            if len(self.detect_times) % 50 == 0:
                avg = np.mean(self.detect_times[-50:])
                logger.info(f"FaceProcessor: avg detection time: {avg:.2f}ms")

        except Exception as e:
            logger.error(f"Frame processing error: {e}")

    def start(self):
        """Start face processing."""
        self.processing = True
        return self.pipeline.start()

    def stop(self):
        """Stop face processing."""
        self.processing = False
        self.pipeline.stop()

    def get_stats(self) -> dict:
        """Get combined performance stats."""
        pipeline_stats = self.pipeline.get_performance_stats()

        if self.detect_times:
            recent = self.detect_times[-50:] if len(self.detect_times) > 50 else self.detect_times
            pipeline_stats.update({
                'avg_detect_ms': np.mean(recent),
                'total_detections': self.total_detections,
                'detect_fps': 1000 / np.mean(recent) if recent else 0
            })

        return pipeline_stats


# Test function
def test_deepstream_decode():
    """Test DeepStream decode pipeline with sample video using native GStreamer."""
    # Initialize GStreamer
    Gst.init(None)

    # Use sample video
    source = "/opt/nvidia/deepstream/deepstream-7.1/samples/streams/sample_1080p_h264.mp4"

    print("Testing DeepStream native decode pipeline...")
    print(f"Source: {source}")

    # Create elements
    pipeline = Gst.Pipeline.new("test-pipeline")

    filesrc = Gst.ElementFactory.make("filesrc", "file-source")
    demux = Gst.ElementFactory.make("qtdemux", "demux")
    parse = Gst.ElementFactory.make("h264parse", "parse")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvidconv")
    capsfilter = Gst.ElementFactory.make("capsfilter", "caps")
    appsink = Gst.ElementFactory.make("appsink", "sink")

    if not all([filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]):
        print("Failed to create elements")
        return

    # Configure
    filesrc.set_property("location", source)
    decoder.set_property("enable-max-performance", True)

    caps = Gst.Caps.from_string("video/x-raw,format=RGBA")
    capsfilter.set_property("caps", caps)

    appsink.set_property("emit-signals", True)
    appsink.set_property("sync", False)
    appsink.set_property("max-buffers", 1)
    appsink.set_property("drop", True)

    # Add to pipeline
    for elem in [filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]:
        pipeline.add(elem)

    # Link static elements
    filesrc.link(demux)
    parse.link(decoder)
    decoder.link(nvvidconv)
    nvvidconv.link(capsfilter)
    capsfilter.link(appsink)

    # Handle dynamic pads from demux
    def on_pad_added(src, pad):
        if pad.get_current_caps().to_string().startswith("video"):
            pad.link(parse.get_static_pad("sink"))

    demux.connect("pad-added", on_pad_added)

    # Frame counter
    frame_count = [0]
    start_time = [time.time()]

    def on_new_sample(sink):
        sample = sink.emit("pull-sample")
        if sample:
            frame_count[0] += 1

            if frame_count[0] == 1:
                start_time[0] = time.time()

            if frame_count[0] % 100 == 0:
                elapsed = time.time() - start_time[0]
                fps = frame_count[0] / elapsed if elapsed > 0 else 0
                print(f"Frame {frame_count[0]}: {fps:.1f} FPS")

        return Gst.FlowReturn.OK

    appsink.connect("new-sample", on_new_sample)

    # Start pipeline
    pipeline.set_state(Gst.State.PLAYING)

    # Run for 5 seconds
    print("Running for 5 seconds...")
    time.sleep(5)

    # Stop
    pipeline.set_state(Gst.State.NULL)

    elapsed = time.time() - start_time[0]
    fps = frame_count[0] / elapsed if elapsed > 0 else 0
    print(f"\nTotal: {frame_count[0]} frames in {elapsed:.1f}s = {fps:.1f} FPS (decode only)")


def test_deepstream_with_extraction():
    """Test DeepStream with frame extraction to numpy."""
    import cv2

    # Initialize GStreamer
    Gst.init(None)

    source = "/opt/nvidia/deepstream/deepstream-7.1/samples/streams/sample_1080p_h264.mp4"
    width, height = 1920, 1080

    print("Testing DeepStream with frame extraction...")
    print(f"Source: {source}")

    # Create pipeline
    pipeline = Gst.Pipeline.new("extract-pipeline")

    filesrc = Gst.ElementFactory.make("filesrc", "file-source")
    demux = Gst.ElementFactory.make("qtdemux", "demux")
    parse = Gst.ElementFactory.make("h264parse", "parse")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvidconv")
    capsfilter = Gst.ElementFactory.make("capsfilter", "caps")
    appsink = Gst.ElementFactory.make("appsink", "sink")

    if not all([filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]):
        print("Failed to create elements")
        return

    # Configure
    filesrc.set_property("location", source)
    decoder.set_property("enable-max-performance", True)

    # RGBA format for easy numpy conversion
    caps = Gst.Caps.from_string(f"video/x-raw,format=RGBA,width={width},height={height}")
    capsfilter.set_property("caps", caps)

    appsink.set_property("emit-signals", True)
    appsink.set_property("sync", False)
    appsink.set_property("max-buffers", 1)
    appsink.set_property("drop", True)

    # Add and link
    for elem in [filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]:
        pipeline.add(elem)

    filesrc.link(demux)
    parse.link(decoder)
    decoder.link(nvvidconv)
    nvvidconv.link(capsfilter)
    capsfilter.link(appsink)

    def on_pad_added(src, pad):
        caps_str = pad.get_current_caps().to_string() if pad.get_current_caps() else ""
        if "video" in caps_str:
            pad.link(parse.get_static_pad("sink"))

    demux.connect("pad-added", on_pad_added)

    # Stats
    frame_count = [0]
    extract_times = []
    start_time = [time.time()]

    def on_new_sample(sink):
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.OK

        t0 = time.perf_counter()

        # Get buffer and map it
        buf = sample.get_buffer()
        success, map_info = buf.map(Gst.MapFlags.READ)

        if success:
            # Convert to numpy array (RGBA)
            frame = np.ndarray(
                (height, width, 4),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()

            buf.unmap(map_info)

            # Convert RGBA to BGR for OpenCV/InsightFace
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)

            extract_time = (time.perf_counter() - t0) * 1000
            extract_times.append(extract_time)

            frame_count[0] += 1

            if frame_count[0] == 1:
                start_time[0] = time.time()
                print(f"First frame shape: {frame_bgr.shape}")

            if frame_count[0] % 50 == 0:
                elapsed = time.time() - start_time[0]
                fps = frame_count[0] / elapsed if elapsed > 0 else 0
                avg_extract = np.mean(extract_times[-50:])
                print(f"Frame {frame_count[0]}: {fps:.1f} FPS, extract: {avg_extract:.2f}ms")

        return Gst.FlowReturn.OK

    appsink.connect("new-sample", on_new_sample)

    # Start
    pipeline.set_state(Gst.State.PLAYING)

    print("Running for 5 seconds...")
    time.sleep(5)

    pipeline.set_state(Gst.State.NULL)

    if frame_count[0] > 0:
        elapsed = time.time() - start_time[0]
        fps = frame_count[0] / elapsed
        avg_extract = np.mean(extract_times) if extract_times else 0
        print(f"\nTotal: {frame_count[0]} frames in {elapsed:.1f}s = {fps:.1f} FPS")
        print(f"Avg extraction time: {avg_extract:.2f}ms")


def test_deepstream_with_detection():
    """Test DeepStream + InsightFace TensorRT detection."""
    import cv2
    from insightface.app import FaceAnalysis

    # Initialize GStreamer
    Gst.init(None)

    source = "/opt/nvidia/deepstream/deepstream-7.1/samples/streams/sample_1080p_h264.mp4"
    width, height = 1280, 720  # Use 720p for faster processing

    print("Testing DeepStream + InsightFace TensorRT...")
    print(f"Source: {source}")

    # Initialize InsightFace with TensorRT EP
    print("Loading InsightFace with TensorRT EP...")
    trt_options = {
        'device_id': 0,
        'trt_fp16_enable': True,
        'trt_engine_cache_enable': True,
        'trt_engine_cache_path': '/home/tempuser/.cache/tensorrt_engines',
    }
    providers = [
        ('TensorrtExecutionProvider', trt_options),
        ('CUDAExecutionProvider', {'device_id': 0}),
        'CPUExecutionProvider'
    ]
    face_app = FaceAnalysis(name="buffalo_l", providers=providers)
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    print("InsightFace loaded")

    # Create pipeline
    pipeline = Gst.Pipeline.new("detect-pipeline")

    filesrc = Gst.ElementFactory.make("filesrc", "file-source")
    demux = Gst.ElementFactory.make("qtdemux", "demux")
    parse = Gst.ElementFactory.make("h264parse", "parse")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvidconv")
    capsfilter = Gst.ElementFactory.make("capsfilter", "caps")
    appsink = Gst.ElementFactory.make("appsink", "sink")

    if not all([filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]):
        print("Failed to create elements")
        return

    # Configure
    filesrc.set_property("location", source)
    decoder.set_property("enable-max-performance", True)

    caps = Gst.Caps.from_string(f"video/x-raw,format=RGBA,width={width},height={height}")
    capsfilter.set_property("caps", caps)

    appsink.set_property("emit-signals", True)
    appsink.set_property("sync", False)
    appsink.set_property("max-buffers", 1)
    appsink.set_property("drop", True)

    # Add and link
    for elem in [filesrc, demux, parse, decoder, nvvidconv, capsfilter, appsink]:
        pipeline.add(elem)

    filesrc.link(demux)
    parse.link(decoder)
    decoder.link(nvvidconv)
    nvvidconv.link(capsfilter)
    capsfilter.link(appsink)

    def on_pad_added(src, pad):
        caps_str = pad.get_current_caps().to_string() if pad.get_current_caps() else ""
        if "video" in caps_str:
            pad.link(parse.get_static_pad("sink"))

    demux.connect("pad-added", on_pad_added)

    # Stats
    frame_count = [0]
    detect_times = []
    total_times = []
    face_counts = []
    start_time = [time.time()]

    def on_new_sample(sink):
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.OK

        t0 = time.perf_counter()

        # Get buffer and extract frame
        buf = sample.get_buffer()
        success, map_info = buf.map(Gst.MapFlags.READ)

        if success:
            frame = np.ndarray(
                (height, width, 4),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()
            buf.unmap(map_info)

            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            t1 = time.perf_counter()

            # Face detection
            faces = face_app.get(frame_bgr)
            t2 = time.perf_counter()

            extract_time = (t1 - t0) * 1000
            detect_time = (t2 - t1) * 1000
            total_time = (t2 - t0) * 1000

            detect_times.append(detect_time)
            total_times.append(total_time)
            face_counts.append(len(faces))

            frame_count[0] += 1

            if frame_count[0] == 1:
                start_time[0] = time.time()

            if frame_count[0] % 25 == 0:
                elapsed = time.time() - start_time[0]
                fps = frame_count[0] / elapsed if elapsed > 0 else 0
                avg_detect = np.mean(detect_times[-25:])
                avg_total = np.mean(total_times[-25:])
                avg_faces = np.mean(face_counts[-25:])
                print(f"Frame {frame_count[0]}: {fps:.1f} FPS, detect: {avg_detect:.1f}ms, total: {avg_total:.1f}ms, faces: {avg_faces:.1f}")

        return Gst.FlowReturn.OK

    appsink.connect("new-sample", on_new_sample)

    # Warmup
    print("Warming up...")
    pipeline.set_state(Gst.State.PLAYING)
    time.sleep(2)

    # Reset stats after warmup
    frame_count[0] = 0
    detect_times.clear()
    total_times.clear()
    face_counts.clear()
    start_time[0] = time.time()

    print("Running benchmark for 10 seconds...")
    time.sleep(10)

    pipeline.set_state(Gst.State.NULL)

    if frame_count[0] > 0:
        elapsed = time.time() - start_time[0]
        fps = frame_count[0] / elapsed
        avg_detect = np.mean(detect_times)
        avg_total = np.mean(total_times)
        p95_total = np.percentile(total_times, 95)
        print(f"\n{'='*60}")
        print("DEEPSTREAM + TENSORRT RESULTS")
        print('='*60)
        print(f"Frames processed: {frame_count[0]}")
        print(f"Throughput: {fps:.1f} FPS")
        print(f"Avg detection: {avg_detect:.1f}ms")
        print(f"Avg total: {avg_total:.1f}ms")
        print(f"P95 total: {p95_total:.1f}ms")
        print('='*60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # test_deepstream_decode()
    # test_deepstream_with_extraction()
    test_deepstream_with_detection()
