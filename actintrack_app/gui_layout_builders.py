"""Main window layout construction helpers for ActinTrackCV.

Extracted from ``MainWindow`` to reduce ``gui.py`` size while preserving the
exact widget hierarchy, attribute names, signal wiring, and visual layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from actintrack_app.analysis_view import AnalysisViewWidget
from actintrack_app.explorer_tree import ExplorerTreeWidget
from actintrack_app.gui_canvas import ImageCanvas
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
    apply_form_group_margins,
    apply_hint_style,
    apply_muted_hint_style,
    apply_panel_inner_margins,
    apply_panel_margins,
    apply_small_secondary_style,
    configure_orient_panel_action_button,
)
from actintrack_app.motion_index import (
    TRACKING_METHOD_BRIGHTEST_LOCAL,
    TRACKING_METHOD_TEMPLATE,
    MotionIndexParams,
)
from actintrack_app.optical_flow_motion_index import OpticalFlowSettings
from actintrack_app.optical_flow_overlay import OpticalFlowVisualizationSettings
from actintrack_app.qt_spin_boxes import NoWheelDoubleSpinBox, NoWheelSpinBox

if TYPE_CHECKING:
    from actintrack_app.gui import MainWindow

LEFT_PANEL_MIN_WIDTH = 200
RIGHT_PANEL_MIN_WIDTH = 260
DEFAULT_SPLITTER_SIZES = [LEFT_PANEL_MIN_WIDTH, 900, RIGHT_PANEL_MIN_WIDTH]
PLAYBACK_SPEED_OPTIONS = ("0.25×", "0.5×", "1×", "1.5×", "2×")
METRIC_ANALYSIS_VIEW_LABEL = "Metric Analysis"
ROI_PREVIEW_PANEL_OBJECT_NAME = "roiPreviewPanel"
ROI_PREVIEW_PANEL_MIN_WIDTH = 180
ROI_PREVIEW_PANEL_MAX_WIDTH = 280
ROI_PREVIEW_CANVAS_MIN_WIDTH = 160
ROI_PREVIEW_CANVAS_MIN_HEIGHT = 120


def configure_orient_roi_control(widget: QWidget) -> None:
    widget.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
    if isinstance(widget, QDoubleSpinBox):
        widget.setMaximumWidth(72)


def configure_tracking_field(widget: QWidget, *, full_column: bool = False) -> None:
    widget.setMinimumWidth(160 if full_column else 140)
    widget.setMinimumHeight(36 if full_column else 30)
    policy = QSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    widget.setSizePolicy(policy)


def add_tracking_setting_row(
    layout: QVBoxLayout,
    label_text: str,
    widget: QWidget,
    tooltip: str,
) -> None:
    label = QLabel(label_text)
    label.setWordWrap(True)
    label.setToolTip(tooltip)
    widget.setToolTip(tooltip)
    layout.addWidget(label)
    layout.addWidget(widget)


def assemble_playback_controls_layout(
    *,
    play_button: QPushButton,
    frame_label: QLabel,
    frame_slider: QSlider,
    speed_label: QLabel,
    speed_combo: QComboBox,
    speed_row_before_stretch: tuple[QWidget, ...] = (),
    speed_row_after_stretch: tuple[QWidget, ...] = (),
) -> QVBoxLayout:
    """Shared two-row playback layout for full-sample and cropped preview."""
    layout = QVBoxLayout()
    layout.setSpacing(CONTROL_ROW_SPACING)
    transport_row = QHBoxLayout()
    transport_row.addWidget(play_button)
    transport_row.addWidget(frame_label)
    transport_row.addWidget(frame_slider, stretch=1)
    speed_row = QHBoxLayout()
    speed_row.addWidget(speed_label)
    speed_row.addWidget(speed_combo)
    for widget in speed_row_before_stretch:
        speed_row.addWidget(widget)
    speed_row.addStretch()
    for widget in speed_row_after_stretch:
        speed_row.addWidget(widget)
    layout.addLayout(transport_row)
    layout.addLayout(speed_row)
    return layout


def create_playback_play_button(window: MainWindow, *, tooltip: str) -> QPushButton:
    btn = QPushButton("Play")
    btn.setToolTip(tooltip)
    btn.clicked.connect(window._playback_toggle)
    return btn


def create_playback_frame_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setMinimumWidth(PLAYBACK_FRAME_LABEL_MIN_WIDTH)
    return label


def create_playback_slider(*, value_changed) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimumWidth(PLAYBACK_SLIDER_MIN_WIDTH)
    slider.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    slider.valueChanged.connect(value_changed)
    return slider


def create_playback_speed_label() -> QLabel:
    return QLabel("Speed:")


def create_playback_speed_combo(window: MainWindow, *, value_changed) -> QComboBox:
    combo = QComboBox()
    combo.addItems(list(PLAYBACK_SPEED_OPTIONS))
    combo.setCurrentText("1×")
    combo.setMinimumWidth(PLAYBACK_SPEED_COMBO_MIN_WIDTH)
    combo.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Fixed,
    )
    combo.currentTextChanged.connect(value_changed)
    return combo


def build_main_workspace(window: MainWindow) -> None:
    central = QWidget()
    window.setCentralWidget(central)
    layout = QHBoxLayout(central)
    splitter = QSplitter(Qt.Orientation.Horizontal)
    window._left_sidebar = build_left_sidebar(window)
    splitter.addWidget(window._left_sidebar)
    window._preview_page = build_center_preview_page(window)
    preview_page = window._preview_page
    window._analysis_view = AnalysisViewWidget()
    window._center_stack = QStackedWidget()
    window._center_stack.addWidget(preview_page)
    window._center_stack.addWidget(window._analysis_view)
    window._right_sidebar = build_right_sidebar(window)
    splitter.addWidget(window._center_stack)
    splitter.addWidget(window._right_sidebar)
    splitter.setSizes(list(DEFAULT_SPLITTER_SIZES))
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setStretchFactor(2, 0)
    splitter.setCollapsible(0, False)
    splitter.setCollapsible(1, False)
    splitter.setCollapsible(2, False)
    window._main_splitter = splitter
    layout.addWidget(splitter)
    window.setStatusBar(QStatusBar())


def build_left_sidebar(window: MainWindow) -> QWidget:
    """Explorer sidebar (import/setup is in the menu bar)."""
    panel = QWidget()
    panel.setMinimumWidth(LEFT_PANEL_MIN_WIDTH)
    panel.setMaximumWidth(360)
    layout = QVBoxLayout(panel)
    apply_panel_margins(layout)
    layout.addWidget(build_samples_panel(window), stretch=1)
    return panel


def build_samples_panel(window: MainWindow) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(CONTROL_ROW_SPACING)
    window.lbl_workspace = QLabel("—")
    window.lbl_workspace.setWordWrap(False)
    apply_small_secondary_style(window.lbl_workspace)
    layout.addWidget(window.lbl_workspace)
    window.combo_filter_group = QComboBox()
    window.combo_filter_group.setVisible(False)
    window.lbl_explorer_empty = QLabel("Create a Condition Group to begin.")
    window.lbl_explorer_empty.setWordWrap(True)
    apply_muted_hint_style(window.lbl_explorer_empty)
    window.lbl_explorer_empty.setVisible(False)
    layout.addWidget(window.lbl_explorer_empty)
    window.tree_samples = ExplorerTreeWidget()
    window.tree_samples.setHeaderHidden(True)
    window.tree_samples.setRootIsDecorated(True)
    window.tree_samples.setAlternatingRowColors(False)
    window.tree_samples.setStyleSheet(
        "QTreeWidget { background: palette(base); border: none; }"
        "QTreeWidget::item:selected {"
        "  background: palette(highlight);"
        "  color: palette(highlighted-text);"
        "}"
    )
    window.tree_samples.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    window.tree_samples.currentItemChanged.connect(window._on_explorer_selection_changed)
    window.tree_samples.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    window.tree_samples.customContextMenuRequested.connect(
        window._on_explorer_context_menu
    )
    window.tree_samples.sample_drop_requested.connect(
        window._on_explorer_sample_dropped
    )
    layout.addWidget(window.tree_samples, stretch=1)
    return panel


def build_center_preview_page(window: MainWindow) -> QWidget:
    preview_page = QWidget()
    center_layout = QVBoxLayout(preview_page)
    window.lbl_preview_mode = QLabel("")
    window.lbl_preview_mode.setWordWrap(True)
    apply_hint_style(window.lbl_preview_mode)
    window.lbl_preview_mode.hide()
    center_layout.addWidget(window.lbl_preview_mode)

    metric_mode_row = QHBoxLayout()
    window.lbl_metric_mode = QLabel("Preview mode:")
    window.combo_metric_mode = QComboBox()
    window.combo_metric_mode.addItem("Template Tracking", "template")
    window.combo_metric_mode.addItem("Optical Flow (Draft)", "optical_flow")
    window.combo_metric_mode.currentIndexChanged.connect(
        window._on_cropped_metric_mode_changed
    )
    metric_mode_row.addWidget(window.lbl_metric_mode)
    metric_mode_row.addWidget(window.combo_metric_mode)
    metric_mode_row.addStretch()
    window._metric_mode_widgets = (
        window.lbl_metric_mode,
        window.combo_metric_mode,
    )
    for widget in window._metric_mode_widgets:
        widget.hide()
    center_layout.addLayout(metric_mode_row)

    center_layout.addWidget(build_image_workspace_row(window), stretch=1)

    build_metric_status_strip(window, center_layout)
    window._hidden_frame_host = build_hidden_frame_controls(window)
    center_layout.addWidget(window._hidden_frame_host)
    build_cropped_playback_controls(window, center_layout)
    return preview_page


def build_image_workspace_row(window: MainWindow) -> QWidget:
    """Horizontal hero image column plus read-only adjacent ROI preview."""
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(PANEL_SECTION_SPACING)

    window._main_image_column = QWidget()
    main_image_layout = QVBoxLayout(window._main_image_column)
    main_image_layout.setContentsMargins(0, 0, 0, 0)
    main_image_layout.setSpacing(CONTROL_ROW_SPACING)

    window.canvas = ImageCanvas(window)
    main_image_layout.addWidget(window.canvas, stretch=1)
    build_roi_workflow_strip(window, main_image_layout)
    build_sample_playback_controls(window, main_image_layout)

    window._roi_preview_host = build_roi_preview_panel(window)

    row_layout.addWidget(window._main_image_column, stretch=1)
    row_layout.addWidget(window._roi_preview_host, stretch=0)
    window._image_workspace_row = row_widget
    return row_widget


def build_roi_preview_panel(window: MainWindow) -> QWidget:
    """Permanent read-only cropped ROI preview beside the microscope image."""
    host = QWidget()
    host.setObjectName(ROI_PREVIEW_PANEL_OBJECT_NAME)
    host.setMinimumWidth(ROI_PREVIEW_PANEL_MIN_WIDTH)
    host.setMaximumWidth(ROI_PREVIEW_PANEL_MAX_WIDTH)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(ROI_HINT_STATUS_SPACING)

    heading = QLabel("ROI preview")
    apply_small_secondary_style(heading)
    layout.addWidget(heading)

    window.lbl_roi_preview_empty = QLabel("Select a sample to preview the ROI.")
    window.lbl_roi_preview_empty.setWordWrap(True)
    apply_muted_hint_style(window.lbl_roi_preview_empty)
    window.lbl_roi_preview_empty.setAlignment(Qt.AlignmentFlag.AlignTop)
    layout.addWidget(window.lbl_roi_preview_empty)

    window.roi_preview_canvas = ImageCanvas(window)
    window.roi_preview_canvas.set_interactive(False)
    window.roi_preview_canvas.setMinimumSize(
        ROI_PREVIEW_CANVAS_MIN_WIDTH,
        ROI_PREVIEW_CANVAS_MIN_HEIGHT,
    )
    window.roi_preview_canvas.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Expanding,
    )
    window.roi_preview_canvas.hide()
    layout.addWidget(window.roi_preview_canvas, stretch=1)
    return host


def build_roi_workflow_strip(window: MainWindow, layout: QVBoxLayout) -> None:
    """ROI and metric status below the microscope image."""
    strip = QVBoxLayout()
    strip.setSpacing(ROI_HINT_STATUS_SPACING)

    window.lbl_roi_save_status = QLabel("—")
    window.lbl_roi_save_status.setWordWrap(True)
    window._set_roi_save_status("No ROI saved yet", saved=False)
    strip.addWidget(window.lbl_roi_save_status)

    metric_status_labels = QVBoxLayout()
    metric_status_labels.setSpacing(METRIC_STATUS_LABEL_SPACING)
    window.lbl_metric_status = QLabel("Metric status: Not analyzed")
    window.lbl_metric_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    apply_hint_style(window.lbl_metric_status)
    window.lbl_metric_status.hide()
    metric_status_labels.addWidget(window.lbl_metric_status)
    window.lbl_last_analyzed = QLabel("Last analyzed: —")
    window.lbl_last_analyzed.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    apply_hint_style(window.lbl_last_analyzed)
    window.lbl_last_analyzed.hide()
    metric_status_labels.addWidget(window.lbl_last_analyzed)
    strip.addLayout(metric_status_labels)

    layout.addLayout(strip)


def build_metric_status_strip(window: MainWindow, center_layout: QVBoxLayout) -> None:
    """Metric action buttons below the image workspace row."""
    window._metric_status_host = QFrame()
    window._metric_status_host.setObjectName(METRIC_STATUS_PANEL_OBJECT_NAME)
    window._metric_status_host.setStyleSheet(STYLE_METRIC_STATUS_PANEL)
    window._metric_status_host.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
    window._metric_status_host.hide()
    metric_status_layout = QVBoxLayout(window._metric_status_host)
    apply_panel_inner_margins(metric_status_layout)
    metric_status_layout.setSpacing(METRIC_STATUS_INNER_SPACING)

    metric_button_row = QHBoxLayout()
    metric_button_row.setSpacing(PANEL_SECTION_SPACING)
    metric_button_row.addStretch()
    window.btn_metric_analysis = window._tool_button(
        METRIC_ANALYSIS_VIEW_LABEL,
        "Open the cropped ROI metric analysis view with Template Tracking "
        "and Optical Flow metrics, overlay, and playback.",
        window._on_show_metric_analysis_view,
    )
    window.btn_metric_analysis.hide()
    metric_button_row.addWidget(window.btn_metric_analysis)
    window.btn_run_metrics = window._tool_button(
        "Run Metrics",
        "Compute Template Tracking and Optical Flow metrics for the current "
        "Sample using its marked ROI.",
        window._on_run_metrics_clicked,
    )
    window.btn_run_metrics.setEnabled(False)
    window.btn_run_metrics.hide()
    metric_button_row.addWidget(window.btn_run_metrics)
    metric_button_row.addStretch()
    metric_status_layout.addLayout(metric_button_row)

    center_layout.addSpacing(PANEL_SECTION_SPACING)
    center_layout.addWidget(window._metric_status_host)


def build_sample_playback_controls(window: MainWindow, parent_layout: QVBoxLayout) -> None:
    window.btn_playback_toggle = create_playback_play_button(
        window,
        tooltip="Play or pause through the loaded sample frames.",
    )
    window.lbl_sample_frame = create_playback_frame_label("Frame —")
    window.slider_sample_frame = create_playback_slider(
        value_changed=window._on_sample_frame_slider,
    )
    window.lbl_sample_playback_speed = create_playback_speed_label()
    window.combo_sample_playback_speed = create_playback_speed_combo(
        window,
        value_changed=window._on_sample_playback_speed_changed,
    )
    window.chk_playback_loop = QCheckBox("Loop")
    window.chk_playback_loop.setToolTip(
        "When checked, playback restarts at the first frame after the last frame."
    )
    window.chk_playback_loop.setChecked(True)
    window._sample_playback_widgets = (
        window.btn_playback_toggle,
        window.lbl_sample_frame,
        window.slider_sample_frame,
        window.lbl_sample_playback_speed,
        window.combo_sample_playback_speed,
        window.chk_playback_loop,
    )
    window._hide_widgets(window._sample_playback_widgets)
    parent_layout.addLayout(
        assemble_playback_controls_layout(
            play_button=window.btn_playback_toggle,
            frame_label=window.lbl_sample_frame,
            frame_slider=window.slider_sample_frame,
            speed_label=window.lbl_sample_playback_speed,
            speed_combo=window.combo_sample_playback_speed,
            speed_row_before_stretch=(window.chk_playback_loop,),
        )
    )


def build_cropped_playback_controls(window: MainWindow, center_layout: QVBoxLayout) -> None:
    window.btn_preview_toggle = create_playback_play_button(
        window,
        tooltip="Play or pause cropped preview playback.",
    )
    window.lbl_cropped_frame = create_playback_frame_label("Frame 1 / 1")
    window.slider_cropped_frame = create_playback_slider(
        value_changed=window._on_cropped_preview_frame_slider,
    )
    window.lbl_preview_speed = create_playback_speed_label()
    window.combo_preview_speed = create_playback_speed_combo(
        window,
        value_changed=window._on_preview_speed_changed,
    )
    window.btn_return_full_preview = QPushButton("Return to Full Preview")
    window.btn_return_full_preview.clicked.connect(window._exit_cropped_preview_mode)
    window.btn_return_full_preview.setSizePolicy(
        QSizePolicy.Policy.Minimum,
        QSizePolicy.Policy.Fixed,
    )
    window._preview_control_widgets = (
        window.btn_preview_toggle,
        window.lbl_cropped_frame,
        window.slider_cropped_frame,
        window.lbl_preview_speed,
        window.combo_preview_speed,
        window.btn_return_full_preview,
    )
    window._hide_widgets(window._preview_control_widgets)
    center_layout.addLayout(
        assemble_playback_controls_layout(
            play_button=window.btn_preview_toggle,
            frame_label=window.lbl_cropped_frame,
            frame_slider=window.slider_cropped_frame,
            speed_label=window.lbl_preview_speed,
            speed_combo=window.combo_preview_speed,
            speed_row_after_stretch=(window.btn_return_full_preview,),
        )
    )


def build_hidden_frame_controls(window: MainWindow) -> QWidget:
    """Frame index widgets kept for navigation logic; not shown in the sidebar."""
    host = QWidget()
    host.setFixedHeight(0)
    host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    window.lbl_frame_info = QLabel("Frame: —")
    window.slider_frame = QSlider(Qt.Orientation.Horizontal)
    window.slider_frame.valueChanged.connect(window._on_frame_slider)
    window.spin_frame = NoWheelSpinBox()
    window.spin_frame.valueChanged.connect(window._on_frame_spin)
    layout.addWidget(window.lbl_frame_info)
    layout.addWidget(window.slider_frame)
    layout.addWidget(window.spin_frame)
    return host


def build_right_sidebar(window: MainWindow) -> QStackedWidget:
    """Normal tabbed controls, or full-column Advanced Tracking Settings."""
    stack = QStackedWidget()
    stack.setMinimumWidth(RIGHT_PANEL_MIN_WIDTH)
    stack.setMaximumWidth(380)

    window._right_tabs = QTabWidget()
    roi_tab = QWidget()
    roi_layout = QVBoxLayout(roi_tab)
    apply_panel_margins(roi_layout)
    roi_layout.addWidget(build_unified_orient_roi_panel(window))
    window._right_tabs.addTab(roi_tab, "Orient && ROI")

    analysis_tab = QWidget()
    analysis_tab_layout = QVBoxLayout(analysis_tab)
    apply_panel_margins(analysis_tab_layout)
    window.btn_refresh_analysis = QPushButton("Refresh Analysis")
    window.btn_refresh_analysis.setToolTip(
        "Reload analysis tables from saved tracking and motion-index results."
    )
    window.btn_refresh_analysis.clicked.connect(window.refresh_analysis_view)
    analysis_tab_layout.addWidget(window.btn_refresh_analysis)
    window.btn_return_to_samples = QPushButton("Return to Samples")
    window.btn_return_to_samples.setToolTip(
        "Leave Analysis and return to the sample preview workflow."
    )
    window.btn_return_to_samples.clicked.connect(window._on_return_to_samples)
    analysis_tab_layout.addWidget(window.btn_return_to_samples)
    analysis_tab_layout.addStretch()
    window._right_tabs.addTab(analysis_tab, "Analysis")

    window._right_tabs.currentChanged.connect(window._on_right_tab_changed)

    stack.addWidget(window._right_tabs)
    stack.addWidget(build_tracking_settings_page(window))
    stack.addWidget(build_optical_flow_settings_page(window))
    window._right_stack = stack
    return stack


def build_export_name_panel(window: MainWindow) -> QWidget:
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(ROI_HINT_STATUS_SPACING)
    export_label = QLabel("Export name")
    apply_small_secondary_style(export_label)
    layout.addWidget(export_label)
    window.edit_export_name = QLineEdit()
    window.edit_export_name.setPlaceholderText(
        "auto-generated from condition group and sample"
    )
    window.edit_export_name.editingFinished.connect(window._on_export_name_edited)
    layout.addWidget(window.edit_export_name)
    window.lbl_auto_export_name = QLabel("Auto name: —")
    window.lbl_auto_export_name.setWordWrap(True)
    apply_hint_style(window.lbl_auto_export_name)
    layout.addWidget(window.lbl_auto_export_name)
    return section


def build_unified_orient_roi_panel(window: MainWindow) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(PANEL_SECTION_SPACING)

    rotation_row = QHBoxLayout()
    rotation_row.setSpacing(CONTROL_ROW_SPACING)
    angle_label = QLabel("Rotation:")
    angle_label.setSizePolicy(
        QSizePolicy.Policy.Minimum,
        QSizePolicy.Policy.Fixed,
    )
    rotation_row.addWidget(angle_label)
    window.spin_custom_angle = NoWheelDoubleSpinBox()
    window.spin_custom_angle.setRange(-180, 180)
    window.spin_custom_angle.setDecimals(1)
    window.spin_custom_angle.setButtonSymbols(
        QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    configure_orient_roi_control(window.spin_custom_angle)
    window.btn_apply_custom = QPushButton("Apply")
    window.btn_apply_custom.clicked.connect(window._on_apply_custom_angle)
    configure_orient_roi_control(window.btn_apply_custom)
    rotation_row.addWidget(window.spin_custom_angle)
    rotation_row.addWidget(window.btn_apply_custom)
    rotation_row.addStretch()
    layout.addLayout(rotation_row)

    window.chk_mirror_y = QCheckBox("Mirror Y-Axis")
    window.chk_mirror_y.setToolTip("Mirror the data left-right before ROI and tracking.")
    window.chk_mirror_y.toggled.connect(window._on_mirror_y_axis)
    layout.addWidget(window.chk_mirror_y)

    orient_actions_row = QHBoxLayout()
    orient_actions_row.setSpacing(PANEL_SECTION_SPACING)
    window.btn_flip = QPushButton("Flip 180°")
    window.btn_flip.clicked.connect(window._on_flip_180)
    configure_orient_panel_action_button(window.btn_flip)
    window.btn_reset_orientation = QPushButton("Reset Orientation")
    window.btn_reset_orientation.clicked.connect(window._on_reset_orientation)
    configure_orient_panel_action_button(window.btn_reset_orientation)
    orient_actions_row.addWidget(window.btn_flip, stretch=1)
    orient_actions_row.addWidget(window.btn_reset_orientation, stretch=1)
    layout.addLayout(orient_actions_row)

    layout.addStretch()
    layout.addSpacing(FORM_SECTION_SPACING)
    layout.addWidget(build_export_name_panel(window))
    window.btn_process = window._tool_button(
        "Export ROI",
        "Crop and export processed outputs to the processed/ folder.",
        window._on_process_sample,
    )
    layout.addWidget(window.btn_process)
    return panel


def create_tracking_setting_widgets(window: MainWindow) -> None:
    defaults = MotionIndexParams()
    window.combo_track_method = QComboBox()
    window.combo_track_method.addItem(
        "Brightest nearby points",
        TRACKING_METHOD_BRIGHTEST_LOCAL,
    )
    window.combo_track_method.addItem("Template matching", TRACKING_METHOD_TEMPLATE)
    method_index = window.combo_track_method.findData(defaults.tracking_method)
    window.combo_track_method.setCurrentIndex(max(0, method_index))
    window.combo_track_method.setToolTip(
        "How each point is matched in the next frame. Brightest nearby points "
        "uses traditional local brightness matching."
    )

    window.spin_track_points = NoWheelSpinBox()
    window.spin_track_points.setRange(1, 50)
    window.spin_track_points.setValue(defaults.num_starting_points)
    window.spin_track_points.setToolTip(
        "Number of bright F-actin signal points selected in the first frame."
    )

    window.spin_track_spacing = NoWheelSpinBox()
    window.spin_track_spacing.setRange(1, 200)
    window.spin_track_spacing.setValue(defaults.min_point_spacing_px)
    window.spin_track_spacing.setToolTip(
        "Minimum pixel distance between starting points so they are spread out."
    )

    window.spin_track_search = NoWheelSpinBox()
    window.spin_track_search.setRange(1, 100)
    window.spin_track_search.setValue(defaults.search_radius_px)
    window.spin_track_search.setToolTip(
        "Maximum pixel distance a point can move between frames."
    )

    window.spin_track_patch = NoWheelSpinBox()
    window.spin_track_patch.setRange(3, 101)
    window.spin_track_patch.setSingleStep(2)
    window.spin_track_patch.setValue(defaults.template_patch_size_px)
    window.spin_track_patch.setToolTip(
        "Size of the local bright-region centroid patch, and template patch "
        "when template matching is selected. Must be odd."
    )

    window.spin_track_confidence = NoWheelDoubleSpinBox()
    window.spin_track_confidence.setRange(0.0, 1.0)
    window.spin_track_confidence.setDecimals(2)
    window.spin_track_confidence.setSingleStep(0.05)
    window.spin_track_confidence.setValue(defaults.min_template_confidence)
    window.spin_track_confidence.setToolTip(
        "Lowest accepted match score. For brightest-point tracking this is a "
        "normalized local brightness threshold."
    )

    window.spin_track_lookahead = NoWheelSpinBox()
    window.spin_track_lookahead.setRange(0, 3)
    window.spin_track_lookahead.setValue(defaults.lookahead_frames)
    window.spin_track_lookahead.setToolTip(
        "Number of future frames to check if a point is temporarily lost."
    )

    window.spin_track_mpp = NoWheelDoubleSpinBox()
    window.spin_track_mpp.setRange(0.001, 10.0)
    window.spin_track_mpp.setDecimals(4)
    window.spin_track_mpp.setValue(defaults.microns_per_pixel)
    window.spin_track_mpp.setToolTip(
        "Physical image scale used to convert pixels to microns."
    )

    window.spin_track_spf = NoWheelDoubleSpinBox()
    window.spin_track_spf.setRange(0.001, 60.0)
    window.spin_track_spf.setDecimals(4)
    window.spin_track_spf.setValue(defaults.seconds_per_frame)
    window.spin_track_spf.setToolTip(
        "Time interval between frames used to convert displacement to velocity."
    )

    window._tracking_setting_widgets = (
        window.combo_track_method,
        window.spin_track_points,
        window.spin_track_spacing,
        window.spin_track_search,
        window.spin_track_patch,
        window.spin_track_confidence,
        window.spin_track_lookahead,
        window.spin_track_mpp,
        window.spin_track_spf,
    )
    for widget in window._tracking_setting_widgets:
        configure_tracking_field(widget, full_column=True)
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(window._on_tracking_setting_changed)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(window._on_tracking_setting_changed)


def build_tracking_settings_form(window: MainWindow) -> QGroupBox:
    box = QGroupBox("Advanced Tracking Settings")
    box.setToolTip(
        "Preview tracking parameters used in Metric Analysis."
    )
    layout = QVBoxLayout(box)
    layout.setSpacing(FORM_SECTION_SPACING)
    apply_form_group_margins(layout)
    rows: list[tuple[str, QWidget, str]] = [
        ("Tracking Method", window.combo_track_method, window.combo_track_method.toolTip()),
        ("Starting Points", window.spin_track_points, window.spin_track_points.toolTip()),
        (
            "Minimum Point Spacing (px)",
            window.spin_track_spacing,
            window.spin_track_spacing.toolTip(),
        ),
        (
            "Search Radius (px)",
            window.spin_track_search,
            window.spin_track_search.toolTip(),
        ),
        (
            "Template Patch Size (px)",
            window.spin_track_patch,
            window.spin_track_patch.toolTip(),
        ),
        (
            "Minimum Match Confidence",
            window.spin_track_confidence,
            window.spin_track_confidence.toolTip(),
        ),
        (
            "Lookahead Frames",
            window.spin_track_lookahead,
            window.spin_track_lookahead.toolTip(),
        ),
        ("Microns per Pixel", window.spin_track_mpp, window.spin_track_mpp.toolTip()),
        ("Seconds per Frame", window.spin_track_spf, window.spin_track_spf.toolTip()),
    ]
    for label_text, widget, tooltip in rows:
        add_tracking_setting_row(layout, label_text, widget, tooltip)
    layout.addStretch()
    return box


def build_tracking_settings_page(window: MainWindow) -> QWidget:
    create_tracking_setting_widgets(window)
    page = QWidget()
    layout = QVBoxLayout(page)
    apply_panel_inner_margins(layout)
    layout.setSpacing(FORM_SECTION_SPACING)

    hint = QLabel(
        "Edit tracking parameters below while previewing the cropped ROI. "
        "Changes auto-refresh tracking for the current sample."
    )
    hint.setWordWrap(True)
    apply_hint_style(hint)
    layout.addWidget(hint)
    layout.addWidget(build_tracking_settings_form(window), stretch=1)
    return page


def create_optical_flow_setting_widgets(window: MainWindow) -> None:
    defaults = OpticalFlowSettings()
    window.spin_of_mask_percentile = NoWheelDoubleSpinBox()
    window.spin_of_mask_percentile.setRange(0.0, 100.0)
    window.spin_of_mask_percentile.setDecimals(1)
    window.spin_of_mask_percentile.setValue(defaults.mask_percentile)
    window.spin_of_mask_percentile.setToolTip(
        "Include pixels brighter than this percentile in optical-flow averaging."
    )

    window.combo_of_blur = QComboBox()
    window.combo_of_blur.addItem("Off (0)", 0)
    window.combo_of_blur.addItem("3", 3)
    window.combo_of_blur.addItem("5", 5)
    window.combo_of_blur.setCurrentIndex(1)
    window.combo_of_blur.setToolTip("Light Gaussian blur applied before optical flow.")

    window.spin_of_pyr_scale = NoWheelDoubleSpinBox()
    window.spin_of_pyr_scale.setRange(0.01, 0.99)
    window.spin_of_pyr_scale.setDecimals(2)
    window.spin_of_pyr_scale.setSingleStep(0.05)
    window.spin_of_pyr_scale.setValue(defaults.pyr_scale)

    window.spin_of_levels = NoWheelSpinBox()
    window.spin_of_levels.setRange(1, 8)
    window.spin_of_levels.setValue(defaults.levels)

    window.spin_of_winsize = NoWheelSpinBox()
    window.spin_of_winsize.setRange(3, 99)
    window.spin_of_winsize.setSingleStep(2)
    window.spin_of_winsize.setValue(defaults.winsize)

    window.spin_of_iterations = NoWheelSpinBox()
    window.spin_of_iterations.setRange(1, 20)
    window.spin_of_iterations.setValue(defaults.iterations)

    window.spin_of_poly_n = NoWheelSpinBox()
    window.spin_of_poly_n.setRange(3, 15)
    window.spin_of_poly_n.setSingleStep(2)
    window.spin_of_poly_n.setValue(defaults.poly_n)

    window.spin_of_poly_sigma = NoWheelDoubleSpinBox()
    window.spin_of_poly_sigma.setRange(0.1, 5.0)
    window.spin_of_poly_sigma.setDecimals(2)
    window.spin_of_poly_sigma.setValue(defaults.poly_sigma)

    viz_defaults = OpticalFlowVisualizationSettings()
    window.chk_show_of_overlay = QCheckBox("Show Optical Flow Overlay")
    window.chk_show_of_overlay.setChecked(True)
    window.chk_show_of_overlay.setToolTip(
        "Draw sampled optical-flow arrows on the cropped ROI preview."
    )
    window.chk_show_of_overlay.toggled.connect(window._on_show_of_overlay_changed)

    window.spin_of_arrow_spacing = NoWheelSpinBox()
    window.spin_of_arrow_spacing.setRange(8, 40)
    window.spin_of_arrow_spacing.setValue(viz_defaults.arrow_spacing_px)
    window.spin_of_arrow_spacing.valueChanged.connect(window._on_of_viz_setting_changed)

    window.spin_of_arrow_scale = NoWheelDoubleSpinBox()
    window.spin_of_arrow_scale.setRange(0.1, 20.0)
    window.spin_of_arrow_scale.setDecimals(1)
    window.spin_of_arrow_scale.setSingleStep(0.5)
    window.spin_of_arrow_scale.setValue(viz_defaults.arrow_scale)
    window.spin_of_arrow_scale.valueChanged.connect(window._on_of_viz_setting_changed)

    window.lbl_of_qc = QLabel("QC: —")
    window.lbl_of_qc.setWordWrap(True)
    apply_hint_style(window.lbl_of_qc)

    window._optical_flow_metric_widgets = (
        window.spin_of_mask_percentile,
        window.combo_of_blur,
        window.spin_of_pyr_scale,
        window.spin_of_levels,
        window.spin_of_winsize,
        window.spin_of_iterations,
        window.spin_of_poly_n,
        window.spin_of_poly_sigma,
    )
    window._optical_flow_setting_widgets = (
        *window._optical_flow_metric_widgets,
        window.chk_show_of_overlay,
        window.spin_of_arrow_spacing,
        window.spin_of_arrow_scale,
    )
    for widget in window._optical_flow_metric_widgets:
        configure_tracking_field(widget, full_column=True)
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(window._on_optical_flow_setting_changed)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(window._on_optical_flow_setting_changed)
    for widget in (window.spin_of_arrow_spacing, window.spin_of_arrow_scale):
        configure_tracking_field(widget, full_column=True)


def build_optical_flow_overlay_panel(window: MainWindow) -> QGroupBox:
    box = QGroupBox("Optical Flow Overlay")
    layout = QVBoxLayout(box)
    layout.setSpacing(PANEL_INNER_MARGIN)
    layout.setContentsMargins(
        PANEL_INNER_MARGIN,
        FORM_SECTION_SPACING,
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
    )
    window.chk_show_of_overlay.setStyleSheet(STYLE_CHECKBOX_COMPACT)
    layout.addWidget(window.chk_show_of_overlay)
    add_tracking_setting_row(
        layout,
        "Arrow Spacing (px)",
        window.spin_of_arrow_spacing,
        "Grid spacing for sampled flow arrows.",
    )
    add_tracking_setting_row(
        layout,
        "Arrow Scale",
        window.spin_of_arrow_scale,
        "Multiplier for arrow length relative to flow magnitude.",
    )
    return box


def build_optical_flow_qc_panel(window: MainWindow) -> QGroupBox:
    box = QGroupBox("Optical Flow QC")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(
        PANEL_INNER_MARGIN,
        FORM_SECTION_SPACING,
        PANEL_INNER_MARGIN,
        PANEL_INNER_MARGIN,
    )
    layout.addWidget(window.lbl_of_qc)
    return box


def build_optical_flow_settings_form(window: MainWindow) -> QGroupBox:
    box = QGroupBox("Optical Flow Advanced Settings")
    box.setToolTip(
        "Dense Farnebäck optical-flow parameters for the preview motion index."
    )
    layout = QVBoxLayout(box)
    layout.setSpacing(FORM_SECTION_SPACING)
    apply_form_group_margins(layout)
    rows: list[tuple[str, QWidget, str]] = [
        ("Mask Percentile", window.spin_of_mask_percentile, window.spin_of_mask_percentile.toolTip()),
        ("Gaussian Blur Kernel", window.combo_of_blur, window.combo_of_blur.toolTip()),
        ("Farnebäck pyr_scale", window.spin_of_pyr_scale, ""),
        ("Farnebäck levels", window.spin_of_levels, ""),
        ("Farnebäck winsize", window.spin_of_winsize, ""),
        ("Farnebäck iterations", window.spin_of_iterations, ""),
        ("Farnebäck poly_n", window.spin_of_poly_n, ""),
        ("Farnebäck poly_sigma", window.spin_of_poly_sigma, ""),
    ]
    for label_text, widget, tooltip in rows:
        add_tracking_setting_row(layout, label_text, widget, tooltip)
    units_hint = QLabel(
        "Microns per Pixel and Seconds per Frame are shared with Template "
        "Tracking settings on the other preview mode panel."
    )
    units_hint.setWordWrap(True)
    apply_hint_style(units_hint)
    layout.addWidget(units_hint)
    return box


def build_optical_flow_settings_page(window: MainWindow) -> QWidget:
    create_optical_flow_setting_widgets(window)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    layout = QVBoxLayout(content)
    apply_panel_inner_margins(layout)
    layout.setSpacing(FORM_SECTION_SPACING)
    hint = QLabel(
        "Edit optical-flow parameters below while previewing the cropped ROI. "
        "Changes auto-recompute the preview optical-flow motion index."
    )
    hint.setWordWrap(True)
    apply_hint_style(hint)
    layout.addWidget(hint)
    layout.addWidget(build_optical_flow_settings_form(window))
    layout.addWidget(build_optical_flow_overlay_panel(window))
    layout.addWidget(build_optical_flow_qc_panel(window))
    layout.addStretch()
    scroll.setWidget(content)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(scroll)
    return page
