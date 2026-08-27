from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


DEFAULT_FINGERPRINTS = {
    "H1_direct_preference": {
        "relevant_clamp": "small_or_no_specific_migration_prediction",
        "irrelevant_matched_clamp": "small_change",
        "structured_arm": "effect_should_remain_if_final preference is direct",
    },
    "H2_threshold_anchoring": {
        "relevant_clamp": "effect_tracks_threshold geometry more than component identity",
        "irrelevant_matched_clamp": "small_change",
        "structured_arm": "no unique component-specific prediction",
    },
    "H3_epistemic_slack_search": {
        "relevant_clamp": "carrier bias falls and/or remaining-component bias rises",
        "irrelevant_matched_clamp": "substantially smaller change than relevant clamp",
        "structured_arm": "qualitative effect survives structuring",
    },
    "H4_late_answer_manipulation": {
        "relevant_clamp": "component distributions largely stable while final effect remains",
        "irrelevant_matched_clamp": "small_change",
        "structured_arm": "intermediate components remain weakly treatment-dependent",
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--slack-table-json", required=True)
    ap.add_argument("--heldout-task-id", required=True)
    args = ap.parse_args()

    slack = json.loads(Path(args.slack_table_json).read_text())
    measurable = {k: v["log_iqr"] for k, v in slack.items() if v.get("log_iqr") is not None}
    if not measurable:
        raise SystemExit("No measurable slack carrier.")
    predicted = max(sorted(measurable), key=lambda k: measurable[k])

    record = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "slack_metric": "IQR(log(component)) on positive neutral-baseline component estimates",
        "predicted_bias_carrier": predicted,
        "heldout_task_id": args.heldout_task_id,
        "hypothesis_fingerprints": DEFAULT_FINGERPRINTS,
        "status": "locked_before_heldout_treatment_results",
    }
    raw = json.dumps(record, sort_keys=True, indent=2)
    record["sha256_before_hash_field"] = hashlib.sha256(raw.encode()).hexdigest()
    Path(args.out).write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
