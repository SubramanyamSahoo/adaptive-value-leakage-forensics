from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import sys

import torch

from .hardware_gh200 import inspect_gh200
from .registry import DEFAULT_JUDGE_CANDIDATES, DEFAULT_TARGETS, MODELS

EXPECTED_HASHES = {
    "baseline": "95c31ebada270055e793bdd6d53484b6878ed94d9bd11a2dbbafd86a5655fde7",
    "below": "657ec591f878cecc6ef91808e559dac061d1fd92483df7b5c0176ed8dff3a91d",
    "above": "0f7602366eb768a1c14115d62911b736238fc89b506e3d92fe46c67ced16bb3a",
    "number": "86f2c657867268b01f2ad2c6ce1a507527f4ccf47f344029786ca32d7723dcd4",
    "trajectory": "f18248937229c3899b513be5445732b163c628ec6e7e32fe2a73f49a702ac8ec",
}


def sha(x: str) -> str:
    return hashlib.sha256(x.encode("utf-8")).hexdigest()


def main() -> None:
    print("===== GH200 LARGE-MODEL PREFLIGHT =====")
    print(json.dumps(inspect_gh200(True), indent=2))
    bad = [p for p in sys.path if "/usr/lib/python3/dist-packages" in p]
    print("system dist-packages:", bad)
    assert not bad, "Venv is contaminated by system packages"

    print("torch:", torch.__version__)
    print("torch CUDA:", torch.version.cuda)
    print("CUDA available:", torch.cuda.is_available())
    assert torch.cuda.is_available()
    print("GPU:", torch.cuda.get_device_name(0))
    print("BF16:", torch.cuda.is_bf16_supported())
    x = torch.randn((1024, 1024), device="cuda", dtype=torch.bfloat16)
    _ = x @ x
    torch.cuda.synchronize()
    print("CUDA COMPUTE: PASS")

    import flashinfer.comm.fd_exchange  # noqa: F401
    print("FlashInfer import: PASS")
    print("vLLM:", importlib.metadata.version("vllm"))
    print("transformers:", importlib.metadata.version("transformers"))

    from value_leakage.sample import BASELINE, BELOW_GOOD, ABOVE_GOOD
    from value_leakage.judge import NUMBER_JUDGE_PROMPT, TRAJECTORY_JUDGE_PROMPT
    actual = {
        "baseline": sha(BASELINE),
        "below": sha(BELOW_GOOD),
        "above": sha(ABOVE_GOOD),
        "number": sha(NUMBER_JUDGE_PROMPT),
        "trajectory": sha(TRAJECTORY_JUDGE_PROMPT),
    }
    print("prompt hashes:", json.dumps(actual, indent=2))
    assert actual == EXPECTED_HASHES, "Original Aditya prompt/judge text changed"

    assert set(MODELS) == {"qwen36_27b", "qwen38_27b", "granite42_30b"}
    assert DEFAULT_TARGETS == ("qwen36_27b",)
    assert DEFAULT_JUDGE_CANDIDATES == ("qwen38_27b", "granite42_30b")
    print("ACTIVE TARGETS:", DEFAULT_TARGETS)
    print("ACTIVE JUDGES:", DEFAULT_JUDGE_CANDIDATES)
    for k, m in MODELS.items():
        print(k, "->", m.model_id)

    if not (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")):
        raise SystemExit("Set HF_TOKEN before model downloads.")
    print("LARGE-MODEL GH200 PREFLIGHT: PASS")


if __name__ == "__main__":
    main()
