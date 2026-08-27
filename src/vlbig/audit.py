from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def deterministic_indices(n: int, k: int, seed: int) -> list[int]:
    if not (0 < k <= n):
        raise ValueError("Require 0 < k <= n.")
    rng = np.random.default_rng(seed)
    return sorted(int(x) for x in rng.choice(n, size=k, replace=False))


def write_manual_audit(run: Path, k_per_condition: int, seed: int) -> Path:
    tr = json.loads((run / "trajectories.json").read_text())
    comp = json.loads((run / "components.json").read_text())
    lines = [
        "# Deterministic manual audit pack",
        "",
        f"seed: `{seed}`",
        f"k_per_condition: `{k_per_condition}`",
        "",
        "Check extraction against the raw trace before trusting aggregate results.",
        "",
    ]
    for cond in ("baseline", "below_good", "above_good"):
        raw = json.loads((run / f"{cond}.json").read_text())
        rows = raw["rows"]
        ids = deterministic_indices(len(rows), min(k_per_condition, len(rows)), seed)
        lines += [f"## {cond}", ""]
        for i in ids:
            row = rows[i]
            lines += [
                f"### rollout {i}",
                f"- trajectory: `{tr.get(cond, [None]*len(rows))[i]}`",
                f"- components: `{comp.get(cond, [None]*len(rows))[i]}`",
                "",
                "```text",
                row.get("reasoning") or row.get("content") or "",
                "```",
                "",
                "- [ ] trajectory extraction correct",
                "- [ ] component extraction correct",
                "- [ ] intermediate arithmetic not misclassified",
                "- [ ] no relevant candidate total omitted",
                "",
            ]
    out = run / "manual_audit_pack.md"
    out.write_text("\n".join(lines))
    return out
