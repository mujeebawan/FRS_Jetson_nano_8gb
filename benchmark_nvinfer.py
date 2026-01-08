#!/usr/bin/env python3
"""
Benchmark DeepStream nvinfer face detection with RTSP camera.

Measures FPS performance of SCRFD detection via nvinfer.
"""

import os
import sys
import time
import logging
import threading
from collections import deque

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DeepStream environment
os.environ['LD_LIBRARY_PATH'] = '/opt/nvidia/deepstream/deepstream-7.1/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

import numpy as np

# Add backend to path
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')
from app.core.scrfd_parser import SCRFDParser

# Camera settings
RTSP_URL = "rtsp://admin:Mujeeb%40321@192.168.1.64:554/Streaming/Channels/101"
CONFIG_PATH = "/home/tempuser/Downloads/Frs_sec/configs/deepstream/scrfd_nvinfer_config.txt"


class NvinferBenchmark:
    """Benchmark nvinfer face detection performance."""

    def __init__(self, rtsp_url: str, batch_size: int = 1, duration: int = 30):
        self.rtsp_url = rtsp_url
        self.batch_size = batch_size
        self.duration = duration

        self.pipeline = None
        self.loop = None
        self.running = False

        # Metrics
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = 0
        self.fps_history = deque(maxlen=100)
        self.last_fps_time = 0
        self.last_fps_count = 0

        # SCRFD parser
        self.scrfd_parser = SCRFDParser(
            input_size=(640, 640),
            confidence_threshold=0.5,
            nms_threshold=0.4
        )

        if not Gst.is_initialized():
            Gst.init(None)

    def _create_element(self, factory_name: str, name: str):
        element = Gst.ElementFactory.make(factory_name, name)
        if not element:
            raise RuntimeError(f"Failed to create: {factory_name}")
        return element

    def _create_pipeline(self) -> bool:
        try:
            self.pipeline = Gst.Pipeline.new("benchmark-pipeline")

            # Source
            source = self._create_element("rtspsrc", "source")
            source.set_property("location", self.rtsp_url)
            source.set_property("latency", 100)
            source.set_property("drop-on-latency", True)

            depay = self._create_element("rtph264depay", "depay")
            parse = self._create_element("h264parse", "parse")
            decoder = self._create_element("nvv4l2decoder", "decoder")
            decoder.set_property("enable-max-performance", True)

            # Stream muxer
            streammux = self._create_element("nvstreammux", "mux")
            streammux.set_property("batch-size", self.batch_size)
            streammux.set_property("width", 640)
            streammux.set_property("height", 640)
            streammux.set_property("batched-push-timeout", 40000)
            streammux.set_property("live-source", True)

            # nvinfer
            nvinfer = self._create_element("nvinfer", "nvinfer")
            nvinfer.set_property("config-file-path", CONFIG_PATH)

            # Output
            sink = self._create_element("fakesink", "sink")
            sink.set_property("sync", False)

            # Add elements
            for elem in [source, depay, parse, decoder, streammux, nvinfer, sink]:
                self.pipeline.add(elem)

            # Link
            depay.link(parse)
            parse.link(decoder)

            # Link decoder to streammux
            srcpad = decoder.get_static_pad("src")
            sinkpad = streammux.request_pad_simple("sink_0")
            srcpad.link(sinkpad)

            streammux.link(nvinfer)
            nvinfer.link(sink)

            # Connect source pad-added
            source.connect("pad-added", self._on_pad_added, depay)

            # Add probe to count frames
            nvinfer_src = nvinfer.get_static_pad("src")
            nvinfer_src.add_probe(Gst.PadProbeType.BUFFER, self._probe_callback, None)

            return True

        except Exception as e:
            logger.error(f"Pipeline creation failed: {e}")
            return False

    def _on_pad_added(self, source, pad, depay):
        sink_pad = depay.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)

    def _probe_callback(self, pad, info, user_data):
        """Count frames and detections."""
        self.frame_count += 1

        # Calculate real-time FPS every second
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            fps = (self.frame_count - self.last_fps_count) / (now - self.last_fps_time)
            self.fps_history.append(fps)
            self.last_fps_time = now
            self.last_fps_count = self.frame_count

        return Gst.PadProbeReturn.OK

    def _bus_callback(self, bus, message, loop):
        msg_type = message.type
        if msg_type == Gst.MessageType.EOS:
            logger.info("End of stream")
            loop.quit()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Error: {err.message}")
            loop.quit()
        return True

    def run(self):
        """Run benchmark."""
        if not self._create_pipeline():
            return None

        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_callback, self.loop)

        # Start
        logger.info(f"Starting benchmark (batch={self.batch_size}, duration={self.duration}s)...")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.start_time = time.time()
        self.last_fps_time = self.start_time

        # Run in thread
        loop_thread = threading.Thread(target=self.loop.run, daemon=True)
        loop_thread.start()

        # Wait for duration with progress updates
        try:
            for i in range(self.duration):
                time.sleep(1)
                if self.fps_history:
                    current_fps = self.fps_history[-1]
                    avg_fps = sum(self.fps_history) / len(self.fps_history)
                    elapsed = time.time() - self.start_time
                    print(f"\r[{i+1:3d}/{self.duration}s] Frames: {self.frame_count:5d} | "
                          f"Current FPS: {current_fps:5.1f} | Avg FPS: {avg_fps:5.1f}", end="")
        except KeyboardInterrupt:
            pass

        print()  # New line

        # Stop
        self.pipeline.set_state(Gst.State.NULL)
        self.loop.quit()
        loop_thread.join(timeout=5)

        # Results
        elapsed = time.time() - self.start_time
        avg_fps = self.frame_count / elapsed if elapsed > 0 else 0

        results = {
            "batch_size": self.batch_size,
            "duration": elapsed,
            "total_frames": self.frame_count,
            "average_fps": avg_fps,
            "peak_fps": max(self.fps_history) if self.fps_history else 0,
            "min_fps": min(self.fps_history) if self.fps_history else 0,
        }

        return results


def main():
    print("=" * 70)
    print("DeepStream nvinfer Face Detection Benchmark")
    print("=" * 70)
    print(f"RTSP URL: {RTSP_URL}")
    print(f"Config: {CONFIG_PATH}")
    print()

    # Test different batch sizes
    batch_sizes = [1, 2, 4]
    all_results = []

    for batch_size in batch_sizes:
        print(f"\n{'='*70}")
        print(f"Testing batch_size = {batch_size}")
        print(f"{'='*70}")

        benchmark = NvinferBenchmark(
            rtsp_url=RTSP_URL,
            batch_size=batch_size,
            duration=20
        )

        results = benchmark.run()
        if results:
            all_results.append(results)
            print(f"\nResults for batch_size={batch_size}:")
            print(f"  Total frames: {results['total_frames']}")
            print(f"  Average FPS:  {results['average_fps']:.1f}")
            print(f"  Peak FPS:     {results['peak_fps']:.1f}")
            print(f"  Min FPS:      {results['min_fps']:.1f}")

        time.sleep(2)  # Brief pause between tests

    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"{'Batch Size':<12} {'Avg FPS':<12} {'Peak FPS':<12} {'Frames':<12}")
    print("-" * 48)
    for r in all_results:
        print(f"{r['batch_size']:<12} {r['average_fps']:<12.1f} {r['peak_fps']:<12.1f} {r['total_frames']:<12}")

    # Compare with current system
    print("\n" + "-" * 70)
    print("Comparison with current TensorRT EP system:")
    print("  Current TensorRT EP: ~47 FPS")
    if all_results:
        best = max(all_results, key=lambda x: x['average_fps'])
        improvement = (best['average_fps'] / 47 - 1) * 100
        print(f"  Best nvinfer result: {best['average_fps']:.1f} FPS (batch={best['batch_size']})")
        print(f"  Improvement: {improvement:+.1f}%")


if __name__ == "__main__":
    main()
