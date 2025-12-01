#!/usr/bin/env python3
"""
Unified Video Pipeline Runner
Connects script_gen.py functionality with video_gen.py video generation
Provides a single entry point for the entire pipeline: 
human_prompts.json → enhanced prompts → scripts → videos
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Import script generation functionality
import script_gen

# Import video pipeline
from video_gen import CompletePipeline

class UnifiedPipeline:
    """Unified pipeline that connects script generation with video production"""
    
    def __init__(self):
        # Initialize video pipeline
        try:
            self.video_pipeline = CompletePipeline()
            self.video_available = True
            print("✅ Video pipeline initialized")
        except Exception as e:
            print(f"⚠️ Video pipeline unavailable: {e}")
            self.video_available = False
        
        # File paths
        self.scripts_dir = "generated_scripts"
        self.videos_dir = "generated_videos"
        os.makedirs(self.scripts_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
    
    def run_script_generation_only(self):
        """Run only the script generation pipeline (script_gen.py functionality)"""
        print("🎭 Running Script Generation Pipeline...")
        print("=" * 60)
        
        # Run the script generation pipeline
        script_gen.run_pipeline()
        
        print("\n✅ Script generation completed!")
        return True
    
    def run_video_generation_from_enhanced_prompts(self, 
                                                  enhanced_prompts_file: str = "enhanced_prompts.json",
                                                  video_models: List[str] = None,
                                                  limit: Optional[int] = None) -> Dict:
        """
        Run video generation using existing enhanced prompts
        
        Args:
            enhanced_prompts_file: Path to enhanced prompts JSON file
            video_models: List of video models to use
            limit: Maximum number of prompts to process
        """
        if not self.video_available:
            print("❌ Video pipeline not available")
            return {"error": "Video pipeline not initialized"}
        
        if video_models is None:
            video_models = ["veo-3.1"]
        
        print("🎬 Running Video Generation Pipeline...")
        print("=" * 60)
        
        # Load enhanced prompts
        if not os.path.exists(enhanced_prompts_file):
            print(f"❌ Error: {enhanced_prompts_file} not found. Run script generation first.")
            return {"error": f"{enhanced_prompts_file} not found"}
        
        with open(enhanced_prompts_file, 'r', encoding='utf-8') as f:
            enhanced_prompts = json.load(f)
        
        if limit:
            enhanced_prompts = enhanced_prompts[:limit]
        
        print(f"📹 Processing {len(enhanced_prompts)} enhanced prompts for video generation")
        print(f"🎥 Video models: {video_models}")
        
        results = []
        successful_videos = 0
        total_videos_attempted = 0
        
        for i, prompt_data in enumerate(enhanced_prompts, 1):
            title = prompt_data.get("Video Title", f"Video {i}")
            enhanced_prompt = prompt_data.get("Enhanced Prompt", "")
            
            if not enhanced_prompt:
                print(f"⚠️ Skipping prompt {i}: No enhanced prompt found")
                continue
            
            print(f"\n🎬 Processing video {i}/{len(enhanced_prompts)}: {title}")
            
            # Generate videos for each model
            video_results = []
            for model in video_models:
                print(f"🔄 Generating with model: {model}")
                
                video_result = self.video_pipeline.video_generator.generate_video(
                    enhanced_prompt=enhanced_prompt,
                    title=title,
                    model=model
                )
                video_results.append(video_result)
                total_videos_attempted += 1
                
                if video_result.get("status") == "success":
                    successful_videos += 1
                    print(f"✅ Video generated: {video_result.get('video_file')}")
                else:
                    print(f"❌ Video generation failed: {video_result.get('error', 'Unknown error')}")
                
                # Rate limiting between models
                if len(video_models) > 1:
                    print("⏳ Waiting before next model...")
                    import time
                    time.sleep(2)
            
            result = {
                "title": title,
                "enhanced_prompt": enhanced_prompt[:200] + "..." if len(enhanced_prompt) > 200 else enhanced_prompt,
                "video_results": video_results,
                "successful_videos": len([v for v in video_results if v.get("status") == "success"]),
                "processing_timestamp": datetime.now().isoformat()
            }
            results.append(result)
            
            print(f"📊 Progress: {i}/{len(enhanced_prompts)} complete")
            
            # Rate limiting between prompts
            if i < len(enhanced_prompts):
                print("⏳ Waiting before next prompt...")
                import time
                time.sleep(3)
        
        # Save results
        results_file = f"video_generation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        summary = {
            "input_file": enhanced_prompts_file,
            "results_file": results_file,
            "total_prompts_processed": len(results),
            "successful_videos": successful_videos,
            "total_videos_attempted": total_videos_attempted,
            "video_models_used": video_models,
            "processing_timestamp": datetime.now().isoformat()
        }
        
        print(f"\n🎉 Video Generation Complete!")
        print(f"📊 Summary:")
        print(f"  • Videos generated: {successful_videos}/{total_videos_attempted}")
        print(f"  • Videos saved to: {self.videos_dir}")
        print(f"  • Results saved to: {results_file}")
        
        return summary
    
    def run_complete_pipeline(self, 
                            video_models: List[str] = None, 
                            limit: Optional[int] = None) -> Dict:
        """
        Run the complete pipeline: script generation → video generation
        
        Args:
            video_models: List of video models to use for video generation
            limit: Maximum number of prompts to process for videos
        """
        print("🚀 Running Complete Pipeline: Scripts + Videos")
        print("=" * 80)
        
        # Step 1: Generate scripts (enhanced prompts, actor scripts, faceless scripts)
        print("\n📝 STEP 1: Script Generation")
        print("-" * 40)
        
        script_success = self.run_script_generation_only()
        
        if not script_success:
            return {"error": "Script generation failed"}
        
        # Step 2: Generate videos from enhanced prompts
        if self.video_available:
            print("\n🎬 STEP 2: Video Generation")
            print("-" * 40)
            
            video_results = self.run_video_generation_from_enhanced_prompts(
                video_models=video_models,
                limit=limit
            )
            
            return {
                "pipeline_type": "complete",
                "script_generation": "completed",
                "video_generation": video_results,
                "completion_timestamp": datetime.now().isoformat()
            }
        else:
            print("\n⚠️ STEP 2: Skipped (Video generation unavailable)")
            return {
                "pipeline_type": "scripts_only",
                "script_generation": "completed",
                "video_generation": "skipped - video pipeline unavailable",
                "completion_timestamp": datetime.now().isoformat()
            }

def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(description="Unified Video Pipeline: Script Generation + Video Production")
    parser.add_argument("--mode", choices=["scripts", "videos", "complete"], default="complete",
                       help="Pipeline mode: scripts only, videos only, or complete pipeline")
    parser.add_argument("--models", nargs='+', default=["veo-3.1"], 
                       help="Video models to use (e.g., veo-3.1 veo-fast)")
    parser.add_argument("--limit", type=int, 
                       help="Limit number of prompts to process for video generation")
    parser.add_argument("--enhanced-file", default="enhanced_prompts.json",
                       help="Enhanced prompts file to use for video generation")
    
    args = parser.parse_args()
    
    try:
        pipeline = UnifiedPipeline()
        
        if args.mode == "scripts":
            # Script generation only
            result = pipeline.run_script_generation_only()
            print(f"\n✅ Script generation completed!")
            
        elif args.mode == "videos":
            # Video generation only (from existing enhanced prompts)
            result = pipeline.run_video_generation_from_enhanced_prompts(
                enhanced_prompts_file=args.enhanced_file,
                video_models=args.models,
                limit=args.limit
            )
            print(f"\n✅ Video generation completed!")
            
        elif args.mode == "complete":
            # Complete pipeline
            result = pipeline.run_complete_pipeline(
                video_models=args.models,
                limit=args.limit
            )
            print(f"\n✅ Complete pipeline finished!")
        
        print(f"🎯 Mode: {args.mode}")
        if args.mode in ["videos", "complete"]:
            print(f"📹 Models: {args.models}")
            if args.limit:
                print(f"🔢 Limit: {args.limit}")
        
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()