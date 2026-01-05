# Claude Instructions - FRS Project Workflow

**Last Updated:** 2025-01-05
**Current Branch:** `feature/base-system-v2`

---

## Project Locations

| Project | Path | Purpose |
|---------|------|---------|
| **Frs_sec (Main Repo)** | `/home/tempuser/Downloads/Frs_sec` | Main GitHub repo, all work here |
| **CV_Project (Reference)** | `/home/tempuser/Downloads/CV_Project` | Basic version, reference only |
| **Backup** | `/home/tempuser/Downloads/CV_Project_backup_*.zip` | Safety backup |

---

## Golden Rules

### 1. Always Check Before Modifying
```bash
# Before ANY code change:
cd /home/tempuser/Downloads/Frs_sec
git status
git branch
```

### 2. Work in Correct Branch
```bash
# Must be on feature/base-system-v2 for base system work
git checkout feature/base-system-v2
```

### 3. Commit Frequently with Clear Messages
```bash
git add <specific-files>
git commit -m "Short description

- Detail 1
- Detail 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

### 4. Never Force Push to Main
```bash
# NEVER do this:
git push --force origin main  # FORBIDDEN
```

### 5. Keep Backup Before Major Changes
```bash
# Before risky operations:
cp -r important_file important_file.backup
```

---

## Folder Structure (Frs_sec)

```
/home/tempuser/Downloads/Frs_sec/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # API endpoints
│   │   ├── core/                # detector.py, recognizer.py
│   │   ├── models/              # Database models
│   │   ├── services/            # Stream, processor, etc.
│   │   ├── config.py            # Configuration
│   │   └── main.py              # FastAPI app
│   └── requirements.txt
├── frontend/                     # React app
├── data/
│   ├── persons/                  # Enrolled person images
│   ├── embeddings/               # Model embeddings (.pkl)
│   └── models/                   # Downloaded models (NEW)
├── configs/                      # Config files (NEW for DeepStream)
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
├── BASE_SYSTEM_UPGRADE_PLAN.md   # Upgrade plan
├── CLAUDE_INSTRUCTIONS.md        # This file
├── PROJECT_DOCUMENTATION.md      # Full project docs (copy from CV_Project)
└── start.sh / stop.sh
```

---

## Current Task: Model Upgrade

### Phase 1 Checklist

- [ ] Create `data/models/` folder for new models
- [ ] Download SCRFD_10G_KPS
- [ ] Download ArcFace ResNet100 (glint360k_r100)
- [ ] Update `backend/app/core/detector.py`
- [ ] Update `backend/app/core/recognizer.py`
- [ ] Update `backend/app/config.py` with new model paths
- [ ] Test detection accuracy
- [ ] Test recognition accuracy
- [ ] Commit and push

### Model Sources

| Model | Source | File |
|-------|--------|------|
| SCRFD_10G_KPS | InsightFace | `scrfd_10g_kps.onnx` |
| ArcFace R100 | InsightFace | `glint360k_r100.onnx` or `w600k_r50.onnx` |

### Download Commands
```bash
# InsightFace models auto-download to ~/.insightface/models/
# Or manually from: https://github.com/deepinsight/insightface/tree/master/model_zoo
```

---

## File Modification Rules

### Before Editing Any File:
1. Read the file first with `Read` tool
2. Understand existing structure
3. Make minimal changes
4. Test after changes

### Files I CAN Modify (base-system-v2 branch):
- `backend/app/core/detector.py`
- `backend/app/core/recognizer.py`
- `backend/app/config.py`
- `backend/app/services/stream.py`
- Documentation files (*.md)
- New files in `data/models/`, `configs/`

### Files I Should NOT Modify Yet:
- `backend/app/services/alerts.py` (product-specific)
- `backend/app/api/routes/auth.py` (product-specific)
- `frontend/*` (until backend is stable)
- `.git/*` (never)

---

## Testing Commands

```bash
# Start backend only (for testing)
cd /home/tempuser/Downloads/Frs_sec/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Check if models load
python -c "from app.core.detector import FaceDetector; d = FaceDetector(); d.initialize()"

# Check GPU usage
tegrastats

# Check CUDA
nvcc --version
python -c "import torch; print(torch.cuda.is_available())"
```

---

## Git Workflow

### Daily Start
```bash
cd /home/tempuser/Downloads/Frs_sec
git status
git branch  # Should be feature/base-system-v2
git pull origin feature/base-system-v2
```

### After Changes
```bash
git status
git diff  # Review changes
git add <files>
git commit -m "message"
git push origin feature/base-system-v2
```

### If Something Goes Wrong
```bash
# Undo uncommitted changes to a file
git checkout -- <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See history
git log --oneline -10
```

---

## Documentation Updates

### When to Update Docs:
- After completing any task
- After changing any configuration
- After adding new feature
- After fixing bugs

### Which Docs to Update:
| Change | Update |
|--------|--------|
| Model change | `BASE_SYSTEM_UPGRADE_PLAN.md`, `PROJECT_DOCUMENTATION.md` |
| Config change | `config.py` comments, `README.md` |
| New feature | `README.md`, relevant plan doc |
| Performance results | `PROJECT_DOCUMENTATION.md` |

---

## Error Recovery

### If Backend Won't Start
```bash
# Check logs
tail -f /tmp/frs_backend.log

# Check Python errors
cd /home/tempuser/Downloads/Frs_sec/backend
python -c "from app.main import app"
```

### If Models Won't Load
```bash
# Check model files exist
ls -la ~/.insightface/models/

# Check ONNX Runtime
python -c "import onnxruntime; print(onnxruntime.get_available_providers())"
```

### If Git Issues
```bash
# Check current state
git status
git branch -v

# Recover stashed changes
git stash list
git stash pop
```

---

## Communication with User

### Always Tell User:
- What I'm about to do
- What files I'm modifying
- Results of tests
- Any errors encountered
- Next steps

### Ask User When:
- Unsure about approach
- Multiple valid options exist
- Need to delete/remove features
- Before major refactoring

---

## Quick Reference

| Action | Command/Tool |
|--------|--------------|
| Read file | `Read` tool |
| Edit file | `Edit` tool |
| Create file | `Write` tool |
| Run command | `Bash` tool |
| Search code | `Grep` tool |
| Find files | `Glob` tool |
| Track tasks | `TodoWrite` tool |

---

## Current Session Notes

*Add notes here during work session:*

- 2025-01-05: Created branch `feature/base-system-v2`
- 2025-01-05: Created upgrade plan document
- 2025-01-05: Downloaded ResNet100 model from OpenVINO
- 2025-01-05: Created buffalo_r100 model pack (SCRFD_10G + ResNet100)
- 2025-01-05: Created buffalo_r100_fp16 (FP16 needs TensorRT for proper use)
- 2025-01-05: Verified buffalo_r100 (FP32) works correctly
- 2025-01-05: buffalo_l_fp16 is current production choice (fastest)
- 2025-01-05: buffalo_r100 available for highest accuracy scenarios

## Model Locations

```
~/.insightface/models/
├── buffalo_sc/          # Smallest (CV_Project default)
├── buffalo_s/           # Small
├── buffalo_l/           # SCRFD_10G + ResNet50
├── buffalo_l_fp16/      # Production (FP16, fast)
├── buffalo_r100/        # SCRFD_10G + ResNet100 (FP32, highest accuracy)
└── buffalo_r100_fp16/   # FP16 (needs TensorRT conversion)

/home/tempuser/Downloads/Frs_sec/data/models/
└── arcface_r100/
    └── arcface_r100.onnx  # Original ResNet100 download
```

---
