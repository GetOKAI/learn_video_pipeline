#!/usr/bin/env python3
"""
FastAPI Video Generation Service
Provides REST API endpoints for the complete video pipeline using Google Veo 3.1
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json
import uuid
from datetime import datetime
import asyncio
from pathlib import Path

# Import our pipeline components
from complete_pipeline import CompletePipeline

# Initialize FastAPI app
app = FastAPI(
    title="Video Generation Pipeline API",
    description="Complete video pipeline: basic prompt → enhanced prompt → script → video using Google Veo 3.1",
    version="1.0.0"
)

# Initialize pipeline
pipeline = CompletePipeline()

# Storage for async job tracking
jobs = {}

class VideoGenerationRequest(BaseModel):
    prompt: str
    title: str = "Generated Video"
    models: Optional[List[str]] = ["veo-3.1"]

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: Optional[str] = None
    result: Optional[Dict[Any, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Video Generation Pipeline API",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "pipeline_components": {
            "prompt_enhancer": "✅ Available",
            "script_generator": "✅ Available", 
            "video_generator": "✅ Google Veo 3.1"
        }
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Check if API key is available
        api_key = os.getenv("GEMINI_API_KEY")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "api_key_configured": bool(api_key),
            "output_directories": {
                "scripts": os.path.exists("generated_scripts"),
                "videos": os.path.exists("generated_videos")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/generate-video", response_model=dict)
async def generate_video_sync(request: VideoGenerationRequest):
    """Synchronous video generation endpoint"""
    try:
        print(f"🚀 Received video generation request: {request.title}")
        
        # Process the request synchronously
        result = pipeline.process_single_prompt(
            basic_prompt=request.prompt,
            title=request.title,
            video_models=request.models
        )
        
        return {
            "status": "completed",
            "message": "Video generation completed",
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
    except Exception as e:
        print(f"❌ Video generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")

@app.post("/generate-video-async", response_model=JobStatus)
async def generate_video_async(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    """Asynchronous video generation endpoint"""
    try:
        # Create unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        job_status = {
            "job_id": job_id,
            "status": "pending",
            "progress": "Job queued for processing",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "request": {
                "prompt": request.prompt,
                "title": request.title,
                "models": request.models
            }
        }
        
        jobs[job_id] = job_status
        
        # Add background task
        background_tasks.add_task(process_video_generation, job_id, request)
        
        return JobStatus(**job_status)
        
    except Exception as e:
        print(f"❌ Failed to queue video generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")

async def process_video_generation(job_id: str, request: VideoGenerationRequest):
    """Background task to process video generation"""
    try:
        # Update job status to processing
        jobs[job_id].update({
            "status": "processing",
            "progress": "Starting video generation pipeline...",
            "updated_at": datetime.now().isoformat()
        })
        
        print(f"🔄 Processing job {job_id}: {request.title}")
        
        # Update progress for each step
        jobs[job_id].update({
            "progress": "Enhancing prompt...",
            "updated_at": datetime.now().isoformat()
        })
        
        # Run the pipeline
        result = pipeline.process_single_prompt(
            basic_prompt=request.prompt,
            title=request.title,
            video_models=request.models
        )
        
        # Update job with results
        jobs[job_id].update({
            "status": "completed",
            "progress": "Video generation completed successfully",
            "result": result,
            "updated_at": datetime.now().isoformat()
        })
        
        print(f"✅ Completed job {job_id}")
        
    except Exception as e:
        print(f"❌ Job {job_id} failed: {str(e)}")
        jobs[job_id].update({
            "status": "failed",
            "progress": "Video generation failed",
            "error": str(e),
            "updated_at": datetime.now().isoformat()
        })

@app.get("/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get status of an async video generation job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    return JobStatus(**job_data)

@app.get("/jobs")
async def list_jobs():
    """List all jobs with their status"""
    return {
        "jobs": list(jobs.values()),
        "total_jobs": len(jobs),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/download/script/{filename}")
async def download_script(filename: str):
    """Download a generated script file"""
    file_path = Path("generated_scripts") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Script file not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='text/plain'
    )

@app.get("/download/video/{filename}")
async def download_video(filename: str):
    """Download a generated video file or production guide"""
    file_path = Path("generated_videos") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Determine media type based on file extension
    media_type = "application/octet-stream"
    if filename.endswith('.mp4'):
        media_type = "video/mp4"
    elif filename.endswith('.txt'):
        media_type = "text/plain"
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type
    )

@app.get("/files/scripts")
async def list_script_files():
    """List all generated script files"""
    scripts_dir = Path("generated_scripts")
    if not scripts_dir.exists():
        return {"scripts": [], "count": 0}
    
    scripts = [
        {
            "filename": file.name,
            "created": datetime.fromtimestamp(file.stat().st_ctime).isoformat(),
            "size_bytes": file.stat().st_size,
            "download_url": f"/download/script/{file.name}"
        }
        for file in scripts_dir.iterdir()
        if file.is_file()
    ]
    
    return {
        "scripts": sorted(scripts, key=lambda x: x["created"], reverse=True),
        "count": len(scripts)
    }

@app.get("/files/videos")
async def list_video_files():
    """List all generated video files"""
    videos_dir = Path("generated_videos")
    if not videos_dir.exists():
        return {"videos": [], "count": 0}
    
    videos = [
        {
            "filename": file.name,
            "created": datetime.fromtimestamp(file.stat().st_ctime).isoformat(),
            "size_bytes": file.stat().st_size,
            "size_mb": round(file.stat().st_size / (1024 * 1024), 2),
            "type": "video" if file.suffix == ".mp4" else "document",
            "download_url": f"/download/video/{file.name}"
        }
        for file in videos_dir.iterdir()
        if file.is_file()
    ]
    
    return {
        "videos": sorted(videos, key=lambda x: x["created"], reverse=True),
        "count": len(videos)
    }

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from tracking"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    del jobs[job_id]
    return {"message": f"Job {job_id} deleted", "timestamp": datetime.now().isoformat()}

@app.post("/test-pipeline")
async def test_pipeline():
    """Test endpoint to verify pipeline functionality"""
    test_request = VideoGenerationRequest(
        prompt="Create a simple safety video about wearing hard hats on construction sites.",
        title="Hard Hat Safety Test",
        models=["veo-3.1"]
    )
    
    try:
        result = pipeline.process_single_prompt(
            basic_prompt=test_request.prompt,
            title=test_request.title,
            video_models=test_request.models
        )
        
        return {
            "status": "test_completed",
            "message": "Pipeline test successful",
            "timestamp": datetime.now().isoformat(),
            "test_result": {
                "enhancement_success": result.get('successful_enhancement', False),
                "script_success": result.get('successful_script', False),
                "video_success": result.get('successful_videos', 0) > 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline test failed: {str(e)}")

# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    # Create output directories
    os.makedirs("generated_scripts", exist_ok=True)
    os.makedirs("generated_videos", exist_ok=True)
    
    print("🚀 Starting Video Generation Pipeline API...")
    print("🎬 Using Google Veo 3.1 for video generation")
    print("📡 API Documentation: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )