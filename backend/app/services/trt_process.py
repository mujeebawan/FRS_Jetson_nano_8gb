"""
TensorRT inference in a separate process.
Avoids CUDA context conflicts between DeepStream and pycuda.
Uses 'spawn' context to create fresh process without inherited CUDA state.
"""

import os
import sys
import time
import logging
import numpy as np
import multiprocessing as mp
from multiprocessing.synchronize import Event as EventType
from dataclasses import dataclass
from typing import List, Tuple, Optional, Any
import queue

# Use spawn context to ensure fresh CUDA state in child process
_mp_context = mp.get_context('spawn')

logger = logging.getLogger(__name__)

# Engine paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
TRT_ENGINE_DIR = os.path.join(PROJECT_ROOT, 'data', 'tensorrt_engines')
DET_ENGINE = os.path.join(TRT_ENGINE_DIR, 'det_10g_fp16.engine')
REC_ENGINE = os.path.join(TRT_ENGINE_DIR, 'w600k_r50_batch32_fp16.engine')


@dataclass
class DetectionResult:
    """Result from TRT process"""
    frame_num: int
    boxes: np.ndarray  # (N, 5) [x1, y1, x2, y2, score]
    embeddings: np.ndarray  # (N, 512)
    detection_time: float
    recognition_time: float


def trt_worker_process(
    input_queue: Any,
    output_queue: Any,
    stop_event: Any,
    det_engine: str,
    rec_engine: str,
    conf_threshold: float = 0.5
):
    """
    TensorRT inference worker - runs in separate process.
    Has its own CUDA context, isolated from DeepStream.
    """
    import pycuda.autoinit  # Initialize CUDA in THIS process only

    # Import TRT inference (creates CUDA resources in this process)
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from core.trt_inference import TRTFaceProcessor

    logger.info(f"TRT worker process started (PID: {os.getpid()})")

    try:
        # Initialize TRT processor
        processor = TRTFaceProcessor(
            detector_engine=det_engine,
            recognizer_engine=rec_engine,
            det_size=(640, 640),
            conf_threshold=conf_threshold,
            batch_size=32
        )
        logger.info("TRT processor initialized in worker process")

        consecutive_errors = 0

        while not stop_event.is_set():
            try:
                # Get frame from queue (with timeout to check stop_event)
                try:
                    frame, frame_num = input_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Detection
                det_start = time.time()
                boxes, kps = processor.detector.detect(frame)
                det_time = (time.time() - det_start) * 1000

                # Recognition
                rec_start = time.time()
                if len(boxes) > 0 and len(kps) > 0:
                    embeddings = processor.recognizer.get_embeddings(frame, kps)
                else:
                    embeddings = np.array([])
                rec_time = (time.time() - rec_start) * 1000

                # Send result back
                result = DetectionResult(
                    frame_num=frame_num,
                    boxes=boxes,
                    embeddings=embeddings,
                    detection_time=det_time,
                    recognition_time=rec_time
                )

                try:
                    output_queue.put_nowait(result)
                except queue.Full:
                    # Drop oldest result if queue full
                    try:
                        output_queue.get_nowait()
                        output_queue.put_nowait(result)
                    except:
                        pass

                consecutive_errors = 0

                # Log periodically
                if frame_num <= 10 or frame_num % 100 == 0:
                    print(f"[TRT-PROC] Frame #{frame_num}: {len(boxes)} faces, "
                          f"det={det_time:.1f}ms, rec={rec_time:.1f}ms", flush=True)

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"TRT worker error ({consecutive_errors}): {e}")
                if consecutive_errors >= 20:
                    logger.critical("Too many TRT errors, worker exiting")
                    break
                time.sleep(0.1)

    except Exception as e:
        logger.critical(f"TRT worker failed to initialize: {e}")
        import traceback
        traceback.print_exc()

    logger.info("TRT worker process exiting")


class TRTProcessManager:
    """
    Manages TensorRT inference in a separate process.
    Main process (DeepStream) sends frames, child process returns detections.
    Uses 'spawn' context to ensure fresh CUDA state in child process.
    """

    def __init__(
        self,
        det_engine: str = DET_ENGINE,
        rec_engine: str = REC_ENGINE,
        conf_threshold: float = 0.5,
        queue_size: int = 4
    ):
        self.det_engine = det_engine
        self.rec_engine = rec_engine
        self.conf_threshold = conf_threshold

        # IPC queues using spawn context (ensures fresh CUDA state)
        self.input_queue = _mp_context.Queue(maxsize=queue_size)
        self.output_queue = _mp_context.Queue(maxsize=queue_size)
        self.stop_event = _mp_context.Event()

        # Worker process
        self.process = None
        self._running = False

        # Latest results cache
        self._latest_result: Optional[DetectionResult] = None

    def start(self) -> bool:
        """Start the TRT worker process."""
        if self._running:
            return True

        # Verify engines exist
        if not os.path.exists(self.det_engine):
            logger.error(f"Detection engine not found: {self.det_engine}")
            return False
        if not os.path.exists(self.rec_engine):
            logger.error(f"Recognition engine not found: {self.rec_engine}")
            return False

        self.stop_event.clear()

        # Start worker process using spawn context (fresh CUDA state)
        self.process = _mp_context.Process(
            target=trt_worker_process,
            args=(
                self.input_queue,
                self.output_queue,
                self.stop_event,
                self.det_engine,
                self.rec_engine,
                self.conf_threshold
            ),
            daemon=True
        )
        self.process.start()
        self._running = True

        # Wait a moment for process to initialize
        time.sleep(1.0)

        logger.info(f"TRT process manager started (worker PID: {self.process.pid})")
        return True

    def stop(self):
        """Stop the TRT worker process."""
        if not self._running:
            return

        self._running = False
        self.stop_event.set()

        if self.process and self.process.is_alive():
            self.process.join(timeout=3)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)

        # Clear queues
        try:
            while not self.input_queue.empty():
                self.input_queue.get_nowait()
        except:
            pass
        try:
            while not self.output_queue.empty():
                self.output_queue.get_nowait()
        except:
            pass

        logger.info("TRT process manager stopped")

    def submit_frame(self, frame: np.ndarray, frame_num: int) -> bool:
        """
        Submit a frame for detection (non-blocking).
        Returns True if frame was queued, False if queue full.
        """
        if not self._running:
            return False

        try:
            self.input_queue.put_nowait((frame.copy(), frame_num))
            return True
        except queue.Full:
            return False

    def get_result(self, timeout: float = 0) -> Optional[DetectionResult]:
        """
        Get detection result (non-blocking by default).
        Returns None if no result available.
        """
        if not self._running:
            return self._latest_result

        try:
            if timeout > 0:
                result = self.output_queue.get(timeout=timeout)
            else:
                result = self.output_queue.get_nowait()
            self._latest_result = result
            return result
        except queue.Empty:
            return None

    def get_latest_result(self) -> Optional[DetectionResult]:
        """Get the most recent detection result (cached)."""
        # Drain queue and return latest
        while True:
            result = self.get_result(timeout=0)
            if result is None:
                break
        return self._latest_result

    @property
    def is_running(self) -> bool:
        return self._running and self.process is not None and self.process.is_alive()
