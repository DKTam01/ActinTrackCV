"""Shared Qt style tokens and helpers for ActinTrackCV desktop UI."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Panel layout
PANEL_MARGIN = 6
PANEL_INNER_MARGIN = 8
PANEL_SECTION_SPACING = 8
CONTROL_ROW_SPACING = 4
FORM_SECTION_SPACING = 10
FORM_GROUP_TOP_MARGIN = 12
SIDE_PANEL_INNER_MARGIN = 4
SIDE_PANEL_FORM_SPACING = 4
SIDE_PANEL_GROUP_TOP_MARGIN = 8
SIDE_PANEL_LABEL_CONTROL_GAP = 1
SIDE_PANEL_SECTION_SPACING = 8
SIDE_PANEL_FIELD_GROUP_SPACING = 4
PREVIEW_CONTROLS_DIVIDER_TOP_SPACING = 6

# Workspace surfaces
EXPLORER_PANEL_OBJECT_NAME = "explorerPanel"
EXPLORER_TREE_HOST_OBJECT_NAME = "explorerTreeHost"
EXPLORER_ROOT_ROW_OBJECT_NAME = "explorerRootRow"
EXPLORER_ROOT_PATH_OBJECT_NAME = "explorerRootPath"
ROI_PREVIEW_PANEL_OBJECT_NAME = "roiPreviewPanel"
WORKSPACE_PREVIEW_PANEL_OBJECT_NAME = "workspacePreviewPanel"
WORKBENCH_ACTION_BUTTON_OBJECT_NAME = "workbenchActionButton"
WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME = "workbenchPlaybackButton"
WORKBENCH_SETTINGS_COMBO_OBJECT_NAME = "workbenchSettingsCombo"
WORKBENCH_CONTROLS_PANEL_OBJECT_NAME = "workbenchControlsPanel"
WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME = "workbenchPlaybackSpeedCombo"

# Dark instrument surfaces (Explorer darker than main workspace)
COLOR_EXPLORER_BACKGROUND = "#1e1e1e"
COLOR_WORKSPACE_BACKGROUND = "#252526"
COLOR_INSPECTOR_BACKGROUND = "#252526"
COLOR_WORKSPACE_DIVIDER = "#333333"
COLOR_EXPLORER_SELECTION = "#2a4a66"
COLOR_EXPLORER_SELECTION_TEXT = "#e0e0e0"
COLOR_EXPLORER_HOVER = "#2a2d2e"

# Shared control surfaces (buttons, inputs, inspector fields)
COLOR_CONTROL_BACKGROUND = "#2a2d2e"
COLOR_CONTROL_BACKGROUND_HOVER = "#333333"
COLOR_CONTROL_BACKGROUND_PRESSED = "#252526"
COLOR_CONTROL_BACKGROUND_DISABLED = "#262626"
COLOR_CONTROL_BORDER = "#3c3c3c"
COLOR_CONTROL_BORDER_FOCUS = "#4a4a4a"
COLOR_CONTROL_TEXT = "#cccccc"
COLOR_CONTROL_TEXT_DISABLED = "#666666"

# Backward-compatible aliases used across Workbench QSS
COLOR_BUTTON_BACKGROUND = COLOR_CONTROL_BACKGROUND
COLOR_BUTTON_BACKGROUND_HOVER = COLOR_CONTROL_BACKGROUND_HOVER
COLOR_BUTTON_BACKGROUND_PRESSED = COLOR_CONTROL_BACKGROUND_PRESSED
COLOR_BUTTON_BACKGROUND_DISABLED = COLOR_CONTROL_BACKGROUND_DISABLED
COLOR_BUTTON_BORDER = COLOR_CONTROL_BORDER
COLOR_BUTTON_TEXT = COLOR_CONTROL_TEXT
COLOR_BUTTON_TEXT_DISABLED = COLOR_CONTROL_TEXT_DISABLED
COLOR_INSPECTOR_FIELD_BACKGROUND = COLOR_CONTROL_BACKGROUND
COLOR_INSPECTOR_FIELD_BORDER = COLOR_CONTROL_BORDER
COLOR_INSPECTOR_FIELD_BORDER_FOCUS = COLOR_CONTROL_BORDER_FOCUS

EXPLORER_CONTENT_PADDING = 8
EXPLORER_CONTENT_LEFT_PADDING = 6
EXPLORER_TREE_INDENTATION = 18
EXPLORER_TREE_ROOT_OFFSET = EXPLORER_TREE_INDENTATION
EXPLORER_BRANCH_CHEVRON_SIZE = 4
EXPLORER_INDENT_GUIDE_WIDTH = 1
EXPLORER_ROOT_ROW_PADDING_H = EXPLORER_CONTENT_LEFT_PADDING
EXPLORER_TREE_CONTENT_LEFT_PADDING = EXPLORER_CONTENT_LEFT_PADDING + EXPLORER_TREE_ROOT_OFFSET

# Typography colors
COLOR_HINT = "#888888"
COLOR_HINT_MUTED = "#aaaaaa"
COLOR_SMALL_LABEL = "#9da5b4"
COLOR_DIALOG_DESCRIPTION = "#666666"
COLOR_STATUS_SAVED = "#9ad4c8"
COLOR_STATUS_WARNING = "#ccaa66"

COLOR_EXPLORER_TEXT = COLOR_CONTROL_TEXT
COLOR_EXPLORER_MUTED_TEXT = COLOR_HINT
COLOR_EXPLORER_ROOT_BACKGROUND = COLOR_EXPLORER_BACKGROUND
COLOR_EXPLORER_GROUP_TEXT = "#cccccc"
COLOR_EXPLORER_ROOT_TEXT = COLOR_EXPLORER_GROUP_TEXT
COLOR_EXPLORER_SAMPLE_TEXT = "#a8b0bd"
COLOR_EXPLORER_BRANCH = "#b0b0b0"
COLOR_EXPLORER_BRANCH_SELECTED = COLOR_EXPLORER_SELECTION_TEXT
COLOR_EXPLORER_INDENT_GUIDE = "#383838"

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
STYLE_INSPECTOR_FIELD_LABEL = (
    f"color: {COLOR_SMALL_LABEL}; font-size: {FONT_SIZE_SMALL}px; padding: 0; margin: 0;"
)
STYLE_MUTED_LABEL = f"color: {COLOR_HINT_MUTED}; font-size: {FONT_SIZE_HINT}px;"
STYLE_EXPLORER_EMPTY_HINT = (
    f"color: {COLOR_HINT_MUTED}; font-size: {FONT_SIZE_HINT}px;"
    f"padding: 0 {EXPLORER_CONTENT_PADDING}px 0 "
    f"{EXPLORER_TREE_CONTENT_LEFT_PADDING}px;"
    "background: transparent;"
)
STYLE_BODY_LABEL = f"font-size: {FONT_SIZE_BODY}px;"
STYLE_DIALOG_DESCRIPTION = (
    f"color: {COLOR_DIALOG_DESCRIPTION}; font-size: {FONT_SIZE_HINT}px;"
)
STYLE_CHECKBOX_COMPACT = f"font-size: {FONT_SIZE_HINT}px;"
STYLE_WORKBENCH_CHECKBOX = (
    f"color: {COLOR_CONTROL_TEXT}; font-size: {FONT_SIZE_HINT}px;"
)
STYLE_WORKBENCH_PLAYBACK_LABEL = (
    f"color: {COLOR_SMALL_LABEL}; font-size: {FONT_SIZE_HINT}px; background: transparent;"
)

PLAYBACK_FRAME_LABEL_MIN_WIDTH = 72
PLAYBACK_SLIDER_MIN_WIDTH = 120
PLAYBACK_SPEED_COMBO_MIN_WIDTH = 72
WORKBENCH_CONTROL_HEIGHT = 24
WORKBENCH_CONTROL_RADIUS = 2
WORKBENCH_CONTROL_PADDING_V = 1
WORKBENCH_CONTROL_PADDING_H = 8
WORKBENCH_CONTROL_FONT_SIZE = FONT_SIZE_HINT
WORKBENCH_ACTION_CONTROL_MIN_WIDTH = 132
WORKBENCH_PLAYBACK_BUTTON_MIN_WIDTH = 60
WORKBENCH_ACTION_CONTROL_MIN_HEIGHT = WORKBENCH_CONTROL_HEIGHT
WORKBENCH_SPEED_ROW_SPACING = 6
PLAYBACK_RETURN_ROW_HEIGHT = WORKBENCH_CONTROL_HEIGHT + 4
EXPLORER_ROOT_ROW_HEIGHT = WORKBENCH_CONTROL_HEIGHT + 4
TRACKING_FIELD_MIN_HEIGHT = 26

ORIENT_PANEL_BUTTON_MIN_HEIGHT = 28
ROI_HINT_STATUS_SPACING = 2

_STYLE_WORKBENCH_CONTROL_METRICS = (
    f"border: none;"
    f"border-radius: {WORKBENCH_CONTROL_RADIUS}px;"
    f"padding: {WORKBENCH_CONTROL_PADDING_V}px {WORKBENCH_CONTROL_PADDING_H}px;"
    f"font-size: {WORKBENCH_CONTROL_FONT_SIZE}px;"
    f"min-height: {WORKBENCH_CONTROL_HEIGHT}px;"
    f"max-height: {WORKBENCH_CONTROL_HEIGHT}px;"
)

_STYLE_INSPECTOR_FIELD_METRICS = (
    f"background-color: {COLOR_CONTROL_BACKGROUND};"
    f"color: {COLOR_CONTROL_TEXT};"
    f"border: 1px solid {COLOR_CONTROL_BORDER};"
    f"border-radius: {WORKBENCH_CONTROL_RADIUS}px;"
    f"padding: 2px 6px;"
    f"min-height: {TRACKING_FIELD_MIN_HEIGHT}px;"
    f"font-size: {FONT_SIZE_HINT}px;"
)

STYLE_EXPLORER_PANEL = (
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} {{"
    f"  background-color: {COLOR_EXPLORER_BACKGROUND};"
    "  border: none;"
    "}"
    f"QWidget#{EXPLORER_TREE_HOST_OBJECT_NAME} {{"
    f"  background-color: {COLOR_EXPLORER_BACKGROUND};"
    "  border: none;"
    "}"
    f"QWidget#{EXPLORER_ROOT_ROW_OBJECT_NAME} {{"
    f"  background-color: {COLOR_EXPLORER_ROOT_BACKGROUND};"
    "  border: none;"
    f"  min-height: {EXPLORER_ROOT_ROW_HEIGHT}px;"
    f"  max-height: {EXPLORER_ROOT_ROW_HEIGHT}px;"
    "}"
    f"QLabel#{EXPLORER_ROOT_PATH_OBJECT_NAME} {{"
    f"  color: {COLOR_EXPLORER_ROOT_TEXT};"
    f"  font-size: {FONT_SIZE_HINT}px;"
    "  padding: 0;"
    "  background: transparent;"
    "}"
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} QTreeWidget {{"
    f"  background-color: {COLOR_EXPLORER_BACKGROUND};"
    f"  color: {COLOR_EXPLORER_TEXT};"
    "  border: none;"
    "  outline: none;"
    "}"
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} QTreeWidget::item {{"
    "  padding: 2px 0;"
    f"  color: {COLOR_EXPLORER_TEXT};"
    "}"
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} QTreeWidget::item:selected {{"
    f"  background-color: {COLOR_EXPLORER_SELECTION};"
    f"  color: {COLOR_EXPLORER_SELECTION_TEXT};"
    "}"
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} QTreeWidget::item:hover {{"
    f"  background-color: {COLOR_EXPLORER_HOVER};"
    "}"
    f"QWidget#{EXPLORER_PANEL_OBJECT_NAME} QTreeWidget::branch {{"
    "  background: transparent;"
    "}"
)
STYLE_INSPECTOR_PANEL = (
    f"QWidget#{ROI_PREVIEW_PANEL_OBJECT_NAME}, "
    f"QStackedWidget#{ROI_PREVIEW_PANEL_OBJECT_NAME} {{"
    f"  background-color: {COLOR_INSPECTOR_BACKGROUND};"
    "  border: none;"
    "}"
)
STYLE_WORKSPACE_PREVIEW_PANEL = (
    f"QWidget#{WORKSPACE_PREVIEW_PANEL_OBJECT_NAME} {{"
    f"  background-color: {COLOR_WORKSPACE_BACKGROUND};"
    "  border: none;"
    "}"
)
STYLE_MAIN_SPLITTER = (
    "QSplitter::handle:horizontal {"
    f"  background-color: {COLOR_WORKSPACE_DIVIDER};"
    "  width: 1px;"
    "}"
    "QSplitter::handle:horizontal:hover {"
    f"  background-color: {COLOR_WORKSPACE_DIVIDER};"
    "}"
)
STYLE_PREVIEW_CONTROLS_DIVIDER = (
    f"background-color: {COLOR_WORKSPACE_DIVIDER};"
    "border: none;"
    "min-height: 1px;"
    "max-height: 1px;"
)
STYLE_WORKBENCH_CONTROLS_PANEL = (
    f"QWidget#{WORKBENCH_CONTROLS_PANEL_OBJECT_NAME} {{"
    "  background-color: transparent;"
    "  border: none;"
    "}"
    f"QWidget#{WORKBENCH_CONTROLS_PANEL_OBJECT_NAME} QLabel {{"
    "  background: transparent;"
    "}"
)
STYLE_WORKBENCH_VERTICAL_DIVIDER = (
    f"background-color: {COLOR_WORKSPACE_DIVIDER};"
    "border: none;"
)
STYLE_WORKBENCH_ACTION_BUTTON = (
    f"QPushButton#{WORKBENCH_ACTION_BUTTON_OBJECT_NAME} {{"
    f"  background-color: {COLOR_BUTTON_BACKGROUND};"
    f"  color: {COLOR_BUTTON_TEXT};"
    f"{_STYLE_WORKBENCH_CONTROL_METRICS}"
    "}"
    f"QPushButton#{WORKBENCH_ACTION_BUTTON_OBJECT_NAME}:hover "
    f"{{ background-color: {COLOR_BUTTON_BACKGROUND_HOVER}; }}"
    f"QPushButton#{WORKBENCH_ACTION_BUTTON_OBJECT_NAME}:pressed "
    f"{{ background-color: {COLOR_BUTTON_BACKGROUND_PRESSED}; }}"
    f"QPushButton#{WORKBENCH_ACTION_BUTTON_OBJECT_NAME}:disabled "
    f"{{"
    f"  background-color: {COLOR_BUTTON_BACKGROUND_DISABLED};"
    f"  color: {COLOR_BUTTON_TEXT_DISABLED};"
    "}"
)
STYLE_WORKBENCH_PLAYBACK_BUTTON = (
    f"QPushButton#{WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME} {{"
    f"  background-color: {COLOR_BUTTON_BACKGROUND};"
    f"  color: {COLOR_BUTTON_TEXT};"
    f"{_STYLE_WORKBENCH_CONTROL_METRICS}"
    f"  min-width: {WORKBENCH_PLAYBACK_BUTTON_MIN_WIDTH}px;"
    "}"
    f"QPushButton#{WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME}:hover "
    f"{{ background-color: {COLOR_BUTTON_BACKGROUND_HOVER}; }}"
    f"QPushButton#{WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME}:pressed "
    f"{{ background-color: {COLOR_BUTTON_BACKGROUND_PRESSED}; }}"
    f"QPushButton#{WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME}:disabled "
    f"{{"
    f"  background-color: {COLOR_BUTTON_BACKGROUND_DISABLED};"
    f"  color: {COLOR_BUTTON_TEXT_DISABLED};"
    "}"
)
STYLE_WORKBENCH_PLAYBACK_SPEED_COMBO = (
    f"QComboBox#{WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME} {{"
    f"  background-color: {COLOR_CONTROL_BACKGROUND};"
    f"  color: {COLOR_CONTROL_TEXT};"
    f"  border: 1px solid {COLOR_CONTROL_BORDER};"
    f"  border-radius: {WORKBENCH_CONTROL_RADIUS}px;"
    f"  padding: {WORKBENCH_CONTROL_PADDING_V}px 6px;"
    f"  padding-right: 18px;"
    f"  font-size: {FONT_SIZE_HINT}px;"
    f"  min-height: {WORKBENCH_CONTROL_HEIGHT}px;"
    f"  max-height: {WORKBENCH_CONTROL_HEIGHT}px;"
    "}"
    f"QComboBox#{WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME}:disabled "
    f"{{"
    f"  background-color: {COLOR_CONTROL_BACKGROUND_DISABLED};"
    f"  color: {COLOR_CONTROL_TEXT_DISABLED};"
    "}"
    f"QComboBox#{WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME}::drop-down "
    "{"
    "  subcontrol-origin: padding;"
    "  subcontrol-position: top right;"
    "  width: 16px;"
    f"  border-left: 1px solid {COLOR_CONTROL_BORDER};"
    "}"
    f"QComboBox#{WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME}::down-arrow "
    "{ width: 8px; height: 8px; }"
)
STYLE_WORKBENCH_SETTINGS_COMBO = (
    f"QComboBox#{WORKBENCH_SETTINGS_COMBO_OBJECT_NAME} {{"
    f"{_STYLE_INSPECTOR_FIELD_METRICS}"
    f"  padding-right: 22px;"
    "}"
    f"QComboBox#{WORKBENCH_SETTINGS_COMBO_OBJECT_NAME}:disabled "
    f"{{"
    f"  background-color: {COLOR_BUTTON_BACKGROUND_DISABLED};"
    f"  color: {COLOR_BUTTON_TEXT_DISABLED};"
    "}"
    f"QComboBox#{WORKBENCH_SETTINGS_COMBO_OBJECT_NAME}:focus "
    f"{{ border-color: {COLOR_INSPECTOR_FIELD_BORDER_FOCUS}; }}"
    f"QComboBox#{WORKBENCH_SETTINGS_COMBO_OBJECT_NAME}::drop-down "
    "{"
    "  subcontrol-origin: padding;"
    "  subcontrol-position: top right;"
    "  width: 18px;"
    f"  border-left: 1px solid {COLOR_INSPECTOR_FIELD_BORDER};"
    "}"
    f"QComboBox#{WORKBENCH_SETTINGS_COMBO_OBJECT_NAME}::down-arrow "
    "{ width: 8px; height: 8px; }"
)
STYLE_INSPECTOR_FIELD = (
    f"QSpinBox, QDoubleSpinBox, QLineEdit {{"
    f"{_STYLE_INSPECTOR_FIELD_METRICS}"
    "}"
    f"QComboBox {{"
    f"{_STYLE_INSPECTOR_FIELD_METRICS}"
    f"  padding-right: 22px;"
    "}"
    f"QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus "
    f"{{ border-color: {COLOR_INSPECTOR_FIELD_BORDER_FOCUS}; }}"
    "QComboBox::drop-down {"
    "  subcontrol-origin: padding;"
    "  subcontrol-position: top right;"
    "  width: 18px;"
    f"  border-left: 1px solid {COLOR_INSPECTOR_FIELD_BORDER};"
    "}"
    "QComboBox::down-arrow { width: 8px; height: 8px; }"
)
STYLE_INSPECTOR_SCROLL = (
    f"QScrollArea {{"
    f"  background-color: {COLOR_INSPECTOR_BACKGROUND};"
    "  border: none;"
    "}"
    f"QScrollArea > QWidget > QWidget {{"
    f"  background-color: {COLOR_INSPECTOR_BACKGROUND};"
    "}"
)

METRIC_STATUS_PANEL_OBJECT_NAME = "metricStatusPanel"
STYLE_METRIC_STATUS_PANEL = (
    f"QFrame#{METRIC_STATUS_PANEL_OBJECT_NAME} {{"
    "  background-color: transparent;"
    "  border: none;"
    "}"
)
METRIC_STATUS_INNER_SPACING = 6
METRIC_STATUS_LABEL_SPACING = 2

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


def apply_inspector_field_label_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_INSPECTOR_FIELD_LABEL)


def apply_muted_hint_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_MUTED_LABEL)


def apply_explorer_empty_hint_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_EXPLORER_EMPTY_HINT)


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


def apply_side_panel_inner_margins(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(
        SIDE_PANEL_INNER_MARGIN,
        SIDE_PANEL_INNER_MARGIN,
        SIDE_PANEL_INNER_MARGIN,
        SIDE_PANEL_INNER_MARGIN,
    )


def apply_side_panel_form_group_margins(layout: QVBoxLayout) -> None:
    layout.setContentsMargins(
        SIDE_PANEL_INNER_MARGIN,
        SIDE_PANEL_GROUP_TOP_MARGIN,
        SIDE_PANEL_INNER_MARGIN,
        SIDE_PANEL_INNER_MARGIN,
    )


def apply_explorer_panel_margins(layout: QVBoxLayout) -> None:
    """Edge-to-edge Explorer rail within the central workspace."""
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)


def apply_explorer_content_margins(layout: QVBoxLayout) -> None:
    """Inner padding for Explorer labels/tree without inseting the panel shell."""
    layout.setContentsMargins(
        EXPLORER_CONTENT_PADDING,
        EXPLORER_CONTENT_PADDING,
        EXPLORER_CONTENT_PADDING,
        EXPLORER_CONTENT_PADDING,
    )


def apply_explorer_root_row_margins(layout) -> None:
    """Quiet workspace root row inset within the Explorer tree surface."""
    layout.setContentsMargins(
        EXPLORER_ROOT_ROW_PADDING_H,
        0,
        EXPLORER_CONTENT_PADDING,
        0,
    )
    layout.setSpacing(0)


def explorer_workspace_display_name(path: Path | str | None) -> str:
    """Prominent workspace folder label for the Explorer root row."""
    if path is None:
        return "—"
    resolved = Path(path)
    name = resolved.name.strip()
    return name or str(resolved)


def explorer_workspace_elide_width(
    container_width: int,
    *,
    horizontal_padding: int = EXPLORER_ROOT_ROW_PADDING_H * 2,
    minimum: int = 80,
) -> int:
    """Available pixel width for eliding the Explorer workspace label."""
    return max(minimum, container_width - horizontal_padding)


def apply_explorer_tree_content_margins(layout) -> None:
    """Nest the Explorer tree one level under the workspace root row."""
    layout.setContentsMargins(
        EXPLORER_TREE_CONTENT_LEFT_PADDING,
        0,
        EXPLORER_CONTENT_PADDING,
        0,
    )


def configure_explorer_root_row(row: QWidget) -> None:
    row.setObjectName(EXPLORER_ROOT_ROW_OBJECT_NAME)
    row.setFixedHeight(EXPLORER_ROOT_ROW_HEIGHT)
    row.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )


def configure_explorer_root_path_label(label: QLabel) -> None:
    label.setObjectName(EXPLORER_ROOT_PATH_OBJECT_NAME)
    label.setWordWrap(False)
    label.setFont(explorer_condition_group_font(label.font()))
    label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )


def configure_explorer_tree_host(host: QWidget) -> None:
    host.setObjectName(EXPLORER_TREE_HOST_OBJECT_NAME)
    host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )


def explorer_base_font(base: QFont) -> QFont:
    """Shared regular-weight Explorer row label."""
    font = QFont(base)
    font.setWeight(QFont.Weight.Normal)
    font.setPixelSize(FONT_SIZE_HINT)
    return font


def explorer_condition_group_font(base: QFont) -> QFont:
    """Condition Group rows use the shared Explorer base font."""
    return explorer_base_font(base)


def explorer_sample_font(base: QFont) -> QFont:
    """Sample rows use the shared Explorer base font."""
    return explorer_base_font(base)


def apply_explorer_panel_style(panel: QWidget) -> None:
    panel.setObjectName(EXPLORER_PANEL_OBJECT_NAME)
    panel.setStyleSheet(STYLE_EXPLORER_PANEL)


def apply_inspector_panel_style(panel: QWidget) -> None:
    panel.setObjectName(ROI_PREVIEW_PANEL_OBJECT_NAME)
    panel.setStyleSheet(STYLE_INSPECTOR_PANEL)


def apply_workspace_preview_panel_style(panel: QWidget) -> None:
    panel.setObjectName(WORKSPACE_PREVIEW_PANEL_OBJECT_NAME)
    panel.setStyleSheet(STYLE_WORKSPACE_PREVIEW_PANEL)


def apply_workbench_controls_panel_style(panel: QWidget) -> None:
    panel.setObjectName(WORKBENCH_CONTROLS_PANEL_OBJECT_NAME)
    panel.setStyleSheet(STYLE_WORKBENCH_CONTROLS_PANEL)


def apply_workbench_playback_label_style(label: QLabel) -> None:
    label.setStyleSheet(STYLE_WORKBENCH_PLAYBACK_LABEL)


def apply_main_splitter_style(splitter: QSplitter) -> None:
    splitter.setHandleWidth(1)
    splitter.setStyleSheet(STYLE_MAIN_SPLITTER)


def _apply_workbench_control_geometry(
    widget: QWidget,
    *,
    min_width: int,
) -> None:
    widget.setFixedHeight(WORKBENCH_CONTROL_HEIGHT)
    widget.setMinimumWidth(min_width)
    widget.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )


def apply_workbench_action_button(button: QPushButton) -> None:
    button.setObjectName(WORKBENCH_ACTION_BUTTON_OBJECT_NAME)
    button.setStyleSheet(STYLE_WORKBENCH_ACTION_BUTTON)
    _apply_workbench_control_geometry(
        button,
        min_width=WORKBENCH_ACTION_CONTROL_MIN_WIDTH,
    )


def apply_workbench_playback_button(button: QPushButton) -> None:
    button.setObjectName(WORKBENCH_PLAYBACK_BUTTON_OBJECT_NAME)
    button.setStyleSheet(STYLE_WORKBENCH_PLAYBACK_BUTTON)
    _apply_workbench_control_geometry(
        button,
        min_width=WORKBENCH_PLAYBACK_BUTTON_MIN_WIDTH,
    )


def apply_workbench_playback_speed_combo(combo: QWidget) -> None:
    combo.setObjectName(WORKBENCH_PLAYBACK_SPEED_COMBO_OBJECT_NAME)
    combo.setStyleSheet(STYLE_WORKBENCH_PLAYBACK_SPEED_COMBO)
    combo.setFixedHeight(WORKBENCH_CONTROL_HEIGHT)
    combo.setMinimumWidth(PLAYBACK_SPEED_COMBO_MIN_WIDTH)
    combo.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )


def apply_workbench_settings_combo(combo: QWidget) -> None:
    combo.setObjectName(WORKBENCH_SETTINGS_COMBO_OBJECT_NAME)
    combo.setStyleSheet(STYLE_WORKBENCH_SETTINGS_COMBO)
    combo.setMinimumHeight(TRACKING_FIELD_MIN_HEIGHT)
    combo.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )


def apply_inspector_field_style(widget: QWidget) -> None:
    widget.setStyleSheet(STYLE_INSPECTOR_FIELD)


def apply_inspector_scroll_style(scroll: QWidget) -> None:
    scroll.setStyleSheet(STYLE_INSPECTOR_SCROLL)


def configure_workbench_action_mode_slot(slot: QStackedWidget) -> None:
    """Fixed slot where Full Preview and Metric Analysis swap right-side controls."""
    slot.setFixedSize(
        WORKBENCH_ACTION_CONTROL_MIN_WIDTH,
        WORKBENCH_CONTROL_HEIGHT,
    )
    slot.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )


def configure_orient_panel_action_button(button: QPushButton) -> None:
    """Equal-width action buttons in the Orient and ROI panel."""
    button.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    button.setMinimumHeight(ORIENT_PANEL_BUTTON_MIN_HEIGHT)
