# TensorRT EP Benchmark Results - LFW Evaluation
## Jetson Orin Nano 8GB | January 7, 2026

---

## Final Production Decision

| Model | Accuracy | Pure FPS | Use Case | Status |
|-------|----------|----------|----------|--------|
| **buffalo_l** | 98.23% | 45.26 | Security System, Access Control | PRODUCTION |
| **buffalo_custom_500m_r50** | 97.53% | 60.30 | Attendance System | PRODUCTION |

```
┌─────────────────────────────────────────────────────────────────┐
│                        BASE SYSTEM V2                           │
│                    (Both models available)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ SECURITY SYS  │     │ ATTENDANCE    │     │ ACCESS CTRL   │
│               │     │               │     │               │
│ buffalo_l     │     │ 500m_r50      │     │ buffalo_l     │
│ 98.23% / 45fps│     │ 97.53% / 60fps│     │ 98.23% / 45fps│
└───────────────┘     └───────────────┘     └───────────────┘
```

---

## Complete Test Matrix (TensorRT Execution Provider + FP16)

| # | Detector | Recognizer | Accuracy | LFW Latency | LFW FPS | Pure Latency | Pure FPS | Status |
|---|----------|------------|----------|-------------|---------|--------------|----------|--------|
| 1 | SCRFD_10G | ResNet50 | **98.23%** | 91.68ms | 10.91 | **22.09ms** | **45.26** | PRODUCTION |
| 2 | SCRFD_500M | ResNet50 | **97.53%** | 82.33ms | 12.15 | **16.58ms** | **60.30** | PRODUCTION |
| 3 | SCRFD_10G | MobileFaceNet | 97.98% | 99.96ms | 10.00 | 22.87ms | 43.72 | Removed |
| 4 | SCRFD_500M | MobileFaceNet | 97.29% | 160.87ms | 6.22 | 16.54ms | 60.47 | Removed |
| 5 | SCRFD_500M | ResNet100 | 49.97% | 71.78ms | 13.93 | - | - | BROKEN |
| 6 | SCRFD_10G | ResNet100 | 49.96% | 95.88ms | 10.43 | - | - | BROKEN |

---

## Pure Inference Results (640x480 input, 100 iterations, TensorRT EP FP16)

| Model Pack | Avg Latency | Min Latency | P50 Latency | P95 Latency | P99 Latency | Throughput |
|------------|-------------|-------------|-------------|-------------|-------------|------------|
| **buffalo_custom_500m_r50** | **16.58ms** | 13.71ms | 15.22ms | 20.90ms | 22.38ms | **60.30 FPS** |
| buffalo_s | 16.54ms | 13.53ms | 15.28ms | 21.42ms | 22.15ms | 60.47 FPS |
| **buffalo_l** | **22.09ms** | 16.54ms | 20.12ms | 30.78ms | 32.22ms | **45.26 FPS** |
| buffalo_custom_10g_mbf | 22.87ms | 16.07ms | 20.10ms | 30.74ms | 35.44ms | 43.72 FPS |

---

## Detailed Results (Production Models)

### buffalo_l (SCRFD_10G + ResNet50) - PRODUCTION
```
LFW Evaluation:
  Accuracy:    98.23%
  Precision:   100.00%
  Recall:      96.45%
  F1-Score:    98.19%
  Best Thresh: 0.250
  Evaluated:   5983 pairs (17 skipped)

Pure Inference (640x480):
  Avg Latency: 22.09 ms
  Min Latency: 16.54 ms
  P50 Latency: 20.12 ms
  P95 Latency: 30.78 ms
  Throughput:  45.26 FPS

Use Case: Security System, Access Control
```

### buffalo_custom_500m_r50 (SCRFD_500M + ResNet50) - PRODUCTION
```
LFW Evaluation:
  Accuracy:    97.53%
  Precision:   99.96%
  Recall:      95.08%
  F1-Score:    97.46%
  Best Thresh: 0.250
  Evaluated:   5982 pairs (18 skipped)

Pure Inference (640x480):
  Avg Latency: 16.58 ms
  Min Latency: 13.71 ms
  P50 Latency: 15.22 ms
  P95 Latency: 20.90 ms
  Throughput:  60.30 FPS

Use Case: Attendance System (high throughput)
```

---

## TensorRT EP vs CUDA EP Comparison

| Model Pack | Provider | Accuracy | Latency | FPS | Speedup |
|------------|----------|----------|---------|-----|---------|
| buffalo_l (10G+R50) | CUDA EP | 98.23% | 223.91ms | 4.47 | baseline |
| buffalo_l (10G+R50) | TensorRT EP | 98.23% | 91.68ms | 10.91 | **2.44x** |

---

## Model Packs - Final Status

```
~/.insightface/models/
├── buffalo_l                    # KEEP - Production (Security/Access)
├── buffalo_custom_500m_r50      # KEEP - Production (Attendance)
├── buffalo_s                    # REMOVED - obsolete (500m_r50 is better)
├── buffalo_custom_10g_mbf       # REMOVED - no advantage over buffalo_l
├── buffalo_custom_500m_r100     # REMOVED - broken with TensorRT FP16
├── buffalo_custom_10g_r100      # REMOVED - broken with TensorRT FP16
└── buffalo_custom_10g_r50       # REMOVED - duplicate of buffalo_l
```

---

## Known Issues

### ResNet100 with TensorRT EP is BROKEN

Both combinations using w600k_r100.onnx show ~50% accuracy (random):

**Symptoms:**
- Best threshold stuck at 0.100
- 100% recall, 0% true negatives
- All pairs predicted as same person

**Root Cause:**
- TensorRT FP16 conversion has precision issues with ResNet100
- Not worth investigating - ResNet50 achieves 98.23% which is sufficient

---

## Configuration for Production

```python
# config.py

# For Security System / Access Control (accuracy priority)
HIGH_ACCURACY_MODEL = "buffalo_l"          # 98.23%, 45 FPS

# For Attendance System (speed priority)
HIGH_SPEED_MODEL = "buffalo_custom_500m_r50"  # 97.53%, 60 FPS

# TensorRT settings
use_tensorrt: bool = True
use_fp16: bool = True
```

```python
# detector.py - TensorRT EP configuration
trt_options = {
    'device_id': 0,
    'trt_fp16_enable': True,
    'trt_engine_cache_enable': True,
    'trt_engine_cache_path': '/home/tempuser/.cache/tensorrt_engines',
}
providers = [
    ('TensorrtExecutionProvider', trt_options),
    ('CUDAExecutionProvider', {'device_id': 0}),
    'CPUExecutionProvider'
]
```

---

## Summary

| Metric | buffalo_l | buffalo_custom_500m_r50 |
|--------|-----------|-------------------------|
| Detector | SCRFD_10G | SCRFD_500M |
| Recognizer | ResNet50 | ResNet50 |
| LFW Accuracy | 98.23% | 97.53% |
| Pure Inference | 45.26 FPS | 60.30 FPS |
| Latency | 22.09ms | 16.58ms |
| Use Case | Security, Access | Attendance |

---

*Generated: January 7, 2026*
*Platform: Jetson Orin Nano 8GB, JetPack 6.2, TensorRT 8.x*
*Test: 100 iterations pure inference, 640x480 input*
