from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="judge_diagnostics_large")
    ap.add_argument("--exclude", help="target key to exclude")
    ap.add_argument("--out", default="judge_diagnostics_large/selection.json")
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--min-parse-rate", type=float, default=0.90)
    args = ap.parse_args()

    rows = []
    for path in sorted(Path(args.dir).glob("judge_calibration_*.json")):
        d = json.loads(path.read_text())
        if args.exclude and d["judge_key"] == args.exclude:
            continue
        m = d["metrics"]
        row = {
            "judge_key": d["judge_key"],
            "judge_model": d["judge_model"],
            "n_examples": int(d["n_examples"]),
            "mean_lcs_recall": float(m.get("mean_lcs_recall", 0.0)),
            "mean_lcs_precision": float(m.get("mean_lcs_precision", 0.0)),
            "exact_match": float(m["exact_match"]),
            "last_match": float(m["last_match"]),
            "parse_rate": float(m["parse_rate"]),
            "median_length_ratio": m.get("median_length_ratio"),
            "source": str(path),
        }
        row["eligible"] = row["n_examples"] >= args.min_n and row["parse_rate"] >= args.min_parse_rate
        rows.append(row)

    eligible = [r for r in rows if r["eligible"]]
    if not eligible:
        result = {
            "selected": None,
            "reason": "No judge met the predeclared minimum N and parse-rate gate. Choose manually after raw audit.",
            "min_n": args.min_n,
            "min_parse_rate": args.min_parse_rate,
            "ranking": rows,
        }
    else:
        ranked = sorted(
            eligible,
            key=lambda r: (
                r["mean_lcs_recall"],
                r["exact_match"],
                r["last_match"],
                r["parse_rate"],
                r["mean_lcs_precision"],
            ),
            reverse=True,
        )
        result = {
            "selection_rule": ["mean_lcs_recall", "exact_match", "last_match", "parse_rate", "mean_lcs_precision"],
            "min_n": args.min_n,
            "min_parse_rate": args.min_parse_rate,
            "selected": ranked[0],
            "ranking": ranked,
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
