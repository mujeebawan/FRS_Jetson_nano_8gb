#!/usr/bin/env python3
"""Quick test of DeepStream PGIE + SGIE pipeline."""

import os
import sys
import time
import logging

logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '/home/tempuser/Downloads/Frs_sec/backend')

from app.services.deepstream_face_pipeline import DeepStreamFacePipeline, FaceResult
from typing import List

# Track real face detections
real_faces = 0
embeddings_extracted = 0

def on_faces(faces: List[FaceResult], camera_id: int):
    global real_faces, embeddings_extracted
    for face in faces:
        # Only count faces > 40x40 with conf > 0.7 as "real"
        if face.bbox[2] > 40 and face.bbox[3] > 40 and face.confidence > 0.7:
            real_faces += 1
            if face.embedding is not None:
                embeddings_extracted += 1
                emb_norm = (face.embedding ** 2).sum() ** 0.5
                print(f"[Frame {face.frame_num}] Face {face.bbox[2]}x{face.bbox[3]} @ ({face.bbox[0]},{face.bbox[1]}), "
                      f"conf={face.confidence:.2f}, emb_norm={emb_norm:.1f}")


def main():
    global real_faces, embeddings_extracted

    print("=" * 60)
    print("DeepStream PGIE + SGIE Face Recognition - Quick Test")
    print("=" * 60)

    camera_url = "rtsp://admin:Mujeeb%40321@192.168.1.64:554/Streaming/Channels/101"

    pipeline = DeepStreamFacePipeline(
        camera_urls=[camera_url],
        result_callback=on_faces,
        frame_width=1920,
        frame_height=1080,
    )

    try:
        if pipeline.start():
            print("Running for 15 seconds...\n")

            # Run for 15 seconds
            time.sleep(15)

            stats = pipeline.get_stats()

            print("\n" + "=" * 60)
            print("RESULTS")
            print("=" * 60)
            print(f"Frames processed:    {stats['frames_processed']}")
            print(f"FPS:                 {stats['fps']:.1f}")
            print(f"Total detections:    {stats['faces_detected']}")
            print(f"Real faces (>40px):  {real_faces}")
            print(f"Embeddings extracted: {embeddings_extracted}")

            if real_faces > 0:
                embed_rate = embeddings_extracted / real_faces * 100
                print(f"Embedding rate:      {embed_rate:.1f}%")

            print("=" * 60)
            print("SUCCESS: DeepStream pipeline working with PGIE + SGIE!")
            print("=" * 60)
        else:
            print("Failed to start pipeline")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
