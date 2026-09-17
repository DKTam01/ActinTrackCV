"""Explicit video timing provenance and analysis interval.

Biological acquisition timing is distinct from container playback FPS.

Lab protocol (PERF1): consecutive scientific acquisition frames for VIDEO
movement analysis are 60 seconds apart. Container CAP_PROP_FPS describes
encoded playback only and must not drive calibrated µm/s.

All µm/s calculations consume one authoritative analysis_seconds_per_frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2

# Centralized scientific acquisition interval for VIDEO movement analysis.
STANDARD_ACQUISITION_INTERVAL_S = 60.0

# Compatibility alias: historical "lab default" name now equals protocol interval.
LAB_DEFAULT_SECONDS_PER_FRAME = float(STANDARD_ACQUISITION_INTERVAL_S)
HISTORICAL_DEFAULT_SECONDS_PER_FRAME = 0.2
# Pre-PERF1 code default (30 s/frame) kept for provenance reading only.
HISTORICAL_CODE_DEFAULT_SECONDS_PER_FRAME = 30.0

ANNOTATION_FIELD_TIMING = "timing"

TIMING_SOURCE_PROTOCOL_STANDARD = "protocol_standard"
TIMING_SOURCE_VIDEO_HEADER = "video_header"
TIMING_SOURCE_LAB_DEFAULT = "lab_default"
TIMING_SOURCE_CUSTOM = "custom"
TIMING_SOURCE_LEGACY_DEFAULT = "legacy_default"

TIMING_SOURCES = frozenset(
    {
        TIMING_SOURCE_PROTOCOL_STANDARD,
        TIMING_SOURCE_VIDEO_HEADER,
        TIMING_SOURCE_LAB_DEFAULT,
        TIMING_SOURCE_CUSTOM,
        TIMING_SOURCE_LEGACY_DEFAULT,
    }
)

# Product policy: Workbench VIDEO analysis uses the protocol acquisition interval.
# Container FPS remains informational provenance only.
ANALYSIS_USES_PROTOCOL_STANDARD = True
# Deprecated alias retained so older tests/docs can detect the policy flip.
ANALYSIS_USES_VIDEO_HEADER_ONLY = False

MISSING_VIDEO_TIMING_MESSAGE = (
    "Valid acquisition timing is not available. Calibrated µm/s cannot run."
)

# Reject absurd container FPS values that cannot be playback cadence.
_MIN_PLAUSIBLE_FPS = 0.01
_MAX_PLAUSIBLE_FPS = 240.0


def validate_observed_fps(fps: Any) -> float | None:
    """Return a finite plausible playback FPS, else None (do not invent a value)."""
    try:
        value = float(fps)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    if value <= 0:
        return None
    if value < _MIN_PLAUSIBLE_FPS or value > _MAX_PLAUSIBLE_FPS:
        return None
    return value


def frame_interval_from_fps(fps: float | None) -> float | None:
    """Convert validated playback FPS to container seconds/frame, or None.

    This is playback metadata only — not biological acquisition interval.
    """
    checked = validate_observed_fps(fps)
    if checked is None:
        return None
    return 1.0 / checked


def probe_video_playback_fps(path: Path | str) -> float | None:
    """Read OpenCV CAP_PROP_FPS as observed playback metadata only."""
    video_path = Path(path)
    if not video_path.is_file():
        return None
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return None
        return validate_observed_fps(cap.get(cv2.CAP_PROP_FPS))
    finally:
        cap.release()


def implied_px_per_frame(
    speed_um_per_s: float,
    *,
    seconds_per_frame: float,
    microns_per_pixel: float,
) -> float:
    """Invert calibrated speed to timing-invariant px/frame displacement."""
    if seconds_per_frame <= 0 or microns_per_pixel <= 0:
        raise ValueError("seconds_per_frame and microns_per_pixel must be positive.")
    return float(speed_um_per_s) * float(seconds_per_frame) / float(microns_per_pixel)


def calibrated_um_per_s(
    displacement_px_per_frame: float,
    *,
    seconds_per_frame: float,
    microns_per_pixel: float,
) -> float:
    """Standard conversion used by sparse tracking and optical flow."""
    if seconds_per_frame <= 0 or microns_per_pixel <= 0:
        raise ValueError("seconds_per_frame and microns_per_pixel must be positive.")
    return (
        float(displacement_px_per_frame)
        * float(microns_per_pixel)
        / float(seconds_per_frame)
    )


@dataclass(frozen=True)
class TimingMetadata:
    """Biological analysis interval vs optional container playback metadata.

    ``observed_video_fps`` / ``observed_frame_interval_s`` are container
    playback provenance only. ``analysis_seconds_per_frame`` is the scientific
    dt used for calibrated velocity.
    """

    observed_video_fps: float | None = None
    observed_frame_interval_s: float | None = None
    analysis_seconds_per_frame: float = STANDARD_ACQUISITION_INTERVAL_S
    timing_source: str = TIMING_SOURCE_PROTOCOL_STANDARD
    confirmed: bool = True

    def __post_init__(self) -> None:
        fps = validate_observed_fps(self.observed_video_fps)
        interval = self.observed_frame_interval_s
        if fps is not None and interval is None:
            interval = frame_interval_from_fps(fps)
        elif fps is None:
            # Keep an explicitly provided positive playback interval if present.
            if interval is not None:
                try:
                    interval = float(interval)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "observed_frame_interval_s must be numeric."
                    ) from exc
                if not math.isfinite(interval) or interval <= 0:
                    raise ValueError("observed_frame_interval_s must be positive.")
            else:
                interval = None
        elif interval is not None:
            try:
                interval = float(interval)
            except (TypeError, ValueError) as exc:
                raise ValueError("observed_frame_interval_s must be numeric.") from exc
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError("observed_frame_interval_s must be positive.")

        spf = float(self.analysis_seconds_per_frame)
        if not math.isfinite(spf) or spf <= 0:
            raise ValueError("analysis_seconds_per_frame must be positive.")

        source = str(self.timing_source or TIMING_SOURCE_PROTOCOL_STANDARD)
        if source not in TIMING_SOURCES:
            raise ValueError(f"Unknown timing_source: {source}")

        object.__setattr__(self, "observed_video_fps", fps)
        object.__setattr__(self, "observed_frame_interval_s", interval)
        object.__setattr__(self, "analysis_seconds_per_frame", spf)
        object.__setattr__(self, "timing_source", source)
        object.__setattr__(self, "confirmed", bool(self.confirmed))

    @property
    def container_playback_interval_s(self) -> float | None:
        """Alias clarifying that observed_frame_interval_s is playback-only."""
        return self.observed_frame_interval_s

    @property
    def has_valid_video_timing(self) -> bool:
        """True when observed container FPS defines a usable playback interval.

        Informational only — not required for calibrated analysis under the
        protocol-standard policy.
        """
        return (
            self.observed_video_fps is not None
            and self.observed_frame_interval_s is not None
            and float(self.observed_frame_interval_s) > 0
        )

    def _video_header_interval_is_authoritative(self) -> bool:
        if not self.has_valid_video_timing:
            return False
        if self.timing_source != TIMING_SOURCE_VIDEO_HEADER:
            return False
        return math.isclose(
            float(self.analysis_seconds_per_frame),
            float(self.observed_frame_interval_s),
            rel_tol=0.0,
            abs_tol=1e-9,
        )

    def _protocol_standard_is_authoritative(self) -> bool:
        if self.timing_source != TIMING_SOURCE_PROTOCOL_STANDARD:
            return False
        return math.isclose(
            float(self.analysis_seconds_per_frame),
            float(STANDARD_ACQUISITION_INTERVAL_S),
            rel_tol=0.0,
            abs_tol=1e-9,
        )

    @property
    def is_calibrated_analysis_ready(self) -> bool:
        """Whether this metadata may drive calibrated µm/s.

        PERF1: protocol-standard acquisition interval is always ready for VIDEO
        analysis when present. Container FPS is not required.
        """
        if ANALYSIS_USES_PROTOCOL_STANDARD:
            return (
                self._protocol_standard_is_authoritative()
                and float(self.analysis_seconds_per_frame) > 0
            )
        if ANALYSIS_USES_VIDEO_HEADER_ONLY:
            return self._video_header_interval_is_authoritative()
        return bool(self.confirmed) and float(self.analysis_seconds_per_frame) > 0

    def display_label(self) -> str:
        """Researcher-facing acquisition timing line."""
        if self.timing_source == TIMING_SOURCE_PROTOCOL_STANDARD or (
            ANALYSIS_USES_PROTOCOL_STANDARD and self.is_calibrated_analysis_ready
        ):
            spf = float(self.analysis_seconds_per_frame)
            if math.isclose(spf, 60.0, rel_tol=0.0, abs_tol=1e-9):
                return "60 s between frames"
            return f"{spf:.4g} s between frames"
        if self.timing_source == TIMING_SOURCE_VIDEO_HEADER and self.has_valid_video_timing:
            fps = float(self.observed_video_fps)
            interval = float(self.observed_frame_interval_s)
            return f"Playback {fps:.2f} FPS · {interval:.4f} s/frame (legacy)"
        if float(self.analysis_seconds_per_frame) > 0:
            return f"{float(self.analysis_seconds_per_frame):.4g} s between frames"
        return "Acquisition timing unavailable"

    def playback_display_label(self) -> str | None:
        """Optional container playback label; never the scientific dt."""
        if not self.has_valid_video_timing:
            return None
        fps = float(self.observed_video_fps)
        interval = float(self.observed_frame_interval_s)
        return f"Container playback: {fps:.2f} FPS · {interval:.4f} s/frame"

    @classmethod
    def from_protocol_standard(
        cls,
        *,
        observed_video_fps: float | None = None,
        confirmed: bool = True,
    ) -> TimingMetadata:
        """Build protocol-standard biological timing (60 s/frame).

        Container FPS is retained as playback provenance when available.
        Missing/invalid FPS does not block calibrated analysis.
        """
        checked = validate_observed_fps(observed_video_fps)
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=frame_interval_from_fps(checked),
            analysis_seconds_per_frame=float(STANDARD_ACQUISITION_INTERVAL_S),
            timing_source=TIMING_SOURCE_PROTOCOL_STANDARD,
            confirmed=confirmed,
        )

    @classmethod
    def from_video_header(
        cls,
        fps: float | None,
        *,
        confirmed: bool = True,
    ) -> TimingMetadata | None:
        """Build legacy video-header timing, or None when FPS is missing/invalid.

        Retained for reading historical provenance. Live Workbench analysis
        uses :meth:`from_protocol_standard` instead.
        """
        checked = validate_observed_fps(fps)
        interval = frame_interval_from_fps(checked)
        if interval is None:
            return None
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=interval,
            analysis_seconds_per_frame=float(interval),
            timing_source=TIMING_SOURCE_VIDEO_HEADER,
            confirmed=confirmed,
        )

    @classmethod
    def unresolved(
        cls,
        *,
        observed_video_fps: float | None = None,
    ) -> TimingMetadata:
        """Observed FPS missing/invalid under legacy video-header policy."""
        checked = validate_observed_fps(observed_video_fps)
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=frame_interval_from_fps(checked),
            analysis_seconds_per_frame=STANDARD_ACQUISITION_INTERVAL_S,
            timing_source=TIMING_SOURCE_VIDEO_HEADER,
            confirmed=False,
        )

    @classmethod
    def from_observed_fps(
        cls,
        fps: float | None,
        *,
        prefer_video_header: bool = False,
        confirmed: bool = True,
    ) -> TimingMetadata:
        """Build timing from optional observed FPS.

        Default (PERF1): protocol-standard acquisition interval. Set
        ``prefer_video_header=True`` only when reconstructing legacy behavior.
        """
        checked = validate_observed_fps(fps)
        interval = frame_interval_from_fps(checked)
        if prefer_video_header and interval is not None:
            return cls(
                observed_video_fps=checked,
                observed_frame_interval_s=interval,
                analysis_seconds_per_frame=float(interval),
                timing_source=TIMING_SOURCE_VIDEO_HEADER,
                confirmed=confirmed,
            )
        return cls.from_protocol_standard(
            observed_video_fps=checked,
            confirmed=confirmed,
        )

    @classmethod
    def lab_default(
        cls,
        *,
        observed_video_fps: float | None = None,
        confirmed: bool = False,
    ) -> TimingMetadata:
        checked = validate_observed_fps(observed_video_fps)
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=frame_interval_from_fps(checked),
            analysis_seconds_per_frame=LAB_DEFAULT_SECONDS_PER_FRAME,
            timing_source=TIMING_SOURCE_LAB_DEFAULT,
            confirmed=confirmed,
        )

    @classmethod
    def custom(
        cls,
        seconds_per_frame: float,
        *,
        observed_video_fps: float | None = None,
        confirmed: bool = False,
    ) -> TimingMetadata:
        checked = validate_observed_fps(observed_video_fps)
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=frame_interval_from_fps(checked),
            analysis_seconds_per_frame=float(seconds_per_frame),
            timing_source=TIMING_SOURCE_CUSTOM,
            confirmed=confirmed,
        )

    @classmethod
    def legacy(
        cls,
        seconds_per_frame: float,
        *,
        observed_video_fps: float | None = None,
        confirmed: bool = False,
    ) -> TimingMetadata:
        checked = validate_observed_fps(observed_video_fps)
        return cls(
            observed_video_fps=checked,
            observed_frame_interval_s=frame_interval_from_fps(checked),
            analysis_seconds_per_frame=float(seconds_per_frame),
            timing_source=TIMING_SOURCE_LEGACY_DEFAULT,
            confirmed=confirmed,
        )

    def with_source_choice(
        self,
        timing_source: str,
        *,
        custom_seconds: float | None = None,
        confirmed: bool | None = None,
    ) -> TimingMetadata:
        """Return a copy after researcher selects a timing option (not yet confirmed)."""
        source = str(timing_source)
        if source == TIMING_SOURCE_PROTOCOL_STANDARD:
            spf = float(STANDARD_ACQUISITION_INTERVAL_S)
        elif source == TIMING_SOURCE_VIDEO_HEADER:
            if self.observed_frame_interval_s is None:
                raise ValueError("Video timing is unavailable for this file.")
            spf = float(self.observed_frame_interval_s)
        elif source == TIMING_SOURCE_LAB_DEFAULT:
            spf = LAB_DEFAULT_SECONDS_PER_FRAME
        elif source == TIMING_SOURCE_CUSTOM:
            if custom_seconds is None:
                raise ValueError("Custom timing requires seconds_per_frame.")
            spf = float(custom_seconds)
        elif source == TIMING_SOURCE_LEGACY_DEFAULT:
            spf = float(
                custom_seconds
                if custom_seconds is not None
                else self.analysis_seconds_per_frame
            )
        else:
            raise ValueError(f"Unknown timing_source: {source}")
        return TimingMetadata(
            observed_video_fps=self.observed_video_fps,
            observed_frame_interval_s=self.observed_frame_interval_s,
            analysis_seconds_per_frame=spf,
            timing_source=source,
            confirmed=self.confirmed if confirmed is None else bool(confirmed),
        )

    def confirm(self) -> TimingMetadata:
        return TimingMetadata(
            observed_video_fps=self.observed_video_fps,
            observed_frame_interval_s=self.observed_frame_interval_s,
            analysis_seconds_per_frame=self.analysis_seconds_per_frame,
            timing_source=self.timing_source,
            confirmed=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_video_fps": self.observed_video_fps,
            # Playback-only container interval (1/FPS). Not biological dt.
            "observed_frame_interval_s": self.observed_frame_interval_s,
            "container_playback_interval_s": self.observed_frame_interval_s,
            "analysis_seconds_per_frame": self.analysis_seconds_per_frame,
            "timing_source": self.timing_source,
            "timing_confirmed": self.confirmed,
            # Compatibility aliases used in result payloads / older wording.
            "seconds_per_frame": self.analysis_seconds_per_frame,
            "confirmed": self.confirmed,
        }

    def result_provenance_dict(self) -> dict[str, Any]:
        """Compact block embedded in tracking/OF result JSON."""
        return {
            "analysis_seconds_per_frame": self.analysis_seconds_per_frame,
            "timing_source": self.timing_source,
            "timing_confirmed": self.confirmed,
            "observed_video_fps": self.observed_video_fps,
            "observed_frame_interval_s": self.observed_frame_interval_s,
            "container_playback_interval_s": self.observed_frame_interval_s,
        }


def timing_from_dict(data: dict[str, Any] | None) -> TimingMetadata | None:
    if not data or not isinstance(data, dict):
        return None
    try:
        confirmed = data.get("timing_confirmed", data.get("confirmed", False))
        spf = data.get("analysis_seconds_per_frame", data.get("seconds_per_frame"))
        if spf is None:
            return None
        source = str(data.get("timing_source") or TIMING_SOURCE_PROTOCOL_STANDARD)
        if source not in TIMING_SOURCES:
            source = TIMING_SOURCE_CUSTOM
        playback_interval = data.get(
            "observed_frame_interval_s",
            data.get("container_playback_interval_s"),
        )
        return TimingMetadata(
            observed_video_fps=data.get("observed_video_fps"),
            observed_frame_interval_s=playback_interval,
            analysis_seconds_per_frame=float(spf),
            timing_source=source,
            confirmed=bool(confirmed),
        )
    except (TypeError, ValueError):
        return None


def timing_from_annotation(ann: dict[str, Any] | None) -> TimingMetadata | None:
    if not ann:
        return None
    return timing_from_dict(ann.get(ANNOTATION_FIELD_TIMING))


def timing_from_result_payload(data: dict[str, Any] | None) -> TimingMetadata | None:
    """Load timing from draft/result JSON (nested or flat legacy)."""
    if not data:
        return None
    nested = data.get("timing_provenance") or data.get("timing")
    loaded = timing_from_dict(nested if isinstance(nested, dict) else None)
    if loaded is not None:
        return loaded
    params = data.get("parameters") or data.get("settings") or {}
    if isinstance(params, dict) and params.get("seconds_per_frame") is not None:
        try:
            return TimingMetadata.legacy(
                float(params["seconds_per_frame"]),
                observed_video_fps=None,
                confirmed=False,
            )
        except (TypeError, ValueError):
            return None
    return None


def require_calibrated_timing(timing: TimingMetadata | None) -> TimingMetadata:
    """Raise if timing cannot drive calibrated µm/s under current policy."""
    if timing is None or not timing.is_calibrated_analysis_ready:
        raise ValueError(MISSING_VIDEO_TIMING_MESSAGE)
    return timing


def merge_timing_into_annotation(
    annotation: dict[str, Any],
    timing: TimingMetadata | None,
) -> dict[str, Any]:
    out = dict(annotation)
    if timing is None:
        out.pop(ANNOTATION_FIELD_TIMING, None)
    else:
        out[ANNOTATION_FIELD_TIMING] = timing.to_dict()
    return out
