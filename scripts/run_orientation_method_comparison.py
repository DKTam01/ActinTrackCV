#!/usr/bin/env python3
"""Compare research candidates for local F-actin structural orientation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actintrack_app.measurement_fidelity import (
    DEFAULT_AUDIT_SAMPLES,
    load_crop_roi_for_sample,
)
from actintrack_app.orientation_research import (
    ORIENTATION_METHODS,
    ORIENTATION_RESEARCH_VERSION,
    OrientationResearchSettings,
    axial_angle_error_deg,
    axial_circular_mean_deg,
    run_orientation_method,
)
from actintrack_app.preview_workflow import load_cropped_frames_from_video


def _line_fixture(
    angle_deg: float,
    *,
    intensity: int = 220,
    noise_sigma: float = 5.0,
    seed: int = 20260908,
) -> np.ndarray:
    rng = np.random.default_rng(seed + int(round(angle_deg * 10)))
    image = rng.normal(12.0, noise_sigma, (160, 160)).clip(0, 255).astype(np.uint8)
    center = np.array([105.0, 80.0])
    direction = np.array(
        [np.cos(np.deg2rad(angle_deg)), np.sin(np.deg2rad(angle_deg))]
    )
    p0 = tuple(np.round(center - direction * 45).astype(int))
    p1 = tuple(np.round(center + direction * 45).astype(int))
    cv2.line(image, p0, p1, int(intensity), 3, cv2.LINE_AA)
    return cv2.GaussianBlur(image, (3, 3), 0)


def _stress_fixtures() -> dict[str, np.ndarray]:
    weak = _line_fixture(30.0, intensity=45, noise_sigma=7.0)
    noisy = _line_fixture(60.0, intensity=150, noise_sigma=25.0)
    crossing = np.full((160, 160), 12, dtype=np.uint8)
    cv2.line(crossing, (30, 45), (130, 115), 210, 3, cv2.LINE_AA)
    cv2.line(crossing, (30, 115), (130, 45), 190, 3, cv2.LINE_AA)
    crossing = cv2.GaussianBlur(crossing, (3, 3), 0)
    curved = np.full((160, 160), 12, dtype=np.uint8)
    cv2.ellipse(curved, (80, 110), (55, 45), 0, 195, 345, 210, 3, cv2.LINE_AA)
    curved = cv2.GaussianBlur(curved, (3, 3), 0)
    return {
        "weak_30deg": weak,
        "noisy_60deg": noisy,
        "crossing": crossing,
        "curved": curved,
    }


def synthetic_comparison(
    settings: OrientationResearchSettings,
) -> dict[str, object]:
    straight_rows: list[dict[str, object]] = []
    method_errors: dict[str, list[float]] = {method: [] for method in ORIENTATION_METHODS}
    for expected in (0.0, 30.0, 45.0, 60.0, 90.0):
        frame = _line_fixture(expected)
        for method in ORIENTATION_METHODS:
            result = run_orientation_method(method, frame, settings=settings)
            mean = axial_circular_mean_deg(result.estimates)
            error = (
                axial_angle_error_deg(mean, expected)
                if mean is not None
                else None
            )
            if error is not None:
                method_errors[method].append(error)
            straight_rows.append(
                {
                    "fixture": f"straight_{int(expected)}deg",
                    "expected_local_orientation_deg": expected,
                    "method": method,
                    "estimated_axial_mean_deg": mean,
                    "axial_error_deg": error,
                    "estimate_count": len(result.estimates),
                    "mean_confidence": (
                        float(np.mean([item.confidence for item in result.estimates]))
                        if result.estimates
                        else None
                    ),
                    "runtime_ms": result.runtime_ms,
                }
            )

    stress_rows: list[dict[str, object]] = []
    for name, frame in _stress_fixtures().items():
        for method in ORIENTATION_METHODS:
            result = run_orientation_method(method, frame, settings=settings)
            stress_rows.append(
                {
                    "fixture": name,
                    "method": method,
                    "estimate_count": len(result.estimates),
                    "estimated_axial_mean_deg": axial_circular_mean_deg(result.estimates),
                    "mean_confidence": (
                        float(np.mean([item.confidence for item in result.estimates]))
                        if result.estimates
                        else None
                    ),
                    "runtime_ms": result.runtime_ms,
                }
            )

    threshold_rows: list[dict[str, object]] = []
    frame = _line_fixture(45.0, intensity=100, noise_sigma=12.0)
    for percentile in (60.0, 70.0, 80.0, 90.0):
        for method in ORIENTATION_METHODS:
            varied = replace(settings, threshold_percentile=percentile)
            result = run_orientation_method(method, frame, settings=varied)
            mean = axial_circular_mean_deg(result.estimates)
            threshold_rows.append(
                {
                    "threshold_percentile": percentile,
                    "method": method,
                    "estimated_axial_mean_deg": mean,
                    "axial_error_deg": (
                        axial_angle_error_deg(mean, 45.0)
                        if mean is not None
                        else None
                    ),
                    "estimate_count": len(result.estimates),
                }
            )

    method_summary = {}
    for method, errors in method_errors.items():
        method_summary[method] = {
            "straight_fixture_count": len(errors),
            "median_straight_axial_error_deg": (
                float(np.median(errors)) if errors else None
            ),
            "max_straight_axial_error_deg": max(errors) if errors else None,
        }
    return {
        "straight_fixtures": straight_rows,
        "stress_fixtures": stress_rows,
        "threshold_sensitivity": threshold_rows,
        "method_summary": method_summary,
    }


def real_sample_comparison(
    root: Path,
    settings: OrientationResearchSettings,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    crop_metadata = root / "metadata" / "crop_metadata.json"
    for spec in DEFAULT_AUDIT_SAMPLES:
        loaded = load_crop_roi_for_sample(crop_metadata, spec["roi_key"])
        if loaded is None:
            continue
        orientation, roi = loaded
        frames = load_cropped_frames_from_video(root / spec["source"], orientation, roi)
        frame = frames[0]
        for method in ORIENTATION_METHODS:
            result = run_orientation_method(method, frame, settings=settings)
            means_by_threshold: list[float] = []
            for percentile in (60.0, 70.0, 80.0):
                varied = replace(settings, threshold_percentile=percentile)
                varied_result = run_orientation_method(method, frame, settings=varied)
                mean = axial_circular_mean_deg(varied_result.estimates)
                if mean is not None:
                    means_by_threshold.append(mean)
            threshold_span = None
            if len(means_by_threshold) >= 2:
                anchor = means_by_threshold[0]
                threshold_span = max(
                    axial_angle_error_deg(value, anchor)
                    for value in means_by_threshold[1:]
                )
            rows.append(
                {
                    "sample_id": spec["sample_id"],
                    "condition": spec["condition"],
                    "method": method,
                    "reference_frame_index": 0,
                    "domain_note": (
                        "saved RectROI only; no CellRegion/cutoff/nucleus "
                        "annotations in audit corpus"
                    ),
                    "estimate_count": len(result.estimates),
                    "valid_pixel_count": result.valid_pixel_count,
                    "foreground_pixel_count": result.foreground_pixel_count,
                    "mean_confidence": (
                        float(np.mean([item.confidence for item in result.estimates]))
                        if result.estimates
                        else None
                    ),
                    "axial_mean_deg_for_method_comparison_only": (
                        axial_circular_mean_deg(result.estimates)
                    ),
                    "threshold_axial_span_deg": threshold_span,
                    "runtime_ms": result.runtime_ms,
                    "nucleus_relative_angle_available": False,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "orientation_research" / "comparison.json",
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    settings = OrientationResearchSettings()
    report = {
        "research_kind": "structural_orientation_method_comparison",
        "research_version": ORIENTATION_RESEARCH_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": asdict(settings),
        "scientific_quantity": (
            "local axial cable orientation; eventual production angle is "
            "acos(abs(filament_unit dot radial_unit)) in [0, 90] degrees"
        ),
        "synthetic": synthetic_comparison(settings),
        "real_samples": real_sample_comparison(root, settings),
        "limitations": [
            "Real audit samples lack researcher-confirmed nucleus references.",
            "Real audit samples lack manual structural-angle ground truth.",
            "Real results are method-stability diagnostics, not biological measurements.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "output": str(args.output.resolve()),
            "synthetic_method_summary": report["synthetic"]["method_summary"],
            "real_row_count": len(report["real_samples"]),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
