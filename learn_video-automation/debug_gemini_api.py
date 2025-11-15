#!/usr/bin/env python3
"""
Debug script to test Gemini API responses
"""

import os
from google import genai
from dotenv import load_dotenv

# Load environment
load_dotenv(dotenv_path="../.env")

def test_gemini_auth():
    """Test basic Gemini authentication and model access"""
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if gemini_api_key:
            os.environ['GOOGLE_API_KEY'] = gemini_api_key
            print(f"✅ Found GEMINI_API_KEY: {gemini_api_key[:10]}...")
        else:
            print("❌ No GEMINI_API_KEY found")
            return False
        
        # Initialize client
        client = genai.Client()
        print("✅ Gemini client initialized")
        
        # Test script generation (text generation)
        print("\n🧪 Testing script generation...")
        script_response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents="Write a short dialogue between two construction workers about safety."
        )
        
        print(f"📝 Script response type: {type(script_response)}")
        print(f"📝 Script response attributes: {dir(script_response)}")
        
        if hasattr(script_response, 'text') and script_response.text:
            print(f"✅ Script generation works! Preview: {script_response.text[:100]}...")
        else:
            print(f"❌ Script generation failed or empty. Response: {script_response}")
        
        # Test listing available models
        print("\n🔍 Testing model availability...")
        try:
            # This might not work with current API, but let's try
            models = client.models.list()
            print(f"📋 Available models: {[m.name for m in models]}")
        except Exception as e:
            print(f"⚠️ Could not list models: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Gemini: {e}")
        return False

def test_video_generation():
    """Test if video generation API is accessible"""
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        os.environ['GOOGLE_API_KEY'] = gemini_api_key
        
        client = genai.Client()
        
        print("\n🎬 Testing video generation access...")
        
        # Try to start a video generation (this will likely fail but shows us the error)
        try:
            operation = client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt="A simple 5-second video of a person waving hello."
            )
            print(f"🎥 Video operation started: {operation}")
            return True
        except Exception as e:
            print(f"❌ Video generation error: {e}")
            
            # Let's see what models might be available for video
            try:
                # Try different model names that might work
                for model in ["veo-1", "veo", "video-generation"]:
                    try:
                        operation = client.models.generate_videos(
                            model=model,
                            prompt="Test video"
                        )
                        print(f"✅ Model {model} works!")
                        return True
                    except Exception as model_e:
                        print(f"❌ Model {model} failed: {model_e}")
            except Exception as list_e:
                print(f"⚠️ Could not test alternative models: {list_e}")
            
            return False
            
    except Exception as e:
        print(f"❌ Error in video test: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Gemini API Debug Test")
    print("=" * 40)
    
    auth_ok = test_gemini_auth()
    if auth_ok:
        test_video_generation()
    
    print("\n" + "=" * 40)
    print("🏁 Debug test complete")