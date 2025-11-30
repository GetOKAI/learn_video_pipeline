#!/usr/bin/env python3
"""
Debug script to test Gemini API responses
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment
load_dotenv(dotenv_path="../.env")

def test_gemini_auth():
    """Test basic Gemini authentication and model access"""
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("❌ No GEMINI_API_KEY found in .env file")
            return False
        
        print(f"✅ Found GEMINI_API_KEY: {gemini_api_key[:10]}...")
        
        # Configure Gemini with API key
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        print("✅ Gemini model initialized")
        
        # Test script generation (text generation)
        print("\n🧪 Testing script generation...")
        script_response = model.generate_content(
            "Write a short dialogue between two construction workers about safety."
        )
        
        print(f"📝 Script response type: {type(script_response)}")
        
        if hasattr(script_response, 'text') and script_response.text:
            print(f"✅ Script generation works! Preview: {script_response.text[:100]}...")
        else:
            print(f"❌ Script generation failed or empty. Response: {script_response}")
        
        # Test another generation to verify consistency
        print("\n🧪 Testing video prompt generation...")
        prompt_response = model.generate_content(
            "Create a detailed video prompt for a workplace safety demonstration video."
        )
        
        if hasattr(prompt_response, 'text') and prompt_response.text:
            print(f"✅ Prompt generation works! Preview: {prompt_response.text[:100]}...")
        else:
            print(f"❌ Prompt generation failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Gemini: {e}")
        return False

def test_video_generation():
    """Test video prompt enhancement using Gemini"""
    try:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("❌ No API key for video test")
            return False
            
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        print("\n� Testing video prompt enhancement...")
        
        # Test prompt enhancement for video generation
        basic_prompt = "Create a video about workplace safety"
        enhanced_response = model.generate_content(
            f"Enhance this video prompt for professional video production: {basic_prompt}"
        )
        
        if hasattr(enhanced_response, 'text') and enhanced_response.text:
            print(f"✅ Video prompt enhancement works! Preview: {enhanced_response.text[:100]}...")
            return True
        else:
            print(f"❌ Video prompt enhancement failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in video prompt test: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Gemini API Debug Test")
    print("=" * 40)
    
    auth_ok = test_gemini_auth()
    if auth_ok:
        test_video_generation()
    
    print("\n" + "=" * 40)
    print("🏁 Debug test complete")