#!/usr/bin/env python3
"""
Convert InsightFace models from FP32 to FP16 for faster inference on Jetson.

FP16 models are ~50% smaller and run faster on NVIDIA GPUs with Tensor Cores.
The Jetson Orin Nano GPU supports FP16 acceleration.

Usage:
    python3 scripts/convert_fp16.py [--model buffalo_s]
"""

import os
import sys
import argparse
import shutil


def convert_models(model_name: str = "buffalo_s"):
    """
    Convert ONNX models from FP32 to FP16.

    Args:
        model_name: InsightFace model pack name (default: buffalo_s)
    """
    try:
        import onnx
        from onnxconverter_common import float16
    except ImportError:
        print("ERROR: Required packages not installed.")
        print("Install with: pip3 install onnx onnxconverter-common")
        sys.exit(1)

    # Paths
    models_dir = os.path.expanduser(f"~/.insightface/models/{model_name}")
    output_dir = os.path.expanduser(f"~/.insightface/models/{model_name}_fp16")

    if not os.path.exists(models_dir):
        print(f"ERROR: Model directory not found: {models_dir}")
        print(f"Run the application once to download models, or manually download {model_name}.")
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Converting models from: {models_dir}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)

    # Convert each ONNX file
    converted = 0
    skipped = 0

    for filename in os.listdir(models_dir):
        src_path = os.path.join(models_dir, filename)
        dst_path = os.path.join(output_dir, filename)

        if filename.endswith('.onnx'):
            try:
                # Get original size
                original_size = os.path.getsize(src_path) / (1024 * 1024)

                print(f"Converting: {filename} ({original_size:.1f} MB)...")

                # Load model
                model = onnx.load(src_path)

                # Convert to FP16 with keep_io_types=True
                # This keeps inputs/outputs as FP32 while internal ops use FP16
                # Required for InsightFace which sends FP32 inputs
                model_fp16 = float16.convert_float_to_float16(
                    model,
                    keep_io_types=True
                )

                # Save
                onnx.save(model_fp16, dst_path)

                # Get new size
                new_size = os.path.getsize(dst_path) / (1024 * 1024)
                reduction = (1 - new_size / original_size) * 100

                print(f"  -> {new_size:.1f} MB ({reduction:.0f}% reduction)")
                converted += 1

            except Exception as e:
                print(f"  ERROR: {e}")
                # Copy original if conversion fails
                shutil.copy2(src_path, dst_path)
                skipped += 1

        else:
            # Copy non-ONNX files (like config)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)

    print("-" * 50)
    print(f"Conversion complete!")
    print(f"  Converted: {converted} models")
    print(f"  Skipped:   {skipped} models")
    print(f"\nFP16 models saved to: {output_dir}")
    print("\nTo use FP16 models, set USE_TENSORRT=true in your .env file.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert InsightFace models to FP16 for Jetson GPU acceleration"
    )
    parser.add_argument(
        "--model", "-m",
        default="buffalo_s",
        help="Model pack name (default: buffalo_s)"
    )

    args = parser.parse_args()
    convert_models(args.model)


if __name__ == "__main__":
    main()
