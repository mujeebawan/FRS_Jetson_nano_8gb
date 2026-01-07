#!/usr/bin/env python3
"""
LFW Evaluation with TensorRT EP
Wrapper that runs LFW evaluation using TensorRT Execution Provider
"""

import os
import sys

# Set library path BEFORE importing anything else
os.environ['LD_LIBRARY_PATH'] = '/usr/lib/aarch64-linux-gnu/nvidia:' + os.environ.get('LD_LIBRARY_PATH', '')

import time
import numpy as np
import cv2
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LFWEvaluatorTRT:
    """LFW benchmark evaluator using TensorRT EP"""

    def __init__(
        self,
        data_dir: str = "data/lfw",
        model_name: str = "buffalo_custom_500m_r50",
        use_fp16: bool = True
    ):
        self.data_dir = Path(data_dir)
        self.lfw_dir = self.data_dir / "lfw"
        self.pairs_file = self.data_dir / "pairs.txt"
        self.model_name = model_name
        self.use_fp16 = use_fp16

        self.results_dir = self.data_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self._app = None

    def _init_model(self):
        """Initialize model with TensorRT EP"""
        from insightface.app import FaceAnalysis

        trt_options = {
            'device_id': 0,
            'trt_fp16_enable': self.use_fp16,
            'trt_engine_cache_enable': True,
            'trt_engine_cache_path': str(Path.home() / '.cache' / 'tensorrt_engines'),
        }

        providers = [
            ('TensorrtExecutionProvider', trt_options),
            ('CUDAExecutionProvider', {'device_id': 0}),
            'CPUExecutionProvider'
        ]

        logger.info(f"Initializing {self.model_name} with TensorRT EP (FP16={self.use_fp16})...")
        self._app = FaceAnalysis(name=self.model_name, providers=providers)
        self._app.prepare(ctx_id=0, det_size=(640, 640))
        logger.info("Model initialized successfully")

    def parse_pairs(self) -> List[Tuple]:
        """Parse LFW pairs.txt"""
        pairs = []

        with open(self.pairs_file, 'r') as f:
            lines = f.readlines()

        # Skip header
        n_folds = int(lines[0].strip().split()[0])

        for line in lines[1:]:
            parts = line.strip().split('\t')

            if len(parts) == 3:
                # Same person
                name, idx1, idx2 = parts
                pairs.append((name, int(idx1), name, int(idx2), True))
            elif len(parts) == 4:
                # Different people
                name1, idx1, name2, idx2 = parts
                pairs.append((name1, int(idx1), name2, int(idx2), False))

        return pairs

    def get_image_path(self, name: str, idx: int) -> Path:
        """Get path to LFW image"""
        return self.lfw_dir / name / f"{name}_{idx:04d}.jpg"

    def get_embedding(self, img_path: Path) -> Optional[np.ndarray]:
        """Extract face embedding from image"""
        if not img_path.exists():
            return None

        img = cv2.imread(str(img_path))
        if img is None:
            return None

        faces = self._app.get(img)

        if len(faces) == 0:
            return None

        return faces[0].normed_embedding if hasattr(faces[0], 'normed_embedding') and faces[0].normed_embedding is not None else faces[0].embedding

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity"""
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))

    def evaluate(self, max_pairs: int = 0) -> Dict:
        """Run LFW evaluation"""
        if self._app is None:
            self._init_model()

        pairs = self.parse_pairs()
        logger.info(f"Parsed {len(pairs)} pairs")

        if max_pairs > 0:
            pairs = pairs[:max_pairs]

        logger.info(f"Evaluating {len(pairs)} pairs...")

        similarities = []
        labels = []
        inference_times = []
        skipped = 0

        for i, (name1, idx1, name2, idx2, is_same) in enumerate(pairs):
            path1 = self.get_image_path(name1, idx1)
            path2 = self.get_image_path(name2, idx2)

            start = time.perf_counter()

            emb1 = self.get_embedding(path1)
            emb2 = self.get_embedding(path2)

            inference_times.append((time.perf_counter() - start) * 1000)

            if emb1 is None or emb2 is None:
                skipped += 1
                continue

            sim = self.compute_similarity(emb1, emb2)
            similarities.append(sim)
            labels.append(is_same)

            if (i + 1) % 500 == 0:
                logger.info(f"Progress: {i + 1}/{len(pairs)} pairs")

        logger.info(f"Evaluated {len(similarities)} pairs, skipped {skipped}")

        # Find best threshold
        similarities = np.array(similarities)
        labels = np.array(labels)

        best_thresh = 0.0
        best_acc = 0.0
        threshold_results = []

        for thresh in np.arange(0.1, 0.8, 0.05):
            preds = similarities >= thresh
            acc = np.mean(preds == labels)

            if acc > best_acc:
                best_acc = acc
                best_thresh = thresh

        # Calculate metrics at best threshold
        preds = similarities >= best_thresh
        tp = np.sum((preds == True) & (labels == True))
        tn = np.sum((preds == False) & (labels == False))
        fp = np.sum((preds == True) & (labels == False))
        fn = np.sum((preds == False) & (labels == True))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        # Threshold analysis
        for thresh in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
            preds = similarities >= thresh
            t_tp = np.sum((preds == True) & (labels == True))
            t_tn = np.sum((preds == False) & (labels == False))
            t_fp = np.sum((preds == True) & (labels == False))
            t_fn = np.sum((preds == False) & (labels == True))
            t_acc = (t_tp + t_tn) / len(labels)
            t_prec = t_tp / (t_tp + t_fp) if (t_tp + t_fp) > 0 else 0
            t_rec = t_tp / (t_tp + t_fn) if (t_tp + t_fn) > 0 else 0
            t_f1 = 2 * t_prec * t_rec / (t_prec + t_rec) if (t_prec + t_rec) > 0 else 0

            threshold_results.append({
                'threshold': thresh,
                'accuracy': t_acc,
                'precision': t_prec,
                'recall': t_rec,
                'f1_score': t_f1,
                'tp': int(t_tp), 'tn': int(t_tn), 'fp': int(t_fp), 'fn': int(t_fn)
            })

        results = {
            'model': f"{self.model_name}_TRT_FP16" if self.use_fp16 else f"{self.model_name}_TRT_FP32",
            'provider': 'TensorRT_EP',
            'fp16_enabled': self.use_fp16,
            'total_pairs': len(pairs),
            'evaluated_pairs': len(similarities),
            'skipped_pairs': skipped,
            'best_threshold': float(best_thresh),
            'accuracy': float(best_acc),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'confusion_matrix': {
                'true_positives': int(tp),
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn)
            },
            'timing': {
                'avg_inference_time_ms': float(np.mean(inference_times)),
                'throughput_fps': 1000 / float(np.mean(inference_times)) if inference_times else 0,
            },
            'threshold_analysis': threshold_results,
            'timestamp': datetime.now().isoformat()
        }

        return results

    def save_results(self, results: Dict):
        """Save results to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lfw_results_{self.model_name}_TRT_{timestamp}.json"
        filepath = self.results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to {filepath}")

    def print_results(self, results: Dict):
        """Print formatted results"""
        print("\n" + "="*60)
        print("LFW EVALUATION RESULTS (TensorRT EP)")
        print("="*60)
        print(f"Model: {results['model']}")
        print(f"Provider: {results['provider']}")
        print(f"FP16 Enabled: {results['fp16_enabled']}")
        print(f"Total Pairs: {results['total_pairs']}")
        print(f"Evaluated Pairs: {results['evaluated_pairs']}")
        print(f"Skipped Pairs: {results['skipped_pairs']}")
        print("-"*60)
        print(f"Best Threshold: {results['best_threshold']:.3f}")
        print(f"Accuracy: {results['accuracy']*100:.2f}%")
        print(f"Precision: {results['precision']*100:.2f}%")
        print(f"Recall: {results['recall']*100:.2f}%")
        print(f"F1-Score: {results['f1_score']*100:.2f}%")
        print("-"*60)
        print("CONFUSION MATRIX")
        cm = results['confusion_matrix']
        print(f"TP: {cm['true_positives']}, TN: {cm['true_negatives']}")
        print(f"FP: {cm['false_positives']}, FN: {cm['false_negatives']}")
        print("-"*60)
        print("INFERENCE TIMING")
        print(f"Avg Time: {results['timing']['avg_inference_time_ms']:.2f} ms/pair")
        print(f"Throughput: {results['timing']['throughput_fps']:.2f} FPS")
        print("="*60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LFW Evaluation with TensorRT EP")
    parser.add_argument("--data-dir", default="data/lfw", help="Data directory")
    parser.add_argument("--model", default="buffalo_custom_500m_r50", help="Model name")
    parser.add_argument("--max-pairs", type=int, default=0, help="Max pairs to evaluate")
    parser.add_argument("--no-fp16", action="store_true", help="Disable FP16")

    args = parser.parse_args()

    evaluator = LFWEvaluatorTRT(
        data_dir=args.data_dir,
        model_name=args.model,
        use_fp16=not args.no_fp16
    )

    results = evaluator.evaluate(max_pairs=args.max_pairs)
    evaluator.print_results(results)
    evaluator.save_results(results)


if __name__ == "__main__":
    main()
