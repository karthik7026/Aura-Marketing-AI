"""
AI Video Studio — this logic already existed in generator.py (real
Replicate integration + a sandbox stock-video fallback) but was never
mounted onto the FastAPI app, so `/api/video/generate` 404'd for every
real user even though the frontend calls it. See
Aura_Marketing_AI_Review.md, "Broken or Actively Risky".

This router wires it up for real: it deducts tokens the same way every
other paid feature does, and — per BRD STU-03 — it now honestly tells the
caller whether the result is a genuine render (Replicate / your own
Colab-or-Kaggle GPU / a free Hugging Face Space) or a stock/library clip,
instead of implying "AI Video compiled successfully" either way.
"""
import os
import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper
from backend.generator import initiate_video_generation, get_job_status, GENERATED_LIBRARY_DIR

router = APIRouter(prefix="/api/video", tags=["AI Video Studio"])

VIDEO_GENERATION_COST = 5


class VideoGenerateRequest(BaseModel):
    prompt: str
    style: str = "cinematic"
    aspect_ratio: str = "16:9"
    camera_motion: str = "zoom_in"
    duration: int = 30
    fps: int = 30
    text_overlay: str = ""


@router.post("/generate")
def generate_video(
    req: VideoGenerateRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    if current_user.get("tokens", 0) < VIDEO_GENERATION_COST:
        raise HTTPException(status_code=400, detail=f"Insufficient tokens. Requires {VIDEO_GENERATION_COST} tokens.")

    result = initiate_video_generation(
        prompt=req.prompt,
        style=req.style,
        aspect_ratio=req.aspect_ratio,
        camera_motion=req.camera_motion,
        duration=req.duration,
        fps=req.fps,
        text_overlay=req.text_overlay,
    )

    tx_id = f"VID_{result['job_id']}"
    db.users.update_one(
        {"email": current_user["email"]},
        {
            "$inc": {"tokens": -VIDEO_GENERATION_COST},
            "$push": {"transactions": {
                "transaction_id": tx_id,
                "tier_name": "AI Video Generation",
                "amount": -VIDEO_GENERATION_COST,
                "price": 0.0,
                "payment_method": "ai_video_generate",
                "status": "success",
                "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            }},
        },
    )

    return {
        "status": "success",
        "job_id": result["job_id"],
        "is_emulator": result["is_emulator"],
        "video_url": result.get("video_url"),
        "keyart_url": result.get("keyart_url"),
        "duration": result.get("duration"),
        "tokens_remaining": current_user.get("tokens", 0) - VIDEO_GENERATION_COST,
        "generation_source": result.get("generation_source", "sandbox"),
        "disclosure": {
            "replicate": "Real Replicate cloud generation in progress.",
            "private_gpu": (
                "Attempting real AI generation on your own Colab/Kaggle GPU (free, no API cost) via "
                "notebooks/free_video_gpu.ipynb. If that session has ended, this job will honestly fall "
                "back to a library/stock clip instead of silently making one up. "
                "Poll /api/video/status/{job_id} for the outcome."
            ),
            "huggingface_space": (
                "Attempting real AI generation via a free public Hugging Face Space (no API cost). "
                "This rides a shared free GPU queue, so it can be busy — if it doesn't finish in time, "
                "this job will honestly fall back to a library/stock clip instead of silently making one up. "
                "Poll /api/video/status/{job_id} for the outcome."
            ),
            "video_library": (
                "Real AI-generated clip from your local library (restocked for free via "
                "notebooks/free_video_gpu.ipynb on Kaggle/Colab) — not a live render, but a genuine "
                "AI-generated clip rather than generic stock footage."
            ),
            "sandbox": (
                "Sandbox stock clip — no REPLICATE_API_TOKEN, PRIVATE_GPU_ENDPOINT, or HF_VIDEO_SPACE is "
                "configured, and the local video library is empty, so this is not a genuine AI render."
            ),
        }.get(result.get("generation_source", "sandbox"), "Sandbox stock clip — not a genuine AI render."),
    }


@router.get("/status/{job_id}")
def video_status(job_id: str, current_user: dict = Depends(get_current_user_helper)):
    return get_job_status(job_id)


@router.get("/library/{filename}")
def serve_library_clip(filename: str):
    """
    Serves a clip from the local generated-video library (see
    backend/generated_library/README.md and notebooks/free_video_gpu.ipynb).
    Unauthenticated by design, same as the public Mixkit stock URLs this
    replaces for matching prompts — it's non-sensitive stock-replacement
    footage, not user data. Filename is validated against path traversal:
    no separators, and the resolved path must stay inside the library dir.
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    full_path = os.path.realpath(os.path.join(GENERATED_LIBRARY_DIR, filename))
    library_root = os.path.realpath(GENERATED_LIBRARY_DIR)
    if not full_path.startswith(library_root + os.sep) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Clip not found.")

    return FileResponse(full_path, media_type="video/mp4")
