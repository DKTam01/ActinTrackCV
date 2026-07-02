"""Shared Qt style tokens and helpers for ActinTrackCV desktop UI."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout

# Panel layout
PANEL_MARGIN = 6
PANEL_INNER_MARGIN = 8
PANEL_SECTION_SPACING = 8
CONTROL_ROW_SPACING = 4
FORM_SECTION_SPACING = 10
FORM_GROUP_TOP_MARGIN = 12

# Typography colors
COLOR_HINT = "#888888"
COLOR_HINT_MUTED = "#aaaaaa"
COLOR_SMALL_LABEL = "#9da5b4"
COLOR_DIALOG_DESCRIPTION = "#666666"
COLOR_STATUS_SAVED = "#9ad4c8"
COLOR_STATUS_WARNING = "#ccaa66"

# Font sizes (px)
FONT_SIZE_HINT = 11
FONT_SIZE_SMALL = 10
FONT_SIZE_STATUS = 12
FONT_SIZE_BODY = 12

# Stylesheets
STYLE_HINT_LABEL = f"color: {COLOR_HINT}; font-size: {FONT_SIZE_HINT}px;"
STYLE_HINT_LABEL_ITALIC = (
    f"color: {COLOR_HINT}; font-size: {FONT_SIZE_HINT}px; font-style: italic;"
)
STYLE_SMALL_LABEL = (
    f"color: {COLOR_SMALL_LABEL}; font-size: {FONT_SIZE_SMALL}px; padding: 2px 0 6px 0;"
)
STYLE_MUTED_LABEL = f"color: {COLOR_HINT_MUTED}; font-size: {FONT_SIZE_HINT}px;"
STYLE_BODY_LABEL = f"font-size: {FONT_SIZE_BODY}px;"
STYLE_DIALOG_DESCRIPTION = (
    f"color: {COLOR_DIALOG_DESCRIPTION}; font-size: {FONT_SIZE_HINT}px;"
)
STYLE_CHECKBOX_COMPACT = f"font-size: {FONT_SIZE_HINT}px;"

METRIC_STATUS_PANEL_OBJECT_NAME = "metricStatusPanel"
STYLE_METRIC_STATUS_PANEL = (
    f"QFrame#{METRIC_STATUS_PANEL_OBJECT_NAME} {{"
    "  background-color: palette(base);"
    "  border: 1px solid palette(mid);"
    "  border-radius: 4px;"
    "}"
)
METRIC_STATUS_INNER_SPACING = 6
METRIC_STATUS_LABEL_SPACING = 2

PLAYBACK_FRAME_LABEL_MIN_WIDTH = 72
PLAYBACK_SLIDER_MIN_WIDTH = 120
PLAYBACK_SPEED_COMBO_MIN_WIDTH = 72

ORIENT_PANEL_BUTTON_MIN_HEIGHT = 28
ROI_HINT_STATUS_SPACING = 2

TRACKING_RESULT_GROUP_PREFIX = "Tracking / Motion Index Results"


def tracking_result_group_title(sample_display: str | None = None) -> str:
    """Consistent group-box title for the Sample tab tracking/OF results panel."""
    if not sample_display:
        return f"{TRACKING_RESULT_GROUP_PREFIX}: No sample selected"
    return f"{TRACKING_RESULT_GROUP_PREFIX}: {sample_display}"


def apply_hint_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_HINT_LABEL)


def apply_hint_italic_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_HINT_LABEL_ITALIC)


def apply_small_secondary_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_SMALL_LABEL)


def apply_muted_hint_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_MUTED_LABEL)


def apply_body_label_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_BODY_LABEL)


def apply_dialog_description_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_DIALOG_DESCRIPTION)


def apply_status_style(label: QLabel, *, saved: bool = True) -> None:
    color = COLOR_STATUS_SAVED if saved else COLOR_STATUS_WARNING
    label.setStyleSheet(
        f"color: {color}; font-size: {FONT_SIZE_STATUS}px; padding: 2px 0;"
    )


def apply_panel_margins(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(
        PANEL_MARGIN,
        PANEL_MARGIN,
        PANEL_MARGIN,
        PANEL_MARGIN,
    )


def apply_panel_inner_margins(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
    )


def apply_form_group_margins(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(
        PANEL_INNER_MARGIN,
        FORM_GROUP_TOP_MARGIN,
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
    )


def configure_orient_panel_action_button(button: QPushButton) -> None:
    """Equal-width action buttons in the Orient and ROI panel."""
    button.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    button.setMinimumHeight(ORIENT_PANEL_BUTTON_MIN_HEIGHT)
