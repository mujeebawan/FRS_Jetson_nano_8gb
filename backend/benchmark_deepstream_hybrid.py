#!/usr/bin/env python3
"""
Benchmark: Current GStreamer vs DeepStream Hybrid Approach
Tests video decode + InsightFace detection performance
"""

import os
import sys
import time
import numpy as np
import logging
import cv2

# Set library paths
os.environ['LD_LIBRARY_PATH'] = '/opt/nvidia/deepstream/deepstream-7.1/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize GStreamer
Gst.init(None)


class CurrentGStreamerPipeline:
    """Current approach: GStreamer with OpenCV VideoCapture"""

    def __init__(self, source: str):
        self.source = source
        self.cap = None

    def _build_pipeline(self) -> str:
        """Current GStreamer pipeline from stream.py"""
        if self.source.startswith('rtsp://'):
            return (
                f"rtspsrc location={self.source} latency=0 drop-on-latency=true ! "
                "rtph264depay ! h264parse ! "
                "nvv4l2decoder enable-max-performance=true ! "
                "nvvidconv ! "
                "video/x-raw,format=BGRx ! "
                "videoconvert ! "
                "video/x-raw,format=BGR ! "
                "appsink sync=false max-buffers=1 drop=true"
            )
        else:
            # File source
            return (
                f"filesrc location={self.source} ! "
                "qtdemux ! h264parse ! "
                "nvv4l2decoder enable-max-performance=true ! "
                "nvvidconv ! "
                "video/x-raw,format=BGRx ! "
                "videoconvert ! "
                "video/x-raw,format=BGR ! "
                "appsink sync=false max-buffers=1 drop=true"
            )

    def start(self):
        pipeline = self._build_pipeline()
        logger.info(f"Current GStreamer pipeline: {pipeline[:80]}...")
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open GStreamer pipeline")
        return self

    def read(self):
        return self.cap.read()

    def stop(self):
        if self.cap:
            self.cap.release()


class DeepStreamHybridPipeline:
    """DeepStream approach: Optimized decode with nvvideoconvert"""

    def __init__(self, source: str):
        self.source = source
        self.cap = None

    def _build_pipeline(self) -> str:
        """DeepStream-optimized pipeline - stays on GPU longer"""
        if self.source.startswith('rtsp://'):
            return (
                f"rtspsrc location={self.source} latency=0 drop-on-latency=true ! "
                "rtph264depay ! h264parse ! "
                "nvv4l2decoder enable-max-performance=true ! "
                "nvvideoconvert ! "  # DeepStream's GPU-based converter
                "video/x-raw,format=BGRx ! "
                "videoconvert ! "
                "video/x-raw,format=BGR ! "
                "appsink sync=false max-buffers=1 drop=true emit-signals=true"
            )
        else:
            # File source
            return (
                f"filesrc location={self.source} ! "
                "qtdemux ! h264parse ! "
                "nvv4l2decoder enable-max-performance=true ! "
                "nvvideoconvert ! "  # DeepStream's GPU-based converter
                "video/x-raw,format=BGRx ! "
                "videoconvert ! "
                "video/x-raw,format=BGR ! "
                "appsink sync=false max-buffers=1 drop=true emit-signals=true"
            )

    def start(self):
        pipeline = self._build_pipeline()
        logger.info(f"DeepStream Hybrid pipeline: {pipeline[:80]}...")
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open DeepStream pipeline")
        return self

    def read(self):
        return self.cap.read()

    def stop(self):
        if self.cap:
            self.cap.release()


def benchmark_decode_only(pipeline_class, source: str, num_frames: int = 200):
    """Benchmark decode speed without AI inference"""
    pipeline = pipeline_class(source)
    pipeline.start()

    # Warmup
    for _ in range(30):
        ret, frame = pipeline.read()
        if not ret:
            break

    # Benchmark
    times = []
    for i in range(num_frames):
        start = time.perf_counter()
        ret, frame = pipeline.read()
        elapsed = (time.perf_counter() - start) * 1000

        if not ret:
            logger.warning(f"Frame read failed at {i}")
            break
        times.append(elapsed)

    pipeline.stop()

    times = np.array(times)
    return {
        'avg_ms': np.mean(times),
        'min_ms': np.min(times),
        'max_ms': np.max(times),
        'p50_ms': np.percentile(times, 50),
        'p95_ms': np.percentile(times, 95),
        'fps': 1000 / np.mean(times),
        'frames': len(times)
    }


def benchmark_with_detection(pipeline_class, source: str, model_name: str = "buffalo_l", num_frames: int = 100):
    """Benchmark decode + InsightFace detection"""
    from insightface.app import FaceAnalysis

    # Initialize InsightFace with TensorRT EP
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

    logger.info(f"Loading {model_name} with TensorRT EP...")
    app = FaceAnalysis(name=model_name, providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))

    # Start pipeline
    pipeline = pipeline_class(source)
    pipeline.start()

    # Warmup
    logger.info("Warming up...")
    for _ in range(20):
        ret, frame = pipeline.read()
        if ret:
            _ = app.get(frame)

    # Benchmark
    logger.info(f"Benchmarking {num_frames} frames...")
    decode_times = []
    detect_times = []
    total_times = []
    face_counts = []

    for i in range(num_frames):
        # Decode
        t0 = time.perf_counter()
        ret, frame = pipeline.read()
        t1 = time.perf_counter()

        if not ret:
            logger.warning(f"Frame read failed at {i}")
            break

        # Detect
        faces = app.get(frame)
        t2 = time.perf_counter()

        decode_times.append((t1 - t0) * 1000)
        detect_times.append((t2 - t1) * 1000)
        total_times.append((t2 - t0) * 1000)
        face_counts.append(len(faces))

        if (i + 1) % 25 == 0:
            logger.info(f"Progress: {i + 1}/{num_frames}")

    pipeline.stop()

    return {
        'decode_avg_ms': np.mean(decode_times),
        'detect_avg_ms': np.mean(detect_times),
        'total_avg_ms': np.mean(total_times),
        'total_min_ms': np.min(total_times),
        'total_p50_ms': np.percentile(total_times, 50),
        'total_p95_ms': np.percentile(total_times, 95),
        'fps': 1000 / np.mean(total_times),
        'avg_faces': np.mean(face_counts),
        'frames': len(total_times)
    }


def print_results(name: str, results: dict):
    print(f"\n{'='*60}")
    print(f"{name}")
    print('='*60)
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark GStreamer vs DeepStream Hybrid")
    parser.add_argument("--source", default="/opt/nvidia/deepstream/deepstream-7.1/samples/streams/sample_1080p_h264.mp4",
                        help="Video source (file or RTSP URL)")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to benchmark")
    parser.add_argument("--model", default="buffalo_l", help="InsightFace model name")
    parser.add_argument("--decode-only", action="store_true", help="Only benchmark decode, skip detection")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("BENCHMARK: Current GStreamer vs DeepStream Hybrid")
    print("="*60)
    print(f"Source: {args.source}")
    print(f"Frames: {args.frames}")
    print(f"Model: {args.model}")
    print("="*60)

    if args.decode_only:
        # Decode-only benchmark
        print("\n[1/2] Benchmarking Current GStreamer (decode only)...")
        current_results = benchmark_decode_only(CurrentGStreamerPipeline, args.source, args.frames)
        print_results("Current GStreamer (decode only)", current_results)

        print("\n[2/2] Benchmarking DeepStream Hybrid (decode only)...")
        ds_results = benchmark_decode_only(DeepStreamHybridPipeline, args.source, args.frames)
        print_results("DeepStream Hybrid (decode only)", ds_results)
    else:
        # Full benchmark with detection
        print("\n[1/2] Benchmarking Current GStreamer + InsightFace...")
        current_results = benchmark_with_detection(CurrentGStreamerPipeline, args.source, args.model, args.frames)
        print_results("Current GStreamer + InsightFace", current_results)

        print("\n[2/2] Benchmarking DeepStream Hybrid + InsightFace...")
        ds_results = benchmark_with_detection(DeepStreamHybridPipeline, args.source, args.model, args.frames)
        print_results("DeepStream Hybrid + InsightFace", ds_results)

    # Comparison
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)

    key = 'fps'
    current_fps = current_results[key]
    ds_fps = ds_results[key]
    improvement = ((ds_fps - current_fps) / current_fps) * 100

    print(f"  Current GStreamer:  {current_fps:.2f} FPS")
    print(f"  DeepStream Hybrid:  {ds_fps:.2f} FPS")
    print(f"  Improvement:        {improvement:+.1f}%")

    if not args.decode_only:
        print(f"\n  Decode overhead:")
        print(f"    Current:   {current_results['decode_avg_ms']:.2f} ms")
        print(f"    DeepStream: {ds_results['decode_avg_ms']:.2f} ms")

    print("="*60)


if __name__ == "__main__":
    main()
