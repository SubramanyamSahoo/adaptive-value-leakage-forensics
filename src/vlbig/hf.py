from __future__ import annotations
import os


def token() -> str:
    t = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not t:
        raise RuntimeError("HF_TOKEN is not set.")
    return t
