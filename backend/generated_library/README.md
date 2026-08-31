# Generated video library

Empty by default — the app works fine with nothing here; it just falls
back to the generic Mixkit stock clips in `backend/generator.py`.

## How to fill it (free)

1. Open `notebooks/free_video_gpu.ipynb` in Kaggle (Settings → Accelerator
   → GPU T4 x2, Internet → On) or Google Colab (Runtime → Change runtime
   type → GPU).
2. Run the "Batch restock" section. It generates one short clip per
   category (cyberpunk, nature, space, technology, ocean, anime, subway,
   abstract) using the free Wan2.1 1.3B model (fits comfortably in a T4's
   16GB VRAM) and writes them here with a matching `manifest.json`.
3. Download the output (Kaggle: the notebook's Output tab; Colab: the
   files panel) and copy `*.mp4` + `manifest.json` into this folder,
   replacing the placeholder manifest.

## Manifest format

```json
{
  "clips": [
    {
      "file": "cyberpunk_001.mp4",
      "tags": ["cyberpunk", "neon", "futuristic", "city"],
      "prompt": "the prompt used to generate it",
      "source": "kaggle_wan2.1_1.3b",
      "generated_at": "2026-08-28T00:00:00Z"
    }
  ]
}
```

`file` must be a bare filename (no `/` or `\`) living directly in this
folder — `backend/video_router.py`'s `/api/video/library/{filename}`
route rejects anything else as a path-traversal attempt. `tags` are
lowercase keywords matched against the user's prompt; the first clip
with a matching tag wins.
