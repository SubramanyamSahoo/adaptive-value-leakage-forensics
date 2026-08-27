from __future__ import annotations

import hashlib
import json
import os
import sys

import torch

from .hardware_gh200 import inspect_gh200
from .registry import MODELS


def sha256_text(x):
    return hashlib.sha256(x.encode("utf-8")).hexdigest()


def main():
    print("===== GH200 HARDWARE =====")
    print(json.dumps(inspect_gh200(True), indent=2))

    print("\n===== PYTHON ISOLATION =====")
    bad = [
        p for p in sys.path
        if "/usr/lib/python3/dist-packages" in p
    ]
    print("system dist-packages:", bad)
    assert not bad, "Venv contaminated by system packages"

    print("\n===== CUDA =====")
    print("torch:", torch.__version__)
    print("torch CUDA:", torch.version.cuda)
    print("CUDA available:", torch.cuda.is_available())

    assert torch.cuda.is_available()

    print("GPU:", torch.cuda.get_device_name(0))
    print("BF16:", torch.cuda.is_bf16_supported())

    x = torch.randn(
        (1024, 1024),
        device="cuda",
        dtype=torch.bfloat16,
    )
    _ = x @ x
    torch.cuda.synchronize()

    print("CUDA COMPUTE: PASS")

    print("\n===== FLASHINFER =====")
    import flashinfer.comm.fd_exchange
    print("FlashInfer Python compatibility: PASS")

    print("\n===== ORIGINAL VALUE-LEAKAGE =====")
    from value_leakage.sample import (
        BASELINE,
        BELOW_GOOD,
        ABOVE_GOOD,
    )
    from value_leakage.judge import (
        NUMBER_JUDGE_PROMPT,
        TRAJECTORY_JUDGE_PROMPT,
    )

    print("baseline:", sha256_text(BASELINE))
    print("below:   ", sha256_text(BELOW_GOOD))
    print("above:   ", sha256_text(ABOVE_GOOD))
    print("number:  ", sha256_text(NUMBER_JUDGE_PROMPT))
    print("traj:    ", sha256_text(TRAJECTORY_JUDGE_PROMPT))

    print("\n===== MODELS =====")
    for key, m in MODELS.items():
        print(key, "->", m.model_id)

    assert set(MODELS) == {
        "qwen35_9b",
        "qwen36_27b",
        "nemotron35_lightning",
    }

    print("\nGH200 PREFLIGHT: PASS")


if __name__ == "__main__":
    main()
