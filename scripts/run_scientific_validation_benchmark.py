#!/usr/bin/env python3
"""Run the V2 durable scientific validation benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actintrack_app.measurement_fidelity import DEFAULT_AUDIT_SAMPLES
from actintrack_app.scientific_validation import run_scientific_validation_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Durable scientific validation for sparse tracking, Optical Flow, "
            "reacquisition provenance, per-track results, nucleus-relative "
            "movement, and structural orientation. Does not tune thresholds."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--sample-id", action="append", dest="sample_ids")
    parser.add_argument(
        "--tracker-mode",
        choices=("current", "historical"),
        default="current",
    )
    parser.add_argument(
        "--flow-mode",
        choices=("current", "historical_draft"),
        default="current",
    )
    parser.add_argument("--seconds-per-frame", type=float, default=None)
    parser.add_argument("--lookahead-frames", type=int, default=None)
    parser.add_argument(
        "--manual-measurements",
        type=Path,
        default=None,
        help="Optional JSON file with quantitative manual references",
    )
    parser.add_argument("--no-saved-roi", action="store_true")
    parser.add_argument("--list-samples", action="store_true")
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

    payload = run_scientific_validation_benchmark(
        args.repo_root,
        output_dir=args.output_dir,
        sample_ids=args.sample_ids,
        use_saved_roi=not args.no_saved_roi,
        tracker_mode=args.tracker_mode,
        flow_mode=args.flow_mode,
        seconds_per_frame=args.seconds_per_frame,
        lookahead_frames=args.lookahead_frames,
        manual_measurements_path=args.manual_measurements,
    )
    sanity = payload.get("condition_sanity") or {}
    print(
        json.dumps(
            {
                "report_json": payload.get("report_json"),
                "sample_csv": payload.get("sample_csv"),
                "n_samples": len(payload.get("samples") or []),
                "investigation_alerts": sanity.get("investigation_alerts"),
                "observed_sparse_wt_gt_mutant": sanity.get(
                    "observed_sparse_wt_gt_mutant"
                ),
                "observed_of_wt_gt_mutant": sanity.get("observed_of_wt_gt_mutant"),
                "manual_stats_by_method": payload.get("manual_stats_by_method"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
