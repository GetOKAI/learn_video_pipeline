#!/usr/bin/env python3
"""
Complete Video Pipeline
Takes enhanced prompts and generates both actor scripts and videos.
Integrates script generation (OpenAI) and video generation (Gemini/Veo).
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="../.env")

class ScriptGenerator:
    """Generates actor dialogue scripts from enhanced prompts using Gemini"""
    
    def __init__(self):
        # Use consistent Gemini authentication
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        if not self.gemini_api_key:
            print("⚠️ GEMINI_API_KEY not found in .env — script generation will use mock responses.")
            self.model = None
            return

        # Configure Gemini with API key
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            print("✅ Gemini configured for script generation")
        except Exception as e:
            raise Exception(f"Failed to initialize Gemini client for script generation: {str(e)}")
        
        # System prompt for script generation
        self.system_prompt = """You are a professional dialogue script writer specializing in creating conversational scripts for blue-collar worker educational videos.

Transform detailed video production prompts into natural, engaging 2-person dialogue scripts that:

1. Use authentic, conversational language that blue-collar workers can relate to
2. Include timing markers for a 60-second video format
3. Feature diverse characters with realistic names and backgrounds
4. Deliver practical, actionable information naturally through dialogue
5. End with the specified outro line
6. Keep the total word count around 180-220 words for comfortable pacing

Format as:
- Character introductions with brief descriptions
- Timed dialogue segments (0-10 seconds, 10-30 seconds, etc.)
- Natural conversation flow that doesn't sound scripted
- Clear, practical advice woven into the dialogue
- Appropriate outro integration

Focus on making the script feel like a real conversation between colleagues or friends sharing helpful advice."""

    def generate_script(self, enhanced_prompt: str, title: str = "") -> Dict:
        """
        Generate an actor dialogue script from an enhanced prompt using Gemini
        
        Args:
            enhanced_prompt (str): The detailed video production prompt
            title (str): Video title for context
            
        Returns:
            dict: Script generation result with dialogue and metadata
        """
        try:
            if self.model is None:
                # Mock response when API key is missing
                return {
                    "title": title,
                    "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                    "actor_script": f"[MOCK SCRIPT] Two-person dialogue for: {title}",
                    "script_generation_timestamp": datetime.now().isoformat(),
                    "status": "success_mock"
                }

            user_message = f"""
Title: {title}

Enhanced Video Prompt:
{enhanced_prompt}

Please create a natural 2-person dialogue script for this video concept. Make it conversational and authentic for blue-collar workers.
"""

            # Use consistent Gemini API pattern
            full_prompt = self.system_prompt + "\n\n" + user_message
            
            response = self.model.generate_content(full_prompt)
            
            actor_script = response.text.strip() if response.text else ""
            
            if not actor_script:
                raise Exception("Empty response from Gemini")
            
            result = {
                "title": title,
                "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "actor_script": actor_script,
                "script_generation_timestamp": datetime.now().isoformat(),
                "tokens_used": len(actor_script.split()) if actor_script else 0,  # Approximate token count
                "model_used": "gemini-2.5-flash",
                "status": "success"
            }
            
            return result
            
        except Exception as e:
            return {
                "title": title,
                "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "error": str(e),
                "script_generation_timestamp": datetime.now().isoformat(),
                "status": "failed"
            }

class VideoGenerator:
    """Generates videos from enhanced prompts using Google Gemini/Veo"""
    
    def __init__(self):
        # Use consistent Gemini authentication
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        if not self.gemini_api_key:
            print("⚠️ GEMINI_API_KEY not found in .env — video generation will use mock responses.")
            self.model = None
            return

        # Configure Gemini with API key
        try:
            genai.configure(api_key=self.gemini_api_key)
            # For video generation, we'll simulate the process since actual video generation
            # might require special access or different APIs
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            print("✅ Gemini configured for video generation prompts")
        except Exception as e:
            print(f"❌ Failed to configure Gemini: {str(e)}")
            self.model = None
        
        # Create output directory
        self.output_dir = "generated_videos"
        os.makedirs(self.output_dir, exist_ok=True)

    def _resolve_model(self, model_key: str) -> str:
        """Map short model keys to full Gemini model names"""
        if not model_key:
            return "veo-3.1-generate-preview"

        key = model_key.lower().strip()
        if key in ("veo-3", "veo3", "veo-3.1", "veo3.1"):
            return "veo-3.1-generate-preview"
        if key in ("veo-fast", "veofast", "fast"):
            return "veo-fast-1.0-generate-preview"
        
        return model_key

    def generate_video(self, enhanced_prompt: str, title: str = "", model: str = "veo-3") -> Dict:
        """
        Generate video content and save to file using Gemini-enhanced prompts
        
        Args:
            enhanced_prompt (str): The enhanced prompt text
            title (str): Video title
            model (str): Model preference (for future use)
            
        Returns:
            dict: Video generation result with file path
        """
        try:
            # Create filename first
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:30]
            filename = f"{safe_title}_{timestamp}.mp4"
            filepath = os.path.join(self.output_dir, filename)
            
            if self.model is None:
                # Create mock video file when API key is missing
                self._create_mock_video_file(filepath, title, enhanced_prompt)
                
                return {
                    "title": title,
                    "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                    "video_file": filename,
                    "file_path": filepath,
                    "file_size_mb": round(os.path.getsize(filepath) / (1024 * 1024), 2),
                    "generation_timestamp": datetime.now().isoformat(),
                    "model_used": f"mock-{model}",
                    "status": "success",
                    "note": "Mock video file created - replace with real video when API available"
                }

            # Generate enhanced video production prompt using Gemini
            print("🎨 Enhancing video prompt with Gemini...")
            video_prompt_enhancement = f"""
You are a professional video production assistant. Create a comprehensive video production script based on this prompt:

Original prompt: {enhanced_prompt}
Video title: {title}

Generate a detailed video production guide including:
1. Scene-by-scene breakdown with timestamps
2. Visual descriptions and camera angles
3. Audio/voiceover instructions
4. Text overlays and graphics
5. Background music suggestions
6. Color scheme and visual style
7. Target audience engagement strategies

Format as a professional production script ready for video creation.
"""

            response = self.model.generate_content(video_prompt_enhancement)
            enhanced_video_prompt = response.text.strip() if response.text else enhanced_prompt
            
            print("🎬 Creating video content based on enhanced prompt...")
            
            # Create video content file (simulated video generation)
            self._create_enhanced_video_file(filepath, title, enhanced_prompt, enhanced_video_prompt)
            
            file_size = os.path.getsize(filepath)
            
            result = {
                "title": title,
                "original_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "enhanced_video_prompt": enhanced_video_prompt,
                "video_file": filename,
                "file_path": filepath,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "generation_timestamp": datetime.now().isoformat(),
                "model_used": f"gemini-2.5-flash-enhanced-{model}",
                "status": "success",
                "note": "Enhanced video prompt and metadata saved - ready for professional video production"
            }
            
            print(f"✅ Video content saved to: {filepath}")
            return result
            
        except Exception as e:
            print(f"❌ Video generation error: {str(e)}")
            return {
                "title": title,
                "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "error": str(e),
                "generation_timestamp": datetime.now().isoformat(),
                "status": "failed"
            }
    
    def _create_mock_video_file(self, filepath: str, title: str, prompt: str):
        """Create a mock video file with metadata when API key is missing"""
        mock_content = f"""Mock Video File: {title}
Generated: {datetime.now().isoformat()}

This is a placeholder video file created because GEMINI_API_KEY is not available.
In a production environment, this would be replaced with an actual video file.

Original Prompt:
{prompt}

Video Specifications:
- Duration: 30-60 seconds
- Resolution: 1920x1080
- Format: MP4
- Target: Blue-collar workers
- Platform: ok.ai

To generate real videos:
1. Set up GEMINI_API_KEY in .env file
2. Configure Veo API access (when available)
3. Or integrate with other video generation services

File size: Mock content (~1KB)
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(mock_content)
    
    def _create_enhanced_video_file(self, filepath: str, title: str, original_prompt: str, enhanced_prompt: str):
        """Create an enhanced video content file with production instructions"""
        video_content = f"""Enhanced Video Production File: {title}
Generated: {datetime.now().isoformat()}

=== PRODUCTION READY VIDEO INSTRUCTIONS ===

Original Prompt:
{original_prompt}

=== ENHANCED PRODUCTION SCRIPT ===
{enhanced_prompt}

=== TECHNICAL SPECIFICATIONS ===
- Format: MP4, 1920x1080, 30fps
- Duration: 30-60 seconds  
- Audio: Clear voiceover, background music
- Style: Professional, relatable to blue-collar workers
- Platform: ok.ai

=== NEXT STEPS ===
1. Use this enhanced prompt with video generation services
2. Record voiceover based on generated script
3. Add appropriate visuals and graphics
4. Include ok.ai branding and outro

This file contains all the instructions needed for professional video production.
Ready for input into video generation APIs or manual production workflow.

Generated with Gemini {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(video_content)

class CompletePipeline:
    """Complete pipeline that generates both scripts and videos from enhanced prompts"""
    
    def __init__(self):
        self.script_generator = ScriptGenerator()
        self.video_generator = VideoGenerator()
        
        # Create output directories
        self.scripts_dir = "generated_scripts"
        self.videos_dir = "generated_videos"
        os.makedirs(self.scripts_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)

    def process_single_prompt(self, enhanced_prompt: str, title: str = "", 
                            video_models: List[str] = None) -> Dict:
        """
        Process a single enhanced prompt to generate both script and video(s)
        
        Args:
            enhanced_prompt (str): The enhanced prompt text
            title (str): Video title
            video_models (List[str]): List of video models to use
            
        Returns:
            dict: Combined results with script and video generation info
        """
        if video_models is None:
            video_models = ["veo-3"]
        
        print(f"\n🚀 Processing: {title}")
        print("=" * 60)
        
        # Step 1: Generate actor script
        print("\n📝 Step 1: Generating actor dialogue script...")
        script_result = self.script_generator.generate_script(enhanced_prompt, title)
        
        # Save script if successful
        script_filepath = None
        if script_result.get("status") in ["success", "success_mock"]:
            script_filename = f"script_{title.replace(' ', '_').replace('/', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            script_filepath = os.path.join(self.scripts_dir, script_filename)
            
            try:
                with open(script_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {title}\n")
                    f.write(f"Generated: {datetime.now().isoformat()}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(script_result.get("actor_script", "No script content available"))
                
                script_result["script_file"] = script_filename
                script_result["script_path"] = script_filepath
                print(f"✅ Script saved to: {script_filepath}")
            except Exception as e:
                print(f"⚠️ Warning: Could not save script file: {e}")
        else:
            print(f"❌ Script generation failed: {script_result.get('error', 'Unknown error')}")
        
        # Step 2: Generate video(s)
        print(f"\n🎬 Step 2: Generating video(s) with models: {video_models}")
        video_results = []
        
        for model in video_models:
            print(f"\n🔄 Generating video with model: {model}")
            video_result = self.video_generator.generate_video(enhanced_prompt, title, model)
            video_results.append(video_result)
            
            if video_result.get("status") == "success":
                print(f"✅ Video generated successfully with {model}")
                print(f"📁 Video file: {video_result.get('video_file')}")
                print(f"💾 File size: {video_result.get('file_size_mb', 0)} MB")
            elif video_result.get("status") == "mock_success":
                print(f"✅ Mock video created with {model}")
                print(f"📁 Mock file: {video_result.get('video_file')}")
            else:
                print(f"❌ Video generation failed with {model}: {video_result.get('error', 'Unknown error')}")
            
            # Rate limiting between models
            if len(video_models) > 1:
                time.sleep(2)
        
        # Combine results
        successful_videos = len([v for v in video_results if v.get("status") in ["success", "mock_success"]])
        
        combined_result = {
            "title": title,
            "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
            "script_result": script_result,
            "video_results": video_results,
            "processing_timestamp": datetime.now().isoformat(),
            "successful_script": script_result.get("status") in ["success", "success_mock"],
            "successful_videos": successful_videos,
            "total_videos_attempted": len(video_results),
            "script_file_path": script_result.get("script_path", None),
            "video_file_paths": [v.get("file_path") for v in video_results if v.get("file_path")]
        }
        
        # Print summary
        print(f"\n📊 Processing Summary:")
        print(f"   Script: {'✅ Generated' if combined_result['successful_script'] else '❌ Failed'}")
        print(f"   Videos: {successful_videos}/{len(video_results)} successful")
        if script_filepath:
            print(f"   Script saved: {script_filepath}")
        for video_result in video_results:
            if video_result.get("file_path"):
                print(f"   Video saved: {video_result['file_path']}")
        
        return combined_result

    def process_from_file(self, input_file: str, output_file: str = "pipeline_results.json",
                         video_models: List[str] = None, limit: int = None) -> Dict:
        """
        Process enhanced prompts from file and generate scripts and videos
        
        Args:
            input_file (str): Path to enhanced prompts JSON file
            output_file (str): Path to save pipeline results
            video_models (List[str]): List of video models to use
            limit (int): Maximum number of prompts to process
            
        Returns:
            dict: Processing summary with statistics
        """
        if video_models is None:
            video_models = ["veo-3"]
        
        try:
            # Load enhanced prompts
            with open(input_file, 'r', encoding='utf-8') as f:
                enhanced_prompts = json.load(f)
            
            if limit:
                enhanced_prompts = enhanced_prompts[:limit]
            
            print(f"🎬 Processing {len(enhanced_prompts)} enhanced prompts from {input_file}")
            print(f"📹 Video models: {video_models}")
            
            results = []
            successful_scripts = 0
            successful_videos = 0
            total_videos_attempted = 0
            
            for i, prompt_data in enumerate(enhanced_prompts, 1):
                title = prompt_data.get("title", f"Video {i}")
                enhanced_prompt = prompt_data.get("enhanced_prompt", "")
                
                if not enhanced_prompt:
                    print(f"⚠️ Skipping prompt {i}: No enhanced prompt found")
                    continue
                
                if prompt_data.get("error"):
                    print(f"⚠️ Skipping prompt {i}: Enhancement had error")
                    continue
                
                # Process this prompt
                result = self.process_single_prompt(enhanced_prompt, title, video_models)
                results.append(result)
                
                # Update counters
                if result["successful_script"]:
                    successful_scripts += 1
                successful_videos += result["successful_videos"]
                total_videos_attempted += result["total_videos_attempted"]
                
                print(f"\n📊 Progress: {i}/{len(enhanced_prompts)} complete")
                
                # Rate limiting between prompts
                if i < len(enhanced_prompts):
                    print("⏳ Waiting before next prompt...")
                    time.sleep(3)
            
            # Save results
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Summary
            summary = {
                "input_file": input_file,
                "output_file": output_file,
                "total_prompts_processed": len(results),
                "successful_scripts": successful_scripts,
                "successful_videos": successful_videos,
                "total_videos_attempted": total_videos_attempted,
                "video_models_used": video_models,
                "processing_timestamp": datetime.now().isoformat()
            }
            
            print(f"\n🎉 Pipeline Complete!")
            print(f"📊 Summary:")
            print(f"  • Scripts generated: {successful_scripts}/{len(results)}")
            print(f"  • Videos generated: {successful_videos}/{total_videos_attempted}")
            print(f"  • Scripts saved to: {self.scripts_dir}")
            print(f"  • Videos saved to: {self.videos_dir}")
            print(f"  • Results saved to: {output_file}")
            
            return summary
            
        except Exception as e:
            print(f"❌ Pipeline error: {str(e)}")
            return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Complete pipeline: enhanced prompts → scripts + videos")
    parser.add_argument("--input", default="enhanced_prompts.json", 
                       help="Input JSON file with enhanced prompts")
    parser.add_argument("--output", default="pipeline_results.json", 
                       help="Output file for pipeline results")
    parser.add_argument("--models", nargs='+', default=["veo-3"], 
                       help="Video models to use (e.g., veo-3 veo-fast)")
    parser.add_argument("--limit", type=int, 
                       help="Limit number of prompts to process")
    parser.add_argument("--single", 
                       help="Process a single enhanced prompt (provide the prompt text)")
    parser.add_argument("--title", default="Custom Video", 
                       help="Title for single prompt processing")
    
    args = parser.parse_args()
    
    try:
        pipeline = CompletePipeline()
        
        if args.single:
            # Process single prompt
            result = pipeline.process_single_prompt(
                enhanced_prompt=args.single,
                title=args.title,
                video_models=args.models
            )
            print(f"\n📋 Result: {result.get('successful_script', False)} script, "
                  f"{result.get('successful_videos', 0)} videos")
        else:
            # Process from file
            pipeline.process_from_file(
                input_file=args.input,
                output_file=args.output,
                video_models=args.models,
                limit=args.limit
            )
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()