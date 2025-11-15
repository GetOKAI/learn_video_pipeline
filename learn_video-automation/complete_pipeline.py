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
        Generate video metadata and enhanced prompts using Gemini
        Note: Actual video generation requires special Veo API access
        
        Args:
            enhanced_prompt (str): The enhanced prompt text
            title (str): Video title
            model (str): Model preference (for future use)
            
        Returns:
            dict: Video generation result with metadata
        """
        try:
            if self.model is None:
                # Mock response when API key is missing
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title.replace(' ', '_')[:30]
                filename = f"{safe_title}_MOCK_{timestamp}.mp4"
                
                return {
                    "title": title,
                    "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                    "video_file": filename,
                    "file_path": os.path.join(self.output_dir, filename),
                    "file_size_mb": 0,
                    "generation_timestamp": datetime.now().isoformat(),
                    "model_used": f"mock-{model}",
                    "status": "mock_success",
                    "note": "Mock generation - actual video would require Veo API access"
                }

            # Generate enhanced video production prompt using Gemini
            video_prompt_enhancement = f"""
You are a professional video production assistant. Enhance this prompt for video generation:

Original prompt: {enhanced_prompt}
Video title: {title}

Create a detailed, professional video production prompt that includes:
1. Visual style and cinematography direction
2. Scene composition and camera angles  
3. Timing and pacing suggestions
4. Audio and music recommendations
5. Target audience considerations

Make it ready for professional video production.
"""

            response = self.model.generate_content(video_prompt_enhancement)
            enhanced_video_prompt = response.text.strip() if response.text else enhanced_prompt

            # Create metadata for video that would be generated
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:30]
            filename = f"{safe_title}_Enhanced_{timestamp}.mp4"
            
            result = {
                "title": title,
                "original_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "enhanced_video_prompt": enhanced_video_prompt,
                "video_file": filename,
                "file_path": os.path.join(self.output_dir, filename),
                "file_size_mb": 0,  # Would be populated after actual generation
                "generation_timestamp": datetime.now().isoformat(),
                "model_used": f"gemini-2.5-flash-enhanced-{model}",
                "status": "enhanced_prompt_ready",
                "note": "Enhanced prompt generated - ready for Veo video generation when API access is available"
            }
            
            return result
            
        except Exception as e:
            return {
                "title": title,
                "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "error": str(e),
                "generation_timestamp": datetime.now().isoformat(),
                "status": "failed"
            }

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
        if script_result.get("status") == "success":
            script_filename = f"script_{title.replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            script_filepath = os.path.join(self.scripts_dir, script_filename)
            
            with open(script_filepath, 'w', encoding='utf-8') as f:
                f.write(f"Title: {title}\n\n")
                f.write(script_result["actor_script"])
            
            script_result["script_file"] = script_filename
            script_result["script_path"] = script_filepath
            print(f"✅ Script saved to: {script_filepath}")
        else:
            print(f"❌ Script generation failed: {script_result.get('error')}")
        
        # Step 2: Generate video(s)
        print(f"\n🎬 Step 2: Generating video(s) with models: {video_models}")
        video_results = []
        
        for model in video_models:
            print(f"\n🔄 Generating with model: {model}")
            video_result = self.video_generator.generate_video(enhanced_prompt, title, model)
            video_results.append(video_result)
            
            if video_result.get("status") == "success":
                print(f"✅ Video generated with {model}")
            else:
                print(f"❌ Video generation failed with {model}: {video_result.get('error')}")
            
            # Rate limiting between models
            if len(video_models) > 1:
                time.sleep(5)
        
        # Combine results
        combined_result = {
            "title": title,
            "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
            "script_result": script_result,
            "video_results": video_results,
            "processing_timestamp": datetime.now().isoformat(),
            "successful_script": script_result.get("status") == "success",
            "successful_videos": len([v for v in video_results if v.get("status") == "success"]),
            "total_videos_attempted": len(video_results)
        }
        
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