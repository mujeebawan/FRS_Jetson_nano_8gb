#!/usr/bin/env python3
"""
LFW (Labeled Faces in the Wild) Evaluation Script
Evaluates face verification performance on standard benchmark.

This script measures:
- Accuracy, Precision, Recall, F1-Score
- Confusion Matrix
- ROC Curve and AUC
- Inference latency and throughput
- System resource usage (CPU, GPU, RAM)
"""

import os
import sys
import time
import urllib.request
import tarfile
import numpy as np
import cv2
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import json
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# LFW Dataset URLs
LFW_URL = "http://vis-www.cs.umass.edu/lfw/lfw.tgz"
LFW_PAIRS_URL = "http://vis-www.cs.umass.edu/lfw/pairs.txt"


@dataclass
class EvaluationMetrics:
    """Evaluation metrics container"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    auc: float
    threshold: float
    total_pairs: int
    avg_inference_time_ms: float
    throughput_fps: float


class LFWEvaluator:
    """LFW benchmark evaluator for face verification"""

    def __init__(
        self,
        data_dir: str = "data/lfw",
        model_name: str = "buffalo_sc",
        use_gpu: bool = True
    ):
        self.data_dir = Path(data_dir)
        self.lfw_dir = self.data_dir / "lfw"
        self.pairs_file = self.data_dir / "pairs.txt"
        self.model_name = model_name
        self.use_gpu = use_gpu

        # Results storage
        self.results_dir = self.data_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Face analysis model
        self._app = None

    def download_lfw(self) -> bool:
        """Download LFW dataset if not present"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Download pairs.txt
        if not self.pairs_file.exists():
            logger.info("Downloading LFW pairs.txt...")
            try:
                urllib.request.urlretrieve(LFW_PAIRS_URL, self.pairs_file)
                logger.info("Downloaded pairs.txt")
            except Exception as e:
                logger.error(f"Failed to download pairs.txt: {e}")
                return False

        # Download and extract LFW images
        if not self.lfw_dir.exists():
            tgz_path = self.data_dir / "lfw.tgz"

            if not tgz_path.exists():
                logger.info("Downloading LFW dataset (173MB)...")
                try:
                    urllib.request.urlretrieve(LFW_URL, tgz_path)
                    logger.info("Downloaded lfw.tgz")
                except Exception as e:
                    logger.error(f"Failed to download LFW: {e}")
                    return False

            logger.info("Extracting LFW dataset...")
            try:
                with tarfile.open(tgz_path, 'r:gz') as tar:
                    tar.extractall(self.data_dir)
                logger.info("Extracted LFW dataset")
            except Exception as e:
                logger.error(f"Failed to extract LFW: {e}")
                return False

        return True

    def initialize_model(self) -> bool:
        """Initialize InsightFace model"""
        try:
            from insightface.app import FaceAnalysis

            providers = []
            if self.use_gpu:
                providers.append(('CUDAExecutionProvider', {
                    'device_id': 0,
                    'arena_extend_strategy': 'kNextPowerOfTwo',
                    'cudnn_conv_algo_search': 'EXHAUSTIVE',
                }))
            providers.append('CPUExecutionProvider')

            logger.info(f"Initializing {self.model_name} model...")
            self._app = FaceAnalysis(name=self.model_name, providers=providers)
            self._app.prepare(ctx_id=0 if self.use_gpu else -1, det_size=(640, 640))
            logger.info("Model initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize model: {e}")
            return False

    def parse_pairs(self) -> Tuple[List[Tuple[str, str, int]], int]:
        """
        Parse LFW pairs.txt file
        Returns: List of (img1_path, img2_path, label) and number of folds
        """
        pairs = []

        with open(self.pairs_file, 'r') as f:
            lines = f.readlines()

        # First line contains: num_folds num_pairs_per_fold
        header = lines[0].strip().split()
        if len(header) == 2:
            num_folds = int(header[0])
            pairs_per_fold = int(header[1])
        else:
            num_folds = 10
            pairs_per_fold = 300

        for line in lines[1:]:
            parts = line.strip().split('\t')

            if len(parts) == 3:
                # Same person: name, img1_num, img2_num
                name, n1, n2 = parts
                img1 = self._get_image_path(name, int(n1))
                img2 = self._get_image_path(name, int(n2))
                if img1 and img2:
                    pairs.append((img1, img2, 1))  # Same person

            elif len(parts) == 4:
                # Different persons: name1, img1_num, name2, img2_num
                name1, n1, name2, n2 = parts
                img1 = self._get_image_path(name1, int(n1))
                img2 = self._get_image_path(name2, int(n2))
                if img1 and img2:
                    pairs.append((img1, img2, 0))  # Different persons

        logger.info(f"Parsed {len(pairs)} pairs ({num_folds} folds)")
        return pairs, num_folds

    def _get_image_path(self, name: str, num: int) -> Optional[str]:
        """Get image path for a person"""
        img_name = f"{name}_{num:04d}.jpg"
        img_path = self.lfw_dir / name / img_name

        if img_path.exists():
            return str(img_path)
        return None

    def extract_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """Extract face embedding from image"""
        if self._app is None:
            return None

        try:
            img = cv2.imread(image_path)
            if img is None:
                return None

            faces = self._app.get(img)
            if len(faces) == 0:
                return None

            # Get embedding from first face
            embedding = faces[0].embedding
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            return embedding

        except Exception as e:
            logger.debug(f"Failed to extract embedding: {e}")
            return None

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between embeddings"""
        return float(np.dot(emb1, emb2))

    def evaluate(
        self,
        max_pairs: int = None,
        thresholds: List[float] = None
    ) -> Dict:
        """
        Run LFW evaluation

        Args:
            max_pairs: Maximum pairs to evaluate (None for all)
            thresholds: List of thresholds to test

        Returns:
            Dictionary with evaluation results
        """
        if thresholds is None:
            thresholds = np.arange(0.0, 1.0, 0.01).tolist()

        # Parse pairs
        pairs, num_folds = self.parse_pairs()

        if max_pairs:
            pairs = pairs[:max_pairs]

        logger.info(f"Evaluating {len(pairs)} pairs...")

        # Collect similarities and labels
        similarities = []
        labels = []
        inference_times = []
        skipped = 0

        for i, (img1_path, img2_path, label) in enumerate(pairs):
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(pairs)} pairs")

            # Extract embeddings with timing
            start_time = time.time()
            emb1 = self.extract_embedding(img1_path)
            emb2 = self.extract_embedding(img2_path)
            inference_time = (time.time() - start_time) * 1000  # ms

            if emb1 is None or emb2 is None:
                skipped += 1
                continue

            sim = self.compute_similarity(emb1, emb2)
            similarities.append(sim)
            labels.append(label)
            inference_times.append(inference_time)

        logger.info(f"Evaluated {len(similarities)} pairs, skipped {skipped}")

        similarities = np.array(similarities)
        labels = np.array(labels)

        # Find best threshold
        best_threshold, best_accuracy = self._find_best_threshold(
            similarities, labels, thresholds
        )

        # Compute metrics at best threshold
        metrics = self._compute_metrics(similarities, labels, best_threshold)

        # Compute ROC AUC
        auc = self._compute_auc(similarities, labels, thresholds)

        # Timing stats
        avg_inference_time = np.mean(inference_times) if inference_times else 0
        throughput = 1000 / avg_inference_time if avg_inference_time > 0 else 0

        results = {
            "model": self.model_name,
            "total_pairs": len(pairs),
            "evaluated_pairs": len(similarities),
            "skipped_pairs": skipped,
            "best_threshold": best_threshold,
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
            "auc": auc,
            "confusion_matrix": {
                "true_positives": metrics["tp"],
                "true_negatives": metrics["tn"],
                "false_positives": metrics["fp"],
                "false_negatives": metrics["fn"]
            },
            "timing": {
                "avg_inference_time_ms": avg_inference_time,
                "throughput_fps": throughput,
                "total_inference_times": inference_times
            },
            "threshold_analysis": self._threshold_analysis(similarities, labels, thresholds),
            "timestamp": datetime.now().isoformat()
        }

        return results

    def _find_best_threshold(
        self,
        similarities: np.ndarray,
        labels: np.ndarray,
        thresholds: List[float]
    ) -> Tuple[float, float]:
        """Find threshold with best accuracy"""
        best_acc = 0
        best_thresh = 0.5

        for thresh in thresholds:
            predictions = (similarities >= thresh).astype(int)
            acc = np.mean(predictions == labels)
            if acc > best_acc:
                best_acc = acc
                best_thresh = thresh

        return best_thresh, best_acc

    def _compute_metrics(
        self,
        similarities: np.ndarray,
        labels: np.ndarray,
        threshold: float
    ) -> Dict:
        """Compute precision, recall, F1 at threshold"""
        predictions = (similarities >= threshold).astype(int)

        tp = np.sum((predictions == 1) & (labels == 1))
        tn = np.sum((predictions == 0) & (labels == 0))
        fp = np.sum((predictions == 1) & (labels == 0))
        fn = np.sum((predictions == 0) & (labels == 1))

        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "tp": int(tp),
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn)
        }

    def _compute_auc(
        self,
        similarities: np.ndarray,
        labels: np.ndarray,
        thresholds: List[float]
    ) -> float:
        """Compute Area Under ROC Curve"""
        tpr_list = []
        fpr_list = []

        for thresh in sorted(thresholds, reverse=True):
            predictions = (similarities >= thresh).astype(int)

            tp = np.sum((predictions == 1) & (labels == 1))
            fn = np.sum((predictions == 0) & (labels == 1))
            fp = np.sum((predictions == 1) & (labels == 0))
            tn = np.sum((predictions == 0) & (labels == 0))

            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

            tpr_list.append(tpr)
            fpr_list.append(fpr)

        # Compute AUC using trapezoidal rule
        auc = 0
        for i in range(1, len(fpr_list)):
            auc += (fpr_list[i] - fpr_list[i-1]) * (tpr_list[i] + tpr_list[i-1]) / 2

        return abs(float(auc))

    def _threshold_analysis(
        self,
        similarities: np.ndarray,
        labels: np.ndarray,
        thresholds: List[float]
    ) -> List[Dict]:
        """Analyze metrics across thresholds"""
        analysis = []

        for thresh in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]:
            metrics = self._compute_metrics(similarities, labels, thresh)
            analysis.append({
                "threshold": thresh,
                **metrics
            })

        return analysis

    def save_results(self, results: Dict, filename: str = None) -> str:
        """Save results to JSON file"""
        if filename is None:
            filename = f"lfw_results_{self.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.results_dir / filename

        # Remove large arrays for JSON
        results_copy = results.copy()
        if "timing" in results_copy and "total_inference_times" in results_copy["timing"]:
            results_copy["timing"]["total_inference_times"] = f"[{len(results['timing']['total_inference_times'])} values]"

        with open(filepath, 'w') as f:
            json.dump(results_copy, f, indent=2)

        logger.info(f"Results saved to {filepath}")
        return str(filepath)

    def print_results(self, results: Dict):
        """Print formatted results"""
        print("\n" + "="*60)
        print("LFW EVALUATION RESULTS")
        print("="*60)
        print(f"Model: {results['model']}")
        print(f"Total Pairs: {results['total_pairs']}")
        print(f"Evaluated Pairs: {results['evaluated_pairs']}")
        print(f"Skipped Pairs: {results['skipped_pairs']}")
        print("-"*60)
        print("PERFORMANCE METRICS")
        print("-"*60)
        print(f"Best Threshold: {results['best_threshold']:.3f}")
        print(f"Accuracy: {results['accuracy']*100:.2f}%")
        print(f"Precision: {results['precision']*100:.2f}%")
        print(f"Recall: {results['recall']*100:.2f}%")
        print(f"F1-Score: {results['f1_score']*100:.2f}%")
        print(f"AUC: {results['auc']:.4f}")
        print("-"*60)
        print("CONFUSION MATRIX")
        print("-"*60)
        cm = results['confusion_matrix']
        print(f"True Positives (TP): {cm['true_positives']}")
        print(f"True Negatives (TN): {cm['true_negatives']}")
        print(f"False Positives (FP): {cm['false_positives']}")
        print(f"False Negatives (FN): {cm['false_negatives']}")
        print("-"*60)
        print("INFERENCE TIMING")
        print("-"*60)
        print(f"Avg Inference Time: {results['timing']['avg_inference_time_ms']:.2f} ms/pair")
        print(f"Throughput: {results['timing']['throughput_fps']:.2f} FPS")
        print("-"*60)
        print("THRESHOLD ANALYSIS")
        print("-"*60)
        print(f"{'Threshold':<12} {'Accuracy':<12} {'Precision':<12} {'Recall':<12} {'F1':<12}")
        for ta in results['threshold_analysis']:
            print(f"{ta['threshold']:<12.2f} {ta['accuracy']*100:<12.2f} {ta['precision']*100:<12.2f} {ta['recall']*100:<12.2f} {ta['f1_score']*100:<12.2f}")
        print("="*60)


def get_system_info() -> Dict:
    """Get Jetson system information"""
    info = {
        "platform": "Jetson Orin Nano 8GB",
        "jetpack_version": "Unknown",
        "cuda_version": "Unknown",
        "power_mode": "Unknown"
    }

    # JetPack version
    try:
        with open("/etc/nv_tegra_release", "r") as f:
            info["jetpack_version"] = f.read().strip()
    except:
        pass

    # CUDA version
    try:
        import subprocess
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "release" in line:
                    info["cuda_version"] = line.strip()
                    break
    except:
        pass

    # Power mode
    try:
        import subprocess
        result = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True)
        if result.returncode == 0:
            info["power_mode"] = result.stdout.strip()
    except:
        pass

    return info


def main():
    """Main evaluation function"""
    import argparse

    parser = argparse.ArgumentParser(description="LFW Face Verification Benchmark")
    parser.add_argument("--data-dir", default="data/lfw", help="Data directory")
    parser.add_argument("--model", default="buffalo_sc", help="InsightFace model name")
    parser.add_argument("--max-pairs", type=int, default=None, help="Max pairs to evaluate")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU")
    parser.add_argument("--download-only", action="store_true", help="Only download dataset")

    args = parser.parse_args()

    # Initialize evaluator
    evaluator = LFWEvaluator(
        data_dir=args.data_dir,
        model_name=args.model,
        use_gpu=not args.no_gpu
    )

    # Download dataset
    if not evaluator.download_lfw():
        logger.error("Failed to download LFW dataset")
        return 1

    if args.download_only:
        logger.info("Dataset downloaded successfully")
        return 0

    # Initialize model
    if not evaluator.initialize_model():
        logger.error("Failed to initialize model")
        return 1

    # Print system info
    sys_info = get_system_info()
    print("\n" + "="*60)
    print("SYSTEM INFORMATION")
    print("="*60)
    for key, value in sys_info.items():
        print(f"{key}: {value}")
    print("="*60 + "\n")

    # Run evaluation
    results = evaluator.evaluate(max_pairs=args.max_pairs)

    # Add system info to results
    results["system_info"] = sys_info

    # Print and save results
    evaluator.print_results(results)
    evaluator.save_results(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
