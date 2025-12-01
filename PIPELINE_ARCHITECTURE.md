# Pipeline Architecture Overview

## Current System Components

### 1. **`script_gen.py`** - Standalone Script Generator
- **Purpose**: Generate enhanced prompts, actor scripts, and faceless scripts
- **Input**: `human_prompts.json` 
- **Output**: 
  - `enhanced_prompts.json`
  - `transcripts_actor.json` 
  - `transcripts_faceless.json`
- **Model**: Gemini 2.5-Flash
- **Status**: ✅ Working independently

### 2. **`video_gen.py`** - Video Generation Pipeline  
- **Purpose**: Generate scripts + videos using Veo 3.1
- **Components**:
  - `ScriptGenerator` class (different from script_gen.py)
  - `VideoGenerator` class (Veo 3.1 integration)
  - `CompletePipeline` class (orchestrator)
- **Input**: Takes enhanced prompts directly
- **Output**: Scripts + actual video files (.mp4)
- **Models**: Gemini 2.5-Flash + Veo 3.1
- **Status**: ✅ Working but separate from script_gen.py

### 3. **`main.py`** - FastAPI Web Service
- **Purpose**: HTTP API endpoints for video generation
- **Features**:
  - `/generate-video` - Synchronous video generation  
  - `/generate-video-async` - Background job processing
  - `/health` - Health check endpoint
  - File download endpoints
- **Backend**: Uses `video_gen.py`
- **Status**: ✅ Web service (not connected to script_gen.py)

## What `main.py` Does:

```python
# main.py provides a REST API for video generation
from video_gen import CompletePipeline

app = FastAPI()
pipeline = CompletePipeline()

@app.post("/generate-video")
async def generate_video_sync(request: VideoGenerationRequest):
    result = pipeline.process_single_prompt(
        basic_prompt=request.prompt,
        title=request.title,
        video_models=request.models
    )
    return result
```

**Main.py Features:**
- ✅ Web API for video generation
- ✅ Synchronous and asynchronous endpoints  
- ✅ Job tracking and status monitoring
- ✅ File download capabilities
- ✅ Health checks and monitoring
- ❌ **NOT connected to script_gen.py**

## What `video_gen.py` Does:

```python
class CompletePipeline:
    def __init__(self):
        self.script_generator = ScriptGenerator()  # Internal script gen
        self.video_generator = VideoGenerator()   # Veo 3.1 integration
    
    def process_single_prompt(self, enhanced_prompt, title, models):
        # 1. Generate script using internal ScriptGenerator
        script = self.script_generator.generate_script(enhanced_prompt, title)
        
        # 2. Generate video using VideoGenerator + Veo 3.1
        video = self.video_generator.generate_video(enhanced_prompt, title, model)
        
        return combined_results
```

**Complete Pipeline Features:**
- ✅ Internal script generation (Gemini 2.5-Flash)
- ✅ Veo 3.1 video generation  
- ✅ File management (saves scripts + videos)
- ✅ Error handling and retries
- ✅ Multiple video models support
- ❌ **Uses different script generation than script_gen.py**

## New `run.py` - Unified Solution

**Purpose**: Connect `script_gen.py` with `video_gen.py` video generation

### Usage Examples:

```bash
# Generate scripts only (uses script_gen.py)
python run.py --mode scripts

# Generate videos only (from existing enhanced_prompts.json)  
python run.py --mode videos --models veo-3.1 veo-fast

# Complete pipeline (scripts → videos)
python run.py --mode complete --models veo-3.1 --limit 5

# Use custom enhanced prompts file
python run.py --mode videos --enhanced-file my_prompts.json
```

### Pipeline Flow:

```
human_prompts.json 
    ↓ (script_gen.py)
enhanced_prompts.json + transcripts_*.json
    ↓ (video_gen.py video generation)  
generated_videos/*.mp4

## 4. `mux_uploader.py` - Optional Mux upload integration
- **Purpose**: Upload generated videos to Mux (hosting/playback) after generation.
- **Implementation**: A small wrapper `mux_uploader.py` uses the installed `mux` CLI to create uploads and return Mux responses. This avoids adding a Python SDK dependency and leverages the already-installed CLI.
- **Requirements**:
  - `mux` CLI installed and available in PATH (e.g., `npm install -g @mux/cli`)
  - Authentication via `mux login` or environment variables `MUX_TOKEN_ID` and `MUX_TOKEN_SECRET` exported before running
- **Behavior**:
  - Can be invoked manually to upload a generated MP4
  - Can be wired into `video_gen.py` or `run.py` to auto-upload when a video is successfully generated
  - Returns the raw Mux CLI JSON response; playback IDs/asset info are available from that response

```

## Architecture Summary:

| Component | Purpose | Input | Output | Status |
|-----------|---------|-------|--------|--------|
| `script_gen.py` | Script generation | human_prompts.json | enhanced_prompts.json, transcripts | ✅ Standalone |
| `video_gen.py` | Video generation | Enhanced prompts | Scripts + Videos | ✅ Separate system |
| `mux_uploader.py` | Upload to Mux | Generated MP4s | Mux asset IDs / playback metadata | ✅ Optional integration |
| `main.py` | Web API | HTTP requests | JSON responses | ✅ Uses video_gen |

## Docker / Container Support

We've added a Dockerfile and `docker-compose.yml` to help automate running the pipeline inside a container.

- Purpose: Provide a reproducible environment that can run the complete pipeline (scripts → videos) or host the FastAPI service.
- What the image contains: Python 3.12, repo code, installed Python requirements, NodeJS + the `@mux/cli` (so `mux` uploads are available).
- How to run (local development):

  1. Build the image:

    ```bash
    docker compose build
    ```

  2. Run the complete pipeline (uses .env and mux-access-token-video_gen.env):

    ```bash
    docker compose up
    ```

  3. To run the FastAPI service instead of the complete pipeline, override the command:

    ```bash
    docker compose run --rm pipeline python main.py
    ```

Notes:
- The container mounts `generated_videos` and `generated_scripts` into the host so outputs persist.
- The `docker_entrypoint.sh` will load project `.env` variables into the container environment if present. For production, prefer setting secrets via your deployment platform.

| **`run.py`** | **Unified runner** | **human_prompts.json** | **Scripts + Videos** | **✅ NEW - Connects both** |

## Key Differences:

### Script Generation Approaches:
1. **`script_gen.py`**: Simple enhancement → `"Enhance this prompt for creativity:"`
2. **`complete_pipeline.py`**: Professional script generation with detailed system prompts

### Video Generation:
- **Only `complete_pipeline.py`** has Veo 3.1 integration
- **`script_gen.py`** only generates text scripts (no videos)

### Integration:
- **Before**: Two separate, unconnected systems
- **After**: `run.py` provides unified interface connecting both

The **`run.py`** solution gives you the best of both worlds: the script generation quality from `script_gen.py` combined with the video generation capabilities from `complete_pipeline.py`!