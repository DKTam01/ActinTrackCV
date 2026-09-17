"""Per-sample scientific calibration: acquisition interval and µm/pixel.

Canonical sample-level model for physical-unit conversion. Container FPS is
not a calibration source. Compute receives these values explicitly; analysis
runs snapshot the values that produced their results.

Legacy samples without an explicit CAL1 block keep PERF1 effective behavior:
60.0 s/frame and 0.265 µm/pixel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from actintrack_app.timing_provenance import (
    STANDARD_ACQUISITION_INTERVAL_S,
    TIMING_SOURCE_PROTOCOL_STANDARD,
    TIMING_SOURCE_RESEARCHER_ENTERED,
    TimingMetadata,
)

# Legacy / protocol defaults. Do not infer from AVI FPS, DPI, or magnification.
# 0.265 matches actintrack_app.motion_index.DEFAULT_MICRONS_PER_PIXEL.
LEGACY_ACQUISITION_INTERVAL_S = float(STANDARD_ACQUISITION_INTERVAL_S)
LEGACY_MICRONS_PER_PIXEL = 0.2650

CALIBRATION_SOURCE_PROTOCOL_DEFAULT = "protocol_default"
CALIBRATION_SOURCE_RESEARCHER_ENTERED = "researcher_entered"
CALIBRATION_SOURCES = frozenset(
    {
        CALIBRATION_SOURCE_PROTOCOL_DEFAULT,
        CALIBRATION_SOURCE_RESEARCHER_ENTERED,
    }
)

ANNOTATION_FIELD_SCIENTIFIC_CALIBRATION = "scientific_calibration"

COMMON_ACQUISITION_INTERVALS_S = (30.0, 60.0)

_INVALID_CALIBRATION_MESSAGE = (
    "Calibration must be a finite number greater than zero."
)


class InvalidScientificCalibration(ValueError):
    """Committed calibration is not a usable scientific value."""


def validate_positive_finite(value: Any, *, field: str = "value") -> float:
    """Return a finite value > 0, or raise InvalidScientificCalibration."""
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidScientificCalibration(_INVALID_CALIBRATION_MESSAGE) from exc
    if not math.isfinite(number) or number <= 0:
        raise InvalidScientificCalibration(_INVALID_CALIBRATION_MESSAGE)
    return number


def parse_calibration_number(text: Any, *, field: str = "value") -> float:
    """Parse researcher-entered text into a validated positive finite float."""
    if text is None:
        raise InvalidScientificCalibration(_INVALID_CALIBRATION_MESSAGE)
    raw = str(text).strip().replace(",", "")
    if not raw:
        raise InvalidScientificCalibration(_INVALID_CALIBRATION_MESSAGE)
    return validate_positive_finite(raw, field=field)


def format_calibration_number(value: float) -> str:
    """Compact display that does not invent trailing zeros."""
    number = float(value)
    if math.isclose(number, round(number), rel_tol=0.0, abs_tol=1e-12):
        return str(int(round(number)))
    text = format(number, ".15g")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _normalize_source(source: Any, *, default: str) -> str:
    text = str(source or "").strip() or default
    if text == "protocol_standard":
        return CALIBRATION_SOURCE_PROTOCOL_DEFAULT
    if text in ("custom", "researcher_entered"):
        return CALIBRATION_SOURCE_RESEARCHER_ENTERED
    if text not in CALIBRATION_SOURCES:
        return default
    return text


@dataclass(frozen=True)
class SampleScientificCalibration:
    """Researcher-controlled per-sample spatial and temporal calibration."""

    acquisition_interval_s: float = LEGACY_ACQUISITION_INTERVAL_S
    microns_per_pixel: float = LEGACY_MICRONS_PER_PIXEL
    acquisition_interval_source: str = CALIBRATION_SOURCE_PROTOCOL_DEFAULT
    spatial_calibration_source: str = CALIBRATION_SOURCE_PROTOCOL_DEFAULT

    def __post_init__(self) -> None:
        interval = validate_positive_finite(
            self.acquisition_interval_s, field="acquisition_interval_s"
        )
        mpp = validate_positive_finite(
            self.microns_per_pixel, field="microns_per_pixel"
        )
        object.__setattr__(self, "acquisition_interval_s", interval)
        object.__setattr__(self, "microns_per_pixel", mpp)
        object.__setattr__(
            self,
            "acquisition_interval_source",
            _normalize_source(
                self.acquisition_interval_source,
                default=CALIBRATION_SOURCE_PROTOCOL_DEFAULT,
            ),
        )
        object.__setattr__(
            self,
            "spatial_calibration_source",
            _normalize_source(
                self.spatial_calibration_source,
                default=CALIBRATION_SOURCE_PROTOCOL_DEFAULT,
            ),
        )

    def with_acquisition_interval(
        self,
        seconds: float,
        *,
        source: str = CALIBRATION_SOURCE_RESEARCHER_ENTERED,
    ) -> SampleScientificCalibration:
        return SampleScientificCalibration(
            acquisition_interval_s=seconds,
            microns_per_pixel=self.microns_per_pixel,
            acquisition_interval_source=source,
            spatial_calibration_source=self.spatial_calibration_source,
        )

    def with_microns_per_pixel(
        self,
        microns: float,
        *,
        source: str = CALIBRATION_SOURCE_RESEARCHER_ENTERED,
    ) -> SampleScientificCalibration:
        return SampleScientificCalibration(
            acquisition_interval_s=self.acquisition_interval_s,
            microns_per_pixel=microns,
            acquisition_interval_source=self.acquisition_interval_source,
            spatial_calibration_source=source,
        )

    def motion_calibration_key(self) -> tuple[float, float]:
        """Identity used to detect motion-metric calibration edits."""
        return (float(self.acquisition_interval_s), float(self.microns_per_pixel))

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquisition_interval_s": float(self.acquisition_interval_s),
            "microns_per_pixel": float(self.microns_per_pixel),
            "acquisition_interval_source": self.acquisition_interval_source,
            "spatial_calibration_source": self.spatial_calibration_source,
        }

    def to_timing_metadata(
        self,
        *,
        observed_video_fps: float | None = None,
        confirmed: bool = True,
    ) -> TimingMetadata:
        """Build compute-time timing from this sample calibration.

        Container FPS is retained as playback provenance only.
        """
        timing_source = (
            TIMING_SOURCE_PROTOCOL_STANDARD
            if self.acquisition_interval_source == CALIBRATION_SOURCE_PROTOCOL_DEFAULT
            else TIMING_SOURCE_RESEARCHER_ENTERED
        )
        return TimingMetadata(
            observed_video_fps=observed_video_fps,
            analysis_seconds_per_frame=float(self.acquisition_interval_s),
            timing_source=timing_source,
            confirmed=confirmed,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SampleScientificCalibration | None:
        if not data or not isinstance(data, dict):
            return None
        if data.get("acquisition_interval_s") is None and data.get("microns_per_pixel") is None:
            return None
        try:
            interval = data.get("acquisition_interval_s", LEGACY_ACQUISITION_INTERVAL_S)
            mpp = data.get("microns_per_pixel", LEGACY_MICRONS_PER_PIXEL)
            return cls(
                acquisition_interval_s=interval,
                microns_per_pixel=mpp,
                acquisition_interval_source=str(
                    data.get("acquisition_interval_source")
                    or CALIBRATION_SOURCE_PROTOCOL_DEFAULT
                ),
                spatial_calibration_source=str(
                    data.get("spatial_calibration_source")
                    or CALIBRATION_SOURCE_PROTOCOL_DEFAULT
                ),
            )
        except (TypeError, ValueError, InvalidScientificCalibration):
            return None

    @classmethod
    def from_compute_inputs(
        cls,
        *,
        seconds_per_frame: float,
        microns_per_pixel: float,
        acquisition_interval_source: str = CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        spatial_calibration_source: str = CALIBRATION_SOURCE_RESEARCHER_ENTERED,
    ) -> SampleScientificCalibration:
        return cls(
            acquisition_interval_s=seconds_per_frame,
            microns_per_pixel=microns_per_pixel,
            acquisition_interval_source=acquisition_interval_source,
            spatial_calibration_source=spatial_calibration_source,
        )


def legacy_default_calibration() -> SampleScientificCalibration:
    """PERF1-compatible defaults for samples without an explicit CAL1 block."""
    return SampleScientificCalibration()


def calibration_from_annotation(
    annotation: dict[str, Any] | None,
) -> SampleScientificCalibration:
    """Load sample calibration, falling back to legacy 60 s / 0.265 µm.

    Pre-CAL1 ``timing`` blocks are not promoted. PERF1 ignored custom/header
    intervals at analysis time; CAL1 preserves that effective 60 s behavior
    until the researcher explicitly sets an interval.
    """
    if not annotation:
        return legacy_default_calibration()
    loaded = SampleScientificCalibration.from_dict(
        annotation.get(ANNOTATION_FIELD_SCIENTIFIC_CALIBRATION)
        if isinstance(annotation.get(ANNOTATION_FIELD_SCIENTIFIC_CALIBRATION), dict)
        else None
    )
    if loaded is not None:
        return loaded
    return legacy_default_calibration()


def calibration_from_result_payload(
    data: dict[str, Any] | None,
) -> SampleScientificCalibration | None:
    """Load the calibration snapshot that produced a persisted analysis run."""
    if not data or not isinstance(data, dict):
        return None
    nested = data.get(ANNOTATION_FIELD_SCIENTIFIC_CALIBRATION)
    loaded = SampleScientificCalibration.from_dict(
        nested if isinstance(nested, dict) else None
    )
    if loaded is not None:
        return loaded
    params = data.get("parameters") or data.get("settings") or {}
    if not isinstance(params, dict):
        return None
    if params.get("seconds_per_frame") is None and params.get("microns_per_pixel") is None:
        return None
    try:
        return SampleScientificCalibration.from_compute_inputs(
            seconds_per_frame=float(
                params.get("seconds_per_frame", LEGACY_ACQUISITION_INTERVAL_S)
            ),
            microns_per_pixel=float(
                params.get("microns_per_pixel", LEGACY_MICRONS_PER_PIXEL)
            ),
            acquisition_interval_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
            spatial_calibration_source=CALIBRATION_SOURCE_RESEARCHER_ENTERED,
        )
    except (TypeError, ValueError, InvalidScientificCalibration):
        return None


def merge_calibration_into_annotation(
    annotation: dict[str, Any],
    calibration: SampleScientificCalibration,
    *,
    observed_video_fps: float | None = None,
) -> dict[str, Any]:
    """Write the canonical calibration block; keep ``timing`` in sync."""
    out = dict(annotation)
    out[ANNOTATION_FIELD_SCIENTIFIC_CALIBRATION] = calibration.to_dict()
    existing_timing = out.get("timing")
    fps = observed_video_fps
    if fps is None and isinstance(existing_timing, dict):
        fps = existing_timing.get("observed_video_fps")
    out["timing"] = calibration.to_timing_metadata(
        observed_video_fps=fps,
        confirmed=True,
    ).to_dict()
    return out


def calibration_state_key_from_annotation(
    annotation: dict[str, Any] | None,
) -> tuple[float, float]:
    """Motion-calibration identity for freshness comparison."""
    return calibration_from_annotation(annotation).motion_calibration_key()
