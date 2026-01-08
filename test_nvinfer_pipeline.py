#!/usr/bin/env python3
"""
Test script for DeepStream nvinfer face detection pipeline.

Tests the SCRFD TensorRT engine with nvinfer for batched inference.
"""

import os
import sys
import time
import logging

# Add backend to path
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# DeepStream environment
os.environ['LD_LIBRARY_PATH'] = '/opt/nvidia/deepstream/deepstream-7.1/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

def test_scrfd_parser():
    """Test SCRFD parser with dummy data."""
    print("\n=== Testing SCRFD Parser ===")

    from app.core.scrfd_parser import SCRFDParser
    import numpy as np

    parser = SCRFDParser(
        input_size=(640, 640),
        confidence_threshold=0.5,
        nms_threshold=0.4
    )

    # Create dummy outputs matching SCRFD format
    # For batch=1, 640x640 input
    outputs = [
        np.random.rand(12800, 1).astype(np.float32) * 0.3,  # scores stride 8 (low confidence)
        np.random.rand(3200, 1).astype(np.float32) * 0.3,   # scores stride 16
        np.random.rand(800, 1).astype(np.float32) * 0.3,    # scores stride 32
        np.random.rand(12800, 4).astype(np.float32),        # boxes stride 8
        np.random.rand(3200, 4).astype(np.float32),         # boxes stride 16
        np.random.rand(800, 4).astype(np.float32),          # boxes stride 32
        np.random.rand(12800, 10).astype(np.float32),       # kps stride 8
        np.random.rand(3200, 10).astype(np.float32),        # kps stride 16
        np.random.rand(800, 10).astype(np.float32),         # kps stride 32
    ]

    # Add a high confidence detection
    outputs[0][1000, 0] = 0.9  # High confidence at index 1000

    detections = parser.parse_outputs(outputs, batch_size=1, original_size=(1280, 720))

    print(f"Detections: {len(detections[0])}")
    for det in detections[0]:
        print(f"  - bbox={det.bbox}, conf={det.confidence:.3f}")

    print("SCRFD Parser: OK\n")
    return True


def test_tensorrt_engine():
    """Test TensorRT engine loading."""
    print("\n=== Testing TensorRT Engine ===")

    engine_path = "/home/tempuser/Downloads/Frs_sec/models/tensorrt/scrfd_10g_batch.engine"

    if not os.path.exists(engine_path):
        print(f"ERROR: Engine not found at {engine_path}")
        return False

    import tensorrt as trt

    # Load engine
    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    with open(engine_path, "rb") as f:
        engine = runtime.deserialize_cuda_engine(f.read())

    if engine is None:
        print("ERROR: Failed to load TensorRT engine")
        return False

    print(f"Engine loaded successfully")
    print(f"  - Num IO tensors: {engine.num_io_tensors}")

    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        shape = engine.get_tensor_shape(name)
        mode = engine.get_tensor_mode(name)
        print(f"  - {name}: {shape} ({'INPUT' if mode == trt.TensorIOMode.INPUT else 'OUTPUT'})")

    print("TensorRT Engine: OK\n")
    return True


def test_gstreamer_elements():
    """Test GStreamer elements availability."""
    print("\n=== Testing GStreamer Elements ===")

    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst

    if not Gst.is_initialized():
        Gst.init(None)

    elements = [
        "rtspsrc",
        "rtph264depay",
        "h264parse",
        "nvv4l2decoder",
        "nvstreammux",
        "nvinfer",
        "nvvideoconvert",
        "nvdsosd",
        "appsink"
    ]

    all_ok = True
    for elem_name in elements:
        elem = Gst.ElementFactory.make(elem_name, None)
        status = "OK" if elem else "MISSING"
        print(f"  - {elem_name}: {status}")
        if not elem:
            all_ok = False

    print(f"GStreamer Elements: {'OK' if all_ok else 'FAILED'}\n")
    return all_ok


def test_nvinfer_config():
    """Test nvinfer config file."""
    print("\n=== Testing nvinfer Config ===")

    config_path = "/home/tempuser/Downloads/Frs_sec/configs/deepstream/scrfd_nvinfer_config.txt"

    if not os.path.exists(config_path):
        print(f"ERROR: Config not found at {config_path}")
        return False

    # Read and validate config
    with open(config_path, 'r') as f:
        config = f.read()

    # Check required fields
    required = [
        "model-engine-file",
        "batch-size",
        "network-type",
        "output-tensor-meta"
    ]

    all_ok = True
    for field in required:
        if field in config:
            print(f"  - {field}: found")
        else:
            print(f"  - {field}: MISSING")
            all_ok = False

    # Check engine file exists
    engine_line = [l for l in config.split('\n') if 'model-engine-file' in l]
    if engine_line:
        engine_path = engine_line[0].split('=')[1].strip()
        if os.path.exists(engine_path):
            print(f"  - Engine file: exists ({os.path.getsize(engine_path)/1024/1024:.1f} MB)")
        else:
            print(f"  - Engine file: NOT FOUND")
            all_ok = False

    print(f"nvinfer Config: {'OK' if all_ok else 'FAILED'}\n")
    return all_ok


def test_simple_pipeline():
    """Test a simple nvinfer pipeline."""
    print("\n=== Testing Simple nvinfer Pipeline ===")

    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib

    if not Gst.is_initialized():
        Gst.init(None)

    try:
        # Create pipeline manually for proper pad linking
        pipeline = Gst.Pipeline.new("test-pipeline")

        # Create elements
        source = Gst.ElementFactory.make("videotestsrc", "source")
        source.set_property("num-buffers", 30)

        capsfilter1 = Gst.ElementFactory.make("capsfilter", "caps1")
        caps1 = Gst.Caps.from_string("video/x-raw,width=640,height=640,framerate=30/1")
        capsfilter1.set_property("caps", caps1)

        nvconv = Gst.ElementFactory.make("nvvideoconvert", "nvconv")

        capsfilter2 = Gst.ElementFactory.make("capsfilter", "caps2")
        caps2 = Gst.Caps.from_string("video/x-raw(memory:NVMM),format=RGBA")
        capsfilter2.set_property("caps", caps2)

        streammux = Gst.ElementFactory.make("nvstreammux", "mux")
        streammux.set_property("batch-size", 1)
        streammux.set_property("width", 640)
        streammux.set_property("height", 640)
        streammux.set_property("batched-push-timeout", 40000)

        nvinfer = Gst.ElementFactory.make("nvinfer", "nvinfer")
        nvinfer.set_property("config-file-path", "/home/tempuser/Downloads/Frs_sec/configs/deepstream/scrfd_nvinfer_config.txt")

        sink = Gst.ElementFactory.make("fakesink", "sink")

        # Add to pipeline
        for elem in [source, capsfilter1, nvconv, capsfilter2, streammux, nvinfer, sink]:
            pipeline.add(elem)

        # Link source chain
        source.link(capsfilter1)
        capsfilter1.link(nvconv)
        nvconv.link(capsfilter2)

        # Link to streammux sink pad
        srcpad = capsfilter2.get_static_pad("src")
        sinkpad = streammux.get_request_pad("sink_0")
        srcpad.link(sinkpad)

        # Link rest
        streammux.link(nvinfer)
        nvinfer.link(sink)

        print("  - Pipeline created: OK")

        # Try to set to PAUSED to validate
        ret = pipeline.set_state(Gst.State.PAUSED)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("  - Pipeline validation: FAILED")
            pipeline.set_state(Gst.State.NULL)
            return False

        print("  - Pipeline validation: OK")

        # Run briefly
        pipeline.set_state(Gst.State.PLAYING)
        time.sleep(2)

        pipeline.set_state(Gst.State.NULL)
        print("Simple Pipeline: OK\n")
        return True

    except Exception as e:
        print(f"  - Error: {e}")
        import traceback
        traceback.print_exc()
        print("Simple Pipeline: FAILED\n")
        return False


def main():
    print("=" * 60)
    print("DeepStream nvinfer Face Detection Pipeline Tests")
    print("=" * 60)

    results = {}

    # Run tests
    results['scrfd_parser'] = test_scrfd_parser()
    results['tensorrt_engine'] = test_tensorrt_engine()
    results['gstreamer'] = test_gstreamer_elements()
    results['nvinfer_config'] = test_nvinfer_config()
    results['simple_pipeline'] = test_simple_pipeline()

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test}: {status}")

    all_passed = all(results.values())
    print("\n" + ("All tests PASSED!" if all_passed else "Some tests FAILED"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
