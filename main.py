import os
import json
from fastapi import FastAPI, HTTPException, Header
from typing import Optional

from .schemas import WebhookPayload, WebhookResponse
from .db import get_or_create_user, save_all_parts
from .vapi_client import (
    fetch_transcript_by_call,
    transcribe_audio_url,
    extract_call_id_from_url,
)
from . import sse  # SSE router

from .extractor import router as extractor_router  # ✅ use router, not extract_all_parts

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

app = FastAPI(title="profile-extraction-service", version="1.0.0")
# ✅ Startup confirmation: insertion locked to Edge API
print(f"✅ Profile insertion locked to: {os.getenv('SUPABASE_EDGE_URL')}")

# Register routers
app.include_router(sse.router, prefix="/sse")
app.include_router(extractor_router, prefix="/api")   # ✅ mount extractor endpoints

def build_profile_summary(profile_data: dict) -> dict:
    """Ensure Profiles.summary always has a meaningful fallback."""
    prof = profile_data.get("Profiles", {})
    if not prof:
        return profile_data

    # If summary already exists → keep it
    if prof.get("summary"):
        return profile_data

    # If currentRole exists
    if prof.get("currentRole"):
        prof["summary"] = f"Professional with experience as {prof['currentRole']}."

    # Fallback to skills
    elif prof.get("skills"):
        prof["summary"] = f"Professional with skills in {', '.join(prof['skills'])}."

    # Fallback to experience
    elif profile_data.get("Experience"):
        exp = profile_data["Experience"][0]
        company = exp.get("company", "an organization")
        duration = exp.get("duration", "some time")
        title = (exp.get("title") or "").strip()
        if title:
            prof["summary"] = f"Worked as {title} at {company} for {duration}."
        else:
            prof["summary"] = f"Worked at {company} for {duration}."

    # Fallback to education
    elif profile_data.get("Education"):
        edu = profile_data["Education"][0]
        program = edu.get("program", "a program")
        institution = edu.get("institution", "an institution")
        prof["summary"] = f"Studied {program} at {institution}."

    # Absolute fallback
    else:
        prof["summary"] = "Professional with diverse experience and skills."

    profile_data["Profiles"] = prof
    return profile_data

def build_profile_headline(profile_data: dict) -> dict:
    """Ensure Profiles.headline always has a meaningful fallback."""
    prof = profile_data.get("Profiles", {})
    if not prof:
        return profile_data

    # If headline already exists → keep it
    if prof.get("headline"):
        return profile_data

    # Fallbacks
    if prof.get("currentRole"):
        prof["headline"] = prof["currentRole"]
    elif prof.get("skills"):
        prof["headline"] = f"Skilled in {', '.join(prof['skills'][:3])}"
    elif profile_data.get("Experience"):
        prof["headline"] = "Experienced Professional"
    elif profile_data.get("Education"):
        prof["headline"] = "Graduate Professional"
    else:
        prof["headline"] = "Professional"

    profile_data["Profiles"] = prof
    print("⚡ headline fallback applied:", prof.get("headline"))
    return profile_data


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "Profile Extraction Service", "status": "running"}


@app.get("/health")
def health():
    return {"ok": True, "status": "healthy"}


@app.get("/debug/db")
def debug_db():
    """Debug endpoint to test database connection"""
    from .db import supabase

    try:
        print("🔍 Testing database connection...")

        users_res = supabase.table("Users").select("count").execute()
        profiles_res = supabase.table("Profiles").select("count").execute()

        env_vars = {
            "SUPABASE_URL": os.getenv("SUPABASE_URL", "NOT_SET"),
            "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY", "NOT_SET")[:20] + "..."
            if os.getenv("SUPABASE_SERVICE_KEY")
            else "NOT_SET",
        }

        return {
            "status": "ok",
            "database_connected": True,
            "users_table": users_res.data if users_res.data else "error",
            "profiles_table": profiles_res.data if profiles_res.data else "error",
            "env_vars": env_vars,
        }
    except Exception as e:
        import traceback
        print(f"❌ Database debug error: {e}")
        traceback.print_exc()
        return {
            "status": "error",
            "database_connected": False,
            "error": str(e),
        }

from datetime import datetime

@app.post("/webhook", response_model=WebhookResponse)
def webhook(payload: WebhookPayload, x_webhook_secret: Optional[str] = Header(default=None)):
    print(f"🎯 Webhook received: {payload}")

    # 0) optional shared-secret check
    if WEBHOOK_SECRET and x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    phone = payload.phoneNumber.strip()
    full_name = payload.fullName or ""
    user_id = get_or_create_user(phone)
    print(f"👤 User ID: {user_id}")

    # 1) Get transcript
    transcript = "" 
    if payload.callId:
        transcript = fetch_transcript_by_call(payload.callId)
    if not transcript and payload.audioUrl:
        call_id = extract_call_id_from_url(str(payload.audioUrl))
        if call_id:
            transcript = fetch_transcript_by_call(call_id)
    if not transcript and payload.audioUrl:
        transcript = transcribe_audio_url(str(payload.audioUrl))
    if not transcript:
        raise HTTPException(status_code=422, detail="Transcript not available")

    print(f"✅ Got transcript: {transcript[:200]}...")

    # 2) Run extraction (call extractor endpoint function directly)
    from .extractor import extract_profile_exact
    extraction_result = extract_profile_exact(phone,user_id,transcript)

    # ✅ unwrap the `profile` part (safe even if nested or direct)
    profile_data = extraction_result.get("profile", extraction_result) or {}

    # 3) Ensure Users has phone + fullName (override blanks)
    # u = (profile_data.get("Users") or {})
    # if not u.get("phoneNumber"):
    #     u["phoneNumber"] = phone
    # if not u.get("fullName") or not str(u["fullName"]).strip():
    #     u["fullName"] = (full_name or "Unknown")
    # profile_data["Users"] = u

    # 4) Normalize createdAt everywhere + summary/roleType/shiftType fallbacks
    now = datetime.utcnow().isoformat()
    for section in ["Profiles", "Experience", "Education", "JobPreferences"]:
        val = profile_data.get(section)
        if isinstance(val, dict):
            if not val.get("createdAt"):
                val["createdAt"] = now
        elif isinstance(val, list):
            for sub in val:
                if isinstance(sub, dict) and not sub.get("createdAt"):
                    sub["createdAt"] = now

    # # 4a) Ensure Profiles.summary fallback from currentRole
    # prof = profile_data.get("Profiles", {})
    # if prof and not prof.get("summary") and prof.get("currentRole"):
    #     prof["summary"] = f"Professional with experience as {prof['currentRole']}."
    # profile_data["Profiles"] = prof
    # 4a) Ensure Profiles.summary fallback (role → skills → experience → education)
    profile_data = build_profile_summary(profile_data)
    profile_data = build_profile_headline(profile_data)
    # 4b) Normalize JobPreferences.shiftType (enforce DB constraint)
    job_pref = profile_data.get("JobPreferences", {})
    if job_pref:
        shift = str(job_pref.get("shiftType") or "").strip().lower()
        if shift not in ["day", "night", "evening"]:  # ✅ allowed values
            job_pref["shiftType"] = None

        # 4c) Normalize JobPreferences.roleType (enforce DB constraint)
        rt = str(job_pref.get("roleType") or "").strip().lower().replace("-", " ").replace("_", " ")
        if rt in ["full time", "fulltime"]:
            job_pref["roleType"] = "Full-time"
        elif rt in ["part time", "parttime"]:
            job_pref["roleType"] = "Part-time"
        elif rt in ["contract"]:
            job_pref["roleType"] = "Contract"
        elif rt in ["internship", "intern"]:
            job_pref["roleType"] = "Internship"
        else:
            job_pref["roleType"] = None  # fallback to satisfy DB constraint

    profile_data["JobPreferences"] = job_pref

    print(f"📋 Extracted JSON: {json.dumps(profile_data, indent=2)}")

    if not profile_data:
        raise HTTPException(status_code=422, detail="No meaningful profile extracted")
    # ✅ Ensure callID field is set with correct casing
    if payload.callId:
        profile_data["callID"] = payload.callId
    elif "callID" not in profile_data:
        profile_data["callID"] = ""

    # 5) Save into DB
    profile_id = save_all_parts(user_id, phone,profile_data)

    if profile_id:
        profile_data["profileId"] = profile_id
        if "Profiles" in profile_data:
            profile_data["Profiles"]["profileId"] = profile_id

    return {
        "userId": user_id or "",
        "status": "ok",
        "profileId": profile_id,
        "profile": profile_data
    }

from app.sse import events   # import the endpoint function

# Existing routes (like /webhook)...

# ------------------------
# SSE Endpoint
# ------------------------
@app.get("/sse/events")
async def sse_events():
    """Clients subscribe here to receive SSE messages."""
    return await events()
