# Quick Start Guide - Video Automation Pipeline

## Prerequisites

1. Python 3.8+ installed
2. Virtual environment created (`video_automation`)
3. `.env` file with `GEMINI_API_KEY` configured

## Step-by-Step Setup

### 1. Activate Virtual Environment

```bash
cd /Users/yshriyasravani/Documents/learn_video_pipeline
source video_automation/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Environment Variables

Make sure your `.env` file contains:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_PROJECT_ID=your_project_id
VIDEO_API_URL=http://localhost:8000
```

### 4. Start the Video API Service

Open **Terminal 1**:

```bash
cd /Users/yshriyasravani/Documents/learn_video_pipeline
source video_automation/bin/activate
python api_call.py
```

You should see:
```
🚀 Starting Video Generation Pipeline API...
🎬 Using Google Veo 3.1 for video generation
📡 API Documentation: http://localhost:8000/docs
```

### 5. Start the Main Application (if needed)

If you need to run `main.py` separately, open **Terminal 2**:

```bash
cd /path/to/your/main/app
source video_automation/bin/activate
uvicorn main:app --reload --port 8001
```

## Testing the Integration

### Option 1: Using the Test Script

```bash
# In a new terminal
cd /Users/yshriyasravani/Documents/learn_video_pipeline
source video_automation/bin/activate
python test_automation_endpoint.py
```

### Option 2: Using curl

**Trigger the pipeline:**

```bash
curl -X POST "http://localhost:8001/video/automation/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "complete",
    "video_models": ["veo-3.1"],
    "limit": 1
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Video automation pipeline triggered successfully",
  "job_info": {
    "job_id": "abc-123-def-456",
    "status": "pending",
    "progress": "Automation pipeline queued for processing"
  },
  "tracking_url": "http://localhost:8000/job/abc-123-def-456"
}
```

**Check job status:**

```bash
curl "http://localhost:8001/video/automation/status/abc-123-def-456"
```

### Option 3: Using Python requests

```python
import requests

# Trigger pipeline
response = requests.post(
    "http://localhost:8001/video/automation/trigger",
    json={
        "mode": "complete",
        "video_models": ["veo-3.1"],
        "limit": 1
    }
)

result = response.json()
job_id = result['job_info']['job_id']
print(f"Job ID: {job_id}")

# Check status
status_response = requests.get(
    f"http://localhost:8001/video/automation/status/{job_id}"
)
print(status_response.json())
```

## Pipeline Modes

### 1. Scripts Only
Generates enhanced prompts and scripts without creating videos:

```json
{
  "mode": "scripts"
}
```

### 2. Videos Only
Generates videos from existing enhanced prompts:

```json
{
  "mode": "videos",
  "video_models": ["veo-3.1"],
  "enhanced_prompts_file": "enhanced_prompts.json"
}
```

### 3. Complete Pipeline (Default)
Runs the full pipeline: scripts → videos:

```json
{
  "mode": "complete",
  "video_models": ["veo-3.1"],
  "limit": 2
}
```

## Monitoring Progress

Job statuses:
- `pending`: Job queued, not started yet
- `processing`: Pipeline is running
- `completed`: Successfully finished
- `failed`: Error occurred

Poll the status endpoint every 5-10 seconds to track progress.

## Output Files

Generated files will be saved in:

- **Scripts**: `generated_scripts/script_*.txt`
- **Videos**: `generated_videos/*.mp4`
- **Results**: `video_generation_results_*.json`

## Troubleshooting

### Issue: "Video automation service unavailable"

**Solution:** Make sure `api_call.py` is running on port 8000

```bash
# Check if service is running
curl http://localhost:8000/health
```

### Issue: "GEMINI_API_KEY not found"

**Solution:** Add your API key to `.env` file

```bash
echo "GEMINI_API_KEY=your_key_here" >> .env
```

### Issue: "Job not found"

**Solution:** The job ID might be incorrect or expired. Trigger a new job.

## API Documentation

Once `api_call.py` is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Next Steps

1. ✅ Test with a single video (`limit: 1`)
2. ✅ Review generated scripts in `generated_scripts/`
3. ✅ Check generated videos in `generated_videos/`
4. ✅ Scale up by removing the `limit` parameter
5. ✅ Integrate into your automation workflow

## Support

For detailed documentation, see:
- `VIDEO_AUTOMATION_SETUP.md` - Complete setup guide
- `CHANGES_SUMMARY.md` - Technical changes overview
- `PIPELINE_ARCHITECTURE.md` - Architecture details (if exists)

