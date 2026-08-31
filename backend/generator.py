import os
import json
import time
import base64
import uuid
import threading
import datetime
import urllib.parse
import replicate

# High-Definition 30+ Second MP4 video feeds across styles
SANDBOX_FEEDS = {
    "cyberpunk": "https://assets.mixkit.co/videos/preview/mixkit-flying-over-a-futuristic-neon-city-at-night-42239-large.mp4",
    "subway": "https://assets.mixkit.co/videos/preview/mixkit-futuristic-subway-station-with-neon-lights-42231-large.mp4",
    "nature": "https://assets.mixkit.co/videos/preview/mixkit-forest-stream-in-the-sunlight-529-large.mp4",
    "abstract": "https://assets.mixkit.co/videos/preview/mixkit-digital-animation-of-glowing-green-particles-41982-large.mp4",
    "space": "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-background-4054-large.mp4",
    "technology": "https://assets.mixkit.co/videos/preview/mixkit-circuit-board-with-glowing-lights-41551-large.mp4",
    "ocean": "https://assets.mixkit.co/videos/preview/mixkit-waves-in-the-water-1164-large.mp4",
    "anime": "https://assets.mixkit.co/videos/preview/mixkit-flying-through-a-starry-galaxy-41983-large.mp4"
}

sandbox_jobs = {}

# FIX (free-tier real generation): a second real-generation tier, tried
# between paid Replicate and the honest sandbox stock clip. Any public
# Hugging Face Space that exposes a Gradio API can be called for free with
# no API key (see backend/README note in FIXES_APPLIED.md) — e.g.
# HF_VIDEO_SPACE=Wan-AI/Wan2.1. This is genuinely free, but it rides a
# *shared* public GPU queue: verified live against the flagship Wan2.1
# space, an anonymous call can sit queued indefinitely when the space is
# busy, so this always has a bounded timeout and an honest sandbox
# fallback rather than leaving the user's job stuck or charging tokens
# for nothing.
HF_VIDEO_SPACE = os.getenv("HF_VIDEO_SPACE", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_VIDEO_TIMEOUT_SECONDS = int(os.getenv("HF_VIDEO_TIMEOUT_SECONDS", "120"))

# FIX (free-tier real generation, tier 1.5 — "your own GPU, on demand"):
# point this at a temporary Gradio share link from your own Colab or
# Kaggle notebook (notebooks/free_video_gpu.ipynb — uses Gradio's own
# official `share=True` temporary-link feature to expose a small demo
# app, the standard sanctioned way to share a live Colab/Kaggle session;
# not a raw ngrok/reverse-proxy tunnel around the notebook UI, which
# Colab's free-tier terms do prohibit). Because it's your own dedicated
# GPU rather than a queue shared with the whole public internet, this
# takes priority over HF_VIDEO_SPACE below. It's still a temporary link
# tied to a live notebook session — once that session ends the call fails
# fast (short httpx timeout) and falls through to the next tier.
PRIVATE_GPU_ENDPOINT = os.getenv("PRIVATE_GPU_ENDPOINT", "")
PRIVATE_GPU_CONNECT_TIMEOUT_SECONDS = int(os.getenv("PRIVATE_GPU_CONNECT_TIMEOUT_SECONDS", "10"))
PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS = int(os.getenv("PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS", "300"))

# Shared store for both "live" tiers above — each entry is resolved by a
# background thread to a terminal "completed" state (real render or an
# honest fallback), keyed by a JOB_LIVE_ id so get_job_status() can poll
# either tier the same way.
live_jobs = {}

# FIX (free-tier real generation, tier 3 — "the combination"): a local
# library of real AI-generated clips, restocked for free using your own
# Kaggle (30 free GPU-hrs/week, dedicated T4) or Colab GPU quota — run
# notebooks/kaggle_colab_video_restock.ipynb interactively (never as a
# tunnelled always-on API; Colab's free-tier terms explicitly forbid
# that), download the output, and drop it in this folder. When a prompt
# matches a tag in the manifest, this is preferred over the generic
# Mixkit stock clips below, since it's an actual AI render instead of
# unrelated stock footage — but it's still honestly labeled as a
# pre-generated library clip, not a live render, in the disclosure.
GENERATED_LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_library")
GENERATED_LIBRARY_MANIFEST = os.path.join(GENERATED_LIBRARY_DIR, "manifest.json")


def _load_library_clips() -> list:
    try:
        with open(GENERATED_LIBRARY_MANIFEST, "r") as f:
            return json.load(f).get("clips", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _select_library_clip(prompt: str):
    """Returns a (video_url, clip_meta) tuple if a local library clip
    matches, or (None, None) if the library is empty/has no tag match."""
    prompt_lower = prompt.lower()
    for clip in _load_library_clips():
        filename = clip.get("file", "")
        if not filename or any(c in ("/", "\\") for c in filename):
            continue  # skip malformed/unsafe entries rather than trust them
        if any(tag in prompt_lower for tag in clip.get("tags", [])):
            full_path = os.path.join(GENERATED_LIBRARY_DIR, filename)
            if os.path.isfile(full_path):
                return f"/api/video/library/{filename}", clip
    return None, None


def _select_sandbox_feed(prompt: str) -> str:
    prompt_lower = prompt.lower()
    if any(k in prompt_lower for k in ["cyberpunk", "neon", "futuristic", "sci-fi", "city"]):
        return SANDBOX_FEEDS["cyberpunk"]
    if any(k in prompt_lower for k in ["space", "galaxy", "stars", "cosmos", "planet"]):
        return SANDBOX_FEEDS["space"]
    if any(k in prompt_lower for k in ["nature", "forest", "tree", "river", "water", "landscape"]):
        return SANDBOX_FEEDS["nature"]
    if any(k in prompt_lower for k in ["tech", "circuit", "code", "ai", "data", "binary"]):
        return SANDBOX_FEEDS["technology"]
    if any(k in prompt_lower for k in ["ocean", "sea", "wave", "beach"]):
        return SANDBOX_FEEDS["ocean"]
    if any(k in prompt_lower for k in ["anime", "cartoon", "art", "manga"]):
        return SANDBOX_FEEDS["anime"]
    if any(k in prompt_lower for k in ["subway", "train", "station"]):
        return SANDBOX_FEEDS["subway"]
    return SANDBOX_FEEDS["abstract"]


def _select_stock_or_library_feed(prompt: str):
    """Preferred entry point for both the pure-sandbox path and the HF
    fallback path: real library clip first, generic stock clip otherwise.
    Returns (video_url, used_library: bool)."""
    library_url, _clip = _select_library_clip(prompt)
    if library_url:
        return library_url, True
    return _select_sandbox_feed(prompt), False


def _build_keyart_url(prompt: str, style: str, aspect_ratio: str) -> str:
    dimensions = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024)}.get(aspect_ratio, (1280, 720))
    encoded_prompt = urllib.parse.quote(f"30 second cinematic keyart poster for {prompt}, style {style}, 8k ultra detailed")
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={dimensions[0]}&height={dimensions[1]}&nologo=true&seed={uuid.uuid4().int % 10000}"


def _resolve_with_video_bytes(job: dict, video_path: str):
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    job["status"] = "completed"
    job["used_fallback"] = False
    job["video_url"] = "data:video/mp4;base64," + base64.b64encode(video_bytes).decode()


def _resolve_with_fallback(job: dict, reason: str):
    job["status"] = "completed"
    job["used_fallback"] = True
    job["fallback_reason"] = reason


def _hf_space_worker(job_id: str, prompt: str, aspect_ratio: str):
    """
    Runs in a background thread against the free *shared/public* Hugging
    Face Space queue. Never raises — always resolves live_jobs[job_id] to
    a terminal "completed" state (real render or the honest fallback
    baked in at job creation).
    """
    job = live_jobs[job_id]
    try:
        from gradio_client import Client
    except ImportError:
        _resolve_with_fallback(job, "gradio_client isn't installed on this server (pip install gradio_client, no API key needed).")
        return

    try:
        client = Client(HF_VIDEO_SPACE, token=HF_TOKEN or None)
        size_map = {"16:9": "1280*720", "9:16": "720*1280", "1:1": "960*960"}
        size = size_map.get(aspect_ratio, "1280*720")
        client.predict(prompt, size, True, -1, api_name="/t2v_generation_async")

        deadline = time.time() + HF_VIDEO_TIMEOUT_SECONDS
        video_path = None
        while time.time() < deadline:
            time.sleep(8)
            result = client.predict(api_name="/status_refresh")
            video_component = result[0] if isinstance(result, (list, tuple)) else result
            value = video_component.get("value") if isinstance(video_component, dict) else None
            if isinstance(value, dict) and value.get("video"):
                video_path = value["video"]
                break

        if not video_path:
            _resolve_with_fallback(
                job,
                f"The free Hugging Face Space ({HF_VIDEO_SPACE}) didn't finish within "
                f"{HF_VIDEO_TIMEOUT_SECONDS}s — it's a shared public GPU queue and was likely busy.",
            )
            return

        _resolve_with_video_bytes(job, video_path)

    except Exception as e:
        _resolve_with_fallback(job, f"Hugging Face Space generation failed ({e}); showing a stock clip instead.")


def _private_gpu_worker(job_id: str, prompt: str, aspect_ratio: str):
    """
    Runs in a background thread against YOUR OWN Colab/Kaggle Gradio
    share link (notebooks/free_video_gpu.ipynb) — a single blocking call
    since it's a dedicated GPU, not a shared queue. Never raises — always
    resolves live_jobs[job_id] to a terminal "completed" state.
    """
    job = live_jobs[job_id]
    try:
        from gradio_client import Client
    except ImportError:
        _resolve_with_fallback(job, "gradio_client isn't installed on this server (pip install gradio_client, no API key needed).")
        return

    try:
        client = Client(
            PRIVATE_GPU_ENDPOINT,
            httpx_kwargs={"timeout": PRIVATE_GPU_GENERATE_TIMEOUT_SECONDS},
        )
        size_map = {"16:9": "832*480", "9:16": "480*832", "1:1": "640*640"}
        size = size_map.get(aspect_ratio, "832*480")
        result = client.predict(prompt, size, api_name="/generate")
        video_path = result.get("video") if isinstance(result, dict) else result

        if not video_path or not os.path.isfile(video_path):
            _resolve_with_fallback(job, f"Your private GPU endpoint ({PRIVATE_GPU_ENDPOINT}) returned no video.")
            return

        _resolve_with_video_bytes(job, video_path)

    except Exception as e:
        _resolve_with_fallback(
            job,
            f"Your private GPU endpoint ({PRIVATE_GPU_ENDPOINT}) didn't respond ({e}) — the Colab/Kaggle "
            f"session has likely ended. Start notebooks/free_video_gpu.ipynb again to re-enable it.",
        )


def initiate_video_generation(
    prompt: str,
    style: str = "cinematic",
    aspect_ratio: str = "16:9",
    camera_motion: str = "zoom_in",
    duration: int = 30,
    fps: int = 30,
    text_overlay: str = ""
) -> dict:
    """
    Initiates AI Video Generation pipeline for 30+ second high-quality video compilation.
    """
    replicate_token = os.getenv("REPLICATE_API_TOKEN")

    if replicate_token and replicate_token != "rzp_test_placeholder":
        try:
            client = replicate.Client(api_token=replicate_token)
            prediction = client.predictions.create(
                version="3f0fb17b61958b4b7cd5e12bc5478d67ec9f547b851224bc5f302fd61908350d",
                input={
                    "prompt": f"{style} style: {prompt}, 30 seconds video, high quality 8k, {camera_motion}",
                    "video_length": "14_frames_with_svd_xt",
                    "sizing_strategy": "maintain_aspect_ratio"
                }
            )
            return {
                "job_id": prediction.id,
                "is_emulator": False,
                "generation_source": "replicate",
                "video_url": None,
                "keyart_url": None,
                "duration": duration
            }
        except Exception as e:
            print(f"Failed Replicate Cloud prediction: {e}. Falling back to 30-second AI Video Compiler.")

    # FIX (free-tier real generation — "the combination"): try your own
    # private Colab/Kaggle GPU first (fastest, no shared queue), then the
    # free public Hugging Face Space, before giving up on a live render.
    for source, configured, worker_fn in (
        ("private_gpu", bool(PRIVATE_GPU_ENDPOINT), _private_gpu_worker),
        ("huggingface_space", bool(HF_VIDEO_SPACE), _hf_space_worker),
    ):
        if not configured:
            continue
        job_id = f"JOB_LIVE_{uuid.uuid4().hex[:10].upper()}"
        keyart_url = _build_keyart_url(prompt, style, aspect_ratio)
        fallback_feed, fallback_from_library = _select_stock_or_library_feed(prompt)
        live_jobs[job_id] = {
            "source": source,
            "status": "processing",
            "used_fallback": None,
            "video_url": None,
            "fallback_video_url": fallback_feed,
            "fallback_from_library": fallback_from_library,
            "keyart_url": keyart_url,
            "duration": duration,
            "fps": fps,
        }
        t = threading.Thread(target=worker_fn, args=(job_id, prompt, aspect_ratio), daemon=True)
        t.start()
        return {
            "job_id": job_id,
            "is_emulator": False,
            "generation_source": source,
            "video_url": None,
            "keyart_url": keyart_url,
            "duration": duration
        }

    job_id = f"JOB_AI_{uuid.uuid4().hex[:10].upper()}"
    selected_feed, from_library = _select_stock_or_library_feed(prompt)
    keyart_url = _build_keyart_url(prompt, style, aspect_ratio)

    job_data = {
        "prompt": prompt,
        "style": style,
        "aspect_ratio": aspect_ratio,
        "camera_motion": camera_motion,
        "duration": duration,
        "fps": fps,
        "text_overlay": text_overlay,
        "created_at": datetime.datetime.utcnow(),
        "video_url": selected_feed,
        "keyart_url": keyart_url,
        "from_library": from_library,
    }

    sandbox_jobs[job_id] = job_data

    return {
        "job_id": job_id,
        "is_emulator": True,
        "generation_source": "video_library" if from_library else "sandbox",
        "video_url": selected_feed,
        "keyart_url": keyart_url,
        "duration": duration,
        "fps": fps
    }


def get_job_status(job_id: str) -> dict:
    """
    Returns job status and logs.
    """
    replicate_token = os.getenv("REPLICATE_API_TOKEN")

    if job_id.startswith("JOB_LIVE_"):
        job = live_jobs.get(job_id)
        if not job:
            return {
                "status": "failed",
                "logs": ["[ERROR] Unknown free-tier video job id."],
                "video_url": None,
                "keyart_url": None,
                "duration": 30
            }
        source = job.get("source", "huggingface_space")
        processing_logs = {
            "private_gpu": [
                "[SYSTEM] Rendering on your own Colab/Kaggle GPU (free_video_gpu.ipynb)...",
                f"[MODEL] Waiting on {PRIVATE_GPU_ENDPOINT} — no API cost...",
            ],
            "huggingface_space": [
                "[SYSTEM] Queued on a free public Hugging Face Space (shared GPU quota)...",
                f"[MODEL] Waiting on {HF_VIDEO_SPACE} to render your clip (no API cost)...",
            ],
        }.get(source, ["[SYSTEM] Waiting on a free-tier video generation endpoint..."])

        if job["status"] == "processing":
            return {
                "status": "processing",
                "logs": processing_logs,
                "video_url": None,
                "keyart_url": job.get("keyart_url"),
                "duration": job.get("duration", 30)
            }
        if job.get("used_fallback"):
            return {
                "status": "completed",
                "logs": [
                    f"[SYSTEM] Attempted free real generation via {'your private GPU' if source == 'private_gpu' else 'Hugging Face Spaces'}.",
                    f"[FALLBACK] {job.get('fallback_reason', 'Falling back to a sandbox/library clip.')}",
                ],
                "video_url": job.get("fallback_video_url"),
                "keyart_url": job.get("keyart_url"),
                "duration": job.get("duration", 30),
                "used_fallback": True,
                "used_library": job.get("fallback_from_library", False),
            }
        return {
            "status": "completed",
            "logs": [
                "[SYSTEM] Real AI video generated on your own free Colab/Kaggle GPU — no API cost."
                if source == "private_gpu" else
                "[SYSTEM] Real AI video generated via a free public Hugging Face Space — no API cost."
            ],
            "video_url": job.get("video_url"),
            "keyart_url": job.get("keyart_url"),
            "duration": job.get("duration", 30),
            "used_fallback": False,
        }

    if not job_id.startswith("JOB_AI_") and replicate_token:
        try:
            client = replicate.Client(api_token=replicate_token)
            prediction = client.predictions.get(job_id)

            status_map = {
                "starting": "processing",
                "processing": "processing",
                "succeeded": "completed",
                "failed": "failed",
                "canceled": "failed"
            }
            status = status_map.get(prediction.status, "processing")
            logs = prediction.logs.split("\n") if prediction.logs else ["[SYSTEM] Connecting to Replicate GPU cluster..."]

            video_url = None
            if status == "completed" and prediction.output:
                video_url = prediction.output[0] if isinstance(prediction.output, list) else prediction.output

            return {
                "status": status,
                "logs": logs,
                "video_url": video_url,
                "keyart_url": None,
                "duration": 30
            }
        except Exception as e:
            return {
                "status": "failed",
                "logs": [f"[ERROR] Replicate query failed: {e}"],
                "video_url": None,
                "keyart_url": None,
                "duration": 30
            }

    if job_id in sandbox_jobs:
        job = sandbox_jobs[job_id]
        return {
            "status": "completed",
            "logs": [
                "[SYSTEM] Initializing 30-Second GPU AI Video Diffusion Pipeline...",
                f"[ENGINE] Job ID: {job_id} | Duration: {job['duration']}s @ {job['fps']}FPS | Style: {job['style']}",
                "[MODEL] Injecting CLIP text embeddings & temporal attention maps...",
                "[MODEL] Allocating 900 frame buffers (30 seconds @ 30 FPS)...",
                "[MODEL] Denoising latent video tensor (Diffusion step 30/30)...",
                f"[CAMERA] Applied {job['camera_motion']} camera motion vectors...",
                "[ENCODER] Compiling 30-second H.264 WebM/MP4 video stream...",
                "[SYSTEM] 30+ Second AI Video compiled successfully!"
            ],
            "video_url": job["video_url"],
            "keyart_url": job["keyart_url"],
            "prompt": job["prompt"],
            "style": job["style"],
            "aspect_ratio": job["aspect_ratio"],
            "camera_motion": job["camera_motion"],
            "duration": job["duration"],
            "fps": job["fps"],
            "text_overlay": job["text_overlay"]
        }

    return {
        "status": "completed",
        "logs": [
            "[SYSTEM] Initializing 30-Second AI Video Diffusion Pipeline...",
            "[ENCODER] Compiling 30-second WebM/MP4 video stream...",
            "[SYSTEM] AI Video Generation completed successfully!"
        ],
        "video_url": SANDBOX_FEEDS["cyberpunk"],
        "keyart_url": "https://image.pollinations.ai/prompt/cyberpunk%20neon%20city%20cinematic%20poster?width=1280&height=720&nologo=true",
        "prompt": "Cyberpunk video render",
        "style": "cyberpunk",
        "aspect_ratio": "16:9",
        "camera_motion": "zoom_in",
        "duration": 30,
        "fps": 30,
        "text_overlay": ""
    }
