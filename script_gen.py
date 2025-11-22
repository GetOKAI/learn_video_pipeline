from flask import Flask
import google.generativeai as genai
import json, os
from dotenv import load_dotenv

# -------------------- SETUP -------------------- #
load_dotenv()

# Load GEMINI API key if available. Do not raise at import-time so the
# module can be inspected / committed / tested locally without the key.
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    # Configure Gemini only when API key is present
    genai.configure(api_key=api_key)
    model_name = "gemini-2.5-flash"  # fast & stable
    model = genai.GenerativeModel(model_name)
    print("✅ Gemini client configured successfully.")
else:
    # When API key is missing, set model to None and run in "mock" mode.
    model = None
    print("⚠️ GEMINI_API_KEY not found in .env — running in mock mode. LLM calls will return placeholders.")

# File paths
INPUT_FILE = "video_generation_prompts_filtered.json"
ENHANCED_FILE = "enhanced_prompts.json"
ACTOR_FILE = "transcripts_actor.json"
FACELESS_FILE = "transcripts_faceless.json"

# -------------------- HELPERS -------------------- #
def load_human_prompts():
    """Load human prompts from input JSON"""
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, filename):
    """Save JSON to disk"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_llm_response(prompt):
    """Generate Gemini output for a given prompt"""
    try:
        if model is None:
            # Mock response to allow offline testing / commits without an API key
            return f"[MOCK RESPONSE] (GEMINI_API_KEY missing) — Prompt: {prompt[:200]}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"[Error generating content: {str(e)}]"

def run_pipeline():
    """Main pipeline function"""
    print("🚀 Starting AI video generation pipeline...")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Input file '{INPUT_FILE}' not found.")
        return

    human_prompts = load_human_prompts()
    if not human_prompts:
        print("❌ Error: Input file is empty or invalid.")
        return

    enhanced_prompts, actor_scripts, faceless_scripts = [], [], []

    for i, item in enumerate(human_prompts, start=1):
        title = item.get("Video Title", f"Untitled_{i}")
        raw_prompt = item.get("Prompts used for original video", "")
        print(f"\n🎯 Processing {i}/{len(human_prompts)} → {title}")

        # Step 1: Enhance prompt
        enhanced = generate_llm_response(f"Enhance this prompt for creativity:\n{raw_prompt}")
        enhanced_prompts.append({"Video Title": title, "Enhanced Prompt": enhanced})
        print("   ✨ Enhanced prompt generated.")

        # Step 2: Actor script
        actor_prompt = (
            f"Using this enhanced prompt, create a 2-person dialogue script "
            f"for a 1-minute explainer video:\n\n{enhanced}"
        )
        actor_script = generate_llm_response(actor_prompt)
        actor_scripts.append({"Video Title": title, "Actor Transcript": actor_script})
        print("   🎭 Actor script generated.")

        # Step 3: Faceless narration
        faceless_prompt = (
            f"Using this enhanced prompt, create a 60-second faceless narration "
            f"with a simple, relatable tone for blue-collar workers:\n\n{enhanced}"
        )
        faceless_script = generate_llm_response(faceless_prompt)
        faceless_scripts.append({"Video Title": title, "Faceless Transcript": faceless_script})
        print("   🗣️ Faceless script generated.")

    # Step 4: Save outputs
    save_json(enhanced_prompts, ENHANCED_FILE)
    save_json(actor_scripts, ACTOR_FILE)
    save_json(faceless_scripts, FACELESS_FILE)

    print("\n✅ Pipeline executed successfully!")
    print(f"📁 Files saved:\n   - {ENHANCED_FILE}\n   - {ACTOR_FILE}\n   - {FACELESS_FILE}")
    print(f"🧮 Total processed: {len(human_prompts)} prompts\n")

# -------------------- FLASK APP (Optional API Wrapper) -------------------- #
app = Flask(__name__)

@app.route('/')
def root():
    return "Gemini Video Pipeline API is running."

# -------------------- MAIN ENTRY -------------------- #
if __name__ == "__main__":
    # Run pipeline automatically at startup
    run_pipeline()

    # Start Flask server (useful for GCP or Cloud Run health checks)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)
