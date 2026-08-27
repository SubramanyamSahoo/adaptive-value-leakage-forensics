from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


def inspect_h100(require_h100: bool = True) -> dict:
    info = {"machine": platform.machine(), "platform": platform.platform()}
    try:
        q = _run([
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ])
    except Exception as e:
        if require_h100:
            raise RuntimeError(f"nvidia-smi unavailable: {e}")
        info["nvidia_smi_error"] = repr(e)
        return info

    rows = [x.strip() for x in q.splitlines() if x.strip()]
    info["gpus"] = []
    for row in rows:
        name, total, free, driver = [x.strip() for x in row.split(",", 3)]
        info["gpus"].append({
            "name": name,
            "memory_total_mib": int(total),
            "memory_free_mib": int(free),
            "driver_version": driver,
        })

    if require_h100:
        if len(info["gpus"]) != 1:
            raise RuntimeError(
                f"Expected exactly one visible H100; found {len(info['gpus'])}."
            )
        if "h100" not in info["gpus"][0]["name"].lower():
            raise RuntimeError(f"Visible GPU is not H100: {info['gpus'][0]['name']!r}")
        if platform.machine().lower() not in {"x86_64", "amd64"}:
            raise RuntimeError(
                f"This H100 bundle expects x86_64; got {platform.machine()!r}."
            )
        if info["gpus"][0]["memory_total_mib"] < 75 * 1024:
            raise RuntimeError(
                "Visible H100 has <75 GiB HBM; this bundle expects an 80GB-class H100."
            )
    return info


def write_hardware_manifest(path: str | Path, require_h100: bool = True) -> dict:
    info = inspect_h100(require_h100=require_h100)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2))
    return info
