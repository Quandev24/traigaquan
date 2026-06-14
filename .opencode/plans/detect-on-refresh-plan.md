# Plan: Auto-run AI Detection on Page Refresh

## Goal
Make AI detection run automatically on every page refresh and save results to `static/ai_detections/` folder without manual button clicks.

## Files to Modify

### 1. Backend: `backend/services/camera_stream_worker.py`
- Add `latest_raw_frame` attribute to store the most recent frame
- Add `force_detect()` method for immediate detection

### 2. Backend: `backend/services/stream_manager.py`
- Add `detect_all()` method to force detection on all workers

### 3. Backend: `backend/api/routes/ai_detection.py`
- Add `POST /api/ai/detect-all` endpoint

### 4. Frontend: `static/index.html`
- Define `renderAIDetection(coopId)` function
- Define `runAIDetection(coopId)` function
- Remove 60-second throttle
- Auto-trigger on page load
