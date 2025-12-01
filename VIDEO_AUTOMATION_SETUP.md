# Video Automation Pipeline Setup

## Overview

The video automation pipeline has been integrated into the main application. When `main.py` is run, it can now trigger the complete video generation pipeline through API endpoints.

## Architecture

```
main.py (FastAPI App)
    ↓ HTTP Request
api_call.py (Video API Service)
    ↓ Background Task
run_pipeline.py (Unified Pipeline)
    ↓ Executes
video_gen.py + script_gen.py (Pipeline Components)
```

## New Endpoints in main.py

### 1. Trigger Video Automation
**POST** `/video/automation/trigger`

Triggers the video generation automation pipeline in the background.

**Request Body:**
```json
{
  "mode": "complete",
  "video_models": ["veo-3.1"],
  "limit": null,
  "enhanced_prompts_file": "enhanced_prompts.json"
}
```

**Parameters:**
- `mode`: Pipeline mode
  - `"scripts"`: Generate enhanced prompts and scripts only
  - `"videos"`: Generate videos from existing enhanced prompts
  - `"complete"`: Run full pipeline (scripts + videos)
- `video_models`: List of video models to use (default: `["veo-3.1"]`)
- `limit`: Maximum number of prompts to process (optional)
- `enhanced_prompts_file`: Path to enhanced prompts JSON file (default: `"enhanced_prompts.json"`)

**Response:**
```json
{
  "status": "success",
  "message": "Video automation pipeline triggered successfully",
  "job_info": {
    "job_id": "uuid-here",
    "status": "pending",
    "progress": "Automation pipeline queued for processing"
  },
  "tracking_url": "http://localhost:8000/job/uuid-here",
  "timestamp": "2024-11-30T12:00:00"
}
```

### 2. Check Job Status
**GET** `/video/automation/status/{job_id}`

Get the current status of a video automation job.

**Response:**
```json
{
  "status": "success",
  "job_status": {
    "job_id": "uuid-here",
    "status": "processing",
    "progress": "Running complete pipeline (scripts + videos)...",
    "result": null,
    "error": null,
    "created_at": "2024-11-30T12:00:00",
    "updated_at": "2024-11-30T12:01:00"
  },
  "timestamp": "2024-11-30T12:01:30"
}
```

## Setup Instructions

### 1. Install Dependencies

```bash
# Activate your virtual environment
source video_automation/bin/activate

# Install/update dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or update your `.env` file:

```bash
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_PROJECT_ID=your_project_id

# Video API Service URL (if running on different host/port)
VIDEO_API_URL=http://localhost:8000
```

### 3. Start the Services

You need to run **both** services:

**Terminal 1 - Start the Video API Service (api_call.py):**
```bash
cd /path/to/learn_video_pipeline
source video_automation/bin/activate
python api_call.py
```
This will start on `http://localhost:8000`

**Terminal 2 - Start the Main Application (main.py):**
```bash
cd /path/to/your/main/app
source video_automation/bin/activate
uvicorn main:app --reload --port 8001
```
This will start on `http://localhost:8001`

## Usage Examples

### Example 1: Trigger Complete Pipeline

```bash
curl -X POST "http://localhost:8001/video/automation/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "complete",
    "video_models": ["veo-3.1"],
    "limit": 2
  }'
```

### Example 2: Generate Scripts Only

```bash
curl -X POST "http://localhost:8001/video/automation/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "scripts"
  }'
```

### Example 3: Check Job Status

```bash
curl -X GET "http://localhost:8001/video/automation/status/your-job-id-here"
```

## How It Works

1. **Client calls** `/video/automation/trigger` on `main.py`
2. **main.py forwards** the request to `api_call.py` service
3. **api_call.py creates** a background job and returns job ID
4. **Background task runs** `run_pipeline.py` which executes the complete pipeline
5. **Client can poll** `/video/automation/status/{job_id}` to track progress
6. **When complete**, the job status will show results with file paths

## Output Files

Generated files are saved in:
- **Scripts**: `generated_scripts/`
- **Videos**: `generated_videos/`
- **Results**: `video_generation_results_*.json`

## Notes

- The pipeline runs asynchronously in the background
- Use the job ID to track progress
- The video API service (`api_call.py`) must be running for automation to work
- Make sure `GEMINI_API_KEY` is configured in your `.env` file

