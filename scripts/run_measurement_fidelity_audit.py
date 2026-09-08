#!/usr/bin/env python3
"""Run the V1 measurement-fidelity audit on the testsamples corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actintrack_app.measurement_fidelity import (
    DEFAULT_AUDIT_SAMPLES,
    run_measurement_fidelity_audit,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit sparse tracking and Optical Flow on identical cropped frames "
            "for WT550 and Mutant515 testsamples. Reports raw px/frame before "
            "unit conversion. Does not tune thresholds or apply correction factors."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/outputs/measurement_fidelity)",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        dest="sample_ids",
        default=None,
        help="Limit to one or more sample IDs (repeatable)",
    )
    parser.add_argument(
        "--tracker-mode",
        choices=("current", "historical"),
        default="current",
        help="Sparse-tracker parameter set (default: current)",
    )
    parser.add_argument(
        "--flow-mode",
        choices=("historical_draft", "current"),
        default="historical_draft",
        help=(
            "Optical Flow settings set. historical_draft uses mask_percentile=90 "
            "to match workspace draft OF artifacts (default)."
        ),
    )
    parser.add_argument(
        "--seconds-per-frame",
        type=float,
        default=None,
        help=(
            "Override seconds_per_frame for both methods. Omit to use the "
            "mode-specific default (current=30, historical=0.2)."
        ),
    )
    parser.add_argument(
        "--no-saved-roi",
        action="store_true",
        help="Ignore crop_metadata.json and analyze whole frames",
    )
    parser.add_argument(
        "--list-samples",
        action="store_true",
        help="Print default audit sample IDs and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_samples:
        for spec in DEFAULT_AUDIT_SAMPLES:
            print(
                f"{spec['sample_id']}\t{spec['condition']}\t"
                f"{spec['source']}\t{spec['role']}"
            )
        return 0

    payload = run_measurement_fidelity_audit(
        args.repo_root,
        output_dir=args.output_dir,
        sample_ids=args.sample_ids,
        use_saved_roi=not args.no_saved_roi,
        tracker_mode=args.tracker_mode,
        flow_mode=args.flow_mode,
        seconds_per_frame=args.seconds_per_frame,
    )
    ordering = payload.get("condition_ordering") or {}
    print(json.dumps(
        {
            "report_json": payload.get("report_json"),
            "sample_csv": payload.get("sample_csv"),
            "n_samples": len(payload.get("samples") or []),
            "observed_sparse_wt_gt_mutant": ordering.get(
                "observed_sparse_wt_gt_mutant"
            ),
            "observed_of_wt_gt_mutant": ordering.get("observed_of_wt_gt_mutant"),
            "by_condition": ordering.get("by_condition"),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
