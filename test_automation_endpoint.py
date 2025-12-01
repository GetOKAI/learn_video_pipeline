#!/usr/bin/env python3
"""
Test script for the video automation endpoints
Demonstrates how to trigger the pipeline and check job status
"""

import requests
import time
import json
from typing import Optional

# Configuration
MAIN_APP_URL = "http://localhost:8001"  # main.py URL
VIDEO_API_URL = "http://localhost:8000"  # api_call.py URL

def trigger_automation(mode: str = "complete", 
                      video_models: Optional[list] = None,
                      limit: Optional[int] = None) -> dict:
    """
    Trigger the video automation pipeline
    
    Args:
        mode: "scripts", "videos", or "complete"
        video_models: List of video models to use
        limit: Maximum number of prompts to process
    
    Returns:
        Response from the API
    """
    if video_models is None:
        video_models = ["veo-3.1"]
    
    endpoint = f"{MAIN_APP_URL}/video/automation/trigger"
    
    payload = {
        "mode": mode,
        "video_models": video_models,
        "limit": limit
    }
    
    print(f"🚀 Triggering automation pipeline...")
    print(f"📡 Endpoint: {endpoint}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Pipeline triggered successfully!")
        print(f"🆔 Job ID: {result['job_info']['job_id']}")
        print(f"📊 Status: {result['job_info']['status']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error triggering pipeline: {e}")
        return {"error": str(e)}

def check_job_status(job_id: str) -> dict:
    """
    Check the status of a video automation job
    
    Args:
        job_id: The job ID to check
    
    Returns:
        Job status information
    """
    endpoint = f"{MAIN_APP_URL}/video/automation/status/{job_id}"
    
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        job_status = result['job_status']
        print(f"📊 Job Status: {job_status['status']}")
        print(f"📝 Progress: {job_status['progress']}")
        
        if job_status.get('error'):
            print(f"❌ Error: {job_status['error']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking status: {e}")
        return {"error": str(e)}

def wait_for_completion(job_id: str, max_wait_seconds: int = 600, poll_interval: int = 5):
    """
    Wait for a job to complete, polling at regular intervals
    
    Args:
        job_id: The job ID to monitor
        max_wait_seconds: Maximum time to wait (default: 10 minutes)
        poll_interval: Seconds between status checks (default: 5)
    """
    print(f"\n⏳ Waiting for job {job_id} to complete...")
    print(f"⏱️  Max wait time: {max_wait_seconds} seconds")
    print(f"🔄 Polling every {poll_interval} seconds")
    
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > max_wait_seconds:
            print(f"\n⚠️ Timeout: Job did not complete within {max_wait_seconds} seconds")
            break
        
        result = check_job_status(job_id)
        
        if "error" in result:
            print(f"\n❌ Error checking status")
            break
        
        status = result['job_status']['status']
        
        if status == "completed":
            print(f"\n✅ Job completed successfully!")
            print(f"📊 Results:")
            print(json.dumps(result['job_status'].get('result', {}), indent=2))
            break
        
        elif status == "failed":
            print(f"\n❌ Job failed!")
            print(f"Error: {result['job_status'].get('error', 'Unknown error')}")
            break
        
        print(f"⏳ Still {status}... (elapsed: {int(elapsed)}s)")
        time.sleep(poll_interval)

def main():
    """Main test function"""
    print("=" * 80)
    print("Video Automation Pipeline Test")
    print("=" * 80)
    
    # Test 1: Trigger complete pipeline with limit
    print("\n📝 Test 1: Trigger complete pipeline (limit: 1)")
    print("-" * 80)
    
    result = trigger_automation(
        mode="complete",
        video_models=["veo-3.1"],
        limit=1
    )
    
    if "error" not in result:
        job_id = result['job_info']['job_id']
        
        # Wait for completion
        wait_for_completion(job_id, max_wait_seconds=600, poll_interval=10)
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    main()

