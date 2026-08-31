import os
import io
import base64
import datetime
import uuid
import requests as req_lib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pymongo.database import Database
from PIL import Image, ImageOps, ImageEnhance

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper

router = APIRouter(prefix="/api/image/ai", tags=["AI Image Editing Suite"])

STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")
CLIPDROP_API_KEY = os.getenv("CLIPDROP_API_KEY", "")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")


@router.get("/config-status")
def get_ai_config_status(current_user: dict = Depends(get_current_user_helper)):
    return {
        "stability_ai": bool(STABILITY_API_KEY),
        "clipdrop": bool(CLIPDROP_API_KEY),
        "cloudinary": bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET),
        "free_local_tools": ["remove-bg", "upscale", "enhance"],
    }


class AiEditRequest(BaseModel):
    source_url: str
    tool: str  # remove-bg, cleanup, reimagine, search-replace, outpaint, upscale, enhance, style-transfer
    prompt: Optional[str] = ""
    search_prompt: Optional[str] = ""
    replace_prompt: Optional[str] = ""
    direction: Optional[str] = "right"
    scale_factor: Optional[str] = "2x"
    style_preset: Optional[str] = "oil_paint"


AI_TOOL_COSTS = {
    "remove-bg": 5,
    "cleanup": 5,
    "reimagine": 8,
    "search-replace": 8,
    "outpaint": 6,
    "upscale": 10,
    "enhance": 3,
    "style-transfer": 5,
}

# FIX (billing integrity): these three tools now do real, free, local image
# processing (Pillow + optionally rembg) instead of the old behavior of
# `result_url = req.source_url` — returning the caller's own unedited image
# back to them while still deducting tokens. The remaining tools genuinely
# need a paid provider (Stability AI / Clipdrop) this build has no key for,
# so they now fail with a clear, unpaid 501 instead of silently no-op'ing
# and charging anyway.
REAL_TOOLS = {"remove-bg", "upscale", "enhance"}


def _download_image_bytes(url: str) -> bytes:
    resp = req_lib.get(url, timeout=15)
    resp.raise_for_status()
    return resp.content


def _image_to_data_url(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.convert("RGBA" if fmt == "PNG" else "RGB").save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/{fmt.lower()};base64,{b64}"


@router.post("/edit")
def ai_edit_image(
    req: AiEditRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    tool = req.tool
    if tool not in AI_TOOL_COSTS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")

    if tool not in REAL_TOOLS:
        raise HTTPException(
            status_code=501,
            detail=(
                f"'{tool}' needs a paid provider (Stability AI / Clipdrop) that isn't configured "
                f"in this free-tier build. No tokens have been charged. Available free tools right "
                f"now: {', '.join(sorted(REAL_TOOLS))}."
            ),
        )

    cost = AI_TOOL_COSTS[tool]
    if current_user.get("tokens", 0) < cost:
        raise HTTPException(status_code=400, detail=f"Insufficient tokens. Requires {cost} tokens.")

    try:
        raw_bytes = _download_image_bytes(req.source_url)
        img = Image.open(io.BytesIO(raw_bytes))

        if tool == "remove-bg":
            try:
                from rembg import remove
                out_bytes = remove(raw_bytes)
                img = Image.open(io.BytesIO(out_bytes))
            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="rembg isn't installed on this server yet. Run: pip install rembg (no API key needed).",
                )
        elif tool == "upscale":
            factor = 4 if req.scale_factor == "4x" else 2
            img = img.convert("RGB").resize((img.width * factor, img.height * factor), Image.LANCZOS)
        elif tool == "enhance":
            img = ImageOps.autocontrast(img.convert("RGB"))
            img = ImageEnhance.Sharpness(img).enhance(1.6)
            img = ImageEnhance.Color(img).enhance(1.15)

        result_url = _image_to_data_url(img)
    except HTTPException:
        raise
    except Exception as e:
        # Real failure — no charge, unlike the old code which charged unconditionally.
        raise HTTPException(status_code=502, detail=f"Image processing failed, no tokens were charged: {e}")

    tx_id = f"AIEDIT_{uuid.uuid4().hex[:10].upper()}"
    db.users.update_one(
        {"email": current_user["email"]},
        {
            "$inc": {"tokens": -cost},
            "$push": {"transactions": {
                "transaction_id": tx_id,
                "tier_name": f"AI Edit: {tool.upper()}",
                "amount": -cost,
                "price": 0.0,
                "payment_method": "ai_image_edit",
                "status": "success",
                "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            }},
        },
    )

    return {
        "status": "success",
        "result_image": result_url,
        "tool": tool,
        "cost": cost,
        "data_source": "real_local_processing",
        "tokens_remaining": current_user.get("tokens", 0) - cost,
    }
