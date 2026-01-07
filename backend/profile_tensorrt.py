#!/usr/bin/env python3
"""
TensorRT Profiling Script
Tests face recognition models with TensorRT Execution Provider
"""

import os
import sys
import time
import numpy as np
import logging
import json
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TensorRT cache directory
TRT_CACHE_DIR = Path.home() / ".cache" / "tensorrt_engines"
TRT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def profile_with_tensorrt(
    model_name: str = "buffalo_custom_500m_r50",
    num_iterations: int = 50,
    input_size: tuple = (640, 480),
    use_fp16: bool = True
):
    """
    Profile model with TensorRT Execution Provider
    """
    from insightface.app import FaceAnalysis

    # TensorRT EP options
    trt_options = {
        'device_id': 0,
        'trt_max_workspace_size': 2147483648,  # 2GB
        'trt_fp16_enable': use_fp16,
        'trt_engine_cache_enable': True,
        'trt_engine_cache_path': str(TRT_CACHE_DIR),
    }

    providers = [
        ('TensorrtExecutionProvider', trt_options),
        ('CUDAExecutionProvider', {'device_id': 0}),
        'CPUExecutionProvider'
    ]

    logger.info(f"Initializing {model_name} with TensorRT EP (FP16={use_fp16})...")
    logger.info(f"TensorRT cache: {TRT_CACHE_DIR}")

    # First run will build TensorRT engines (slow)
    app = FaceAnalysis(name=model_name, providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))

    # Create test image
    test_image = np.random.randint(0, 255, (input_size[1], input_size[0], 3), dtype=np.uint8)

    # Warmup (builds TRT engines on first run)
    logger.info("Warmup (building TensorRT engines if first run)...")
    for i in range(10):
        _ = app.get(test_image)
        if i == 0:
            logger.info("First inference complete (TRT engine built)")

    # Profile
    logger.info(f"Running {num_iterations} profiling iterations...")
    inference_times = []

    for i in range(num_iterations):
        start = time.perf_counter()
        _ = app.get(test_image)
        end = time.perf_counter()
        inference_times.append((end - start) * 1000)

        if (i + 1) % 20 == 0:
            logger.info(f"Progress: {i + 1}/{num_iterations}")

    # Calculate stats
    inference_times = np.array(inference_times)

    results = {
        'model_name': model_name,
        'provider': 'TensorRT',
        'fp16_enabled': use_fp16,
        'input_size': input_size,
        'num_iterations': num_iterations,
        'avg_latency_ms': float(np.mean(inference_times)),
        'min_latency_ms': float(np.min(inference_times)),
        'max_latency_ms': float(np.max(inference_times)),
        'std_latency_ms': float(np.std(inference_times)),
        'throughput_fps': 1000 / float(np.mean(inference_times)),
        'timestamp': datetime.now().isoformat()
    }

    return results


def print_results(results: dict):
    """Print formatted results"""
    print("\n" + "="*60)
    print("TENSORRT PROFILING RESULTS")
    print("="*60)
    print(f"Model: {results['model_name']}")
    print(f"Provider: {results['provider']}")
    print(f"FP16 Enabled: {results['fp16_enabled']}")
    print(f"Input Size: {results['input_size']}")
    print("-"*60)
    print(f"Avg Latency: {results['avg_latency_ms']:.2f} ms")
    print(f"Min Latency: {results['min_latency_ms']:.2f} ms")
    print(f"Max Latency: {results['max_latency_ms']:.2f} ms")
    print(f"Std Dev: {results['std_latency_ms']:.2f} ms")
    print(f"Throughput: {results['throughput_fps']:.2f} FPS")
    print("="*60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TensorRT Face Recognition Profiler")
    parser.add_argument("--model", default="buffalo_custom_500m_r50", help="Model name")
    parser.add_argument("--iterations", type=int, default=50, help="Number of iterations")
    parser.add_argument("--no-fp16", action="store_true", help="Disable FP16")
    parser.add_argument("--output", type=str, help="Output JSON file")

    args = parser.parse_args()

    results = profile_with_tensorrt(
        model_name=args.model,
        num_iterations=args.iterations,
        use_fp16=not args.no_fp16
    )

    print_results(results)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
