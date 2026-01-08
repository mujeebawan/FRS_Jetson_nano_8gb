#!/usr/bin/env python3
"""
Pure Inference Benchmark - Fair Comparison

Compares:
1. Current TensorRT EP (InsightFace)
2. DeepStream nvinfer

Both tested on same images, same iterations, measuring pure inference time.
No camera involved - this measures raw processing capability.
"""

import os
import sys
import time
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')

# DeepStream environment
os.environ['LD_LIBRARY_PATH'] = '/opt/nvidia/deepstream/deepstream-7.1/lib:' + os.environ.get('LD_LIBRARY_PATH', '')


def benchmark_tensorrt_ep(iterations: int = 100, num_faces: int = 1):
    """Benchmark current TensorRT EP system."""
    print("\n" + "="*60)
    print("Benchmark: TensorRT Execution Provider (Current System)")
    print("="*60)

    from app.core.detector import FaceDetector

    # Initialize detector only (it handles detection + embedding extraction)
    detector = FaceDetector(model_name="buffalo_l", use_tensorrt=True)
    detector.initialize()

    # Create test image (640x480 with synthetic face region)
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Warmup
    print("Warming up...")
    for _ in range(10):
        detections = detector.detect(test_image, extract_embedding=True)

    # Benchmark detection only
    print(f"\nBenchmarking detection only ({iterations} iterations)...")
    det_times = []
    for i in range(iterations):
        start = time.perf_counter()
        detections = detector.detect(test_image, extract_embedding=False)
        det_times.append((time.perf_counter() - start) * 1000)

    det_avg = np.mean(det_times)
    det_p50 = np.percentile(det_times, 50)
    det_p95 = np.percentile(det_times, 95)

    print(f"  Detection: avg={det_avg:.2f}ms, p50={det_p50:.2f}ms, p95={det_p95:.2f}ms")
    print(f"  Detection FPS: {1000/det_avg:.1f}")

    # Benchmark detection + recognition (full pipeline)
    print(f"\nBenchmarking full pipeline ({iterations} iterations)...")
    full_times = []
    for i in range(iterations):
        start = time.perf_counter()
        detections = detector.detect(test_image, extract_embedding=True)
        full_times.append((time.perf_counter() - start) * 1000)

    full_avg = np.mean(full_times)
    full_p50 = np.percentile(full_times, 50)
    full_p95 = np.percentile(full_times, 95)

    print(f"  Full pipeline: avg={full_avg:.2f}ms, p50={full_p50:.2f}ms, p95={full_p95:.2f}ms")
    print(f"  Full pipeline FPS: {1000/full_avg:.1f}")

    return {
        "name": "TensorRT EP",
        "detection_ms": det_avg,
        "detection_fps": 1000/det_avg,
        "full_ms": full_avg,
        "full_fps": 1000/full_avg,
    }


def benchmark_nvinfer(iterations: int = 100):
    """Benchmark DeepStream nvinfer detection."""
    print("\n" + "="*60)
    print("Benchmark: DeepStream nvinfer (SCRFD TensorRT)")
    print("="*60)

    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit

    ENGINE_PATH = "/home/tempuser/Downloads/Frs_sec/models/tensorrt/scrfd_10g_batch.engine"

    # Load engine
    print("Loading TensorRT engine...")
    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    with open(ENGINE_PATH, "rb") as f:
        engine = runtime.deserialize_cuda_engine(f.read())

    context = engine.create_execution_context()

    # Set input shape (batch=1, 3, 640, 640)
    context.set_input_shape("input.1", (1, 3, 640, 640))

    # Allocate buffers
    input_shape = (1, 3, 640, 640)
    input_size = int(np.prod(input_shape) * 4)  # float32

    # Get output sizes
    output_sizes = []
    output_shapes = []
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        if engine.get_tensor_mode(name) == trt.TensorIOMode.OUTPUT:
            shape = context.get_tensor_shape(name)
            output_shapes.append((name, shape))
            output_sizes.append(int(np.prod(shape) * 4))

    # Allocate GPU memory
    d_input = cuda.mem_alloc(input_size)
    d_outputs = [cuda.mem_alloc(size) for size in output_sizes]

    # Create test input
    test_input = np.random.rand(1, 3, 640, 640).astype(np.float32)
    h_outputs = [np.empty(int(size/4), dtype=np.float32) for size in output_sizes]

    # Set tensor addresses
    context.set_tensor_address("input.1", int(d_input))
    for i, (name, shape) in enumerate(output_shapes):
        context.set_tensor_address(name, int(d_outputs[i]))

    # Warmup
    print("Warming up...")
    for _ in range(10):
        cuda.memcpy_htod(d_input, test_input)
        context.execute_async_v3(0)
        cuda.Context.synchronize()

    # Benchmark
    print(f"\nBenchmarking nvinfer detection ({iterations} iterations)...")
    times = []
    for i in range(iterations):
        cuda.memcpy_htod(d_input, test_input)

        start = time.perf_counter()
        context.execute_async_v3(0)
        cuda.Context.synchronize()
        times.append((time.perf_counter() - start) * 1000)

    avg = np.mean(times)
    p50 = np.percentile(times, 50)
    p95 = np.percentile(times, 95)
    min_t = np.min(times)

    print(f"  Detection: avg={avg:.2f}ms, min={min_t:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms")
    print(f"  Detection FPS: {1000/avg:.1f}")

    # Cleanup
    d_input.free()
    for d in d_outputs:
        d.free()

    return {
        "name": "nvinfer (TRT)",
        "detection_ms": avg,
        "detection_fps": 1000/avg,
        "full_ms": avg,  # Detection only for now
        "full_fps": 1000/avg,
    }


def benchmark_nvinfer_batch(iterations: int = 100, batch_size: int = 4):
    """Benchmark nvinfer with batching."""
    print("\n" + "="*60)
    print(f"Benchmark: nvinfer batch={batch_size}")
    print("="*60)

    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit

    ENGINE_PATH = "/home/tempuser/Downloads/Frs_sec/models/tensorrt/scrfd_10g_batch.engine"

    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    with open(ENGINE_PATH, "rb") as f:
        engine = runtime.deserialize_cuda_engine(f.read())

    context = engine.create_execution_context()
    context.set_input_shape("input.1", (batch_size, 3, 640, 640))

    input_shape = (batch_size, 3, 640, 640)
    input_size = int(np.prod(input_shape) * 4)

    output_sizes = []
    output_shapes = []
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        if engine.get_tensor_mode(name) == trt.TensorIOMode.OUTPUT:
            shape = context.get_tensor_shape(name)
            output_shapes.append((name, shape))
            output_sizes.append(int(np.prod(shape) * 4))

    d_input = cuda.mem_alloc(input_size)
    d_outputs = [cuda.mem_alloc(size) for size in output_sizes]

    test_input = np.random.rand(batch_size, 3, 640, 640).astype(np.float32)

    context.set_tensor_address("input.1", int(d_input))
    for i, (name, shape) in enumerate(output_shapes):
        context.set_tensor_address(name, int(d_outputs[i]))

    # Warmup
    for _ in range(10):
        cuda.memcpy_htod(d_input, test_input)
        context.execute_async_v3(0)
        cuda.Context.synchronize()

    # Benchmark
    print(f"Benchmarking ({iterations} iterations, batch={batch_size})...")
    times = []
    for i in range(iterations):
        cuda.memcpy_htod(d_input, test_input)
        start = time.perf_counter()
        context.execute_async_v3(0)
        cuda.Context.synchronize()
        times.append((time.perf_counter() - start) * 1000)

    avg = np.mean(times)
    p50 = np.percentile(times, 50)
    images_per_sec = batch_size * 1000 / avg

    print(f"  Batch latency: avg={avg:.2f}ms, p50={p50:.2f}ms")
    print(f"  Per-image: {avg/batch_size:.2f}ms")
    print(f"  Throughput: {images_per_sec:.1f} images/sec")

    d_input.free()
    for d in d_outputs:
        d.free()

    return {
        "name": f"nvinfer batch={batch_size}",
        "detection_ms": avg/batch_size,
        "detection_fps": images_per_sec,
        "batch_latency_ms": avg,
    }


def main():
    print("="*70)
    print("PURE INFERENCE BENCHMARK")
    print("Fair comparison: Same iterations, same conditions")
    print("="*70)

    iterations = 100
    results = []

    # Benchmark TensorRT EP
    try:
        r = benchmark_tensorrt_ep(iterations)
        results.append(r)
    except Exception as e:
        print(f"TensorRT EP benchmark failed: {e}")

    # Benchmark nvinfer (batch=1)
    try:
        r = benchmark_nvinfer(iterations)
        results.append(r)
    except Exception as e:
        print(f"nvinfer benchmark failed: {e}")
        import traceback
        traceback.print_exc()

    # Benchmark nvinfer batched
    for batch_size in [2, 4, 8]:
        try:
            r = benchmark_nvinfer_batch(iterations, batch_size)
            results.append(r)
        except Exception as e:
            print(f"nvinfer batch={batch_size} failed: {e}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY - Pure Detection Speed")
    print("="*70)
    print(f"{'Method':<25} {'Latency':<15} {'FPS':<15}")
    print("-"*55)
    for r in results:
        print(f"{r['name']:<25} {r['detection_ms']:.2f}ms{'':<7} {r['detection_fps']:.1f}")

    print("\n" + "-"*70)
    if len(results) >= 2:
        trt_ep = results[0]
        nvinfer = results[1]
        speedup = nvinfer['detection_fps'] / trt_ep['detection_fps']
        print(f"nvinfer vs TensorRT EP: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")

        if len(results) >= 4:
            batch4 = results[3]  # batch=4
            speedup_batch = batch4['detection_fps'] / trt_ep['detection_fps']
            print(f"nvinfer batch=4 vs TensorRT EP: {speedup_batch:.2f}x {'faster' if speedup_batch > 1 else 'slower'}")


if __name__ == "__main__":
    main()
