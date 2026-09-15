"""Production structural F-actin orientation relative to a nucleus reference."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

from actintrack_app.orientation_research import (
    OrientationResearchSettings,
    angle_relative_to_nucleus_deg,
    structure_tensor_orientations,
)

ALGORITHM_NAME = "structure_tensor_nucleus_relative_orientation"
ALGORITHM_VERSION = 1
RESULT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StructuralOrientationSettings:
    threshold_percentile: float = 70.0
    tensor_window_size_px: int = 15
    sample_spacing_px: int = 6
    minimum_coherence: float = 0.20
    minimum_measurements: int = 3

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold_percentile <= 100.0:
            raise ValueError("threshold_percentile must be between 0 and 100.")
        if self.tensor_window_size_px < 5 or self.tensor_window_size_px % 2 == 0:
            raise ValueError("tensor_window_size_px must be odd and >= 5.")
        if self.sample_spacing_px < 1:
            raise ValueError("sample_spacing_px must be positive.")
        if not 0.0 <= self.minimum_coherence <= 1.0:
            raise ValueError("minimum_coherence must be between 0 and 1.")
        if self.minimum_measurements < 1:
            raise ValueError("minimum_measurements must be positive.")


@dataclass(frozen=True)
class FilamentOrientationMeasurement:
    x_px: float
    y_px: float
    angle_relative_nucleus_deg: float
    local_orientation_deg: float
    coherence: float


@dataclass
class StructuralOrientationResult:
    has_valid_result: bool = False
    failure_reason: str = ""
    sample_id: str = ""
    reference_frame_index: int = 0
    nucleus_reference_xy_px: tuple[float, float] | None = None
    settings: StructuralOrientationSettings = field(
        default_factory=StructuralOrientationSettings
    )
    measurements: list[FilamentOrientationMeasurement] = field(default_factory=list)
    mean_angle_relative_nucleus_deg: float | None = None
    median_angle_relative_nucleus_deg: float | None = None
    std_angle_relative_nucleus_deg: float | None = None
    mean_coherence: float | None = None
    valid_pixel_count: int = 0
    foreground_pixel_count: int = 0
    analysis_timestamp_utc: str = ""
    analysis_run_id: str = ""

    def summary_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "algorithm": ALGORITHM_NAME,
            "algorithm_version": ALGORITHM_VERSION,
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "has_valid_result": self.has_valid_result,
            "failure_reason": self.failure_reason,
            "sample_id": self.sample_id,
            "reference_frame_index": self.reference_frame_index,
            "settings": asdict(self.settings),
            "measurement_count": len(self.measurements),
            "mean_angle_relative_nucleus_deg": self.mean_angle_relative_nucleus_deg,
            "median_angle_relative_nucleus_deg": self.median_angle_relative_nucleus_deg,
            "std_angle_relative_nucleus_deg": self.std_angle_relative_nucleus_deg,
            "mean_coherence": self.mean_coherence,
            "valid_pixel_count": self.valid_pixel_count,
            "foreground_pixel_count": self.foreground_pixel_count,
            "analysis_timestamp_utc": self.analysis_timestamp_utc,
            "analysis_run_id": self.analysis_run_id or self.analysis_timestamp_utc,
            "angle_definition": {
                "formula": "acos(abs(filament_unit dot radial_unit))",
                "range_degrees": [0.0, 90.0],
                "zero_degrees": "radial_relative_to_nucleus",
                "ninety_degrees": "tangential_relative_to_nucleus",
                "traversal_direction_invariant": True,
                "not_motion_or_trajectory_angle": True,
            },
            "coordinate_space": "crop_local_pixels",
            "measurements": [asdict(item) for item in self.measurements],
        }
        if self.nucleus_reference_xy_px is not None:
            payload["nucleus_reference"] = {
                "x_px": float(self.nucleus_reference_xy_px[0]),
                "y_px": float(self.nucleus_reference_xy_px[1]),
                "coordinate_space": "crop_local_pixels",
            }
        return payload


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_structural_orientation(
    frame: np.ndarray,
    *,
    nucleus_xy_px: tuple[float, float] | None,
    valid_mask: np.ndarray | None = None,
    settings: StructuralOrientationSettings | None = None,
    sample_id: str = "",
    reference_frame_index: int = 0,
) -> StructuralOrientationResult:
    """Measure local axial cable angles relative to a confirmed nucleus."""
    settings = settings or StructuralOrientationSettings()
    if nucleus_xy_px is None:
        return StructuralOrientationResult(
            failure_reason="Missing researcher-confirmed NucleusReference.",
            sample_id=sample_id,
            reference_frame_index=int(reference_frame_index),
            settings=settings,
            analysis_timestamp_utc=_timestamp(),
        )

    research_settings = OrientationResearchSettings(
        threshold_percentile=settings.threshold_percentile,
        window_size_px=settings.tensor_window_size_px,
        sample_spacing_px=settings.sample_spacing_px,
        minimum_confidence=settings.minimum_coherence,
    )
    local_result = structure_tensor_orientations(
        frame,
        valid_mask=valid_mask,
        settings=research_settings,
    )
    measurements: list[FilamentOrientationMeasurement] = []
    for estimate in local_result.estimates:
        try:
            relative = angle_relative_to_nucleus_deg(
                estimate.local_orientation_deg,
                estimate.x_px,
                estimate.y_px,
                nucleus_xy_px,
            )
        except ValueError:
            continue
        measurements.append(
            FilamentOrientationMeasurement(
                x_px=estimate.x_px,
                y_px=estimate.y_px,
                angle_relative_nucleus_deg=relative,
                local_orientation_deg=estimate.local_orientation_deg,
                coherence=estimate.confidence,
            )
        )

    if len(measurements) < settings.minimum_measurements:
        return StructuralOrientationResult(
            failure_reason=(
                f"Only {len(measurements)} valid local orientation measurement(s); "
                f"minimum is {settings.minimum_measurements}."
            ),
            sample_id=sample_id,
            reference_frame_index=int(reference_frame_index),
            nucleus_reference_xy_px=tuple(map(float, nucleus_xy_px)),
            settings=settings,
            measurements=measurements,
            valid_pixel_count=local_result.valid_pixel_count,
            foreground_pixel_count=local_result.foreground_pixel_count,
            analysis_timestamp_utc=_timestamp(),
        )

    angles = np.array(
        [item.angle_relative_nucleus_deg for item in measurements],
        dtype=np.float64,
    )
    coherence = np.array(
        [item.coherence for item in measurements],
        dtype=np.float64,
    )
    return StructuralOrientationResult(
        has_valid_result=True,
        sample_id=sample_id,
        reference_frame_index=int(reference_frame_index),
        nucleus_reference_xy_px=tuple(map(float, nucleus_xy_px)),
        settings=settings,
        measurements=measurements,
        mean_angle_relative_nucleus_deg=float(np.mean(angles)),
        median_angle_relative_nucleus_deg=float(np.median(angles)),
        std_angle_relative_nucleus_deg=float(np.std(angles)),
        mean_coherence=float(np.mean(coherence)),
        valid_pixel_count=local_result.valid_pixel_count,
        foreground_pixel_count=local_result.foreground_pixel_count,
        analysis_timestamp_utc=_timestamp(),
    )


def result_from_dict(data: dict[str, Any]) -> StructuralOrientationResult:
    settings_data = data.get("settings")
    settings = (
        StructuralOrientationSettings(**settings_data)
        if isinstance(settings_data, dict)
        else StructuralOrientationSettings()
    )
    nucleus_data = data.get("nucleus_reference")
    nucleus = None
    if isinstance(nucleus_data, dict):
        nucleus = (float(nucleus_data["x_px"]), float(nucleus_data["y_px"]))
    measurements = [
        FilamentOrientationMeasurement(**row)
        for row in data.get("measurements", [])
        if isinstance(row, dict)
    ]
    return StructuralOrientationResult(
        has_valid_result=bool(data.get("has_valid_result")),
        failure_reason=str(data.get("failure_reason", "")),
        sample_id=str(data.get("sample_id", "")),
        reference_frame_index=int(data.get("reference_frame_index", 0) or 0),
        nucleus_reference_xy_px=nucleus,
        settings=settings,
        measurements=measurements,
        mean_angle_relative_nucleus_deg=data.get(
            "mean_angle_relative_nucleus_deg"
        ),
        median_angle_relative_nucleus_deg=data.get(
            "median_angle_relative_nucleus_deg"
        ),
        std_angle_relative_nucleus_deg=data.get("std_angle_relative_nucleus_deg"),
        mean_coherence=data.get("mean_coherence"),
        valid_pixel_count=int(data.get("valid_pixel_count", 0) or 0),
        foreground_pixel_count=int(data.get("foreground_pixel_count", 0) or 0),
        analysis_timestamp_utc=str(data.get("analysis_timestamp_utc", "")),
    )


def render_structural_orientation_overlay(
    frame: np.ndarray,
    result: StructuralOrientationResult,
    *,
    maximum_glyphs: int = 80,
) -> np.ndarray:
    """Render subsampled QC glyphs from persisted measurements only.

    Tangent ticks use ``local_orientation_deg``. Color encodes the persisted
    0–90° nucleus-relative structural angle (cyan radial → amber tangential).
    This does not recompute structure-tensor orientation.
    """
    if frame.ndim == 2:
        output = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    else:
        output = frame.copy()
    if result.nucleus_reference_xy_px is not None:
        nx, ny = (int(round(value)) for value in result.nucleus_reference_xy_px)
        cv2.drawMarker(
            output,
            (nx, ny),
            (255, 0, 255),
            cv2.MARKER_CROSS,
            14,
            2,
            cv2.LINE_AA,
        )
    if not result.measurements:
        return output

    stride = max(1, int(np.ceil(len(result.measurements) / max(maximum_glyphs, 1))))
    sampled = result.measurements[::stride]
    for index, measurement in enumerate(sampled):
        theta = np.deg2rad(measurement.local_orientation_deg)
        dx, dy = 7.0 * np.cos(theta), 7.0 * np.sin(theta)
        center = (int(round(measurement.x_px)), int(round(measurement.y_px)))
        p0 = (int(round(center[0] - dx)), int(round(center[1] - dy)))
        p1 = (int(round(center[0] + dx)), int(round(center[1] + dy)))
        color = _nucleus_relative_angle_bgr(measurement.angle_relative_nucleus_deg)
        cv2.line(output, p0, p1, color, 1, cv2.LINE_AA)
        if (
            index % 5 == 0
            and result.nucleus_reference_xy_px is not None
        ):
            nucleus = tuple(
                int(round(value)) for value in result.nucleus_reference_xy_px
            )
            cv2.line(output, nucleus, center, (120, 80, 120), 1, cv2.LINE_AA)
    return output


def _nucleus_relative_angle_bgr(angle_deg: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, float(angle_deg) / 90.0))
    # BGR: cyan (radial) -> amber (tangential).
    blue = int(round(255 * (1.0 - t)))
    green = int(round(210 - 40 * t))
    red = int(round(40 + 215 * t))
    return (blue, green, red)
