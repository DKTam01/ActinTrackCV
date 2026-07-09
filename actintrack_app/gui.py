"""PyQt6 GUI — Arabidopsis reproductive-cell F-actin preprocessing and ROI annotation."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from actintrack_app.analysis_service import AnalysisReport, build_analysis_report
from actintrack_app.annotation_schema import (
    annotation_from_legacy,
    build_sample_annotation,
    merge_processed_into_annotation,
)
from actintrack_app.batch_annotation import (
    annotation_is_protected,
    propagate_annotation,
    resolve_propagation_targets,
    save_propagated_annotations,
)
from actintrack_app.batch_manager import (
    batch_has_samples,
    delete_empty_batch,
    display_batch_name,
    display_sample_label,
    ensure_default_batch,
    get_batch_by_name,
    list_batches,
    parse_batch_number_from_name,
    rename_batch,
    repair_batch_registry,
    sanitize_batch_name,
    sync_registry_from_samples,
)
from actintrack_app.file_importer import set_custom_export_name
from actintrack_app.gui_menus import (
    PurgeFilteredDialog,
    refresh_recent_workspaces_menu,
    setup_application_menus,
)
from actintrack_app.gui_layout_builders import (
    DEFAULT_SPLITTER_SIZES as _DEFAULT_SPLITTER_SIZES,
    LEFT_PANEL_MIN_WIDTH as _LEFT_PANEL_MIN_WIDTH,
    METRIC_ANALYSIS_VIEW_LABEL as _METRIC_ANALYSIS_VIEW_LABEL,
    PLAYBACK_SPEED_OPTIONS as _PLAYBACK_SPEED_OPTIONS,
    assemble_playback_controls_layout,
    build_export_name_panel,
    build_hidden_frame_controls,
    build_left_sidebar,
    build_main_workspace,
    build_optical_flow_settings_page,
    build_samples_panel,
    build_tracking_settings_page,
    configure_orient_roi_control,
    configure_tracking_field,
    create_playback_frame_label,
    create_playback_play_button,
    create_playback_slider,
    create_playback_speed_combo,
    create_playback_speed_label,
)
from actintrack_app.gui_styles import (
    CONTROL_ROW_SPACING,
    FORM_SECTION_SPACING,
    METRIC_STATUS_INNER_SPACING,
    METRIC_STATUS_LABEL_SPACING,
    METRIC_STATUS_PANEL_OBJECT_NAME,
    PANEL_INNER_MARGIN,
    PANEL_SECTION_SPACING,
    PLAYBACK_FRAME_LABEL_MIN_WIDTH,
    PLAYBACK_SLIDER_MIN_WIDTH,
    PLAYBACK_SPEED_COMBO_MIN_WIDTH,
    ROI_HINT_STATUS_SPACING,
    STYLE_CHECKBOX_COMPACT,
    STYLE_METRIC_STATUS_PANEL,
    apply_body_label_style,
    apply_form_group_margins,
    apply_hint_style,
    apply_muted_hint_style,
    apply_panel_inner_margins,
    apply_panel_margins,
    apply_small_secondary_style,
    apply_status_style,
    configure_orient_panel_action_button,
    explorer_workspace_display_name,
    explorer_workspace_elide_width,
    tracking_result_group_title,
)
from actintrack_app.qt_spin_boxes import NoWheelDoubleSpinBox, NoWheelSpinBox
from actintrack_app.image_processing import TrackingCrop, detect_tracking_crop
from actintrack_app.metadata import (
    load_samples_csv,
    get_sample_annotation,
    load_crop_metadata,
    migrate_workspace_schema,
    remove_sample_crop_annotation,
    remove_samples_from_metadata,
    save_sample_crop_annotation,
    sync_samples_with_disk,
    update_samples_csv,
)
from actintrack_app.metric_display import render_metric_display_lines
from actintrack_app.purge_cleanup_dialog import pick_empty_batch_name
from actintrack_app.sample_service import (
    DATA_IMPORT_FILTER,
    create_samples_from_data_files,
    delete_sample_and_artifacts,
    format_sample_import_summary,
    get_primary_data_row,
    replace_sample_data,
    sample_has_derived_state,
)
from actintrack_app.purge_manager import (
    complete_batch_purge,
    delete_sample_from_batch,
    purge_batch_annotations,
    purge_filtered_samples,
    purge_sample_annotations_only,
    purge_sample_completely,
)
from actintrack_app.condition_group_manager import (
    condition_group_exists,
    condition_group_display_name,
    condition_group_has_samples,
    create_condition_group,
    delete_empty_condition_group,
    display_export_name_for_row,
    get_condition_group_name,
    list_condition_group_records,
    rename_condition_group,
    resolve_condition_group_id,
)
from actintrack_app.explorer_sidebar import (
    ITEM_TYPE_CONDITION_GROUP,
    ITEM_TYPE_EMPTY_SAMPLE,
    ITEM_TYPE_SAMPLE,
    condition_group_tree_meta,
    empty_sample_sidebar_label,
    empty_sample_tree_meta,
    sample_sidebar_display_label,
    sample_tree_meta,
    tree_item_condition_group_id,
)
from actintrack_app.explorer_tree import (
    collect_condition_group_expansion_state,
    configure_condition_group_tree_item,
    default_expanded_state_for_condition_group,
    restore_selected_sample_by_id,
)
from actintrack_app.recent_workspaces import add_recent
from actintrack_app.user_preferences import get_last_import_breed, set_last_import_breed
from actintrack_app.orientation import (
    OrientationState,
    RectROI,
    apply_orientation,
    crop_rect_roi,
    tracking_crop_to_rect,
)
from actintrack_app.project_manager import (
    create_project_structure,
    is_valid_project,
)
from actintrack_app.motion_index import (
    MotionIndexParams,
    TRACKING_METHOD_BRIGHTEST_LOCAL,
    TRACKING_METHOD_TEMPLATE,
)
from actintrack_app.optical_flow_motion_index import (
    OpticalFlowResult,
    OpticalFlowSettings,
    build_optical_flow_fingerprint,
    compute_optical_flow_motion_index,
    result_from_dict,
    result_to_dict,
)
from actintrack_app.optical_flow_overlay import (
    OpticalFlowFlowCache,
    OpticalFlowVisualizationSettings,
    build_flow_cache,
    format_optical_flow_qc,
    get_flow_arrows_for_frame,
    render_optical_flow_overlay,
    resolve_qc_status,
)
from actintrack_app.preview_workflow import (
    CroppedPreviewAnalysis,
    analyze_cropped_preview,
    is_supported_video_path,
    load_cropped_frames_from_video,
    render_cropped_tracking_frame,
)
from actintrack_app.roi_workflow import (
    RoiValidationResult,
    is_wip_sample_path,
    list_output_paths_for_export,
    process_batch_approved_rois,
    process_sample_roi,
    validate_roi_for_sample,
)
from actintrack_app.utils import (
    CROP_METADATA_JSON,
    METADATA_DIR,
    METRIC_DEBOUNCE_MS,
    RAW_DIR,
    SAMPLES_CSV,
    STATUS_IMPORTED,
    STATUS_MOTION_INDEX_FAILED,
    STATUS_MOTION_INDEX_GENERATED,
    STATUS_PROCESSED,
    STATUS_RAW_IMPORTED,
    STATUS_ROI_APPROVED,
    STATUS_ROI_MARKED,
    STATUS_ROI_PROPAGATED,
    STATUS_UNANNOTATED,
    SCOPE_SELECTED,
)
from actintrack_app.video_processing import MediaLoadError, load_media_frame
from actintrack_app import gui_dialogs
from actintrack_app.gui_result_loaders import (
    load_latest_optical_flow_result_view,
    load_latest_tracking_result_view,
)
from actintrack_app.gui_result_views import (
    OpticalFlowResultView,
    SampleTrackingResultView,
    format_tracking_result_panel_lines,
)
from actintrack_app.debug_log import breadcrumb
from actintrack_app.__version__ import __version__
from actintrack_app.paths import (
    app_root,
    default_source_root,
    default_workspace_root,
    icon_path,
    resource_path,
    resource_root,
)


APP_ROOT = app_root()
RESOURCE_ROOT = resource_root()
DEFAULT_SOURCE_ROOT = default_source_root()


def _app_qicon() -> Optional[QIcon]:
    """Bundled app icon as a QIcon, or None if no runtime icon is available."""
    path = icon_path()
    if path is not None and path.is_file():
        return QIcon(str(path))
    return None
AUTO_APPLY_ROI_CONFIDENCE = 0.15
DRAFT_TRACKING_DIR = "draft_tracking"
_PLAYBACK_SPEED_MULTIPLIERS = {
    "0.25×": 0.25,
    "0.5×": 0.5,
    "1×": 1.0,
    "1.5×": 1.5,
    "2×": 2.0,
}
_PLAYBACK_BASE_FPS = 5.0

_ADVANCED_SAMPLE_STATUSES = frozenset(
    {
        STATUS_PROCESSED,
        STATUS_MOTION_INDEX_GENERATED,
        STATUS_MOTION_INDEX_FAILED,
    }
)
_ROI_STATUS_UPGRADE_FROM = frozenset(
    {
        STATUS_RAW_IMPORTED,
        STATUS_IMPORTED,
        STATUS_UNANNOTATED,
    }
)


@dataclass(frozen=True)
class _TrackingRunSnapshot:
    sample_id: str
    roi_key: tuple[int, int, int, int]
    params_key: tuple[tuple[str, Any], ...]
    orientation_key: tuple[float, bool, bool]
    video_path: str
    run_token: int


@dataclass(frozen=True)
class _OpticalFlowRunSnapshot:
    sample_id: str
    roi_key: tuple[int, int, int, int]
    settings_key: tuple[tuple[str, Any], ...]
    orientation_key: tuple[float, bool, bool]
    video_path: str
    run_token: int


STATUS_COLORS = {
    STATUS_IMPORTED: QColor("#bbbbbb"),
    STATUS_RAW_IMPORTED: QColor("#bbbbbb"),
    STATUS_UNANNOTATED: QColor("#aaaaaa"),
    "cutoff_marked": QColor("#c9b84c"),
    STATUS_ROI_MARKED: QColor("#6aa8ff"),
    STATUS_ROI_PROPAGATED: QColor("#ff9944"),
    STATUS_ROI_APPROVED: QColor("#66dd88"),
    STATUS_PROCESSED: QColor("#3ddc84"),
    STATUS_MOTION_INDEX_GENERATED: QColor("#2ec4b6"),
    STATUS_MOTION_INDEX_FAILED: QColor("#e07070"),
    "missing_file": QColor("#cc6666"),
}


class PropagateDialog(QDialog):
    def __init__(self, parent: QWidget, group: str, batch_name: str):
        super().__init__(parent)
        self.setWindowTitle("Propagate ROI")
        layout = QFormLayout(self)
        num = parse_batch_number_from_name(batch_name) or 1
        sample_label = display_sample_label(num, batch_name)
        help_lbl = QLabel(
            "By default, ROI changes apply only to the current sample, "
            "not to other samples in the condition group."
        )
        help_lbl.setWordWrap(True)
        layout.addRow(help_lbl)
        self.combo_scope = QComboBox()
        self.combo_scope.addItems(
            [
                f"Same sample ({sample_label})",
                f"Unprocessed samples in {sample_label}",
                f"All samples in condition group {group}",
                "Currently selected samples in Explorer",
            ]
        )
        self.combo_scaling = QComboBox()
        self.combo_scaling.addItem(
            "Scale proportionally to frame size",
            "proportional_scaled",
        )
        self.combo_scaling.addItem(
            "Use same pixel coordinates",
            "same_coordinates",
        )
        self.chk_overwrite = QCheckBox(
            "Overwrite existing ROIs (approved and processed samples still "
            "require confirmation)"
        )
        layout.addRow("Propagation scope:", self.combo_scope)
        layout.addRow("ROI scaling:", self.combo_scaling)
        layout.addRow(self.chk_overwrite)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def scope_key(self) -> str:
        from actintrack_app.utils import (
            SCOPE_ALL_IN_GROUP,
            SCOPE_SAME_BATCH,
            SCOPE_UNPROCESSED_IN_BATCH,
        )

        text = self.combo_scope.currentText()
        if text.startswith("Same sample"):
            return SCOPE_SAME_BATCH
        if text.startswith("Unprocessed"):
            return SCOPE_UNPROCESSED_IN_BATCH
        if text.startswith("All samples in condition group"):
            return SCOPE_ALL_IN_GROUP
        return SCOPE_SELECTED

    def scaling_method(self) -> str:
        data = self.combo_scaling.currentData()
        if data is not None:
            return str(data)
        return self.combo_scaling.currentText()

    def overwrite(self) -> bool:
        return self.chk_overwrite.isChecked()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ActinTrackCV — Arabidopsis F-actin Tracking Workbench")
        self.resize(1280, 720)
        self.setMinimumSize(960, 600)

        _icon = _app_qicon()
        if _icon is not None:
            self.setWindowIcon(_icon)

        self._project_root: Optional[Path] = None
        self._current_sample: Optional[dict] = None
        self._current_sample_id: Optional[str] = None
        self._base_frame: Optional[np.ndarray] = None
        self._frame_index = 0
        self._total_frames = 1
        self._reference_frame_index = 0
        self._orientation = OrientationState()
        self._workspace_root = default_workspace_root()
        self._default_source_root = (
            DEFAULT_SOURCE_ROOT if DEFAULT_SOURCE_ROOT.exists() else self._workspace_root
        )
        self._last_import_dir = self._default_source_root
        self._last_import_breed: Optional[str] = None
        self._roi_user_adjusted = False
        self._loaded_annotation_source = "manual"
        self._loaded_sample_notes = ""
        self._preview_mode = "full"
        self._preview_playing = False
        self._preview_frame_index = 0
        self._cropped_preview: Optional[CroppedPreviewAnalysis] = None
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._on_preview_timer_tick)
        self._roi_autosave_pending = False
        self._tracking_results_by_sample: dict[str, CroppedPreviewAnalysis] = {}
        self._tracking_result_stale_by_sample: dict[str, bool] = {}
        self._pending_tracking_snapshot: Optional[_TrackingRunSnapshot] = None
        self._tracking_run_token = 0
        self._tracking_job_running = False
        self._cropped_metric_mode = "template"
        self._metric_analysis_view_active = False
        self._optical_flow_results_by_sample: dict[str, OpticalFlowResult] = {}
        self._optical_flow_stale_by_sample: dict[str, bool] = {}
        self._optical_flow_run_token = 0
        self._optical_flow_job_running = False
        self._pending_optical_flow_snapshot: Optional[_OpticalFlowRunSnapshot] = None
        self._metric_debounce_timer = QTimer(self)
        self._metric_debounce_timer.setSingleShot(True)
        self._metric_debounce_timer.setInterval(METRIC_DEBOUNCE_MS)
        self._metric_debounce_timer.timeout.connect(self._on_metric_debounce_fired)
        self._metric_settings_timer = QTimer(self)
        self._metric_settings_timer.setSingleShot(True)
        self._metric_settings_timer.setInterval(METRIC_DEBOUNCE_MS)
        self._metric_settings_timer.timeout.connect(
            self._on_metric_settings_debounce_fired
        )
        self._of_flow_caches: dict[str, OpticalFlowFlowCache] = {}
        # Per-Sample metric scheduling/state (decoupled from the live canvas).
        self._metrics_inflight: set[str] = set()
        self._metric_error_by_sample: dict[str, bool] = {}
        self._metric_compute_queue: list[str] = []
        self._metric_flush_timer = QTimer(self)
        self._metric_flush_timer.setSingleShot(True)
        self._metric_flush_timer.setInterval(150)
        self._metric_flush_timer.timeout.connect(self._on_metric_flush_timer)

        self._splitter_sizes_before_analysis: list[int] | None = None
        self._explorer_group_expansion_by_id: dict[str, bool] = {}
        self._build_ui()
        self._set_tracking_settings_editable(False)
        setup_application_menus(self)
        self._load_project(self._workspace_root, "Workspace project loaded")

    def _build_ui(self) -> None:
        build_main_workspace(self)

    def _build_left_sidebar(self) -> QWidget:
        return build_left_sidebar(self)

    def _build_samples_panel(self) -> QWidget:
        return build_samples_panel(self)

    def _build_hidden_frame_controls(self) -> QWidget:
        return build_hidden_frame_controls(self)

    def _build_export_name_panel(self) -> QWidget:
        return build_export_name_panel(self)

    @staticmethod
    def _configure_orient_roi_control(widget: QWidget) -> None:
        configure_orient_roi_control(widget)

    @staticmethod
    def _configure_tracking_field(widget: QWidget, *, full_column: bool = False) -> None:
        configure_tracking_field(widget, full_column=full_column)

    def _create_tracking_setting_widgets(self) -> None:
        from actintrack_app.gui_layout_builders import create_tracking_setting_widgets

        create_tracking_setting_widgets(self)

    @staticmethod
    def _add_tracking_setting_row(
        layout: QVBoxLayout,
        label_text: str,
        widget: QWidget,
        tooltip: str,
    ) -> None:
        from actintrack_app.gui_layout_builders import add_tracking_setting_row

        add_tracking_setting_row(layout, label_text, widget, tooltip)

    def _build_tracking_settings_form(self) -> QWidget:
        from actintrack_app.gui_layout_builders import build_tracking_settings_form

        return build_tracking_settings_form(self)

    def _build_tracking_settings_page(self) -> QWidget:
        return build_tracking_settings_page(self)

    def _create_optical_flow_setting_widgets(self) -> None:
        from actintrack_app.gui_layout_builders import create_optical_flow_setting_widgets

        create_optical_flow_setting_widgets(self)

    def _build_optical_flow_overlay_section(self) -> QWidget:
        from actintrack_app.gui_layout_builders import build_optical_flow_overlay_section

        return build_optical_flow_overlay_section(self)

    def _build_optical_flow_settings_form(self) -> QWidget:
        from actintrack_app.gui_layout_builders import build_optical_flow_settings_form

        return build_optical_flow_settings_form(self)

    def _build_optical_flow_settings_page(self) -> QWidget:
        return build_optical_flow_settings_page(self)

    @staticmethod
    def _tool_button(text: str, tooltip: str, slot) -> QPushButton:
        from actintrack_app.gui_styles import apply_workbench_action_button

        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.clicked.connect(slot)
        apply_workbench_action_button(btn)
        return btn

    @staticmethod
    def _hide_widgets(widgets: tuple[QWidget, ...]) -> None:
        for widget in widgets:
            widget.hide()

    def _create_playback_play_button(self, *, tooltip: str) -> QPushButton:
        return create_playback_play_button(self, tooltip=tooltip)

    @staticmethod
    def _create_playback_frame_label(text: str) -> QLabel:
        return create_playback_frame_label(text)

    @staticmethod
    def _create_playback_slider(*, value_changed) -> QSlider:
        return create_playback_slider(value_changed=value_changed)

    @staticmethod
    def _create_playback_speed_label() -> QLabel:
        return create_playback_speed_label()

    def _create_playback_speed_combo(self, *, value_changed) -> QComboBox:
        return create_playback_speed_combo(self, value_changed=value_changed)

    @staticmethod
    def _assemble_playback_controls_layout(
        *,
        play_button: QPushButton,
        frame_label: QLabel,
        frame_slider: QSlider,
        speed_label: QLabel,
        speed_combo: QComboBox,
        speed_row_before_stretch: tuple[QWidget, ...] = (),
        speed_row_after_stretch: tuple[QWidget, ...] = (),
    ) -> QVBoxLayout:
        return assemble_playback_controls_layout(
            play_button=play_button,
            frame_label=frame_label,
            frame_slider=frame_slider,
            speed_label=speed_label,
            speed_combo=speed_combo,
            speed_row_before_stretch=speed_row_before_stretch,
            speed_row_after_stretch=speed_row_after_stretch,
        )

    def _status(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 8000)

    def _require_project_root(self) -> Path | None:
        if self._project_root is not None:
            return self._project_root
        gui_dialogs.warning(
            self,
            "Workspace Required",
            "Open or create a workspace first.",
        )
        return None

    _SELECT_SAMPLE_HINT = "Select a sample to preview."

    def _set_preview_mode_banner(self, text: str | None) -> None:
        if text:
            self.lbl_preview_mode.setText(text)
        else:
            self.lbl_preview_mode.clear()

    def reset_preview_state(
        self,
        *,
        clear_image: bool = True,
        placeholder: Optional[str] = None,
        reset_roi_controls: bool = True,
    ) -> None:
        """Stop playback and clear cropped/tracking preview when context changes."""
        self._preview_pause()
        self._metric_debounce_timer.stop()
        self._metric_settings_timer.stop()
        self._cancel_pending_debounced_tracking()
        self._set_metric_mode_widgets_visible(False)
        self._clear_of_flow_cache()
        self._preview_frame_index = 0
        self._cropped_preview = None
        self._preview_playing = False
        self.canvas.set_interactive(True)
        self._set_preview_controls_visible(False)
        if reset_roi_controls:
            self._set_tracking_settings_editable(False)
            self._show_roi_controls_view()
        if clear_image:
            self._base_frame = None
            self._total_frames = 1
            self._frame_index = 0
            self._reference_frame_index = 0
            self.canvas.clear_preview()
            self.lbl_frame_info.setText("—")
            self.slider_frame.setMaximum(0)
            self.spin_frame.setMaximum(0)
            self.slider_frame.setValue(0)
            self.spin_frame.setValue(0)
            self._reset_sample_frame_ui()
            self._preview_mode = "no_sample"
        else:
            self._preview_mode = "full"
        if placeholder is not None:
            self._set_preview_mode_banner(placeholder)
        elif clear_image and self._current_sample is None:
            self._set_preview_mode_banner(self._SELECT_SAMPLE_HINT)
        else:
            self._set_preview_mode_banner(None)
        if self._current_sample_id is None:
            self.update_tracking_result_panel()
        self._update_metric_analysis_button_visibility()
        self._refresh_roi_preview_panel()

    def _set_roi_preview_panel_visible(self, visible: bool) -> None:
        if hasattr(self, "_adjacent_panel_stack"):
            if visible:
                self._adjacent_panel_stack.setCurrentIndex(0)
            elif self._metric_analysis_view_active or self._preview_mode == "cropped_tracking":
                self._adjacent_panel_stack.setCurrentIndex(1)
            return
        if hasattr(self, "_roi_preview_host"):
            self._roi_preview_host.setVisible(visible)

    def _set_roi_preview_placeholder(self, message: str) -> None:
        if not hasattr(self, "lbl_roi_preview_empty"):
            return
        self.lbl_roi_preview_empty.setText(message)
        self.lbl_roi_preview_empty.show()
        if hasattr(self, "roi_preview_canvas"):
            self.roi_preview_canvas.hide()
            self.roi_preview_canvas.clear_preview()

    def _refresh_roi_preview_panel(self) -> None:
        if not hasattr(self, "roi_preview_canvas"):
            return
        if self._metric_analysis_view_active or self._preview_mode == "cropped_tracking":
            self._set_roi_preview_panel_visible(False)
            return
        self._set_roi_preview_panel_visible(True)
        if self._current_sample is None or self._base_frame is None:
            self._set_roi_preview_placeholder("Select a sample to preview the ROI.")
            return
        roi = self.canvas.rect_roi()
        if roi is None:
            self._set_roi_preview_placeholder("Draw an ROI on the preview.")
            return
        oriented = self._oriented_frame()
        if oriented is None:
            self._set_roi_preview_placeholder("No frame loaded.")
            return
        try:
            cropped = crop_rect_roi(oriented, roi)
        except (ValueError, IndexError):
            self._set_roi_preview_placeholder("ROI is outside the frame.")
            return
        if cropped.size == 0:
            self._set_roi_preview_placeholder("ROI crop is empty.")
            return
        self.lbl_roi_preview_empty.hide()
        self.roi_preview_canvas.show()
        self.roi_preview_canvas.set_preview_frame(cropped)

    def _show_tracking_settings_view(self) -> None:
        self._right_stack.setCurrentIndex(0)
        if hasattr(self, "_adjacent_panel_stack"):
            self._adjacent_panel_stack.setCurrentIndex(1)

    def _show_optical_flow_settings_view(self) -> None:
        self._right_stack.setCurrentIndex(1)
        if hasattr(self, "_adjacent_panel_stack"):
            self._adjacent_panel_stack.setCurrentIndex(1)

    def _show_cropped_metric_settings_view(self) -> None:
        if self._cropped_metric_mode == "optical_flow":
            self._show_optical_flow_settings_view()
        else:
            self._show_tracking_settings_view()

    def _set_metric_mode_widgets_visible(self, visible: bool) -> None:
        if hasattr(self, "_workbench_action_mode_slot"):
            from actintrack_app.gui_layout_builders import (
                WORKBENCH_ACTION_MODE_FULL,
                WORKBENCH_ACTION_MODE_METRIC,
            )

            self._workbench_action_mode_slot.setCurrentIndex(
                WORKBENCH_ACTION_MODE_METRIC if visible else WORKBENCH_ACTION_MODE_FULL
            )
            return
        for widget in getattr(self, "_metric_mode_widgets", ()):
            widget.setVisible(visible)

    def _sync_workbench_action_mode_slot(self) -> None:
        if not hasattr(self, "_workbench_action_mode_slot"):
            return
        has_sample = (
            self._current_sample_id is not None and self._base_frame is not None
        )
        if not has_sample:
            return
        self._set_metric_mode_widgets_visible(self._metric_analysis_view_active)

    def _sync_metric_mode_combo(self) -> None:
        idx = self.combo_metric_mode.findData(self._cropped_metric_mode)
        if idx >= 0:
            self.combo_metric_mode.blockSignals(True)
            self.combo_metric_mode.setCurrentIndex(idx)
            self.combo_metric_mode.blockSignals(False)

    def _on_cropped_metric_mode_changed(self, _index: int) -> None:
        mode = self.combo_metric_mode.currentData()
        if mode not in ("template", "optical_flow"):
            return
        self._cropped_metric_mode = str(mode)
        if self._preview_mode == "cropped_tracking":
            self._show_cropped_metric_settings_view()
            self._update_optical_flow_qc_readout()
            self._show_cropped_preview_frame(self._preview_frame_index)

    def _show_roi_controls_view(self) -> None:
        if hasattr(self, "_adjacent_panel_stack"):
            self._adjacent_panel_stack.setCurrentIndex(0)

    def _set_left_explorer_visible(self, visible: bool) -> None:
        """Show or hide the workspace tree (e.g. while Analysis is active)."""
        if not hasattr(self, "_left_sidebar"):
            return
        if visible:
            self._left_sidebar.show()
            if self._splitter_sizes_before_analysis:
                self._main_splitter.setSizes(self._splitter_sizes_before_analysis)
                self._splitter_sizes_before_analysis = None
            return
        if self._left_sidebar.isVisible():
            self._splitter_sizes_before_analysis = self._main_splitter.sizes()
        self._left_sidebar.hide()

    def _add_explorer_refresh_action(self, menu: QMenu) -> None:
        menu.addSeparator()
        refresh = menu.addAction(
            "Refresh Explorer",
            self._on_refresh_explorer,
        )
        refresh.setEnabled(self._project_root is not None)

    def _on_refresh_explorer(self) -> None:
        if self._require_project_root() is None:
            return
        self._refresh_sample_list()
        self._status("Explorer refreshed from workspace metadata.")

    def _on_explorer_sample_dropped(
        self, sample_id: str, target_condition_group_id: str
    ) -> None:
        if self._project_root is None:
            return
        if sample_id in self._metrics_inflight:
            QMessageBox.warning(
                self,
                "Move Sample",
                "Wait for metric analysis to finish before moving this Sample.",
            )
            return
        from actintrack_app.sample_transfer import (
            SampleMoveError,
            move_sample_to_condition_group,
        )

        try:
            result = move_sample_to_condition_group(
                self._project_root,
                sample_id,
                target_condition_group_id,
            )
        except SampleMoveError as exc:
            QMessageBox.critical(self, "Move Sample", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Move Sample",
                f"Could not move Sample folders on disk:\n{exc}",
            )
            return

        if not result.moved:
            return

        was_selected = str(self._current_sample_id or "") == sample_id
        self._refresh_sample_list()
        item = restore_selected_sample_by_id(self.tree_samples, sample_id)
        if item is None and was_selected:
            self._set_active_sample(None)
            self.reset_preview_state(
                clear_image=True,
                placeholder=self._SELECT_SAMPLE_HINT,
            )

        target_name = get_condition_group_name(
            self._project_root, result.target_condition_group_id
        )
        self._status(f"Moved Sample to Condition Group: {target_name}")

    def _on_return_to_samples(self) -> None:
        if self._center_stack.currentIndex() == 1:
            self._center_stack.setCurrentIndex(0)
        self._set_left_explorer_visible(True)

    def show_analysis_view(self) -> None:
        if self._preview_mode == "cropped_tracking":
            self._exit_cropped_preview_mode()
        self._set_left_explorer_visible(False)
        self._center_stack.setCurrentIndex(1)
        self.refresh_analysis_view()

    def refresh_analysis_view(self) -> None:
        if self._project_root is None:
            self._analysis_view.refresh(
                AnalysisReport([], [], [], "Open or create a workspace first.")
            )
            return
        try:
            report = build_analysis_report(self._project_root)
        except Exception as exc:
            self._analysis_view.refresh(
                AnalysisReport([], [], [], f"Could not load analysis data:\n{exc}")
            )
            return
        self._analysis_view.refresh(report)

    def _refresh_analysis_if_visible(self) -> None:
        if self._center_stack.currentIndex() == 1:
            self.refresh_analysis_view()

    def _set_tracking_settings_editable(self, editable: bool) -> None:
        widgets = getattr(self, "_tracking_setting_widgets", ())
        for widget in widgets:
            widget.setEnabled(editable)
        of_widgets = getattr(self, "_optical_flow_setting_widgets", ())
        for widget in of_widgets:
            widget.setEnabled(editable)

    def _sample_display_title(self, sample: Optional[dict[str, Any]] = None) -> str:
        sample = sample or self._current_sample
        if not sample:
            return ""
        group_id = str(
            sample.get("condition_group_id") or sample.get("group", "")
        ).strip()
        sample_label = sample_sidebar_display_label(sample)
        if group_id:
            display = ""
            if self._project_root is not None:
                display = condition_group_display_name(self._project_root, sample)
            return f"{display or group_id} / {sample_label}"
        return sample_label

    def _tracking_result_group_title(self, sample_id: Optional[str] = None) -> str:
        if sample_id is None:
            return tracking_result_group_title()
        sample = self._sample_row_for_id(sample_id) or self._current_sample
        display = self._sample_display_title(sample)
        if not display:
            display = sample_id
        return tracking_result_group_title(display)

    def _update_metric_analysis_button_visibility(self) -> None:
        has_sample = (
            self._current_sample_id is not None and self._base_frame is not None
        )
        if hasattr(self, "_sample_playback_host"):
            self._sample_playback_host.setVisible(has_sample)
        self._sync_workbench_action_mode_slot()
        if hasattr(self, "btn_run_metrics"):
            self.btn_run_metrics.setVisible(has_sample)
        if hasattr(self, "lbl_metric_status"):
            self.lbl_metric_status.setVisible(has_sample)
        if hasattr(self, "lbl_last_analyzed"):
            self.lbl_last_analyzed.setVisible(has_sample)
        self._update_metric_freshness_label()
        self._update_playback_controls_state()

    def _set_sample_playback_visible(self, visible: bool) -> None:
        for widget in getattr(self, "_sample_playback_widgets", ()):
            widget.setVisible(visible)

    def _playback_loop_enabled(self) -> bool:
        return bool(
            hasattr(self, "chk_playback_loop") and self.chk_playback_loop.isChecked()
        )

    def _sync_playback_toggle_buttons(self) -> None:
        label = "Pause" if self._preview_playing else "Play"
        if hasattr(self, "btn_playback_toggle"):
            self.btn_playback_toggle.setText(label)

    def _update_playback_controls_state(self) -> None:
        if not hasattr(self, "btn_playback_toggle"):
            return
        has_sample = (
            self._current_sample_id is not None and self._base_frame is not None
        )
        can_show_full = (
            has_sample
            and not self._metric_analysis_view_active
            and self._preview_mode == "full"
        )
        can_show_metric = (
            has_sample
            and self._metric_analysis_view_active
            and self._preview_mode == "cropped_tracking"
        )
        self._set_sample_playback_visible(can_show_full or can_show_metric)
        total = max(0, int(self._total_frames))
        can_scrub_full = can_show_full and total > 0
        can_play_full = can_show_full and total > 1
        cropped_count = (
            len(self._cropped_preview.frames)
            if self._cropped_preview is not None
            else 0
        )
        can_scrub_metric = can_show_metric and cropped_count > 0
        can_play_metric = can_show_metric and cropped_count > 1
        can_scrub = can_scrub_full or can_scrub_metric
        can_play = can_play_full or can_play_metric
        self.btn_playback_toggle.setEnabled(can_play or self._preview_playing)
        if hasattr(self, "slider_sample_frame"):
            self.slider_sample_frame.setEnabled(can_scrub)
        self._sync_playback_toggle_buttons()

    @staticmethod
    def _playback_interval_ms_for_speed_text(speed_text: str) -> int:
        mult = _PLAYBACK_SPEED_MULTIPLIERS.get(str(speed_text), 1.0)
        fps = max(1.0, _PLAYBACK_BASE_FPS * mult)
        return max(20, int(1000.0 / fps))

    def _sync_sample_frame_ui(self, index: int, total: int) -> None:
        """Update visible sample playback widgets and hidden frame index controls."""
        total = max(0, int(total))
        index = max(0, min(int(index), max(0, total - 1)))
        max_index = max(0, total - 1)
        if hasattr(self, "lbl_sample_frame"):
            if total <= 0:
                self.lbl_sample_frame.setText("Frame —")
            else:
                self.lbl_sample_frame.setText(f"Frame {index + 1} / {total}")
        if hasattr(self, "slider_sample_frame"):
            self.slider_sample_frame.blockSignals(True)
            self.slider_sample_frame.setMaximum(max_index)
            self.slider_sample_frame.setValue(index)
            self.slider_sample_frame.blockSignals(False)
        if hasattr(self, "slider_frame"):
            self.slider_frame.blockSignals(True)
            self.spin_frame.blockSignals(True)
            self.slider_frame.setMaximum(max_index)
            self.spin_frame.setMaximum(max_index)
            self.slider_frame.setValue(index)
            self.spin_frame.setValue(index)
            self.slider_frame.blockSignals(False)
            self.spin_frame.blockSignals(False)

    def _reset_sample_frame_ui(self) -> None:
        if hasattr(self, "lbl_sample_frame"):
            self.lbl_sample_frame.setText("Frame —")
        if hasattr(self, "slider_sample_frame"):
            self.slider_sample_frame.blockSignals(True)
            self.slider_sample_frame.setMaximum(0)
            self.slider_sample_frame.setValue(0)
            self.slider_sample_frame.blockSignals(False)

    def _on_sample_frame_slider(self, value: int) -> None:
        if self._preview_playing:
            self._playback_pause()
        if self._preview_mode == "cropped_tracking":
            if self._cropped_preview is None:
                return
            self._show_cropped_preview_frame(int(value))
            return
        if self._preview_mode != "full" or self._base_frame is None:
            return
        self._load_frame_index(int(value))

    def _on_sample_playback_speed_changed(self, _text: str) -> None:
        if self._preview_playing and self._preview_mode in ("full", "cropped_tracking"):
            self._update_playback_timer_interval()

    def _playback_interval_ms(self) -> int:
        return self._playback_interval_ms_for_speed_text(
            self.combo_sample_playback_speed.currentText()
        )

    def _playback_play(self) -> None:
        if self._preview_mode == "cropped_tracking" and self._cropped_preview is not None:
            if len(self._cropped_preview.frames) <= 1:
                return
            self._preview_playing = True
            self._update_playback_timer_interval()
            self._update_playback_controls_state()
            return
        if self._preview_mode != "full" or self._base_frame is None:
            return
        if self._total_frames <= 1:
            return
        self._preview_playing = True
        self._update_playback_timer_interval()
        self._update_playback_controls_state()

    def _update_playback_timer_interval(self) -> None:
        if self._preview_playing:
            self._preview_timer.start(self._playback_interval_ms())

    def _on_preview_speed_changed(self, _text: str) -> None:
        self._on_sample_playback_speed_changed(_text)

    def _playback_toggle(self) -> None:
        if self._preview_playing:
            self._playback_pause()
        else:
            self._playback_play()

    def _playback_pause(self) -> None:
        self._preview_playing = False
        self._preview_timer.stop()
        self._update_playback_controls_state()

    def _preview_play(self) -> None:
        """Backward-compatible alias."""
        self._playback_play()

    def _preview_pause(self) -> None:
        """Backward-compatible alias."""
        self._playback_pause()

    def _clear_metric_preview_state(self) -> None:
        self._clear_sample_specific_metric_state()

    def _clear_sample_specific_metric_state(self) -> None:
        self._preview_pause()
        self._metric_debounce_timer.stop()
        self._metric_settings_timer.stop()
        self._cancel_pending_debounced_tracking()
        self._cropped_preview = None
        self._preview_frame_index = 0
        self._clear_of_flow_cache()
        self.canvas.clear_preview()
        if hasattr(self, "lbl_sample_frame"):
            self.lbl_sample_frame.setText("—")
        self.lbl_frame_info.setText("—")

    def _ensure_metric_view_shell_visible(self) -> None:
        self._center_stack.setCurrentIndex(0)
        self._metric_analysis_view_active = True
        self._preview_mode = "cropped_tracking"
        self.canvas.set_interactive(False)
        self._set_preview_controls_visible(True)
        self._set_metric_mode_widgets_visible(True)
        self._sync_metric_mode_combo()
        self._set_tracking_settings_editable(True)
        self._show_cropped_metric_settings_view()
        self._refresh_roi_preview_panel()

    def _reload_metric_analysis_view_for_current_sample(
        self,
        *,
        resume_playback: bool = False,
    ) -> bool:
        self._ensure_metric_view_shell_visible()
        self._set_preview_mode_banner(f"{_METRIC_ANALYSIS_VIEW_LABEL} — loading…")
        self.update_tracking_result_panel()
        self._update_optical_flow_qc_readout()
        return self.enter_metric_analysis_view_for_current_sample(
            quiet=True,
            resume_playback=resume_playback,
        )

    def _display_metric_analysis_view_for_current_sample(
        self,
        *,
        resume_playback: bool = False,
    ) -> None:
        """Show Metric Analysis shell and any cached/draft results without recomputing."""
        self._ensure_metric_view_shell_visible()
        self.update_tracking_result_panel()
        self._update_optical_flow_qc_readout()
        sid = self._current_sample_id
        if sid is None:
            self._show_metric_analysis_placeholder("Select a sample first.")
            return
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            message = check.message or (
                "Metric Analysis is unavailable because this Sample "
                "does not have a saved ROI."
            )
            self._show_metric_analysis_placeholder(message)
            return
        cached = self._tracking_results_by_sample.get(sid)
        if cached is not None:
            self._enter_cropped_preview_mode(cached)
            if resume_playback:
                self._preview_play()
            return
        self._show_metric_analysis_placeholder(
            "Run Metrics to generate the analysis preview."
        )

    def _set_active_sample(self, sample: Optional[dict[str, Any]]) -> None:
        self._cancel_pending_debounced_tracking()
        prev_sid = self._current_sample_id
        self._current_sample = sample
        sid = str(sample.get("sample_id", "")).strip() if sample else ""
        self._current_sample_id = sid or None
        if sample is None:
            self._loaded_sample_notes = ""
        if prev_sid and prev_sid != self._current_sample_id:
            self._of_flow_caches.pop(prev_sid, None)

    def _on_tracking_setting_changed(self, *_args: object) -> None:
        if self._current_sample_id:
            self._tracking_result_stale_by_sample[self._current_sample_id] = True
            self._optical_flow_stale_by_sample[self._current_sample_id] = True
            self.update_tracking_result_panel()
        self._update_metric_freshness_label()

    def _on_optical_flow_setting_changed(self, *_args: object) -> None:
        if self._current_sample_id:
            self._optical_flow_stale_by_sample[self._current_sample_id] = True
            self._clear_of_flow_cache(self._current_sample_id)
            self._update_optical_flow_qc_readout()
            self.update_tracking_result_panel()
        self._update_metric_freshness_label()

    @staticmethod
    def _status_after_roi_autosave(current_status: str) -> Optional[str]:
        current = str(current_status).strip()
        if current in _ADVANCED_SAMPLE_STATUSES:
            return None
        if current == STATUS_ROI_MARKED:
            return None
        if current in _ROI_STATUS_UPGRADE_FROM:
            return STATUS_ROI_MARKED
        if current in (STATUS_ROI_PROPAGATED, STATUS_ROI_APPROVED):
            return None
        return STATUS_ROI_MARKED

    def _cancel_pending_debounced_tracking(self) -> None:
        self._metric_debounce_timer.stop()
        self._metric_settings_timer.stop()
        self._tracking_run_token += 1
        self._optical_flow_run_token += 1
        self._pending_tracking_snapshot = None
        self._pending_optical_flow_snapshot = None

    def _capture_tracking_snapshot(self) -> Optional[_TrackingRunSnapshot]:
        if self._current_sample_id is None or self._current_sample is None:
            return None
        roi = self.canvas.rect_roi()
        if roi is None:
            return None
        path = self._sample_file_path()
        if path is None or not path.exists() or not is_supported_video_path(path):
            return None
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            return None
        try:
            params = self._tracking_params_from_ui()
        except ValueError:
            return None
        return _TrackingRunSnapshot(
            sample_id=self._current_sample_id,
            roi_key=(roi.x, roi.y, roi.width, roi.height),
            params_key=tuple(sorted(asdict(params).items())),
            orientation_key=(
                float(self._orientation.rotation_angle_degrees),
                bool(self._orientation.mirror_y_axis),
                bool(self._orientation.flipped_180),
            ),
            video_path=str(path.resolve()),
            run_token=self._tracking_run_token,
        )

    def _snapshot_matches_current(self, snapshot: _TrackingRunSnapshot) -> bool:
        if snapshot.run_token != self._tracking_run_token:
            return False
        current = self._capture_tracking_snapshot()
        if current is None:
            return False
        return (
            current.sample_id == snapshot.sample_id
            and current.roi_key == snapshot.roi_key
            and current.params_key == snapshot.params_key
            and current.orientation_key == snapshot.orientation_key
            and current.video_path == snapshot.video_path
        )

    def _schedule_debounced_metrics(self) -> None:
        track_snap = self._capture_tracking_snapshot()
        of_snap = self._capture_optical_flow_snapshot()
        if track_snap is None and of_snap is None:
            return
        if track_snap is not None:
            self._pending_tracking_snapshot = track_snap
        if of_snap is not None:
            if self._current_sample_id:
                self._clear_of_flow_cache(self._current_sample_id)
            self._pending_optical_flow_snapshot = of_snap
        self._metric_debounce_timer.start()
        self._update_metric_freshness_label()

    def _schedule_metric_settings_refresh(self) -> None:
        if self._preview_mode != "cropped_tracking":
            return
        track_snap = self._capture_tracking_snapshot()
        of_snap = self._capture_optical_flow_snapshot()
        if track_snap is None and of_snap is None:
            return
        if track_snap is not None:
            self._pending_tracking_snapshot = track_snap
        if of_snap is not None:
            if self._current_sample_id:
                self._clear_of_flow_cache(self._current_sample_id)
            self._pending_optical_flow_snapshot = of_snap
        self._metric_settings_timer.start()

    def _on_metric_debounce_fired(self) -> None:
        track_snap = self._pending_tracking_snapshot
        of_snap = self._pending_optical_flow_snapshot
        self._pending_tracking_snapshot = None
        self._pending_optical_flow_snapshot = None
        try:
            if track_snap is not None:
                self._run_draft_tracking_for_snapshot(
                    track_snap,
                    update_cropped_preview=self._preview_mode == "cropped_tracking",
                    quiet_skip=True,
                )
            if of_snap is not None:
                self._run_optical_flow_for_snapshot(of_snap, quiet_skip=True)
        finally:
            self._update_metric_freshness_label()

    def _on_metric_settings_debounce_fired(self) -> None:
        if self._preview_mode != "cropped_tracking":
            return
        self._on_metric_debounce_fired()

    def _optical_flow_settings_from_ui(self) -> OpticalFlowSettings:
        blur = int(self.combo_of_blur.currentData() or 0)
        return OpticalFlowSettings(
            mask_percentile=float(self.spin_of_mask_percentile.value()),
            gaussian_blur_kernel=blur,
            pyr_scale=float(self.spin_of_pyr_scale.value()),
            levels=int(self.spin_of_levels.value()),
            winsize=int(self.spin_of_winsize.value()),
            iterations=int(self.spin_of_iterations.value()),
            poly_n=int(self.spin_of_poly_n.value()),
            poly_sigma=float(self.spin_of_poly_sigma.value()),
            microns_per_pixel=float(self.spin_track_mpp.value()),
            seconds_per_frame=float(self.spin_track_spf.value()),
        )

    def _capture_optical_flow_snapshot(self) -> Optional[_OpticalFlowRunSnapshot]:
        if self._current_sample_id is None or self._current_sample is None:
            return None
        roi = self.canvas.rect_roi()
        if roi is None:
            return None
        path = self._sample_file_path()
        if path is None or not path.exists() or not is_supported_video_path(path):
            return None
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            return None
        try:
            settings = self._optical_flow_settings_from_ui()
        except ValueError:
            return None
        return _OpticalFlowRunSnapshot(
            sample_id=self._current_sample_id,
            roi_key=(roi.x, roi.y, roi.width, roi.height),
            settings_key=tuple(sorted(asdict(settings).items())),
            orientation_key=(
                float(self._orientation.rotation_angle_degrees),
                bool(self._orientation.mirror_y_axis),
                bool(self._orientation.flipped_180),
            ),
            video_path=str(path.resolve()),
            run_token=self._optical_flow_run_token,
        )

    def _optical_flow_snapshot_matches_current(
        self, snapshot: _OpticalFlowRunSnapshot
    ) -> bool:
        if snapshot.run_token != self._optical_flow_run_token:
            return False
        current = self._capture_optical_flow_snapshot()
        if current is None:
            return False
        return (
            current.sample_id == snapshot.sample_id
            and current.roi_key == snapshot.roi_key
            and current.settings_key == snapshot.settings_key
            and current.orientation_key == snapshot.orientation_key
            and current.video_path == snapshot.video_path
        )

    def _draft_optical_flow_json_path(self, data_id: str) -> Path:
        assert self._project_root is not None
        from actintrack_app.schema_compat import draft_optical_flow_path

        return draft_optical_flow_path(self._project_root, data_id)

    def _run_optical_flow_for_snapshot(
            self,
        snapshot: _OpticalFlowRunSnapshot,
        *,
        quiet_skip: bool = True,
    ) -> bool:
        if self._optical_flow_job_running:
            return False
        if snapshot.sample_id != self._current_sample_id:
            return False
        if not self._optical_flow_snapshot_matches_current(snapshot):
            if not quiet_skip:
                self._status("Optical flow paused — ROI changed")
                self._update_metric_freshness_label()
            return False
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            return False
        path = Path(snapshot.video_path)
        if not path.is_file() or not is_supported_video_path(path):
            return False
        try:
            settings = self._optical_flow_settings_from_ui()
        except ValueError:
            return False

        roi_bounds = (
            int(check.roi_oriented.x),
            int(check.roi_oriented.y),
            int(check.roi_oriented.width),
            int(check.roi_oriented.height),
        )
        self._optical_flow_job_running = True
        self._update_optical_flow_qc_readout()
        QApplication.processEvents()
        try:
            frames = load_cropped_frames_from_video(
                path, self._orientation, check.roi_oriented
            )
            fingerprint = build_optical_flow_fingerprint(
                sample_id=snapshot.sample_id,
                roi_bounds=roi_bounds,
                settings=settings,
                data_identity=str(path.resolve()),
                frame_count=len(frames),
            )
            result = compute_optical_flow_motion_index(
                frames,
                settings,
                sample_id=snapshot.sample_id,
                data_identity=str(path.resolve()),
                roi_bounds=roi_bounds,
                fingerprint=fingerprint,
            )
        except Exception:
            if not quiet_skip:
                self._status("Optical flow failed")
                self._update_metric_freshness_label()
            return False
        finally:
            self._optical_flow_job_running = False

        if not self._optical_flow_snapshot_matches_current(snapshot):
            if not quiet_skip:
                self._status("Optical flow paused — settings changed")
                self._update_metric_freshness_label()
            return False

        self._clear_of_flow_cache(snapshot.sample_id)
        self._commit_optical_flow_result(snapshot.sample_id, result)
        if self._preview_mode == "cropped_tracking":
            self._show_cropped_preview_frame(self._preview_frame_index)
        return True

    def _save_draft_optical_flow_result(
        self, sample_id: str, result: OpticalFlowResult
    ) -> None:
        if self._project_root is None:
            return
        path = self._draft_optical_flow_json_path(sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result_to_dict(result), indent=2), encoding="utf-8")

    def _invalidate_optical_flow_for_sample(self, sample_id: str) -> None:
        self._optical_flow_results_by_sample.pop(sample_id, None)
        self._optical_flow_stale_by_sample.pop(sample_id, None)
        self._of_flow_caches.pop(sample_id, None)
        if self._project_root is not None:
            draft_path = self._draft_optical_flow_json_path(sample_id)
            if draft_path.is_file():
                try:
                    draft_path.unlink()
                except OSError:
                    pass

    def _clear_of_flow_cache(self, sample_id: Optional[str] = None) -> None:
        if sample_id is None:
            self._of_flow_caches.clear()
        else:
            self._of_flow_caches.pop(sample_id, None)

    def _optical_flow_viz_settings_from_ui(self) -> OpticalFlowVisualizationSettings:
        return OpticalFlowVisualizationSettings(
            arrow_spacing_px=int(self.spin_of_arrow_spacing.value()),
            arrow_scale=float(self.spin_of_arrow_scale.value()),
        )

    def _current_optical_flow_fingerprint(self) -> str:
        if self._current_sample_id is None or self._cropped_preview is None:
            return ""
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            return ""
        path = self._sample_file_path()
        data_identity = str(path.resolve()) if path is not None else ""
        roi_bounds = (
            int(check.roi_oriented.x),
            int(check.roi_oriented.y),
            int(check.roi_oriented.width),
            int(check.roi_oriented.height),
        )
        try:
            settings = self._optical_flow_settings_from_ui()
        except ValueError:
            return ""
        return build_optical_flow_fingerprint(
            sample_id=self._current_sample_id,
            roi_bounds=roi_bounds,
            settings=settings,
            data_identity=data_identity,
            frame_count=len(self._cropped_preview.frames),
        )

    def _get_optical_flow_result_object(
        self, sample_id: str
    ) -> Optional[OpticalFlowResult]:
        cached = self._optical_flow_results_by_sample.get(sample_id)
        if cached is not None:
            return cached
        if self._project_root is not None:
            from actintrack_app.schema_compat import resolve_draft_optical_flow_path

            draft_path = resolve_draft_optical_flow_path(self._project_root, sample_id)
            if draft_path is not None:
                try:
                    data = json.loads(draft_path.read_text(encoding="utf-8"))
                    return result_from_dict(data)
                except (OSError, json.JSONDecodeError):
                    pass
        return None

    def _optical_flow_qc_status_for_sample(self, sample_id: str) -> str:
        result = self._get_optical_flow_result_object(sample_id)
        fingerprint = self._current_optical_flow_fingerprint() if sample_id == self._current_sample_id else ""
        return resolve_qc_status(
            result=result,
            is_computing=self._optical_flow_job_running and sample_id == self._current_sample_id,
            is_stale_flag=bool(self._optical_flow_stale_by_sample.get(sample_id)),
            current_fingerprint=fingerprint,
        )

    def _update_optical_flow_qc_readout(self) -> None:
        if not hasattr(self, "lbl_of_qc"):
            return
        sid = self._current_sample_id
        if sid is None:
            self.lbl_of_qc.setText("QC: —")
            return
        result = self._get_optical_flow_result_object(sid)
        status = self._optical_flow_qc_status_for_sample(sid)
        qc = format_optical_flow_qc(result)
        lines = [
            f"Status: {status}",
            f"General Movement: {qc['general_movement']} µm/s",
            f"Downward Motion: {qc['downward_motion']} µm/s",
            f"Net Y Velocity: {qc['net_y_velocity']} µm/s",
            f"Directionality Ratio: {qc['directionality_ratio']}",
            f"Valid Pixel Fraction: {qc['valid_pixel_fraction']}",
            f"Saturated Pixel Fraction: {qc['saturated_pixel_fraction']}",
            f"Frame pairs used: {qc['frame_pairs_used']}",
        ]
        self.lbl_of_qc.setText("\n".join(lines))

    def _ensure_of_flow_cache(self) -> Optional[OpticalFlowFlowCache]:
        if self._current_sample_id is None or self._cropped_preview is None:
            return None
        fingerprint = self._current_optical_flow_fingerprint()
        if not fingerprint:
            return None
        sid = self._current_sample_id
        existing = self._of_flow_caches.get(sid)
        if existing is not None and existing.fingerprint == fingerprint:
            return existing
        try:
            settings = self._optical_flow_settings_from_ui()
        except ValueError:
            return None
        cache = build_flow_cache(
            self._cropped_preview.frames,
            settings,
            sample_id=sid,
            fingerprint=fingerprint,
        )
        self._of_flow_caches[sid] = cache
        return cache

    def _get_overlay_arrows_for_frame(self, frame_index: int) -> list:
        cache = self._ensure_of_flow_cache()
        if cache is None or self._cropped_preview is None:
            return []
        return get_flow_arrows_for_frame(
            cache,
            frame_index,
            len(self._cropped_preview.frames),
            self._optical_flow_viz_settings_from_ui(),
        )

    def _on_show_of_overlay_changed(self, _checked: bool) -> None:
        if self._preview_mode == "cropped_tracking":
            self._show_cropped_preview_frame(self._preview_frame_index)

    def _on_of_viz_setting_changed(self, *_args: object) -> None:
        if self._preview_mode == "cropped_tracking":
            self._show_cropped_preview_frame(self._preview_frame_index)

    def _commit_optical_flow_result(
        self, sample_id: str, result: OpticalFlowResult
    ) -> None:
        if sample_id != self._current_sample_id:
            return
        self._optical_flow_results_by_sample[sample_id] = result
        self._optical_flow_stale_by_sample.pop(sample_id, None)
        self._clear_of_flow_cache(sample_id)
        self._save_draft_optical_flow_result(sample_id, result)
        self._update_optical_flow_qc_readout()
        self.update_tracking_result_panel(sample_id)
        self._update_metric_freshness_label()
        self._refresh_analysis_if_visible()

    def load_latest_optical_flow_result_for_sample(
        self, sample_id: str
    ) -> Optional[OpticalFlowResultView]:
        return load_latest_optical_flow_result_view(
            sample_id,
            project_root=self._project_root,
            cached_result=self._optical_flow_results_by_sample.get(sample_id),
        )

    def _run_draft_tracking_for_snapshot(
        self,
        snapshot: _TrackingRunSnapshot,
        *,
        update_cropped_preview: bool,
        quiet_skip: bool = True,
    ) -> bool:
        if self._tracking_job_running:
            return False
        if snapshot.sample_id != self._current_sample_id:
            return False
        if not self._snapshot_matches_current(snapshot):
            if not quiet_skip:
                self._status("Tracking paused — ROI changed")
                self._update_metric_freshness_label()
            return False
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            return False
        path = Path(snapshot.video_path)
        if not path.is_file() or not is_supported_video_path(path):
            return False
        try:
            params = self._tracking_params_from_ui()
        except ValueError:
            return False
        crop_w = int(check.roi_oriented.width)
        crop_h = int(check.roi_oriented.height)
        min_dim = params.template_patch_size_px + (2 * params.search_radius_px) + 2
        if min(crop_w, crop_h) < min_dim:
            return False

        self._tracking_job_running = True
        QApplication.processEvents()
        try:
            frames = load_cropped_frames_from_video(
                path, self._orientation, check.roi_oriented
            )
            analysis = analyze_cropped_preview(frames, params=params)
        except Exception:
            if not quiet_skip:
                self._status("Tracking failed")
                self._update_metric_freshness_label()
            return False
        finally:
            self._tracking_job_running = False

        if not self._snapshot_matches_current(snapshot):
            if not quiet_skip:
                self._status("Tracking paused — ROI changed")
                self._update_metric_freshness_label()
            return False

        self._commit_tracking_result(snapshot.sample_id, analysis, params)
        if update_cropped_preview and self._preview_mode == "cropped_tracking":
            self._cropped_preview = analysis
            max_index = max(0, len(analysis.frames) - 1)
            self.slider_frame.setMaximum(max_index)
            self.spin_frame.setMaximum(max_index)
            self.slider_sample_frame.setMaximum(max_index)
            frame_idx = min(self._preview_frame_index, max_index)
            self._show_cropped_preview_frame(frame_idx)
        return True

    def _update_sample_list_row_for_id(self, sample_id: str) -> None:
        item = self._find_sample_tree_item(sample_id)
        if item is None:
            return
        data = self._tree_item_meta(item)
        if not data or data.get("item_type") != ITEM_TYPE_SAMPLE:
            return
        if (
            self._current_sample is not None
            and str(self._current_sample.get("sample_id")) == str(sample_id)
        ):
            data = dict(self._current_sample)
            data["item_type"] = ITEM_TYPE_SAMPLE
        status = str(data.get("processing_status", ""))
        item.setText(0, sample_sidebar_display_label(data))
        item.setData(0, Qt.ItemDataRole.UserRole, data)
        color = STATUS_COLORS.get(status)
        if color:
            item.setForeground(0, QBrush(color))

    def _draft_tracking_json_path(self, data_id: str) -> Path:
        assert self._project_root is not None
        from actintrack_app.schema_compat import draft_tracking_path

        return draft_tracking_path(self._project_root, data_id)

    def _sample_row_for_id(self, sample_id: str) -> Optional[dict[str, Any]]:
        if (
            self._current_sample is not None
            and str(self._current_sample.get("sample_id", "")) == sample_id
        ):
            return self._current_sample
        if self._project_root is None:
            return None
        df = load_samples_csv(self._project_root / METADATA_DIR / SAMPLES_CSV)
        rows = df[df["sample_id"].astype(str) == str(sample_id)]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def load_latest_tracking_result_for_sample(
        self, sample_id: str
    ) -> Optional[SampleTrackingResultView]:
        return load_latest_tracking_result_view(
            sample_id,
            project_root=self._project_root,
            sample_row=self._sample_row_for_id(sample_id),
            cached_preview=self._tracking_results_by_sample.get(sample_id),
        )

    def _render_tracking_result_panel(
        self,
        template_view: Optional[SampleTrackingResultView],
        optical_flow_view: Optional[OpticalFlowResultView],
        *,
        template_stale: bool = False,
        optical_flow_stale: bool = False,
    ) -> None:
        if self.__dict__.get("lbl_tracking_result") is None:
            return
        sid = self._current_sample_id
        of_status = self._optical_flow_qc_status_for_sample(sid) if sid else "Not computed"
        result_obj = self._get_optical_flow_result_object(sid) if sid else None
        frame_pairs = (
            str(result_obj.frame_pair_count)
            if result_obj is not None and result_obj.frame_pair_count
            else "—"
        )
        text = format_tracking_result_panel_lines(
            template_view,
            optical_flow_view,
            template_stale=template_stale,
            optical_flow_stale=optical_flow_stale,
            optical_flow_qc_status=of_status,
            optical_flow_frame_pair_count=frame_pairs,
        )
        self.lbl_tracking_result.setText(text)

    def update_tracking_result_panel(self, sample_id: Optional[str] = None) -> None:
        if self.__dict__.get("lbl_tracking_result") is None:
            return
        sid = sample_id or self._current_sample_id
        if sid is None:
            self.grp_tracking_result.setTitle(self._tracking_result_group_title())
            self.lbl_tracking_result.setText("")
            return
        if sid != self._current_sample_id:
            return
        self.grp_tracking_result.setTitle(self._tracking_result_group_title(sid))
        self._render_tracking_result_panel(
            self.load_latest_tracking_result_for_sample(sid),
            self.load_latest_optical_flow_result_for_sample(sid),
            template_stale=bool(self._tracking_result_stale_by_sample.get(sid)),
            optical_flow_stale=bool(self._optical_flow_stale_by_sample.get(sid)),
        )

    def _save_draft_tracking_result(
                self,
        sample_id: str,
        analysis: CroppedPreviewAnalysis,
        params: MotionIndexParams,
    ) -> None:
        if self._project_root is None:
            return
        path = self._draft_tracking_json_path(sample_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "data_id": sample_id,
            "sample_id": sample_id,
            "primary_velocity_metric": "absolute_velocity_index_um_per_s",
            "primary_velocity_index_um_per_s": analysis.general_movement_index_um_per_s,
            "absolute_velocity_index_um_per_s": analysis.general_movement_index_um_per_s,
            "downward_velocity_index_um_per_s": analysis.downward_velocity_index_um_per_s,
            "downward_velocity_index_definition": (
                "mean(dy/dt | dy > 0); increasing image y is downward"
            ),
            "time_weighted_mean_speed_um_per_s": (
                analysis.time_weighted_mean_speed_um_per_s
            ),
            "signed_vertical_velocity_um_per_s": (
                analysis.signed_vertical_velocity_um_per_s
            ),
            "downward_velocity_contribution_um_per_s": (
                analysis.downward_velocity_contribution_um_per_s
            ),
            "general_movement_index_um_per_s": analysis.general_movement_index_um_per_s,
            "num_tracks_with_valid_steps": analysis.num_tracks_with_valid_steps,
            "num_tracks_started": analysis.num_tracks_started,
            "num_tracks_requested": params.num_starting_points,
            "total_valid_steps": analysis.total_valid_steps,
            "tracking_warning": analysis.tracking_warning,
            "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "parameters": asdict(params),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _invalidate_tracking_result_for_sample(self, sample_id: str) -> None:
        self._tracking_results_by_sample.pop(sample_id, None)
        self._tracking_result_stale_by_sample.pop(sample_id, None)
        if self._project_root is not None:
            draft_path = self._draft_tracking_json_path(sample_id)
            if draft_path.is_file():
                try:
                    draft_path.unlink()
                except OSError:
                    pass
        self._invalidate_optical_flow_for_sample(sample_id)

    def _commit_tracking_result(
        self,
        sample_id: str,
        analysis: CroppedPreviewAnalysis,
        params: MotionIndexParams,
    ) -> None:
        if sample_id != self._current_sample_id:
            return
        self._tracking_results_by_sample[sample_id] = analysis
        self._tracking_result_stale_by_sample.pop(sample_id, None)
        self._save_draft_tracking_result(sample_id, analysis, params)
        self.update_tracking_result_panel(sample_id)
        self._update_metric_freshness_label()
        self._refresh_analysis_if_visible()

    # ----- Decoupled per-Sample metric calculation -------------------------
    # The live-canvas debounce path keeps the Metric Analysis View preview in
    # sync for the *current* Sample. These helpers compute metrics for any
    # Sample from its *saved* orientation + ROI so quick Sample switching never
    # loses analysis. Results commit by sample_id regardless of which Sample is
    # currently selected.

    def _commit_tracking_result_for_sid(
        self,
        sample_id: str,
        analysis: CroppedPreviewAnalysis,
        params: MotionIndexParams,
    ) -> None:
        self._tracking_results_by_sample[sample_id] = analysis
        self._tracking_result_stale_by_sample.pop(sample_id, None)
        self._save_draft_tracking_result(sample_id, analysis, params)
        if sample_id == self._current_sample_id:
            self.update_tracking_result_panel(sample_id)

    def _commit_optical_flow_result_for_sid(
        self, sample_id: str, result: OpticalFlowResult
    ) -> None:
        self._optical_flow_results_by_sample[sample_id] = result
        self._optical_flow_stale_by_sample.pop(sample_id, None)
        self._clear_of_flow_cache(sample_id)
        self._save_draft_optical_flow_result(sample_id, result)
        if sample_id == self._current_sample_id:
            self._update_optical_flow_qc_readout()
            self.update_tracking_result_panel(sample_id)

    def _saved_orientation_roi_for_sample(
        self, sample_id: str
    ) -> tuple[Optional[OrientationState], Optional[RectROI]]:
        if self._project_root is None:
            return None, None
        ann = get_sample_annotation(self._project_root, sample_id)
        if not ann:
            return None, None
        orientation, roi = annotation_from_legacy(ann)
        return orientation, roi

    def _sample_video_path(self, sample_id: str) -> Optional[Path]:
        row = self._sample_row_for_id(sample_id)
        if row is None or self._project_root is None:
            return None
        stored = str(row.get("stored_path", "")).strip()
        if not stored:
            return None
        path = self._project_root / stored
        if not path.is_file() or not is_supported_video_path(path):
            return None
        return path

    def _sample_has_valid_data_and_roi(self, sample_id: str) -> bool:
        if self._sample_video_path(sample_id) is None:
            return False
        _orientation, roi = self._saved_orientation_roi_for_sample(sample_id)
        return roi is not None

    @staticmethod
    def _roi_key_from_rect(roi: Optional[RectROI]) -> tuple[int, int, int, int] | None:
        if roi is None:
            return None
        return (int(roi.x), int(roi.y), int(roi.width), int(roi.height))

    def _saved_roi_key_for_sample(
        self, sample_id: str
    ) -> tuple[int, int, int, int] | None:
        if self._project_root is None:
            return None
        ann = get_sample_annotation(self._project_root, sample_id)
        if not ann:
            return None
        _orientation, roi = annotation_from_legacy(ann)
        return self._roi_key_from_rect(roi)

    def _sample_has_measurable_draft_results(self, sample_id: str) -> bool:
        track = self._read_draft_tracking_payload(sample_id)
        of_payload = self._read_draft_optical_flow_payload(sample_id)
        track_ok = bool(
            track
            and int(track.get("num_tracks_with_valid_steps", 0) or 0) > 0
        )
        of_ok = bool(of_payload and of_payload.get("has_valid_result"))
        return track_ok or of_ok

    def _mark_metrics_stale_if_saved_roi_changed(
        self,
        sample_id: str,
        *,
        previous_roi_key: tuple[int, int, int, int] | None,
        new_roi_key: tuple[int, int, int, int] | None,
    ) -> None:
        if previous_roi_key is None or new_roi_key is None:
            return
        if previous_roi_key == new_roi_key:
            return
        if not self._sample_has_measurable_draft_results(sample_id):
            return
        self._tracking_result_stale_by_sample[sample_id] = True
        self._optical_flow_stale_by_sample[sample_id] = True

    def _compute_metrics_for_sample(self, sample_id: str) -> str:
        """Compute Template Tracking + Optical Flow for one Sample from its
        saved orientation/ROI and current metric settings.

        Returns one of: 'unavailable', 'running', 'error', 'analyzed'.
        """
        if self._project_root is None:
            return "unavailable"
        if sample_id in self._metrics_inflight:
            return "running"
        path = self._sample_video_path(sample_id)
        if path is None:
            return "unavailable"
        orientation, roi = self._saved_orientation_roi_for_sample(sample_id)
        if roi is None or orientation is None:
            return "unavailable"
        try:
            params = self._tracking_params_from_ui()
            of_settings = self._optical_flow_settings_from_ui()
        except ValueError:
            self._metric_error_by_sample[sample_id] = True
            return "error"
        crop_w, crop_h = int(roi.width), int(roi.height)
        min_dim = params.template_patch_size_px + (2 * params.search_radius_px) + 2
        if min(crop_w, crop_h) < min_dim:
            self._metric_error_by_sample[sample_id] = True
            return "error"

        self._metrics_inflight.add(sample_id)
        self._update_metric_freshness_label()
        QApplication.processEvents()
        had_error = False
        ok_any = False
        try:
            frames = load_cropped_frames_from_video(path, orientation, roi)
            try:
                analysis = analyze_cropped_preview(frames, params=params)
                self._commit_tracking_result_for_sid(sample_id, analysis, params)
                if analysis.num_tracks_with_valid_steps == 0:
                    had_error = True
                else:
                    ok_any = True
            except Exception:
                had_error = True
            roi_bounds = (int(roi.x), int(roi.y), int(roi.width), int(roi.height))
            try:
                fingerprint = build_optical_flow_fingerprint(
                    sample_id=sample_id,
                    roi_bounds=roi_bounds,
                    settings=of_settings,
                    data_identity=str(path.resolve()),
                    frame_count=len(frames),
                )
                result = compute_optical_flow_motion_index(
                    frames,
                    of_settings,
                    sample_id=sample_id,
                    data_identity=str(path.resolve()),
                    roi_bounds=roi_bounds,
                    fingerprint=fingerprint,
                )
                self._commit_optical_flow_result_for_sid(sample_id, result)
                if result.has_valid_result:
                    ok_any = True
                else:
                    had_error = True
            except Exception:
                had_error = True
        except Exception:
            had_error = True
        finally:
            self._metrics_inflight.discard(sample_id)

        self._metric_error_by_sample[sample_id] = had_error and not ok_any
        if sample_id == self._current_sample_id:
            self.update_tracking_result_panel(sample_id)
        self._update_metric_freshness_label()
        self._refresh_analysis_if_visible()
        if had_error and not ok_any:
            return "error"
        return "analyzed"

    def ensure_metrics_scheduled_for_sample_if_needed(
        self, sample_id: Optional[str], reason: str = ""
    ) -> None:
        """Queue metric calculation for a Sample if it has valid Data + ROI and
        its metrics are missing/stale and not already queued or running."""
        if not sample_id or self._project_root is None:
            return
        if sample_id in self._metrics_inflight:
            return
        if sample_id in self._metric_compute_queue:
            return
        if not self._sample_has_valid_data_and_roi(sample_id):
            return
        state = self._metric_state_for_sample(sample_id)
        if state in ("analyzed", "running", "scheduled"):
            return
        self._metric_compute_queue.append(sample_id)
        if not self._metric_flush_timer.isActive():
            self._metric_flush_timer.start()
        if sample_id == self._current_sample_id:
            self._update_metric_freshness_label()

    def _on_metric_flush_timer(self) -> None:
        if not self._metric_compute_queue:
            return
        sample_id = self._metric_compute_queue.pop(0)
        try:
            self._compute_metrics_for_sample(sample_id)
        finally:
            if self._metric_compute_queue:
                self._metric_flush_timer.start()

    def run_metrics_now_for_current_sample(self) -> None:
        sid = self._current_sample_id
        if not sid:
            return
        if sid in self._metrics_inflight:
            self._update_metric_freshness_label()
            return
        if not self._sample_has_valid_data_and_roi(sid):
            self._status(
                "Run Metrics requires a Sample with valid Data and a saved ROI."
            )
            self._update_metric_freshness_label()
            return
        if sid in self._metric_compute_queue:
            self._metric_compute_queue.remove(sid)
        self._compute_metrics_for_sample(sid)

    # ----- Metric freshness state + rendering ------------------------------

    def _read_draft_tracking_payload(self, sid: str) -> Optional[dict[str, Any]]:
        if self._project_root is None:
            return None
        from actintrack_app.schema_compat import resolve_draft_tracking_path

        path = resolve_draft_tracking_path(self._project_root, sid)
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _read_draft_optical_flow_payload(self, sid: str) -> Optional[dict[str, Any]]:
        if self._project_root is None:
            return None
        from actintrack_app.schema_compat import resolve_draft_optical_flow_path

        path = resolve_draft_optical_flow_path(self._project_root, sid)
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _metric_state_for_sample(self, sid: Optional[str]) -> str:
        if not sid:
            return "unavailable_no_roi"
        if sid in self._metrics_inflight:
            return "running"
        if sid == self._current_sample_id and (
            self._tracking_job_running or self._optical_flow_job_running
        ):
            return "running"
        if not self._sample_has_valid_data_and_roi(sid):
            return "unavailable_no_roi"

        track = self._read_draft_tracking_payload(sid)
        of = self._read_draft_optical_flow_payload(sid)
        track_present = track is not None
        of_present = of is not None
        if not track_present and not of_present:
            return "not_analyzed"
        track_ok = track_present and int(
            track.get("num_tracks_with_valid_steps", 0) or 0
        ) > 0
        of_ok = of_present and bool(of.get("has_valid_result"))
        stale_flag = bool(
            self._tracking_result_stale_by_sample.get(sid)
        ) or bool(self._optical_flow_stale_by_sample.get(sid))
        error_flag = bool(self._metric_error_by_sample.get(sid)) or (
            track_present and not track_ok
        ) or (of_present and not of_ok)
        if error_flag:
            return "error"
        if stale_flag:
            return "stale"
        if track_ok and of_ok:
            return "analyzed"
        # Only one metric present (e.g. legacy) — not fully analyzed.
        return "stale"

    def _last_analyzed_at_for_sample(self, sid: str) -> Optional[datetime]:
        stamps: list[datetime] = []
        for payload in (
            self._read_draft_tracking_payload(sid),
            self._read_draft_optical_flow_payload(sid),
        ):
            if not payload:
                continue
            raw = str(payload.get("analysis_timestamp_utc", "")).strip()
            if not raw:
                continue
            try:
                stamps.append(datetime.fromisoformat(raw))
            except ValueError:
                continue
        if not stamps:
            return None
        return max(stamps)

    def render_metric_display_lines(
        self, sid: Optional[str]
    ) -> tuple[str, str]:
        state = self._metric_state_for_sample(sid)
        last_ts = None
        if sid and state in ("analyzed", "stale", "scheduled", "running", "error"):
            last_ts = self._last_analyzed_at_for_sample(sid)
        return render_metric_display_lines(state, last_ts)

    def _update_metric_freshness_label(self) -> None:
        if not hasattr(self, "lbl_metric_status"):
            return
        sid = self._current_sample_id
        status_line, last_line = self.render_metric_display_lines(sid)
        self.lbl_metric_status.setText(status_line)
        if hasattr(self, "lbl_last_analyzed"):
            self.lbl_last_analyzed.setText(last_line)
        has_roi = bool(sid) and self._sample_has_valid_data_and_roi(sid)
        if hasattr(self, "btn_run_metrics"):
            running = bool(sid) and sid in self._metrics_inflight
            self.btn_run_metrics.setEnabled(has_roi and not running)

    def _update_orientation_label(self) -> None:
        self.chk_mirror_y.blockSignals(True)
        self.chk_mirror_y.setChecked(self._orientation.mirror_y_axis)
        self.chk_mirror_y.blockSignals(False)
        self.spin_custom_angle.blockSignals(True)
        self.spin_custom_angle.setValue(self._orientation.rotation_angle_degrees)
        self.spin_custom_angle.blockSignals(False)

    def _oriented_frame(self) -> Optional[np.ndarray]:
        if self._base_frame is None:
            return None
        return apply_orientation(self._base_frame, self._orientation)

    def _refresh_display(self, *, keep_roi: bool = True) -> None:
        oriented = self._oriented_frame()
        if oriented is None:
            self._refresh_roi_preview_panel()
            return
        roi = self.canvas.rect_roi() if keep_roi else None
        self.canvas.set_frame(oriented, keep_roi=keep_roi)
        if roi is not None:
            self.canvas.set_rect_roi(roi.clamp(oriented.shape[1], oriented.shape[0]))
        self._update_orientation_label()
        if keep_roi and roi is not None:
            self._autosave_roi(quiet=True)
        self._refresh_roi_preview_panel()

    def _set_roi_save_status(self, text: str, *, saved: bool = True) -> None:
        self.lbl_roi_save_status.setText(text)
        apply_status_style(self.lbl_roi_save_status, saved=saved)

    def _refresh_roi_save_status_from_context(self) -> None:
        """Refresh ROI-only persistence/edit status for the current sample."""
        if not hasattr(self, "lbl_roi_save_status"):
            return
        if self._current_sample is None:
            self._set_roi_save_status("No ROI saved yet", saved=False)
            return
        if self.canvas.rect_roi() is None:
            self._set_roi_save_status("No ROI saved yet", saved=False)
            return
        if self._roi_user_adjusted or self._roi_autosave_pending:
            self._set_roi_save_status("Unsaved changes", saved=False)
            return
        self._set_roi_save_status("ROI saved", saved=True)

    def _autosave_roi(self, *, quiet: bool = True) -> bool:
        if self._project_root is None or self._current_sample is None:
            return False
        if self.canvas.rect_roi() is None:
            self._set_roi_save_status("No ROI to save", saved=False)
            return False
        try:
            ann = self._current_annotation_dict(status=STATUS_ROI_MARKED)
        except ValueError as exc:
            self._set_roi_save_status("Unsaved changes", saved=False)
            if not quiet:
                QMessageBox.warning(self, "Save ROI", str(exc))
            return False

        sid = ann["sample_id"]
        previous_roi_key = self._saved_roi_key_for_sample(sid)
        current_status = str(self._current_sample.get("processing_status", ""))
        new_status = self._status_after_roi_autosave(current_status)
        try:
            crop_path = self._project_root / METADATA_DIR / CROP_METADATA_JSON
            save_sample_crop_annotation(crop_path, sid, ann)
            csv_update: dict[str, Any] = {
                "sample_id": sid,
                "notes": ann["notes"],
                "annotation_source": ann["annotation_source"],
                "review_status": ann.get("review_status", "approved"),
            }
            if new_status is not None:
                csv_update["processing_status"] = new_status
            update_samples_csv(
                self._project_root / METADATA_DIR / SAMPLES_CSV,
                csv_update,
            )
        except OSError as exc:
            self._set_roi_save_status(f"Could not save ROI: {exc}", saved=False)
            self._status(f"Could not save ROI: {exc}")
            if not quiet:
                QMessageBox.warning(self, "Save ROI", f"Could not save ROI:\n{exc}")
            return False

        if new_status is not None:
            self._current_sample["processing_status"] = new_status
            self._update_sample_list_row_for_id(sid)
        self._loaded_annotation_source = ann["annotation_source"]
        self._roi_user_adjusted = False
        self._roi_autosave_pending = False
        self._metric_error_by_sample.pop(sid, None)
        self._set_roi_save_status("ROI saved", saved=True)
        self._mark_metrics_stale_if_saved_roi_changed(
            sid,
            previous_roi_key=previous_roi_key,
            new_roi_key=self._roi_key_from_rect(self.canvas.rect_roi()),
        )
        self._update_metric_freshness_label()
        return True

    def _on_apply_custom_angle(self) -> None:
        self._exit_cropped_preview_mode()
        self._orientation.rotation_angle_degrees = float(self.spin_custom_angle.value())
        self._orientation.manual_rotation_steps = []
        self._refresh_display()

    def _on_mirror_y_axis(self, checked: bool) -> None:
        self._exit_cropped_preview_mode()
        self._orientation.mirror_y_axis = bool(checked)
        self._orientation.manual_rotation_steps = []
        self._refresh_display()

    def _on_flip_180(self) -> None:
        self._exit_cropped_preview_mode()
        self._orientation.flipped_180 = not self._orientation.flipped_180
        self._orientation.manual_rotation_steps = []
        self._refresh_display()

    def _on_reset_orientation(self) -> None:
        self._exit_cropped_preview_mode()
        self._orientation = OrientationState()
        self._refresh_display(keep_roi=True)

    def on_roi_changed(self, roi: Optional[RectROI]) -> None:
        if roi is None:
            return
        self._roi_user_adjusted = True
        self._roi_autosave_pending = True
        self._set_roi_save_status("Unsaved changes", saved=False)
        if str(self._loaded_annotation_source) == "auto_suggested":
            self._loaded_annotation_source = "auto_suggested_adjusted"
        self._refresh_roi_preview_panel()

    def on_roi_edit_finished(self) -> None:
        self._autosave_roi(quiet=True)

    def _on_clear_roi(self) -> None:
        self._cancel_pending_debounced_tracking()
        self._exit_cropped_preview_mode()
        self.canvas.set_rect_roi(None)
        self._roi_user_adjusted = True
        self._roi_autosave_pending = False
        self._set_roi_save_status("ROI cleared", saved=False)
        self._persist_roi_cleared_for_current_sample()
        self._update_metric_freshness_label()
        self._refresh_roi_preview_panel()

    def _persist_roi_cleared_for_current_sample(self) -> None:
        """Clearing the ROI returns the Sample to Raw and drops stale metrics."""
        if self._project_root is None or self._current_sample is None:
            return
        sid = str(self._current_sample.get("sample_id", "")).strip()
        if not sid:
            return
        current_status = str(self._current_sample.get("processing_status", ""))
        if current_status in _ADVANCED_SAMPLE_STATUSES:
            # Exported/processed Samples keep their advanced status.
            return
        try:
            crop_path = self._project_root / METADATA_DIR / CROP_METADATA_JSON
            remove_sample_crop_annotation(crop_path, sid)
            update_samples_csv(
                self._project_root / METADATA_DIR / SAMPLES_CSV,
                {"sample_id": sid, "processing_status": STATUS_RAW_IMPORTED},
            )
        except OSError:
            return
        self._current_sample["processing_status"] = STATUS_RAW_IMPORTED
        self._loaded_annotation_source = "manual"
        self._invalidate_tracking_result_for_sample(sid)
        self._update_sample_list_row_for_id(sid)
        self._refresh_analysis_if_visible()

    def _tracking_params_from_ui(self) -> MotionIndexParams:
        patch = int(self.spin_track_patch.value())
        if patch % 2 == 0:
            raise ValueError("Template patch size must be an odd integer.")
        if patch < 3:
            raise ValueError("Template patch size must be at least 3 px.")
        search_radius = int(self.spin_track_search.value())
        if search_radius < 1:
            raise ValueError("Search radius must be at least 1 px.")
        min_spacing = int(self.spin_track_spacing.value())
        if min_spacing < 1:
            raise ValueError("Minimum point spacing must be at least 1 px.")
        return MotionIndexParams(
            num_starting_points=int(self.spin_track_points.value()),
            min_point_spacing_px=min_spacing,
            search_radius_px=search_radius,
            template_patch_size_px=patch,
            min_template_confidence=float(self.spin_track_confidence.value()),
            lookahead_frames=int(self.spin_track_lookahead.value()),
            microns_per_pixel=float(self.spin_track_mpp.value()),
            seconds_per_frame=float(self.spin_track_spf.value()),
            downward_direction="increasing_y",
            tracking_method=str(
                self.combo_track_method.currentData() or TRACKING_METHOD_BRIGHTEST_LOCAL
            ),
        )

    def _on_show_metric_analysis_view(self) -> None:
        self.enter_metric_analysis_view_for_current_sample(quiet=False)

    def _on_run_metrics_clicked(self) -> None:
        self.run_metrics_now_for_current_sample()

    def _report_metric_view_blocked(self, message: str, *, quiet: bool) -> None:
        if quiet:
            self._show_metric_analysis_placeholder(message)
        else:
            gui_dialogs.warning(self, _METRIC_ANALYSIS_VIEW_LABEL, message)

    def enter_metric_analysis_view_for_current_sample(
        self,
        *,
        quiet: bool = False,
        resume_playback: bool = False,
    ) -> bool:
        if self._project_root is None or self._current_sample is None:
            if not quiet:
                QMessageBox.warning(
                    self, _METRIC_ANALYSIS_VIEW_LABEL, "Select a sample first."
                )
            return False

        self._cancel_pending_debounced_tracking()
        self._autosave_roi(quiet=True)
        check = self._validate_current_roi()
        if not check.ok or check.roi_oriented is None:
            message = check.message or (
                "Metric Analysis is unavailable because this Sample "
                "does not have a saved ROI."
            )
            self._report_metric_view_blocked(message, quiet=quiet)
            return False

        path = self._sample_file_path()
        if path is None or not path.exists():
            message = (
                "Metric Analysis is unavailable because this Sample "
                "does not have valid Data."
            )
            self._report_metric_view_blocked(message, quiet=quiet)
            return False
        if not is_supported_video_path(path):
            message = (
                "Only AVI and MP4 videos are supported."
            )
            if quiet:
                self._show_metric_analysis_placeholder(message)
            else:
                QMessageBox.information(self, "Unsupported", message)
            return False

        try:
            params = self._tracking_params_from_ui()
        except ValueError as exc:
            if quiet:
                self._show_metric_analysis_placeholder(str(exc))
            else:
                QMessageBox.warning(self, "Tracking Settings", str(exc))
            return False

        crop_w = int(check.roi_oriented.width)
        crop_h = int(check.roi_oriented.height)
        min_dim = params.template_patch_size_px + (2 * params.search_radius_px) + 2
        if min(crop_w, crop_h) < min_dim:
            message = (
                f"The ROI ({crop_w}×{crop_h} px) is too small for patch size "
                f"{params.template_patch_size_px} and search radius "
                f"{params.search_radius_px}."
            )
            self._report_metric_view_blocked(message, quiet=quiet)
            return False

        if not quiet:
            self._status("Building metric analysis preview…")
        QApplication.processEvents()
        try:
            frames = load_cropped_frames_from_video(
                path,
                self._orientation,
                check.roi_oriented,
            )
            analysis = analyze_cropped_preview(frames, params=params)
        except Exception as exc:
            self._report_metric_view_blocked(str(exc), quiet=quiet)
            return False

        self._enter_cropped_preview_mode(analysis, params=params)
        if self._current_sample_id:
            of_settings = self._optical_flow_settings_from_ui()
            roi_bounds = (
                int(check.roi_oriented.x),
                int(check.roi_oriented.y),
                int(check.roi_oriented.width),
                int(check.roi_oriented.height),
            )
            fingerprint = build_optical_flow_fingerprint(
                sample_id=self._current_sample_id,
                roi_bounds=roi_bounds,
                settings=of_settings,
                data_identity=str(path.resolve()),
                frame_count=len(frames),
            )
            of_result = compute_optical_flow_motion_index(
                frames,
                of_settings,
                sample_id=self._current_sample_id,
                data_identity=str(path.resolve()),
                roi_bounds=roi_bounds,
                fingerprint=fingerprint,
            )
            self._commit_optical_flow_result(self._current_sample_id, of_result)
        if resume_playback:
            self._preview_play()
        return True

    def _show_metric_analysis_placeholder(self, message: str) -> None:
        self._metric_analysis_view_active = True
        self._preview_pause()
        self._cropped_preview = None
        self._preview_frame_index = 0
        self._center_stack.setCurrentIndex(0)
        self._preview_mode = "cropped_tracking"
        self.canvas.set_interactive(False)
        self.canvas.clear_preview()
        self._set_preview_controls_visible(False)
        self._set_metric_mode_widgets_visible(True)
        self._sync_metric_mode_combo()
        self._set_tracking_settings_editable(True)
        self._show_cropped_metric_settings_view()
        self._update_optical_flow_qc_readout()
        self.update_tracking_result_panel()
        self._set_preview_mode_banner(f"{_METRIC_ANALYSIS_VIEW_LABEL} — {message}")
        if hasattr(self, "lbl_sample_frame"):
            self.lbl_sample_frame.setText("—")
        self.lbl_frame_info.setText("—")
        self._update_metric_analysis_button_visibility()

    def _set_preview_controls_visible(self, visible: bool) -> None:
        for widget in getattr(self, "_preview_control_widgets", ()):
            widget.setVisible(visible)

    def _enter_cropped_preview_mode(
            self,
        analysis: CroppedPreviewAnalysis,
        *,
        params: Optional[MotionIndexParams] = None,
    ) -> None:
        self._preview_pause()
        self._center_stack.setCurrentIndex(0)
        self._metric_analysis_view_active = True
        self._preview_mode = "cropped_tracking"
        self._cropped_preview = analysis
        self._preview_frame_index = 0
        self.canvas.set_interactive(False)
        self._set_preview_controls_visible(True)
        self._set_metric_mode_widgets_visible(True)
        self._sync_metric_mode_combo()
        self._set_tracking_settings_editable(True)
        self._show_cropped_metric_settings_view()
        self._update_optical_flow_qc_readout()
        if self._current_sample_id:
            commit_params = params or analysis.params
            if commit_params is None:
                try:
                    commit_params = self._tracking_params_from_ui()
                except ValueError:
                    commit_params = MotionIndexParams()
            self._commit_tracking_result(
                self._current_sample_id, analysis, commit_params
            )
        self._set_preview_mode_banner(_METRIC_ANALYSIS_VIEW_LABEL)
        count = max(1, len(analysis.frames))
        max_index = max(0, count - 1)
        self.slider_frame.setMaximum(max_index)
        self.spin_frame.setMaximum(max_index)
        self.slider_sample_frame.setMaximum(max_index)
        self._show_cropped_preview_frame(0)
        if analysis.tracking_warning:
            self._status(
                f"{_METRIC_ANALYSIS_VIEW_LABEL} ready. {analysis.tracking_warning}"
            )
        else:
            self._status(f"{_METRIC_ANALYSIS_VIEW_LABEL} ready. Press Play to loop.")
        self._update_metric_analysis_button_visibility()
        self._refresh_roi_preview_panel()

    def _exit_cropped_preview_mode(self) -> None:
        if not self._metric_analysis_view_active:
            self._set_tracking_settings_editable(False)
            self._show_roi_controls_view()
            return
        self._metric_analysis_view_active = False
        self._set_tracking_settings_editable(False)
        self.reset_preview_state(clear_image=False, reset_roi_controls=True)
        self._set_preview_mode_banner(None)
        self._update_metric_analysis_button_visibility()
        if self._base_frame is not None:
            self._sync_sample_frame_ui(self._frame_index, self._total_frames)
            self._refresh_display(keep_roi=True)

    def _on_preview_timer_tick(self) -> None:
        if self._preview_mode == "cropped_tracking" and self._cropped_preview is not None:
            count = len(self._cropped_preview.frames)
            if count <= 1:
                self._playback_pause()
                return
            next_index = self._preview_frame_index + 1
            if next_index >= count:
                if self._playback_loop_enabled():
                    next_index = 0
                else:
                    self._playback_pause()
                    return
            self._show_cropped_preview_frame(next_index)
            return
        if self._preview_mode == "full" and self._base_frame is not None:
            total = max(1, int(self._total_frames))
            if total <= 1:
                self._playback_pause()
                return
            next_index = int(self._frame_index) + 1
            if next_index >= total:
                if self._playback_loop_enabled():
                    next_index = 0
                else:
                    self._playback_pause()
                    return
            self._load_frame_index(next_index)
            return
        self._playback_pause()

    def _on_cropped_preview_frame_slider(self, value: int) -> None:
        self._on_sample_frame_slider(value)

    def _show_cropped_preview_frame(self, index: int) -> None:
        if self._cropped_preview is None:
            return
        count = len(self._cropped_preview.frames)
        index = max(0, min(index, count - 1))
        if self._cropped_metric_mode == "optical_flow":
            frame = self._cropped_preview.frames[index].copy()
            if (
                hasattr(self, "chk_show_of_overlay")
                and self.chk_show_of_overlay.isChecked()
            ):
                arrows = self._get_overlay_arrows_for_frame(index)
                if arrows:
                    frame = render_optical_flow_overlay(frame, arrows)
        else:
            frame = render_cropped_tracking_frame(self._cropped_preview, index)
        self._preview_frame_index = index
        self.canvas.set_preview_frame(frame)
        self.slider_frame.blockSignals(True)
        self.spin_frame.blockSignals(True)
        self.slider_sample_frame.blockSignals(True)
        self.slider_frame.setValue(index)
        self.spin_frame.setValue(index)
        self.slider_sample_frame.setValue(index)
        self.slider_frame.blockSignals(False)
        self.spin_frame.blockSignals(False)
        self.slider_sample_frame.blockSignals(False)
        h, w = frame.shape[:2]
        frame_text = f"Frame {index + 1} / {count}"
        if hasattr(self, "lbl_sample_frame"):
            self.lbl_sample_frame.setText(frame_text)
        self.lbl_frame_info.setText(
            f"Cropped preview {frame_text} ({w}×{h} px)"
        )

    def _on_auto_suggest_roi(self) -> None:
        oriented = self._oriented_frame()
        if oriented is None:
            return
        try:
            crop = detect_tracking_crop(oriented)
            self.canvas.set_rect_roi(tracking_crop_to_rect(crop))
            self._loaded_annotation_source = "auto_suggested"
            self._roi_user_adjusted = False
            self._autosave_roi(quiet=True)
        except ValueError as e:
            QMessageBox.warning(self, "ROI Suggestion", str(e))

    def _validate_current_roi(self) -> RoiValidationResult:
        if self._base_frame is None:
            return RoiValidationResult(False, "No frame loaded. Select a sample first.")
        roi = self.canvas.rect_roi()
        if roi is None and self._project_root is not None and self._current_sample:
            ann = get_sample_annotation(
                self._project_root, str(self._current_sample["sample_id"])
            )
            if ann:
                _, roi = annotation_from_legacy(ann)
        if roi is None:
            return RoiValidationResult(
                False,
                "Please draw or load a rectangular ROI before previewing "
                "the cropped region.",
            )
        return validate_roi_for_sample(
            roi,
            base_frame=self._base_frame,
            orientation=self._orientation,
        )

    def _annotation_source_for_save(self) -> str:
        src = str(self._loaded_annotation_source or "manual")
        if self._roi_user_adjusted:
            if src in ("auto_suggested", "auto_suggested_adjusted"):
                return "auto_suggested_adjusted"
            if src in ("propagated", "propagated_adjusted"):
                return "propagated_adjusted"
            if src != "manual":
                return "propagated_adjusted"
        return src if src else "manual"

    def _suggestion_method_for_save(self) -> str | None:
        src = self._annotation_source_for_save()
        if src.startswith("auto_suggested"):
            return "f_actin_signal"
        return None

    def _current_annotation_dict(self, *, status: str) -> dict[str, Any]:
        assert self._current_sample is not None and self._base_frame is not None
        check = self._validate_current_roi()
        if not check.ok:
            raise ValueError(check.message)
        assert check.roi_oriented is not None and check.roi_original is not None
        oriented = self._oriented_frame()
        assert oriented is not None
        oh, ow = oriented.shape[:2]
        bh, bw = self._base_frame.shape[:2]
        ann_src = self._annotation_source_for_save()
        review = str(self._current_sample.get("review_status", "approved"))
        requires_review = status == STATUS_ROI_PROPAGATED
        if status == STATUS_ROI_MARKED and ann_src.startswith("auto_suggested"):
            review = "pending"
            requires_review = True
        elif status == STATUS_ROI_MARKED and ann_src.startswith("propagated"):
            review = "pending"
            requires_review = True
        roi_method = (
            "f_actin_signal_suggestion"
            if ann_src.startswith("auto_suggested")
            else "manual_rectangle"
        )
        return build_sample_annotation(
            sample_id=str(self._current_sample["sample_id"]),
            group=str(self._current_sample["group"]),
            batch_name=str(self._current_sample.get("batch_name", "")),
            batch_id=str(self._current_sample.get("batch_id", "")),
            original_file=str(self._current_sample["original_filename"]),
            stored_raw_path=str(self._current_sample["stored_path"]),
            reference_frame_index=self._reference_frame_index,
            orientation=self._orientation,
            roi=check.roi_oriented.clamp(ow, oh),
            roi_original=check.roi_original.clamp(bw, bh),
            original_dimensions={"width": bw, "height": bh},
            oriented_dimensions={"width": ow, "height": oh},
            notes=self._loaded_sample_notes.strip(),
            annotation_source=ann_src,
            suggestion_method=self._suggestion_method_for_save(),
            roi_method=roi_method,
            segmentation_method="manual",
            segmentation_parameters={},
            status=status,
            requires_review=requires_review,
            review_status=review if requires_review else "approved",
        )

    def _on_save_annotation(self) -> None:
        if self._project_root is None or self._current_sample is None:
            QMessageBox.warning(self, "Save ROI", "Select a sample first.")
            return
        if not self._autosave_roi(quiet=False):
            return
        sid = str(self._current_sample["sample_id"])
        self._refresh_sample_list()
        self._status(f"Saved ROI for {sid}")

    def _process_kwargs_from_sample(self) -> dict[str, Any]:
        assert self._current_sample is not None
        try:
            batch_number = int(self._current_sample.get("batch_number", 1) or 1)
        except ValueError:
            batch_number = 1
        is_video = str(self._current_sample.get("is_video", "")).lower() == "true"
        return {
            "batch_number": batch_number,
            "final_export_name": str(
                self._current_sample.get("final_export_name", "")
            ).strip(),
            "is_video": is_video,
        }

    def _confirm_overwrite(self, paths: list[Path]) -> bool:
        existing = [p for p in paths if p.exists()]
        if not existing:
            return True
        names = "\n".join(f"  • {p.name}" for p in existing[:5])
        if len(existing) > 5:
            names += f"\n  … +{len(existing) - 5} more"
        reply = QMessageBox.question(
            self,
            "Overwrite Outputs?",
            f"The following processed file(s) already exist:\n{names}\n\nOverwrite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _confirm_pending_export(self, ann: dict[str, Any]) -> bool:
        if str(ann.get("review_status", "")) != "pending" and not ann.get(
            "requires_review"
        ):
            return True
        reply = QMessageBox.warning(
            self,
            "ROI Pending Review",
            "This ROI is marked pending review (e.g. propagated annotation). "
            "Export anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _on_process_sample(self) -> None:
        if self._project_root is None or self._current_sample is None:
            return
        try:
            ann = self._current_annotation_dict(status=STATUS_ROI_MARKED)
        except ValueError as e:
            QMessageBox.warning(self, "Export ROI", str(e))
            return
        if not self._confirm_pending_export(ann):
            return
        path = self._sample_file_path()
        if path is None or not path.exists():
            QMessageBox.warning(self, "Export ROI", "Imported video not found for this sample.")
            return
        if is_wip_sample_path(path):
            QMessageBox.information(
                self,
                "Unsupported",
                "Raw or 3D formats are not supported in the 2D crop workflow.",
            )
            return
        sid = str(self._current_sample["sample_id"])
        pk = self._process_kwargs_from_sample()
        if not pk["final_export_name"]:
            QMessageBox.warning(self, "Export ROI", "Export name is missing.")
            return
        check = self._validate_current_roi()
        assert check.roi_oriented is not None and check.roi_original is not None
        out_paths = list_output_paths_for_export(
            self._project_root,
            str(self._current_sample["group"]),
            str(self._current_sample.get("batch_name", "")),
            pk["final_export_name"],
            pk["is_video"],
        )
        if not self._confirm_overwrite(out_paths):
            return
        try:
            result = process_sample_roi(
                root=self._project_root,
                sample_row=self._current_sample,
                annotation=ann,
                source_path=path,
                orientation=self._orientation,
                roi_oriented=check.roi_oriented,
                roi_original=check.roi_original,
                overwrite=True,
                export_frames=False,
            )
            ann = merge_processed_into_annotation(ann, result)
            ann.update(result.get("export_metadata", {}))
            save_sample_crop_annotation(
                self._project_root / METADATA_DIR / CROP_METADATA_JSON, sid, ann
            )
            update_samples_csv(
                self._project_root / METADATA_DIR / SAMPLES_CSV,
                {
                    "sample_id": sid,
                    "processing_status": STATUS_PROCESSED,
                    "review_status": "approved",
                },
            )
            self._refresh_sample_list()
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {result['frame_count']} frame(s) to:\n{result.get('output_file')}",
            )
            self._status(f"Processed {sid}")
        except FileExistsError as e:
            QMessageBox.warning(self, "Export ROI", str(e))
        except (MediaLoadError, OSError, ValueError) as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _on_propagate_batch(self) -> None:
        if self._project_root is None or self._current_sample is None:
            return
        if self.canvas.rect_roi() is None:
            QMessageBox.warning(
                self,
                "Propagate",
                "Set orientation and ROI on the source sample first.",
            )
            return
        group = str(self._current_sample["group"])
        batch_name = str(self._current_sample.get("batch_name", ""))
        if not batch_name:
            QMessageBox.warning(
                self,
                "Propagate",
                "Current sample has no sample label in metadata. Re-import or migrate project.",
            )
            return
        dlg = PropagateDialog(self, group, batch_name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source_ann = self._current_annotation_dict(status=STATUS_ROI_MARKED)
        source_id = source_ann["sample_id"]
        scope = dlg.scope_key()
        selected = None
        if scope == SCOPE_SELECTED:
            selected = self._selected_sample_ids()
            if not selected:
                gui_dialogs.warning(self, "Propagate", "Select target samples in the list.")
                return
        targets = resolve_propagation_targets(
            self._project_root, source_id, scope, selected
        )
        if not targets:
            gui_dialogs.information(self, "Propagate", "No target samples for this scope.")
            return
        crop_data = load_crop_metadata(self._project_root / METADATA_DIR / CROP_METADATA_JSON)
        src_orient = source_ann.get("oriented_dimensions", {})
        src_w, src_h = int(src_orient.get("width", 0)), int(src_orient.get("height", 0))
        dim_warnings: list[str] = []
        to_write: list[dict] = []
        skipped = 0
        protected_skipped = 0
        for tgt in targets:
            tid = str(tgt["sample_id"])
            existing = crop_data.get("samples", {}).get(tid)
            tgt_status = str(tgt.get("processing_status", ""))
            if annotation_is_protected(tgt_status) or (
                existing and annotation_is_protected(str(existing.get("status", "")))
            ):
                protected_skipped += 1
                continue
            if existing and not dlg.overwrite():
                skipped += 1
                continue
            try:
                ann = propagate_annotation(
                    self._project_root,
                    source_ann,
                    tgt,
                    scaling_method=dlg.scaling_method(),
                )
                tgt_o = ann.get("oriented_dimensions", {})
                tw, th = int(tgt_o.get("width", 0)), int(tgt_o.get("height", 0))
                if src_w and src_h and (tw != src_w or th != src_h):
                    dim_warnings.append(
                        f"{tid}: {src_w}×{src_h} → {tw}×{th} ({dlg.scaling_method()})"
                    )
                to_write.append(ann)
            except (MediaLoadError, ValueError) as e:
                gui_dialogs.warning(self, "Propagate", f"Skipped {tid}: {e}")
        if not to_write:
            QMessageBox.information(
                self,
                "Propagate",
                f"No annotations written ({skipped} skipped).",
            )
            return
        if dim_warnings and dlg.scaling_method() == "same_coordinates":
            preview = "\n".join(dim_warnings[:6])
            if len(dim_warnings) > 6:
                preview += f"\n… +{len(dim_warnings) - 6} more"
            reply = QMessageBox.warning(
                self,
                "Dimension Mismatch",
                "Some targets differ in size from the source. "
                "Using the same pixel coordinates may place the ROI incorrectly.\n\n"
                f"{preview}\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        save_propagated_annotations(self._project_root, to_write)
        samples_path = self._project_root / METADATA_DIR / SAMPLES_CSV
        for ann in to_write:
            update_samples_csv(
                samples_path,
                {
                    "sample_id": ann["sample_id"],
                    "processing_status": STATUS_ROI_PROPAGATED,
                },
            )
        self._refresh_sample_list()
        QMessageBox.information(
            self,
            "Propagate",
            f"Propagated to {len(to_write)} sample(s). "
            f"{skipped} skipped (existing annotations). "
            f"{protected_skipped} skipped (approved/processed). "
            "Review and adjust each propagated ROI as needed.",
        )

    def _on_process_approved_batch(self) -> None:
        if self._project_root is None or self._current_sample is None:
            return
        group = str(self._current_sample["group"])
        batch_name = sanitize_batch_name(str(self._current_sample.get("batch_name", "")))
        sample_label = display_sample_label(
            int(self._current_sample.get("batch_number", 1) or 1),
            batch_name,
        )
        approved, skipped, _ = process_batch_approved_rois(
            root=self._project_root,
            group=group,
            batch_name=batch_name,
            overwrite=False,
            export_frames=False,
        )
        pre_skipped = len(skipped)
        if not approved:
            QMessageBox.information(
                self,
                "Sample Export",
                f"No ROI-marked data ready in {group} / {sample_label}.\n"
                f"Skipped (not marked or missing ROI): {pre_skipped}",
            )
            return
        reply = QMessageBox.question(
            self,
            "Process Marked ROIs in Sample",
            f"Condition Group: {group}\n"
            f"Sample: {sample_label}\n\n"
            f"Samples to export: {len(approved)}\n"
            f"Samples skipped: {pre_skipped}\n\n"
            "Only ROI-marked samples will be exported. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        all_out: list[Path] = []
        df = pd.read_csv(
            self._project_root / METADATA_DIR / SAMPLES_CSV,
            dtype=str,
            keep_default_na=False,
        )
        for sid in approved:
            row = df[df["sample_id"] == sid].iloc[0].to_dict()
            final_name = str(row.get("final_export_name", "")).strip()
            is_video = str(row.get("is_video", "")).lower() == "true"
            if final_name:
                all_out.extend(
                    list_output_paths_for_export(
                        self._project_root,
                        group,
                        batch_name,
                        final_name,
                        is_video,
                    )
                )
        if not self._confirm_overwrite(all_out):
            return
        _, _, report = process_batch_approved_rois(
            root=self._project_root,
            group=group,
            batch_name=batch_name,
            overwrite=True,
            export_frames=False,
        )
        self._refresh_sample_list()
        err_preview = ""
        if report.errors:
            err_preview = "\n\nIssues:\n" + "\n".join(report.errors[:8])
            if len(report.errors) > 8:
                err_preview += f"\n… +{len(report.errors) - 8} more"
        QMessageBox.information(
            self,
            "Sample Export Complete",
            f"Successful exports: {report.processed}\n"
            f"Failed: {report.failed}\n"
            f"Skipped: {pre_skipped + report.skipped}"
            f"{err_preview}",
        )

    def _tree_item_meta(self, item: QTreeWidgetItem | None) -> dict[str, Any] | None:
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return data if isinstance(data, dict) else None

    @staticmethod
    def _is_sample_tree_item(item: QTreeWidgetItem | None) -> bool:
        if item is None:
            return False
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return isinstance(data, dict) and data.get("item_type") == ITEM_TYPE_SAMPLE

    def _iter_explorer_tree_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []

        def walk(parent: QTreeWidgetItem) -> None:
            for idx in range(parent.childCount()):
                child = parent.child(idx)
                items.append(child)
                walk(child)

        for top_idx in range(self.tree_samples.topLevelItemCount()):
            top = self.tree_samples.topLevelItem(top_idx)
            if top is not None:
                items.append(top)
                walk(top)
        return items

    def _iter_sample_tree_items(self) -> list[QTreeWidgetItem]:
        return [
            item
            for item in self._iter_explorer_tree_items()
            if self._is_sample_tree_item(item)
        ]

    def _find_sample_tree_item(self, sample_id: str) -> QTreeWidgetItem | None:
        target = str(sample_id)
        for item in self._iter_sample_tree_items():
            meta = self._tree_item_meta(item)
            if meta and str(meta.get("sample_id", "")) == target:
                return item
        return None

    def _selected_condition_group_id_from_tree(self) -> str | None:
        item = self.tree_samples.currentItem()
        if item is None:
            return None
        meta = self._tree_item_meta(item)
        gid = tree_item_condition_group_id(meta)
        if gid:
            return gid
        parent = item.parent()
        while parent is not None:
            meta = self._tree_item_meta(parent)
            gid = tree_item_condition_group_id(meta)
            if gid:
                return gid
            parent = parent.parent()
        return None

    def _sync_combo_from_tree_selection(self) -> None:
        gid = self._selected_condition_group_id_from_tree()
        if gid and self._project_root is not None:
            self._refresh_condition_group_combo(select=gid)
            self._set_last_import_breed(gid)

    def _selected_sample_ids(self) -> list[str]:
        ids = []
        for item in self.tree_samples.selectedItems():
            data = self._tree_item_meta(item)
            if data and data.get("item_type") == ITEM_TYPE_SAMPLE:
                ids.append(str(data["sample_id"]))
        return ids

    # --- Project / import (unchanged core) ---

    def _load_project(self, root: Path, status_msg: str) -> None:
        try:
            root = Path(root).resolve()
            if not is_valid_project(root):
                create_project_structure(root)
            migrate_workspace_schema(root)
            repair_batch_registry(root)
            self._project_root = root
            saved_breed = get_last_import_breed(root)
            if saved_breed:
                self._last_import_breed = saved_breed
            add_recent(root, root)
            self._refresh_recent_menu()
            self._update_workspace_label()
            self._set_active_sample(None)
            self.reset_preview_state(
                clear_image=True,
                placeholder=self._SELECT_SAMPLE_HINT,
            )
            self._refresh_condition_group_combo()
            self._refresh_sample_list()
            self._status(f"{status_msg}: {root}")
        except OSError as e:
            gui_dialogs.critical(self, "Project Error", str(e))

    def _set_last_import_breed(self, breed: str | None) -> None:
        if not breed or self._project_root is None:
            return
        if not condition_group_exists(self._project_root, breed):
            return
        self._last_import_breed = breed
        set_last_import_breed(self._project_root, breed)

    def _current_condition_group(self) -> str | None:
        """Return the selected stable condition_group_id, if any."""
        if self._project_root is None:
            return None
        from_tree = self._selected_condition_group_id_from_tree()
        if from_tree:
            resolved = resolve_condition_group_id(self._project_root, from_tree)
            if resolved:
                return resolved
        data = self.combo_filter_group.currentData()
        if isinstance(data, str) and data.strip():
            return resolve_condition_group_id(self._project_root, data)
        text = self.combo_filter_group.currentText().strip()
        if not text or text.startswith("("):
            return None
        return resolve_condition_group_id(self._project_root, text)

    def _refresh_condition_group_combo(self, *, select: str | None = None) -> None:
        if self._project_root is None:
            self.combo_filter_group.blockSignals(True)
            self.combo_filter_group.clear()
            self.combo_filter_group.blockSignals(False)
            return
        records = list_condition_group_records(self._project_root)
        preferred = select or self.combo_filter_group.currentData()
        if not preferred and self._last_import_breed:
            preferred = self._last_import_breed
        self.combo_filter_group.blockSignals(True)
        self.combo_filter_group.clear()
        if records:
            for record in records:
                self.combo_filter_group.addItem(record.name, record.id)
            idx = -1
            if preferred:
                idx = self.combo_filter_group.findData(preferred)
                if idx < 0:
                    resolved = resolve_condition_group_id(
                        self._project_root, str(preferred)
                    )
                    if resolved:
                        idx = self.combo_filter_group.findData(resolved)
            if idx >= 0:
                self.combo_filter_group.setCurrentIndex(idx)
            else:
                self.combo_filter_group.setCurrentIndex(0)
        else:
            self.combo_filter_group.addItem(
                "(create a Condition Group first)",
                "",
            )
            self.combo_filter_group.setCurrentIndex(0)
        self.combo_filter_group.blockSignals(False)

    def _on_create_condition_group(self) -> None:
        if self._require_project_root() is None:
            return
        name, ok = QInputDialog.getText(
            self,
            "New Condition Group",
            "Condition Group name:",
        )
        if not ok:
            return
        try:
            record = create_condition_group(self._project_root, name)
        except ValueError as exc:
            gui_dialogs.warning(self, "New Condition Group", str(exc))
            return
        self._refresh_condition_group_combo(select=record.id)
        self._refresh_sample_list()
        self._status(f"Created Condition Group: {record.name}")

    def _on_rename_condition_group(self) -> None:
        if self._project_root is None:
            return
        current = self._current_condition_group()
        if not current:
            QMessageBox.information(
                self,
                "Rename Condition Group",
                "Create or select a Condition Group first.",
            )
            return
        current_name = get_condition_group_name(self._project_root, current)
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Condition Group",
            "New name:",
            text=current_name,
        )
        if not ok or not new_name.strip():
            return
        try:
            renamed = rename_condition_group(
                self._project_root, current, new_name.strip()
            )
        except (ValueError, OSError) as exc:
            gui_dialogs.warning(self, "Rename Condition Group", str(exc))
            return
        self._set_last_import_breed(current)
        self._refresh_condition_group_combo(select=current)
        self._refresh_sample_list()
        self._refresh_analysis_if_visible()
        self.update_tracking_result_panel()
        self._status(f"Renamed Condition Group to: {renamed}")

    def _on_delete_condition_group(self) -> None:
        if self._project_root is None:
            return
        current = self._current_condition_group()
        if not current:
            QMessageBox.information(
                self,
                "Delete Condition Group",
                "Create or select a Condition Group first.",
            )
            return
        if condition_group_has_samples(self._project_root, current):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.NoIcon)
            box.setWindowTitle("Condition Group Not Empty")
            box.setText("Delete the Samples in this Condition Group first.")
            box.setStandardButtons(QMessageBox.StandardButton.Ok)
            box.exec()
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle("Delete Condition Group")
        box.setText("Delete this empty Condition Group?")
        delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        if box.clickedButton() is not delete_btn:
            return
        try:
            delete_empty_condition_group(self._project_root, current)
        except ValueError as exc:
            gui_dialogs.warning(self, "Delete Condition Group", str(exc))
            return
        current_name = get_condition_group_name(self._project_root, current)
        self._refresh_condition_group_combo()
        self._refresh_sample_list()
        self._refresh_analysis_if_visible()
        self._status(f"Deleted Condition Group: {current_name}")

    def _on_filter_group_changed(self) -> None:
        """Legacy hook; filter combo is hidden — tree drives group selection."""
        group = self._current_condition_group()
        if group:
            self._set_last_import_breed(group)

    def _after_import_refresh(
            self,
        *,
        group: str | None = None,
        batch_name: str | None = None,
    ) -> None:
        if group and condition_group_exists(self._project_root, group):
            self.combo_filter_group.blockSignals(True)
            idx = self.combo_filter_group.findData(group)
            if idx < 0:
                idx = self.combo_filter_group.findText(group)
            if idx >= 0:
                self.combo_filter_group.setCurrentIndex(idx)
            self.combo_filter_group.blockSignals(False)
            self._set_last_import_breed(group)
        self._refresh_sample_list()
        if group and batch_name:
            self._select_first_video_in_batch(group, batch_name)

    def _select_first_video_in_batch(self, group: str, batch_name: str) -> None:
        safe = sanitize_batch_name(batch_name)
        for item in self._iter_sample_tree_items():
            meta = self._tree_item_meta(item)
            if not meta:
                continue
            if str(meta.get("group")) != group:
                continue
            if sanitize_batch_name(str(meta.get("batch_name", ""))) != safe:
                continue
            self.tree_samples.setCurrentItem(item)
            return
        for item in self._iter_explorer_tree_items():
            meta = self._tree_item_meta(item)
            if not meta or meta.get("item_type") != ITEM_TYPE_EMPTY_SAMPLE:
                continue
            if str(meta.get("group")) != group:
                continue
            if sanitize_batch_name(str(meta.get("batch_name", ""))) != safe:
                continue
            self.tree_samples.setCurrentItem(item)
            return

    def _ensure_filter_group_valid(self) -> str:
        """Return the selected Condition Group name, or empty when none exist."""
        group = self._current_condition_group()
        return group or ""

    def _selected_batch_record(self) -> dict[str, str] | None:
        if self._project_root is None:
            return None
        group = self._ensure_filter_group_valid()
        name = self._context_batch_name(group)
        if not name:
            return None
        return get_batch_by_name(self._project_root, group, name)

    @staticmethod
    def _batch_list_header_text(
        root: Path | None, group_id: str, batch: dict[str, Any]
    ) -> str:
        num = int(batch.get("batch_number", 1) or 1)
        name = str(batch.get("batch_name", "")).strip()
        sample_label = display_sample_label(num, name)
        group_label = (
            get_condition_group_name(root, group_id) if root is not None else group_id
        )
        if sanitize_batch_name(name) == sanitize_batch_name(display_batch_name(num)):
            return f"──── {group_label} / {sample_label} ────"
        return f"──── {group_label} / {sample_label}: {name} ────"

    def _context_batch_name(self, group: str | None = None) -> str | None:
        """Sample name for menu actions: current data file's sample, or ask if ambiguous."""
        if self._project_root is None:
            return None
        group = group or self._ensure_filter_group_valid()
        if self._current_sample and str(self._current_sample.get("group")) == group:
            name = str(self._current_sample.get("batch_name", "")).strip()
            if name:
                return name
        batches = list_batches(self._project_root, group)
        if not batches:
            return None
        if len(batches) == 1:
            return str(batches[0]["batch_name"])
        labels = [self._batch_list_header_text(self._project_root, group, b) for b in batches]
        names = [str(b["batch_name"]) for b in batches]
        picked, ok = QInputDialog.getItem(
            self,
            "Select Sample",
            f"Choose a sample in {group}:",
            labels,
            0,
            False,
        )
        if not ok or not picked:
            return None
        idx = labels.index(picked)
        return names[idx]

    def _pick_batch_name_to_rename(self, group: str) -> str | None:
        batches = list_batches(self._project_root, group) if self._project_root else []
        if not batches:
            gui_dialogs.information(
                self, "Rename Sample", "No samples exist for this condition group."
            )
            return None
        labels = [self._batch_list_header_text(self._project_root, group, b) for b in batches]
        names = [str(b["batch_name"]) for b in batches]
        picked, ok = QInputDialog.getItem(
            self,
            "Rename Sample",
            f"Sample to rename in {group}:",
            labels,
            0,
            False,
        )
        if not ok or not picked:
            return None
        return names[labels.index(picked)]

    def _on_add_sample(self, group: str | None = None) -> None:
        if self._require_project_root() is None:
            return
        breed = group or self._current_condition_group()
        if not breed:
            QMessageBox.information(
                self,
                "Add Sample",
                "Create a Condition Group before adding Samples.",
            )
            return
        path_strs, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Sample",
            str(self._default_import_dir()),
            DATA_IMPORT_FILTER,
        )
        if not path_strs:
            return
        sources = [Path(p) for p in path_strs]
        self._last_import_dir = sources[0].parent
        breadcrumb(
            "gui.add_sample: selected",
            count=len(sources),
            first=str(sources[0]),
        )
        results = create_samples_from_data_files(self._project_root, breed, sources)
        successes = [r for r in results if r.succeeded]
        failures = [r for r in results if r.error]
        if not successes:
            summary = format_sample_import_summary(results, total_selected=len(sources))
            breadcrumb("gui.add_sample: all failed", count=len(failures))
            gui_dialogs.warning(self, "Add Sample", summary)
            return
        breadcrumb(
            "gui.add_sample: create returned, refreshing UI",
            succeeded=len(successes),
            failed=len(failures),
        )
        first = successes[0]
        batch = first.batch
        assert batch is not None
        self._set_last_import_breed(breed)
        if self._current_condition_group() != breed:
            self._refresh_condition_group_combo(select=breed)
        if self._preview_mode == "cropped_tracking":
            self.reset_preview_state(clear_image=True)
        self._after_import_refresh(group=breed, batch_name=str(batch["batch_name"]))
        self._auto_suggest_roi_for_new_sample(str(batch.get("sample_id", "")))
        self._refresh_analysis_if_visible()
        if failures:
            summary = format_sample_import_summary(results, total_selected=len(sources))
            gui_dialogs.warning(self, "Add Sample", summary)
        if len(sources) == 1:
            label = display_sample_label(
                int(batch.get("batch_number", 1) or 1),
                str(batch.get("batch_name", "")),
            )
            self._status(f"Added {label} from {sources[0].name}")
        elif failures:
            self._status(
                f"Added {len(successes)} of {len(sources)} samples "
                f"(see import summary for failures)"
            )
        else:
            self._status(f"Added {len(successes)} samples from {len(sources)} files")

    def _auto_suggest_roi_for_new_sample(self, sample_id: str) -> None:
        """Persist an auto-suggested ROI for a freshly added Sample.

        ``_after_import_refresh`` already selected the Sample and ran the
        auto-suggestion onto the canvas (when confidence is high enough). Here
        we persist that suggestion so the Sample becomes "ROI marked".
        If no ROI was suggested, the Sample stays "Raw".
        """
        if self._project_root is None or self._current_sample is None:
            return
        sid = str(self._current_sample.get("sample_id", "")).strip()
        if not sid or (sample_id and sid != str(sample_id).strip()):
            return
        status = str(self._current_sample.get("processing_status", ""))
        if status not in _ROI_STATUS_UPGRADE_FROM and status != "":
            return
        suggested = self.canvas.rect_roi() is not None and str(
            self._loaded_annotation_source
        ).startswith("auto_suggested")
        if suggested:
            if self._autosave_roi(quiet=True):
                self._status(f"Auto-suggested ROI for {sid}")
        else:
            self._set_roi_save_status(
                "Could not auto-suggest an ROI — mark one manually.", saved=False
            )
        self._update_metric_freshness_label()

    def _select_sample_header(self, group: str, batch_name: str) -> None:
        safe = sanitize_batch_name(batch_name)
        for item in self._iter_explorer_tree_items():
            meta = self._tree_item_meta(item)
            if not meta:
                continue
            if str(meta.get("group")) != group:
                continue
            if sanitize_batch_name(str(meta.get("batch_name", ""))) != safe:
                continue
            if meta.get("item_type") in (ITEM_TYPE_EMPTY_SAMPLE, ITEM_TYPE_SAMPLE):
                self.tree_samples.setCurrentItem(item)
                return

    def _on_rename_batch(self) -> None:
        if self._project_root is None:
            return
        group = self._ensure_filter_group_valid()
        old = self._pick_batch_name_to_rename(group)
        if not old:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Sample",
            "New sample name:",
            text=old,
        )
        if not ok or not new_name.strip():
            return
        try:
            rename_batch(self._project_root, group, old, new_name.strip())
            self._refresh_sample_list()
        except (ValueError, OSError) as e:
            gui_dialogs.critical(self, "Rename Sample", str(e))

    def _update_workspace_label(self) -> None:
        if self._project_root is None:
            self.lbl_workspace.setText("—")
            self.lbl_workspace.setToolTip("")
            return
        path = str(self._project_root)
        self.lbl_workspace.setToolTip(path)
        folder_name = explorer_workspace_display_name(self._project_root)
        container_width = 0
        if hasattr(self, "_left_sidebar") and self._left_sidebar.isVisible():
            container_width = self._left_sidebar.width()
        elif hasattr(self, "lbl_workspace"):
            container_width = self.lbl_workspace.width()
        width = explorer_workspace_elide_width(container_width)
        elided = self.lbl_workspace.fontMetrics().elidedText(
            folder_name, Qt.TextElideMode.ElideRight, width
        )
        self.lbl_workspace.setText(elided)

    def _default_import_dir(self) -> Path:
        if self._last_import_dir.exists():
            return self._last_import_dir
        if self._default_source_root.exists():
            return self._default_source_root
        return self._project_root or Path.home()

    def _on_select_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Project folder", str(self._workspace_root)
        )
        if folder:
            self._load_project(Path(folder), "Project loaded")

    def _remember_explorer_group_expansion(self) -> None:
        self._explorer_group_expansion_by_id.update(
            collect_condition_group_expansion_state(self.tree_samples)
        )

    def _explorer_group_has_tree_children(
        self,
        group_id: str,
        df: pd.DataFrame,
    ) -> bool:
        batches = list_batches(self._project_root, group_id)
        group_df = (
            df[df["condition_group_id"].astype(str) == group_id]
            if "condition_group_id" in df.columns
            else df[df["group"].astype(str) == group_id]
        )
        return bool(batches) or not group_df.empty

    def _expanded_state_for_explorer_group(
        self,
        group_id: str,
        *,
        has_children: bool,
    ) -> bool:
        return default_expanded_state_for_condition_group(
            group_id,
            has_children=has_children,
            remembered=self._explorer_group_expansion_by_id,
        )

    def _add_explorer_group_item(
        self,
        group_id: str,
        display_name: str,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([display_name])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            condition_group_tree_meta(group_id),
        )
        configure_condition_group_tree_item(item)
        self.tree_samples.addTopLevelItem(item)
        return item

    def _add_explorer_sample_item(
        self,
        parent: QTreeWidgetItem,
        row: pd.Series,
    ) -> QTreeWidgetItem:
        row_dict = row.to_dict()
        label = sample_sidebar_display_label(row_dict)
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, sample_tree_meta(row_dict))
        status = str(row_dict.get("processing_status", ""))
        color = STATUS_COLORS.get(status)
        if color:
            item.setForeground(0, QBrush(color))
        parent.addChild(item)
        return item

    def _add_explorer_empty_sample_item(
        self,
        parent: QTreeWidgetItem,
        group_id: str,
        batch: dict[str, Any],
    ) -> QTreeWidgetItem:
        batch_name = str(batch.get("batch_name", ""))
        label = empty_sample_sidebar_label(batch_name)
        item = QTreeWidgetItem([label])
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            empty_sample_tree_meta(
                group_id,
                batch_name,
                batch_number=int(batch.get("batch_number", 1) or 1),
            ),
        )
        item.setForeground(0, QBrush(QColor("#666666")))
        parent.addChild(item)
        return item

    def _populate_explorer_group(
        self,
        parent: QTreeWidgetItem,
        group_id: str,
        df: pd.DataFrame,
    ) -> None:
        sync_registry_from_samples(self._project_root)
        batches = list_batches(self._project_root, group_id)
        group_df = (
            df[df["condition_group_id"].astype(str) == group_id]
            if "condition_group_id" in df.columns
            else df[df["group"].astype(str) == group_id]
        )

        if not batches and not group_df.empty:
            sync_registry_from_samples(self._project_root)
            batches = list_batches(self._project_root, group_id)

        seen_batches: set[str] = set()
        for batch in batches:
            batch_name = str(batch["batch_name"])
            safe = sanitize_batch_name(batch_name)
            seen_batches.add(safe)
            batch_rows = group_df[
                group_df["batch_name"].astype(str).apply(sanitize_batch_name) == safe
            ]
            if batch_rows.empty:
                self._add_explorer_empty_sample_item(parent, group_id, batch)
                continue
            batch_rows = batch_rows.sort_values(
                by=["frame_number", "sample_id"],
                key=lambda col: col.astype(str),
            )
            for _, row in batch_rows.iterrows():
                self._add_explorer_sample_item(parent, row)

        orphan = group_df[
            ~group_df["batch_name"]
            .astype(str)
            .apply(sanitize_batch_name)
            .isin(seen_batches)
        ]
        if not orphan.empty:
            for batch_name in sorted(
                orphan["batch_name"].astype(str).unique(),
                key=lambda n: sanitize_batch_name(n),
            ):
                safe = sanitize_batch_name(batch_name)
                orphan_batch = {
                    "batch_name": batch_name,
                    "batch_number": parse_batch_number_from_name(batch_name) or 0,
                }
                batch_rows = orphan[
                    orphan["batch_name"]
                    .astype(str)
                    .apply(sanitize_batch_name)
                    == safe
                ].sort_values(
                    by=["frame_number", "sample_id"],
                    key=lambda col: col.astype(str),
                )
                if batch_rows.empty:
                    self._add_explorer_empty_sample_item(
                        parent, group_id, orphan_batch
                    )
                else:
                    for _, row in batch_rows.iterrows():
                        self._add_explorer_sample_item(parent, row)

    def _refresh_sample_list(self) -> None:
        keep_id = (
            str(self._current_sample["sample_id"])
            if self._current_sample
            else None
        )
        self._remember_explorer_group_expansion()
        self.tree_samples.blockSignals(True)
        self.tree_samples.clear()
        if self._project_root is None:
            self.lbl_explorer_empty.setVisible(False)
            self.tree_samples.blockSignals(False)
            return
        try:
            df, _missing_ids = sync_samples_with_disk(self._project_root)
        except Exception as e:
            self.tree_samples.blockSignals(False)
            gui_dialogs.warning(self, "Metadata", str(e))
            return

        records = list_condition_group_records(self._project_root)
        if not records:
            self.lbl_explorer_empty.setVisible(True)
            self._set_active_sample(None)
            self._clear_preview_pane()
            self.tree_samples.blockSignals(False)
            return

        self.lbl_explorer_empty.setVisible(False)
        for record in records:
            has_children = self._explorer_group_has_tree_children(record.id, df)
            should_expand = self._expanded_state_for_explorer_group(
                record.id,
                has_children=has_children,
            )
            group_item = self._add_explorer_group_item(
                record.id,
                record.name,
            )
            self._populate_explorer_group(group_item, record.id, df)
            group_item.setExpanded(should_expand)

        if keep_id:
            item = restore_selected_sample_by_id(self.tree_samples, keep_id)
            if item is None:
                self._set_active_sample(None)
                self._clear_preview_pane()
        else:
            sample_items = self._iter_sample_tree_items()
            if sample_items:
                self.tree_samples.setCurrentItem(sample_items[0])
            else:
                self._set_active_sample(None)
                self._clear_preview_pane()

        self._sync_combo_from_tree_selection()
        self.tree_samples.blockSignals(False)
        current = self.tree_samples.currentItem()
        if current is not None and self._is_sample_tree_item(current):
            self._load_sample_from_tree_item(current)

    def _on_remove_missing_samples(self) -> None:
        if self._project_root is None:
            return
        _, missing_ids = sync_samples_with_disk(self._project_root)
        if not missing_ids:
            return
        if self._ask_yes_no(
            "Remove Missing Samples",
            f"Remove {len(missing_ids)} Sample(s) whose copied video data is missing?",
            informative="Only workspace metadata is updated.",
        ):
            remove_samples_from_metadata(self._project_root, missing_ids)
            self._refresh_sample_list()

    def _clear_preview_pane(self) -> None:
        self.lbl_auto_export_name.setText("Auto name: —")
        self.edit_export_name.clear()
        self.reset_preview_state(
            clear_image=True,
            placeholder=self._SELECT_SAMPLE_HINT,
        )

    def _on_explorer_selection_changed(
        self,
        current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem],
    ) -> None:
        self._sync_combo_from_tree_selection()
        if current is None:
            self._metric_analysis_view_active = False
            self._set_active_sample(None)
            self.reset_preview_state(
                clear_image=True,
                placeholder=self._SELECT_SAMPLE_HINT,
            )
            self.update_tracking_result_panel()
            self._refresh_roi_save_status_from_context()
            return
        if not self._is_sample_tree_item(current):
            return
        self._load_sample_from_tree_item(current)

    def _load_sample_from_tree_item(self, item: QTreeWidgetItem) -> None:
        data = self._tree_item_meta(item)
        if not data or data.get("item_type") != ITEM_TYPE_SAMPLE:
            return

        was_metric_analysis_view = self._metric_analysis_view_active
        resume_playback = self._preview_playing if was_metric_analysis_view else False
        self._playback_pause()

        self._set_active_sample(data)
        group = str(data.get("group", ""))
        if (
            group
            and self._project_root is not None
            and condition_group_exists(self._project_root, group)
            and self._current_condition_group() != group
        ):
            self._refresh_condition_group_combo(select=group)
        if data.get("processing_status") == "missing_file":
            return

        sid = str(data.get("sample_id", ""))
        self._preview_page.setUpdatesEnabled(False)
        try:
            if was_metric_analysis_view:
                self._clear_sample_specific_metric_state()
                self._ensure_metric_view_shell_visible()
                self._set_preview_mode_banner(f"{_METRIC_ANALYSIS_VIEW_LABEL} — loading…")
                if not self._load_sample_data_context(render_full_preview=False):
                    self._show_metric_analysis_placeholder(
                        "Metric Analysis is unavailable because this Sample "
                        "does not have valid Data."
                    )
                else:
                    self.update_tracking_result_panel(sid)
                    self._display_metric_analysis_view_for_current_sample(
                        resume_playback=resume_playback,
                    )
            else:
                self.reset_preview_state(clear_image=True)
                self.update_tracking_result_panel(sid)
                self._load_full_roi_preview_for_current_sample()
        finally:
            self._preview_page.setUpdatesEnabled(True)
            self._preview_page.update()
        self._refresh_roi_save_status_from_context()
        self._update_metric_freshness_label()

    def _sample_file_path(self) -> Optional[Path]:
        if self._project_root is None or self._current_sample is None:
            return None
        return self._project_root / str(self._current_sample["stored_path"])

    def _apply_annotation_from_dict(
        self, ann: dict[str, Any], *, render_canvas: bool = True
    ) -> None:
        self._orientation, roi = annotation_from_legacy(ann)
        self._reference_frame_index = int(ann.get("reference_frame_index", 0))
        self._loaded_sample_notes = str(ann.get("notes", ""))
        if render_canvas:
            self._refresh_display(keep_roi=False)
            if roi is not None:
                oriented = self._oriented_frame()
                if oriented is not None:
                    self.canvas.set_rect_roi(
                        roi.clamp(oriented.shape[1], oriented.shape[0])
                    )
        elif roi is not None:
            oriented = self._oriented_frame()
            if oriented is not None:
                self.canvas.set_rect_roi(
                    roi.clamp(oriented.shape[1], oriented.shape[0])
                )
            else:
                self.canvas.set_rect_roi(roi)
        else:
            self.canvas.set_rect_roi(None)
        self._loaded_annotation_source = str(ann.get("annotation_source", "manual"))
        self._roi_user_adjusted = False
        self._roi_autosave_pending = False
        self._update_orientation_label()
        self._refresh_roi_save_status_from_context()
        self._refresh_roi_preview_panel()
        self._update_metric_freshness_label()

    def _apply_auto_suggested_roi(self, *, render_canvas: bool) -> None:
        oriented = self._oriented_frame()
        if oriented is None:
            return
        try:
            crop = detect_tracking_crop(oriented)
            if crop.confidence >= AUTO_APPLY_ROI_CONFIDENCE:
                self.canvas.set_rect_roi(tracking_crop_to_rect(crop))
                self._loaded_annotation_source = "auto_suggested"
                self._roi_user_adjusted = False
        except ValueError:
            pass

    def _update_current_sample_panel_fields(
        self, sid: str, frame: np.ndarray, idx: int, total: int
    ) -> None:
        assert self._current_sample is not None
        self._sync_sample_frame_ui(idx, total)
        h, w = frame.shape[:2]
        self.lbl_frame_info.setText(f"Frame {idx}/{max(0, total-1)} ({w}×{h})")
        auto_name = (
            display_export_name_for_row(self._project_root, self._current_sample)
            if self._project_root is not None
            else str(self._current_sample.get("auto_export_name", ""))
        )
        custom = str(self._current_sample.get("custom_export_name", "")).strip()
        final_name = custom or auto_name
        self.lbl_auto_export_name.setText(f"Auto name: {auto_name or '—'}")
        self.edit_export_name.blockSignals(True)
        self.edit_export_name.setText(final_name)
        self.edit_export_name.blockSignals(False)
        self._update_playback_controls_state()

    def _load_sample_data_context(self, *, render_full_preview: bool = True) -> bool:
        path = self._sample_file_path()
        if path is None or not path.exists():
            if render_full_preview:
                gui_dialogs.warning(self, "Load", "File not found.")
            return False
        if self._project_root is None or self._current_sample is None:
            return False
        sid = str(self._current_sample["sample_id"])
        ann = get_sample_annotation(self._project_root, sid)
        ref_idx = int(ann.get("reference_frame_index", 0)) if ann else 0
        try:
            frame, idx, total = load_media_frame(path, ref_idx)
        except MediaLoadError as e:
            if render_full_preview:
                gui_dialogs.critical(self, "Load", str(e))
            return False
        self._base_frame = frame
        self._frame_index = idx
        self._reference_frame_index = idx
        self._total_frames = total
        self._orientation = OrientationState()
        self._update_current_sample_panel_fields(sid, frame, idx, total)

        if ann:
            self._apply_annotation_from_dict(ann, render_canvas=render_full_preview)
        elif render_full_preview:
            self._loaded_sample_notes = ""
            self._refresh_display(keep_roi=False)
            self._apply_auto_suggested_roi(render_canvas=True)
        else:
            self._loaded_sample_notes = ""
            self.canvas.set_rect_roi(None)
            self._apply_auto_suggested_roi(render_canvas=False)

        if render_full_preview:
            self._preview_mode = "full"
            self._set_preview_mode_banner(None)
            self.update_tracking_result_panel()
            self._update_metric_analysis_button_visibility()
        self._refresh_roi_save_status_from_context()
        self._update_metric_freshness_label()
        return True

    def _load_full_roi_preview_for_current_sample(self) -> None:
        self._load_sample_data_context(render_full_preview=True)

    def _on_frame_slider(self, value: int) -> None:
        self.spin_frame.blockSignals(True)
        self.spin_frame.setValue(value)
        self.spin_frame.blockSignals(False)
        self._load_frame_index(value)

    def _on_frame_spin(self, value: int) -> None:
        self.slider_frame.blockSignals(True)
        self.slider_frame.setValue(value)
        self.slider_frame.blockSignals(False)
        self._load_frame_index(value)

    def _load_frame_index(self, index: int) -> None:
        if self._preview_mode == "cropped_tracking" and self._cropped_preview is not None:
            if self._preview_playing:
                self._playback_pause()
            self._show_cropped_preview_frame(index)
            return
        path = self._sample_file_path()
        if path is None:
            return
        roi = self.canvas.rect_roi()
        try:
            frame, idx, total = load_media_frame(path, index)
        except MediaLoadError as e:
            gui_dialogs.critical(self, "Load", str(e))
            return
        self._base_frame = frame
        self._frame_index = idx
        self._total_frames = total
        self._refresh_display(keep_roi=True)
        if roi is not None:
            oriented = self._oriented_frame()
            if oriented is not None:
                self.canvas.set_rect_roi(
                    roi.clamp(oriented.shape[1], oriented.shape[0])
                )
        h, w = frame.shape[:2]
        self.lbl_frame_info.setText(f"Frame {idx}/{max(0, total-1)} ({w}×{h})")
        self._sync_sample_frame_ui(idx, total)
        self._update_playback_controls_state()

    def _refresh_recent_menu(self) -> None:
        refresh_recent_workspaces_menu(self)

    def _on_export_name_edited(self) -> None:
        if self._project_root is None or self._current_sample is None:
            return
        sid = str(self._current_sample["sample_id"])
        auto_name = str(self._current_sample.get("auto_export_name", ""))
        text = self.edit_export_name.text().strip()
        custom = None if text == auto_name or not text else text
        try:
            result = set_custom_export_name(self._project_root, sid, custom)
            self._current_sample.update(result)
            update_samples_csv(
                self._project_root / METADATA_DIR / SAMPLES_CSV,
                {"sample_id": sid, **result},
            )
            self._status(f"Export name: {result['final_export_name']}")
        except ValueError as e:
            gui_dialogs.warning(self, "Export Name", str(e))
            self.edit_export_name.setText(
                str(self._current_sample.get("final_export_name", auto_name))
            )

    def _menu_new_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "New workspace folder", str(self._workspace_root)
        )
        if folder:
            root = Path(folder)
            create_project_structure(root)
            self._load_project(root, "New workspace created")

    def _menu_refresh_workspace(self) -> None:
        if self._project_root is None:
            return
        migrate_workspace_schema(self._project_root)
        repair_batch_registry(self._project_root)
        self._refresh_sample_list()
        self._status("Workspace refreshed")

    def _menu_open_workspace_folder(self) -> None:
        if self._project_root is None:
            return
        import subprocess
        import sys

        path = str(self._project_root)
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def _after_purge_refresh(self, *, prefer_sample_id: str | None = None) -> None:
        if prefer_sample_id:
            row = self._sample_row_for_id(prefer_sample_id)
            self._set_active_sample(row or {"sample_id": prefer_sample_id})
        else:
            self._set_active_sample(None)
        self._refresh_sample_list()
        self.update_tracking_result_panel()

    def _populate_roi_actions_menu(
        self, menu: QMenu, *, inside_roi: bool = True
    ) -> None:
        menu.clear()
        suggest = menu.addAction("Suggest ROI from F-actin Signal")
        suggest.setToolTip(
            "Suggest a rectangular region with strong visible F-actin signal. "
            "Review and adjust before export."
        )
        suggest.triggered.connect(self._on_auto_suggest_roi)
        if inside_roi:
            clear = menu.addAction("Clear ROI")
            clear.setToolTip("Remove the current ROI rectangle from the preview.")
            clear.triggered.connect(self._on_clear_roi)
            export_roi = menu.addAction("Export ROI")
            export_roi.setToolTip(
                "Crop and export processed outputs to the processed/ folder "
                "using the auto-generated export name."
            )
            export_roi.triggered.connect(self._on_process_sample)

    def _ask_yes_no(
        self,
        title: str,
        text: str,
        *,
        informative: str = "",
    ) -> bool:
        return gui_dialogs.ask_yes_no(self, title, text, informative=informative)

    def _ask_remove_workspace_raw(
        self,
        *,
        title: str = "Copied Video Data",
        text: str = "Remove the workspace's copied video data for this file?",
    ) -> bool | None:
        """Return True to remove copied video data, False to keep, None if cancelled."""
        chk = QCheckBox("Also remove the workspace's copied video data")
        chk.setChecked(False)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setCheckBox(chk)
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if box.exec() != QMessageBox.StandardButton.Ok:
            return None
        return chk.isChecked()

    def _confirm_delete_sample(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle("Delete Sample")
        box.setText("Delete this Sample?")
        delete_btn = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        return box.clickedButton() is delete_btn

    def _confirm_typed_phrase(
        self,
        title: str,
        message: str,
        phrase: str,
    ) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(message))
        layout.addWidget(QLabel(f'Type "{phrase}" to confirm:'))
        edit = QLineEdit()
        layout.addWidget(edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        return edit.text().strip() == phrase

    def _show_purge_summary(self, title: str, stats: dict[str, Any]) -> None:
        lines = [f"  • {k}: {v}" for k, v in stats.items() if v not in (None, "", [])]
        QMessageBox.information(
            self,
            title,
            "Operation finished.\n\n" + ("\n".join(lines) if lines else "Done."),
        )

    def _on_explorer_context_menu(self, pos) -> None:
        if self._require_project_root() is None:
            return
        item = self.tree_samples.itemAt(pos)
        menu = QMenu(self)
        meta = self._tree_item_meta(item)

        if item is None:
            menu.addAction(
                "New Condition Group",
                self._on_create_condition_group,
            )
            self._add_explorer_refresh_action(menu)
            menu.exec(self.tree_samples.viewport().mapToGlobal(pos))
            return

        item_type = meta.get("item_type") if meta else None

        if item_type == ITEM_TYPE_CONDITION_GROUP:
            group_id = str(meta.get("condition_group_id", ""))
            menu.addAction(
                "Add Sample(s)",
                lambda gid=group_id: self._on_add_sample(gid),
            )
            menu.addAction(
                "Rename Condition Group",
                lambda gid=group_id: self._ctx_rename_condition_group(gid),
            )
            menu.addAction(
                "Delete Condition Group",
                lambda gid=group_id: self._ctx_delete_condition_group(gid),
            )
            self._add_explorer_refresh_action(menu)
        elif item_type in (ITEM_TYPE_SAMPLE, ITEM_TYPE_EMPTY_SAMPLE):
            group = str(meta.get("group", self._ensure_filter_group_valid()))
            batch_name = str(meta.get("batch_name", ""))
            menu.addAction(
                "Replace Data",
                lambda g=group, b=batch_name: self._ctx_replace_sample_data(g, b),
            )
            menu.addSeparator()
            menu.addAction(
                "Rename Sample",
                lambda g=group, b=batch_name: self._ctx_rename_batch(g, b),
            )
            menu.addAction(
                "Delete Sample",
                lambda g=group, b=batch_name: self._ctx_delete_batch(g, b),
            )
            self._add_explorer_refresh_action(menu)
        else:
            menu.addAction(
                "New Condition Group",
                self._on_create_condition_group,
            )
            self._add_explorer_refresh_action(menu)

        if not menu.isEmpty():
            menu.exec(self.tree_samples.viewport().mapToGlobal(pos))

    def _ctx_rename_condition_group(self, group_id: str) -> None:
        self._refresh_condition_group_combo(select=group_id)
        self._on_rename_condition_group()

    def _ctx_delete_condition_group(self, group_id: str) -> None:
        self._refresh_condition_group_combo(select=group_id)
        self._on_delete_condition_group()

    def _ctx_replace_sample_data(self, group: str, batch_name: str) -> None:
        if self._project_root is None or not group or not batch_name:
            gui_dialogs.warning(
                self,
                "Replace Data",
                "Could not determine the sample for data replacement.",
            )
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Replace Data",
            str(self._default_import_dir()),
            DATA_IMPORT_FILTER,
        )
        if not path_str:
            return
        source = Path(path_str)
        self._last_import_dir = source.parent
        row = get_primary_data_row(self._project_root, group, batch_name)
        if row and sample_has_derived_state(self._project_root, str(row["sample_id"])):
            reply = QMessageBox.question(
                self,
                "Replace Data",
                "This sample has ROI, tracking, or processed outputs.\n\n"
                "Replacing the imported video will clear those derived results. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        if self._preview_mode == "cropped_tracking":
            self.reset_preview_state(clear_image=True)
        try:
            updated = replace_sample_data(
                self._project_root, group, batch_name, source
            )
        except ValueError as exc:
            gui_dialogs.warning(self, "Replace Data", str(exc))
            return
        except (MediaLoadError, OSError) as exc:
            gui_dialogs.warning(self, "Replace Data", f"Import failed: {exc}")
            return
        final_batch_name = str(updated.get("batch_name", batch_name))
        self._set_last_import_breed(group)
        self.reset_preview_state(clear_image=True)
        self._after_import_refresh(group=group, batch_name=final_batch_name)
        self._refresh_analysis_if_visible()
        self._status(f"Replaced data for {final_batch_name} with {source.name}")

    def _ctx_rename_batch(self, group: str, batch_name: str) -> None:
        if self._project_root is None:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Sample",
            "New sample name:",
            text=batch_name,
        )
        if not ok or not new_name.strip():
            return
        try:
            rename_batch(self._project_root, group, batch_name, new_name.strip())
            self._refresh_sample_list()
            self._select_sample_header(group, sanitize_batch_name(new_name))
        except (ValueError, OSError) as e:
            gui_dialogs.critical(self, "Rename Sample", str(e))

    def _ctx_purge_file_annotations(self, sample_id: str) -> None:
        if self._project_root is None:
            return
        if not self._ask_yes_no(
            "Purge Sample Annotations",
            "Clear annotations, previews, and processed outputs for this sample?",
            informative=(
                "The sample entry and the workspace's copied video will be kept."
            ),
        ):
            return
        try:
            stats = purge_sample_annotations_only(self._project_root, sample_id)
            self._invalidate_tracking_result_for_sample(sample_id)
            self._after_purge_refresh(prefer_sample_id=sample_id)
            self._show_purge_summary("Purge Complete", stats)
        except (ValueError, OSError) as e:
            gui_dialogs.warning(self, "Purge", str(e))

    def _ctx_purge_file_complete(
        self, sample_id: str, meta: dict[str, Any]
    ) -> None:
        if self._project_root is None:
            return
        if not self._ask_yes_no(
            "Remove Sample",
            "Remove this sample from the workspace?",
            informative=(
                "This removes its metadata, annotations, previews, and processed "
                "outputs. Files on your computer outside this workspace are not "
                "deleted."
            ),
        ):
            return
        remove_raw = self._ask_remove_workspace_raw()
        if remove_raw is None:
            return
        try:
            stats = purge_sample_completely(
                self._project_root,
                sample_id,
                remove_workspace_raw=remove_raw,
            )
            group = str(meta.get("group", ""))
            batch_name = str(meta.get("batch_name", ""))
            self._invalidate_tracking_result_for_sample(sample_id)
            self._set_active_sample(None)
            self._after_purge_refresh()
            self._show_purge_summary("Purge Complete", stats)
            if group and batch_name and not batch_has_samples(
                self._project_root, group, batch_name
            ):
                num = parse_batch_number_from_name(batch_name) or 1
                sample_label = display_sample_label(num, batch_name)
                if self._ask_yes_no(
                    "Empty Sample",
                    f'Remove empty Sample "{sample_label}"?',
                ):
                    delete_empty_batch(self._project_root, group, batch_name)
            self._refresh_sample_list()
        except (ValueError, OSError) as e:
            gui_dialogs.warning(self, "Purge", str(e))

    def _ctx_delete_file(self, sample_id: str, meta: dict[str, Any]) -> None:
        if self._project_root is None:
            return
        if not self._ask_yes_no(
            "Remove Sample",
            "Remove this sample and its imported video from the workspace?",
            informative=(
                "This removes its metadata, annotations, previews, and processed "
                "outputs. The workspace's copied video data can be removed in the "
                "next step if you choose."
            ),
        ):
            return
        remove_raw = self._ask_remove_workspace_raw()
        if remove_raw is None:
            return
        try:
            delete_sample_from_batch(
                self._project_root,
                sample_id,
                remove_workspace_raw=remove_raw,
            )
            group = str(meta.get("group", ""))
            batch_name = str(meta.get("batch_name", ""))
            self._invalidate_tracking_result_for_sample(sample_id)
            self._set_active_sample(None)
            self._after_purge_refresh()
            self._status(f"Deleted {sample_id} from sample")
            if group and batch_name and not batch_has_samples(
                self._project_root, group, batch_name
            ):
                num = parse_batch_number_from_name(batch_name) or 1
                sample_label = display_sample_label(num, batch_name)
                if self._ask_yes_no(
                    "Empty Sample",
                    f'Remove empty Sample "{sample_label}"?',
                ):
                    delete_empty_batch(self._project_root, group, batch_name)
                    self._refresh_sample_list()
        except (ValueError, OSError) as e:
            gui_dialogs.critical(self, "Delete Failed", str(e))

    def _ctx_purge_batch_annotations(self, group: str, batch_name: str) -> None:
        if self._project_root is None:
            return
        num = parse_batch_number_from_name(batch_name) or 1
        sample_label = display_sample_label(num, batch_name)
        if not self._ask_yes_no(
            "Clear Sample Annotations",
            f"Clear annotations and processed outputs for {sample_label}?",
            informative=(
                "Data entries and the workspace's copied video data will be kept."
            ),
        ):
            return
        try:
            stats = purge_batch_annotations(self._project_root, group, batch_name)
            self._after_purge_refresh()
            self._show_purge_summary("Purge Complete", stats)
        except (ValueError, OSError) as e:
            gui_dialogs.warning(self, "Purge", str(e))

    def _ctx_complete_batch_purge(self, group: str, batch_name: str) -> None:
        if self._project_root is None:
            return
        if not self._confirm_typed_phrase(
            "Complete Sample Purge",
            "This will completely remove this Sample from the workspace, including "
            "its label, data entries, annotations, previews, and processed outputs. "
            "You can optionally remove the workspace's copied video data next. "
            "Files outside this workspace are not deleted. This cannot be undone.",
            "PURGE SAMPLE",
        ):
            QMessageBox.information(
                self, "Cancelled", 'Type exactly "PURGE SAMPLE" to run this action.'
            )
            return
        remove_raw = self._ask_remove_workspace_raw(
            text="Also remove the workspace's copied video data for this Sample?",
        )
        if remove_raw is None:
            return
        try:
            stats = complete_batch_purge(
                self._project_root,
                group,
                batch_name,
                remove_workspace_raw=remove_raw,
            )
            self._current_sample = None
            self._after_purge_refresh()
            self._show_purge_summary("Complete Sample Purge", stats)
        except (ValueError, OSError) as e:
            gui_dialogs.warning(self, "Purge", str(e))

    def _current_selection_in_batch(self, group: str, batch_name: str) -> bool:
        if not self._current_sample:
            return False
        return (
            str(self._current_sample.get("group", "")) == group
            and sanitize_batch_name(str(self._current_sample.get("batch_name", "")))
            == sanitize_batch_name(batch_name)
        )

    def _clear_preview_before_sample_delete(
        self, group: str, batch_name: str
    ) -> None:
        if (
            self._current_selection_in_batch(group, batch_name)
            or self._preview_mode == "cropped_tracking"
        ):
            self.reset_preview_state(
                clear_image=True,
                placeholder=self._SELECT_SAMPLE_HINT,
            )

    def _ctx_delete_batch(self, group: str, batch_name: str) -> None:
        if self._project_root is None:
            return
        sample_name = sanitize_batch_name(batch_name)
        has_files = batch_has_samples(self._project_root, group, batch_name)
        if not self._confirm_delete_sample():
            return
        try:
            if has_files:
                stats = delete_sample_and_artifacts(
                    self._project_root,
                    group,
                    batch_name,
                    remove_workspace_raw=True,
                )
                self._clear_preview_before_sample_delete(group, batch_name)
                self._set_active_sample(None)
                self._after_purge_refresh()
                self._refresh_analysis_if_visible()
                self._show_purge_summary("Sample Deleted", stats)
            else:
                delete_empty_batch(self._project_root, group, batch_name)
                self._clear_preview_before_sample_delete(group, batch_name)
                self._set_active_sample(None)
                self._after_purge_refresh()
                self._refresh_analysis_if_visible()
                self._status(f'Deleted Sample "{sample_name}"')
        except (ValueError, OSError) as e:
            gui_dialogs.warning(self, "Delete Sample", str(e))

    def _menu_purge_filtered(self) -> None:
        if self._project_root is None:
            return
        dlg = PurgeFilteredDialog(self, self._project_root)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        ids = dlg.selected_sample_ids()
        if not ids:
            gui_dialogs.information(self, "Purge", "No samples match the filters.")
            return
        if not self._ask_yes_no(
            "Confirm Filtered Purge",
            f"Clear annotations and processed outputs for {len(ids)} Sample(s)?",
            informative="The workspace's copied video data will be kept.",
        ):
            return
        stats = purge_filtered_samples(self._project_root, ids)
        self._refresh_sample_list()
        QMessageBox.information(
            self,
            "Purge Complete",
            f"Updated {stats['samples_updated']} sample(s).",
        )

    def _menu_delete_empty_batch(self) -> None:
        if self._project_root is None:
            return
        group = self._ensure_filter_group_valid()
        batch_name = pick_empty_batch_name(self, self._project_root, group)
        if not batch_name:
            return
        num = parse_batch_number_from_name(batch_name) or 1
        sample_label = display_sample_label(num, batch_name)
        if not self._ask_yes_no(
            "Delete Empty Sample",
            f'Remove empty Sample "{sample_label}" from this Condition Group?',
        ):
            return
        try:
            delete_empty_batch(self._project_root, group, batch_name)
            self._after_purge_refresh()
            self._status(f"Deleted empty sample {sample_label}")
        except ValueError as e:
            gui_dialogs.warning(self, "Delete Sample", str(e))

    def _menu_delete_file_from_batch(self) -> None:
        if self._project_root is None or self._current_sample is None:
            gui_dialogs.warning(self, "Delete", "Select a sample in Explorer first.")
            return
        sid = str(self._current_sample["sample_id"])
        self._ctx_delete_file(sid, self._current_sample)

    def _menu_review_batch(self) -> None:
        self._refresh_sample_list()
        self._status(
            "Review propagated annotations and adjust each ROI as needed."
        )

    def _menu_how_to_run(self) -> None:
        readme = resource_path("README.md")
        text = (
            "Typical workflow:\n\n"
            "1. Create or open a workspace (File menu).\n"
            "2. Add a Condition Group and import AVI/MP4 samples.\n"
            "3. Orient each video, mark an ROI, and export processed output.\n"
            "4. Review metrics and open Analysis for condition-group comparisons.\n"
        )
        if readme.is_file():
            text += f"\nFor installation and setup, see:\n{readme}"
        gui_dialogs.information(self, "Getting Started", text)

    def _menu_about(self) -> None:
        QMessageBox.about(
            self,
            "About ActinTrackCV",
            f"ActinTrackCV {__version__}\n\n"
            "ActinTrackCV — Arabidopsis reproductive-cell F-actin fluorescence microscopy: "
            "2D time-lapse preprocessing, orientation, ROI selection, template tracking, "
            "optical-flow motion index, and cropped export for actin cable velocity analysis.\n\n"
            "Suggest ROI from F-actin Signal proposes a rectangular region where "
            "bright F-actin signal is strongest. Review, adjust, approve, or clear "
            "the ROI before export.",
        )

    def _confirm_project_root_if_source_folder(self, root: Path) -> Optional[Path]:
        if root.resolve() != DEFAULT_SOURCE_ROOT.resolve():
            return root
        reply = QMessageBox.question(
            self,
            "Use workspace?",
            "Use the default workspace folder instead of the development source folder?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            return self._workspace_root
        return root if reply == QMessageBox.StandardButton.No else None


def run_app() -> None:
    breadcrumb("app start", version=__version__)
    app = QApplication(sys.argv)
    app.setApplicationName("ActinTrackCV")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ActinTrackCV")
    icon = _app_qicon()
    if icon is not None:
        app.setWindowIcon(icon)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
