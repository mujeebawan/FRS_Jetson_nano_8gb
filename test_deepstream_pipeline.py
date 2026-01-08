#!/usr/bin/env python3
"""
Test DeepStream PGIE + SGIE face recognition pipeline.
"""

import os
import sys
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')

from app.services.deepstream_face_pipeline import DeepStreamFacePipeline, FaceResult
from typing import List


def on_faces(faces: List[FaceResult], camera_id: int):
    """Callback for face detections."""
    for face in faces:
        if face.embedding is not None:
            emb_norm = (face.embedding ** 2).sum() ** 0.5
            emb_str = f"emb[512] norm={emb_norm:.2f}"
        else:
            emb_str = "no_emb"

        print(f"Cam{camera_id} Frame{face.frame_num}: "
              f"Face ({face.bbox[2]}x{face.bbox[3]}) at ({face.bbox[0]},{face.bbox[1]}), "
              f"conf={face.confidence:.3f}, track={face.track_id}, {emb_str}")


def main():
    print("=" * 70)
    print("DeepStream PGIE + SGIE Face Recognition Pipeline Test")
    print("=" * 70)

    # Camera URL
    camera_url = "rtsp://admin:Mujeeb%40321@192.168.1.64:554/Streaming/Channels/101"

    print(f"\nCamera: {camera_url}")
    print(f"Duration: 30 seconds")
    print()

    pipeline = DeepStreamFacePipeline(
        camera_urls=[camera_url],
        result_callback=on_faces,
        frame_width=1920,
        frame_height=1080,
    )

    try:
        if pipeline.start():
            print("Pipeline started, waiting for faces...")
            print("-" * 70)

            # Run for 30 seconds with periodic stats
            for i in range(30):
                time.sleep(1)
                stats = pipeline.get_stats()
                if i % 5 == 4:  # Every 5 seconds
                    print(f"\n[{i+1}s] Frames: {stats['frames_processed']}, "
                          f"Faces detected: {stats['faces_detected']}, "
                          f"Faces recognized: {stats['faces_recognized']}, "
                          f"FPS: {stats['fps']:.1f}")

            print("\n" + "=" * 70)
            print("FINAL STATS")
            print("=" * 70)
            stats = pipeline.get_stats()
            print(f"Total frames: {stats['frames_processed']}")
            print(f"Total faces detected: {stats['faces_detected']}")
            print(f"Total faces recognized: {stats['faces_recognized']}")
            print(f"Average FPS: {stats['fps']:.1f}")

            if stats['faces_detected'] > 0:
                recognition_rate = stats['faces_recognized'] / stats['faces_detected'] * 100
                print(f"Recognition rate: {recognition_rate:.1f}%")
        else:
            print("Failed to start pipeline")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
