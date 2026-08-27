from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import sys

from packaging.version import Version

from .hardware import inspect_h100
from .registry import MODELS


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> None:
    print("== H100 SXM5 / 80GB-class hardware ==")
    print(json.dumps(inspect_h100(require_h100=True), indent=2))

    print("\n== Python isolation ==")
    bad = [p for p in sys.path if "/usr/lib/python3/dist-packages" in p]
    print("system dist-packages visible:", bad)
    if bad:
        raise SystemExit("Clean-venv invariant violated: system dist-packages are visible.")

    print("\n== HF token ==")
    if not (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")):
        raise SystemExit("Set HF_TOKEN before model downloads.")
    print("HF token present (not printed).")

    print("\n== vLLM ==")
    if shutil.which("vllm") is None:
        raise SystemExit("vllm executable not found.")
    try:
        v = importlib.metadata.version("vllm")
    except Exception:
        v = "unknown"
    print("vLLM version:", v)
    if v != "unknown" and Version(v) < Version("0.19.0"):
        raise SystemExit("vLLM < 0.19.0 is too old for Qwen3.6.")

    print("\n== Original repository ==")
    try:
        from value_leakage.sample import BASELINE, BELOW_GOOD, ABOVE_GOOD
        from value_leakage.judge import NUMBER_JUDGE_PROMPT, TRAJECTORY_JUDGE_PROMPT
    except Exception as e:
        raise SystemExit(
            "Run from the Aditya repo root with vlh100/ copied in. "
            f"Original package import failed: {e}"
        )

    print(json.dumps({
        "baseline_prompt_sha256": sha256_text(BASELINE),
        "below_good_prompt_sha256": sha256_text(BELOW_GOOD),
        "above_good_prompt_sha256": sha256_text(ABOVE_GOOD),
        "number_judge_prompt_sha256": sha256_text(NUMBER_JUDGE_PROMPT),
        "trajectory_judge_prompt_sha256": sha256_text(TRAJECTORY_JUDGE_PROMPT),
    }, indent=2))

    print("\n== 2026 model registry ==")
    for k, m in MODELS.items():
        assert m.release_year == 2026
        print(k, "->", m.model_id)

    print("\nPreflight passed.")


if __name__ == "__main__":
    main()
