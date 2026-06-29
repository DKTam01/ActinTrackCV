"""Reproducible synthetic ground-truth validation for dense optical-flow motion index."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from actintrack_app.optical_flow_motion_index import (
    OpticalFlowSettings,
    compute_optical_flow_motion_index,
)
from actintrack_app.tracker_validation import SyntheticScenario


@dataclass(frozen=True)
class OpticalFlowValidationThresholds:
    max_speed_relative_error: float = 0.15
    max_vertical_absolute_error_px_per_frame: float = 0.25
    max_downward_contribution_absolute_error_px_per_frame: float = 0.25
    min_valid_pixel_fraction: float = 0.02


@dataclass(frozen=True)
class OpticalFlowScenarioResult:
    scenario: str
    passed: bool
    expected_speed_px_per_frame: float
    measured_speed_px_per_frame: float
    speed_bias_px_per_frame: float
    speed_relative_error: float
    expected_signed_vertical_px_per_frame: float
    measured_signed_vertical_px_per_frame: float
    signed_vertical_bias_px_per_frame: float
    expected_downward_contribution_px_per_frame: float
    measured_downward_contribution_px_per_frame: float
    downward_contribution_bias_px_per_frame: float
    valid_pixel_fraction: float
    frame_pair_count: int
    failure_reasons: tuple[str, ...]


DEFAULT_SCENARIOS = (
    SyntheticScenario("clean_integer_down", 2.0, 1.0),
    SyntheticScenario(
        "subpixel_down",
        0.65,
        0.35,
        read_noise_sd=1.0,
        poisson_noise=True,
    ),
    SyntheticScenario(
        "noisy_upward",
        -0.40,
        -0.55,
        read_noise_sd=3.0,
        poisson_noise=True,
        bleaching_per_frame=0.02,
    ),
    SyntheticScenario(
        "horizontal_only",
        1.20,
        0.0,
        read_noise_sd=1.5,
        poisson_noise=True,
    ),
)

DEFAULT_VALIDATION_SETTINGS = OpticalFlowSettings(
    mask_percentile=60.0,
    gaussian_blur_kernel=0,
    winsize=31,
    microns_per_pixel=1.0,
    seconds_per_frame=1.0,
)


def generate_uniform_translation_frames(
    scenario: SyntheticScenario,
    *,
    seed: int = 20260622,
    shape: tuple[int, int] = (96, 112),
) -> list[np.ndarray]:
    """Return uint8 frames with known uniform translation between consecutive frames."""
    rng = np.random.default_rng(seed)
    height, width = shape
    base = np.full((height, width), scenario.background, dtype=np.float32)
    base[18:42, 12 : width - 12] = scenario.peak_intensity
    base[48:68, 18 : width - 18] = scenario.peak_intensity - 25.0
    base += np.linspace(0.0, 3.0, width, dtype=np.float32)[None, :]
    frames: list[np.ndarray] = []

    for frame_index in range(scenario.frame_count):
        shift_x = scenario.dx_px_per_frame * frame_index
        shift_y = scenario.dy_px_per_frame * frame_index
        matrix = np.float32([[1.0, 0.0, shift_x], [0.0, 1.0, shift_y]])
        image = cv2.warpAffine(
            base,
            matrix,
            (width, height),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=scenario.background,
        )
        if scenario.poisson_noise:
            image = rng.poisson(np.clip(image, 0.0, 255.0)).astype(np.float32)
        if scenario.read_noise_sd > 0:
            image += rng.normal(0.0, scenario.read_noise_sd, image.shape)
        bleach = max(0.15, 1.0 - (scenario.bleaching_per_frame * frame_index))
        image *= bleach
        frames.append(np.clip(np.rint(image), 0, 255).astype(np.uint8))

    return frames


def validate_optical_flow_scenario(
    scenario: SyntheticScenario,
    *,
    thresholds: OpticalFlowValidationThresholds = OpticalFlowValidationThresholds(),
    settings: OpticalFlowSettings | None = None,
    seed: int = 20260622,
) -> OpticalFlowScenarioResult:
    frames = generate_uniform_translation_frames(scenario, seed=seed)
    flow_settings = settings or DEFAULT_VALIDATION_SETTINGS
    result = compute_optical_flow_motion_index(frames, flow_settings)

    expected_speed = float(
        np.hypot(scenario.dx_px_per_frame, scenario.dy_px_per_frame)
    )
    expected_vertical = scenario.dy_px_per_frame
    expected_downward = max(scenario.dy_px_per_frame, 0.0)

    if not result.has_valid_result:
        return OpticalFlowScenarioResult(
            scenario=scenario.name,
            passed=False,
            expected_speed_px_per_frame=expected_speed,
            measured_speed_px_per_frame=float("nan"),
            speed_bias_px_per_frame=float("nan"),
            speed_relative_error=float("inf"),
            expected_signed_vertical_px_per_frame=expected_vertical,
            measured_signed_vertical_px_per_frame=float("nan"),
            signed_vertical_bias_px_per_frame=float("nan"),
            expected_downward_contribution_px_per_frame=expected_downward,
            measured_downward_contribution_px_per_frame=float("nan"),
            downward_contribution_bias_px_per_frame=float("nan"),
            valid_pixel_fraction=0.0,
            frame_pair_count=0,
            failure_reasons=("no_valid_result",),
        )

    measured_speed = float(result.mean_magnitude_px_frame or 0.0)
    measured_vertical = float(result.mean_net_y_px_frame or 0.0)
    measured_downward = float(result.mean_downward_px_frame or 0.0)
    speed_bias = measured_speed - expected_speed
    speed_relative_error = abs(speed_bias) / max(expected_speed, 1e-12)
    vertical_bias = measured_vertical - expected_vertical
    downward_bias = measured_downward - expected_downward
    valid_fraction = float(result.optical_flow_valid_pixel_fraction or 0.0)

    failures: list[str] = []
    if speed_relative_error > thresholds.max_speed_relative_error:
        failures.append("speed_relative_error")
    if abs(vertical_bias) > thresholds.max_vertical_absolute_error_px_per_frame:
        failures.append("signed_vertical_error")
    if abs(downward_bias) > thresholds.max_downward_contribution_absolute_error_px_per_frame:
        failures.append("downward_contribution_error")
    if valid_fraction < thresholds.min_valid_pixel_fraction:
        failures.append("valid_pixel_fraction")

    return OpticalFlowScenarioResult(
        scenario=scenario.name,
        passed=not failures,
        expected_speed_px_per_frame=expected_speed,
        measured_speed_px_per_frame=measured_speed,
        speed_bias_px_per_frame=speed_bias,
        speed_relative_error=speed_relative_error,
        expected_signed_vertical_px_per_frame=expected_vertical,
        measured_signed_vertical_px_per_frame=measured_vertical,
        signed_vertical_bias_px_per_frame=vertical_bias,
        expected_downward_contribution_px_per_frame=expected_downward,
        measured_downward_contribution_px_per_frame=measured_downward,
        downward_contribution_bias_px_per_frame=downward_bias,
        valid_pixel_fraction=valid_fraction,
        frame_pair_count=int(result.frame_pair_count),
        failure_reasons=tuple(failures),
    )


def run_optical_flow_validation(
    *,
    output_dir: str | Path | None = None,
    scenarios: Sequence[SyntheticScenario] = DEFAULT_SCENARIOS,
    thresholds: OpticalFlowValidationThresholds = OpticalFlowValidationThresholds(),
    settings: OpticalFlowSettings | None = None,
    seed: int = 20260629,
) -> dict[str, object]:
    results = [
        validate_optical_flow_scenario(
            scenario,
            thresholds=thresholds,
            settings=settings,
            seed=seed + index,
        )
        for index, scenario in enumerate(scenarios)
    ]
    payload: dict[str, object] = {
        "validation_kind": "optical_flow_synthetic_ground_truth",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": seed,
        "thresholds": asdict(thresholds),
        "settings": asdict(settings or DEFAULT_VALIDATION_SETTINGS),
        "passed": all(result.passed for result in results),
        "scenario_count": len(results),
        "passed_scenario_count": sum(result.passed for result in results),
        "results": [asdict(result) for result in results],
        "limitations": [
            "Synthetic validation uses affine-warped bright bands with known uniform translation.",
            "Engineering thresholds must be approved against the biological effect size of interest.",
        ],
    }

    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "optical_flow_validation_report.json"
        csv_path = directory / "optical_flow_validation_scenarios.csv"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            rows = [asdict(result) for result in results]
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        payload["report_json"] = str(json_path.resolve())
        payload["scenario_csv"] = str(csv_path.resolve())

    return payload
