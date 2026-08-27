from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


def inspect_gh200(require_gh200: bool = True) -> dict:
    info = {"machine": platform.machine(), "platform": platform.platform()}
    q = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    ])
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
    if require_gh200:
        if len(info["gpus"]) != 1:
            raise RuntimeError(f"Expected exactly one visible GPU; found {len(info['gpus'])}")
        if "gh200" not in info["gpus"][0]["name"].lower():
            raise RuntimeError(f"Expected GH200; found {info['gpus'][0]['name']!r}")
        if platform.machine().lower() != "aarch64":
            raise RuntimeError(f"Expected aarch64 GH200 host; found {platform.machine()!r}")
    return info


def write_hardware_manifest(path: str | Path, require_gh200: bool = True) -> dict:
    info = inspect_gh200(require_gh200=require_gh200)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2))
    return info
