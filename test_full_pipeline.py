#!/usr/bin/env python3
"""
Full Face Recognition Pipeline Test

Tests the complete PGIE + SGIE + FAISS pipeline:
- PGIE: SCRFD face detection
- SGIE: ArcFace embedding extraction
- FAISS: Batch similarity matching

This demonstrates multi-camera ready architecture with batch processing.
"""

import os
import sys
import time
import logging
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')

from app.services.deepstream_face_pipeline import DeepStreamFacePipeline, FaceResult
from app.core.recognizer import FaceRecognizer
from typing import List


class PipelineTester:
    """Test harness for full face recognition pipeline."""

    def __init__(self, camera_urls: List[str], match_threshold: float = 0.4):
        self.camera_urls = camera_urls
        self.match_threshold = match_threshold

        # Counters for reporting
        self.known_detections = 0
        self.unknown_detections = 0
        self.known_persons = set()

    def on_faces(self, faces: List[FaceResult], camera_id: int):
        """Callback for face detection results."""
        for face in faces:
            # Only report significant faces (>40x40 pixels)
            if face.bbox[2] < 40 or face.bbox[3] < 40:
                continue

            if face.is_known:
                self.known_detections += 1
                self.known_persons.add(face.person_name)
                logger.info(
                    f"[Cam{camera_id}] KNOWN: {face.person_name} "
                    f"(sim={face.match_similarity:.2f}, track={face.track_id})"
                )
            else:
                self.unknown_detections += 1
                logger.info(
                    f"[Cam{camera_id}] UNKNOWN face "
                    f"(sim={face.match_similarity:.2f}, track={face.track_id})"
                )

    def run(self, duration: int = 30):
        """Run the pipeline test."""
        print("=" * 70)
        print("FULL FACE RECOGNITION PIPELINE TEST")
        print("PGIE (SCRFD) + SGIE (ArcFace) + FAISS (Batch Matching)")
        print("=" * 70)

        # Initialize recognizer
        print("\n[1/3] Initializing FAISS recognizer...")
        recognizer = FaceRecognizer(
            embeddings_dir="/home/tempuser/Downloads/Frs_sec/backend/data/embeddings",
            threshold=self.match_threshold,
            use_gpu=False
        )
        recognizer.load()
        print(f"      Loaded {recognizer.count} enrolled faces")

        if recognizer.count == 0:
            print("\n      WARNING: No faces enrolled! All detections will be 'unknown'.")
            print("      Enroll faces via the web UI or API first.")

        # Initialize pipeline
        print("\n[2/3] Initializing DeepStream pipeline...")
        print(f"      Cameras: {len(self.camera_urls)}")
        for i, url in enumerate(self.camera_urls):
            # Mask password in URL for logging
            masked = url.replace(url.split('@')[0].split(':')[-1], '***') if '@' in url else url
            print(f"      Cam{i}: {masked}")

        pipeline = DeepStreamFacePipeline(
            camera_urls=self.camera_urls,
            recognizer=recognizer,
            result_callback=self.on_faces,
            match_threshold=self.match_threshold
        )

        # Run pipeline
        print(f"\n[3/3] Starting pipeline for {duration} seconds...")
        try:
            if pipeline.start():
                print("      Pipeline running. Waiting for faces...\n")
                time.sleep(duration)

                # Get final stats
                stats = pipeline.get_stats()

                print("\n" + "=" * 70)
                print("RESULTS")
                print("=" * 70)
                print(f"\n  PERFORMANCE:")
                print(f"    Frames processed:  {stats['frames_processed']}")
                print(f"    FPS:               {stats['fps']:.1f}")
                print(f"    Match latency:     {stats['match_time_ms']:.2f}ms (avg)")

                print(f"\n  DETECTION:")
                print(f"    Faces detected:    {stats['faces_detected']}")
                print(f"    Embeddings:        {stats['faces_recognized']}")

                print(f"\n  MATCHING:")
                print(f"    Enrolled faces:    {stats['enrolled_faces']}")
                print(f"    Known matches:     {stats['faces_matched']}")
                print(f"    Unknown faces:     {stats['faces_unknown']}")

                if self.known_persons:
                    print(f"\n  IDENTIFIED PERSONS:")
                    for name in sorted(self.known_persons):
                        print(f"    - {name}")

                print("\n" + "=" * 70)

                # Calculate match rate
                total = stats['faces_matched'] + stats['faces_unknown']
                if total > 0:
                    match_rate = stats['faces_matched'] / total * 100
                    print(f"  Match rate: {match_rate:.1f}%")

                print("=" * 70)

            else:
                print("ERROR: Failed to start pipeline")
                return False

        except KeyboardInterrupt:
            print("\n\nStopped by user")
        finally:
            pipeline.stop()

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Test full face recognition pipeline with FAISS matching"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.4,
        help="Match threshold 0-1 (default: 0.4)"
    )
    parser.add_argument(
        "--cameras", "-c",
        type=str,
        nargs="+",
        default=["rtsp://admin:Mujeeb%40321@192.168.1.64:554/Streaming/Channels/101"],
        help="Camera RTSP URLs"
    )

    args = parser.parse_args()

    tester = PipelineTester(
        camera_urls=args.cameras,
        match_threshold=args.threshold
    )

    success = tester.run(duration=args.duration)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
