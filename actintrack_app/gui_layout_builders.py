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
    QVBoxLayout,
    QWidget,
)

from actintrack_app.analysis_view import AnalysisViewWidget
from actintrack_app.explorer_tree import ExplorerTreeWidget
from actintrack_app.gui_canvas import ImageCanvas
from actintrack_app.gui_styles import (
    CONTROL_ROW_SPACING,
    METRIC_STATUS_LABEL_SPACING,
    PANEL_MARGIN,
    PANEL_SECTION_SPACING,
    PLAYBACK_FRAME_LABEL_MIN_WIDTH,
    PLAYBACK_RETURN_ROW_HEIGHT,
    PLAYBACK_SLIDER_MIN_WIDTH,
    PLAYBACK_SPEED_COMBO_MIN_WIDTH,
    PREVIEW_CONTROLS_DIVIDER_TOP_SPACING,
    ROI_HINT_STATUS_SPACING,
    SIDE_PANEL_FIELD_GROUP_SPACING,
    SIDE_PANEL_FORM_SPACING,
    SIDE_PANEL_LABEL_CONTROL_GAP,
    SIDE_PANEL_SECTION_SPACING,
    STYLE_CHECKBOX_COMPACT,
    STYLE_WORKBENCH_CHECKBOX,
    STYLE_INSPECTOR_SCROLL,
    STYLE_PREVIEW_CONTROLS_DIVIDER,
    STYLE_WORKBENCH_VERTICAL_DIVIDER,
    TRACKING_FIELD_MIN_HEIGHT,
    WORKBENCH_SPEED_ROW_SPACING,
    apply_explorer_empty_hint_style,
    apply_explorer_panel_margins,
    apply_explorer_tree_content_margins,
    apply_explorer_panel_style,
    apply_explorer_root_row_margins,
    configure_explorer_root_path_label,
    configure_explorer_root_row,
    configure_explorer_tree_host,
    apply_hint_style,
    apply_inspector_field_label_style,
    apply_inspector_field_style,
    apply_inspector_scroll_style,
    apply_inspector_panel_style,
    apply_main_splitter_style,
    apply_muted_hint_style,
    apply_panel_margins,
    apply_side_panel_inner_margins,
    apply_small_secondary_style,
    apply_workbench_action_button,
    apply_workbench_controls_panel_style,
    apply_workbench_playback_button,
    apply_workbench_playback_label_style,
    apply_workbench_playback_speed_combo,
    apply_workbench_settings_combo,
    apply_workspace_preview_panel_style,
    configure_orient_panel_action_button,
    configure_workbench_action_mode_slot,
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
# Widths at or below this after restore are treated as corrupt / unusable.
LEFT_PANEL_INVALID_WIDTH = 40
DEFAULT_SPLITTER_SIZES = [LEFT_PANEL_MIN_WIDTH, 900]
PLAYBACK_SPEED_OPTIONS = ("0.25×", "0.5×", "1×", "1.5×", "2×")
METRIC_ANALYSIS_VIEW_LABEL = "Metric Analysis"
ROI_PREVIEW_PANEL_OBJECT_NAME = "roiPreviewPanel"
ROI_PREVIEW_PANEL_MIN_WIDTH = 180
ROI_PREVIEW_PANEL_MAX_WIDTH = 280
SAMPLE_RESULTS_PANEL_MIN_WIDTH = 168
SAMPLE_RESULTS_PANEL_MAX_WIDTH = 220
ROI_PREVIEW_CANVAS_MIN_WIDTH = 160
ROI_PREVIEW_CANVAS_MIN_HEIGHT = 120
WORKBENCH_ACTION_MODE_FULL = 0
WORKBENCH_ACTION_MODE_METRIC = 1


def sanitize_main_splitter_sizes(
    sizes: list[int] | tuple[int, ...] | None,
    *,
    total_width: int | None = None,
    explorer_min: int = LEFT_PANEL_MIN_WIDTH,
    invalid_below: int = LEFT_PANEL_INVALID_WIDTH,
) -> list[int]:
    """Return usable Explorer|Preview splitter sizes; recover from near-zero panes.

    Researchers may resize the Explorer; valid custom widths are preserved.
    Near-zero / missing sizes fall back to ``DEFAULT_SPLITTER_SIZES``.
    """
    default = list(DEFAULT_SPLITTER_SIZES)
    if not sizes or len(sizes) < 2:
        return default
    left = int(sizes[0])
    right = int(sizes[1])
    if left < invalid_below or right < invalid_below:
        return default
    left = max(left, explorer_min)
    if total_width is not None and total_width > 0:
        # Keep preview as the expanding remainder when the window is known.
        right = max(invalid_below, int(total_width) - left)
    elif right < invalid_below:
        right = default[1]
    return [left, right]


def configure_workbench_adjacent_panel(host: QWidget) -> None:
    """Fixed-width side panel shell shared by ROI preview and metric settings."""
    apply_inspector_panel_style(host)
    host.setFixedWidth(ROI_PREVIEW_PANEL_MAX_WIDTH)
    host.setMinimumWidth(ROI_PREVIEW_PANEL_MIN_WIDTH)
    host.setMaximumWidth(ROI_PREVIEW_PANEL_MAX_WIDTH)
    host.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Expanding,
    )


def configure_workbench_adjacent_panel_stack(stack: QStackedWidget) -> None:
    configure_workbench_adjacent_panel(stack)


def configure_orient_roi_control(widget: QWidget) -> None:
    widget.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )
    if isinstance(widget, QDoubleSpinBox):
        widget.setMaximumWidth(72)


def configure_tracking_field(widget: QWidget, *, full_column: bool = False) -> None:
    if full_column:
        widget.setMinimumWidth(0)
        widget.setMinimumHeight(TRACKING_FIELD_MIN_HEIGHT)
        apply_inspector_field_style(widget)
    else:
        widget.setMinimumWidth(140)
        widget.setMinimumHeight(30)
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
    *,
    compact: bool = False,
) -> None:
    label = QLabel(label_text)
    label.setWordWrap(True)
    if compact:
        apply_inspector_field_label_style(label)
    label.setToolTip(tooltip)
    widget.setToolTip(tooltip)
    layout.addWidget(label)
    if compact:
        layout.addSpacing(SIDE_PANEL_LABEL_CONTROL_GAP)
    layout.addWidget(widget)


def build_workbench_side_panel_scroll(content: QWidget) -> QScrollArea:
    """Shared scroll container for metric settings in the adjacent side panel."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    apply_inspector_scroll_style(scroll)
    content.setStyleSheet(f"background-color: transparent;")
    scroll.setWidget(content)
    return scroll


def build_workbench_vertical_divider() -> QFrame:
    """Thin divider between the hero preview and adjacent inspector panel."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setFixedWidth(1)
    line.setStyleSheet(STYLE_WORKBENCH_VERTICAL_DIVIDER)
    line.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Expanding,
    )
    return line


def build_preview_controls_divider() -> QFrame:
    """Subtle separator between the image workspace and status/playback controls."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setFixedHeight(1)
    line.setStyleSheet(STYLE_PREVIEW_CONTROLS_DIVIDER)
    line.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    return line


def build_inspector_fields_section(
    rows: list[tuple[str, QWidget, str]],
) -> QWidget:
    """Flat inspector field list without group-box framing."""
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SIDE_PANEL_FIELD_GROUP_SPACING)
    for label_text, widget, tooltip in rows:
        add_tracking_setting_row(layout, label_text, widget, tooltip, compact=True)
    return section


def assemble_playback_controls_layout(
    *,
    play_button: QPushButton,
    frame_label: QLabel,
    frame_slider: QSlider,
    speed_label: QLabel,
    speed_combo: QComboBox,
    speed_row_before_stretch: tuple[QWidget, ...] = (),
    speed_row_after_stretch: tuple[QWidget, ...] = (),
    footer_row_after_stretch: tuple[QWidget, ...] = (),
) -> QVBoxLayout:
    """Shared playback layout for full-sample and Metric Analysis preview."""
    layout = QVBoxLayout()
    layout.setSpacing(CONTROL_ROW_SPACING)
    transport_row = QHBoxLayout()
    transport_row.addWidget(play_button)
    transport_row.addWidget(frame_label)
    transport_row.addWidget(frame_slider, stretch=1)
    speed_row = QHBoxLayout()
    speed_row.setSpacing(WORKBENCH_SPEED_ROW_SPACING)
    row_align = Qt.AlignmentFlag.AlignVCenter
    speed_row.addWidget(speed_label, alignment=row_align)
    speed_row.addWidget(speed_combo, alignment=row_align)
    for widget in speed_row_before_stretch:
        speed_row.addWidget(widget, alignment=row_align)
    speed_row.addStretch()
    for widget in speed_row_after_stretch:
        speed_row.addWidget(widget, alignment=row_align)
    layout.addLayout(transport_row)
    layout.addLayout(speed_row)
    if footer_row_after_stretch:
        footer_host = QWidget()
        footer_host.setFixedHeight(PLAYBACK_RETURN_ROW_HEIGHT)
        footer_row = QHBoxLayout(footer_host)
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.addStretch()
        for widget in footer_row_after_stretch:
            footer_row.addWidget(widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(footer_host)
    return layout


def create_playback_play_button(window: MainWindow, *, tooltip: str) -> QPushButton:
    btn = QPushButton("Play")
    btn.setToolTip(tooltip)
    btn.clicked.connect(window._playback_toggle)
    apply_workbench_playback_button(btn)
    return btn


def create_playback_frame_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setMinimumWidth(PLAYBACK_FRAME_LABEL_MIN_WIDTH)
    apply_workbench_playback_label_style(label)
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
    label = QLabel("Speed:")
    apply_workbench_playback_label_style(label)
    return label


def create_playback_speed_combo(window: MainWindow, *, value_changed) -> QComboBox:
    combo = QComboBox()
    combo.addItems(list(PLAYBACK_SPEED_OPTIONS))
    combo.setCurrentText("1×")
    apply_workbench_playback_speed_combo(combo)
    combo.currentTextChanged.connect(value_changed)
    return combo


def build_main_workspace(window: MainWindow) -> None:
    central = QWidget()
    window.setCentralWidget(central)
    layout = QHBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    splitter = QSplitter(Qt.Orientation.Horizontal)
    window._left_sidebar = build_left_sidebar(window)
    splitter.addWidget(window._left_sidebar)
    window._preview_page = build_center_preview_page(window)
    preview_page = window._preview_page
    window._analysis_view = AnalysisViewWidget()
    window._center_stack = QStackedWidget()
    window._center_stack.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    window._center_stack.addWidget(preview_page)
    window._center_stack.addWidget(build_analysis_page(window))
    splitter.addWidget(window._center_stack)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setCollapsible(0, False)
    splitter.setCollapsible(1, False)
    apply_main_splitter_style(splitter)
    splitter.setSizes(
        sanitize_main_splitter_sizes(
            DEFAULT_SPLITTER_SIZES,
            explorer_min=LEFT_PANEL_MIN_WIDTH,
        )
    )
    splitter.splitterMoved.connect(window._update_workspace_label)
    window._main_splitter = splitter
    layout.addWidget(splitter)
    window.setStatusBar(QStatusBar())


def build_left_sidebar(window: MainWindow) -> QWidget:
    """Explorer sidebar (import/setup is in the menu bar)."""
    panel = QWidget()
    apply_explorer_panel_style(panel)
    panel.setMinimumWidth(LEFT_PANEL_MIN_WIDTH)
    panel.setMaximumWidth(360)
    panel.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Expanding,
    )
    layout = QVBoxLayout(panel)
    apply_explorer_panel_margins(layout)
    layout.addWidget(build_samples_panel(window), stretch=1)
    return panel


def build_explorer_root_row(window: MainWindow) -> QWidget:
    """Quiet workspace location row at the top of the Explorer file manager."""
    row = QWidget()
    configure_explorer_root_row(row)
    layout = QHBoxLayout(row)
    apply_explorer_root_row_margins(layout)
    window.lbl_workspace = QLabel("—")
    configure_explorer_root_path_label(window.lbl_workspace)
    layout.addWidget(window.lbl_workspace, stretch=1)
    return row


def build_explorer_tree_host(window: MainWindow) -> QWidget:
    """Unified Explorer tree surface: workspace root row plus sample tree."""
    host = QWidget()
    configure_explorer_tree_host(host)
    layout = QVBoxLayout(host)
    apply_explorer_panel_margins(layout)
    layout.setSpacing(0)
    layout.addWidget(build_explorer_root_row(window))
    window.lbl_explorer_empty = QLabel("Create a Condition Group to begin.")
    window.lbl_explorer_empty.setObjectName("explorerEmptyHint")
    window.lbl_explorer_empty.setWordWrap(True)
    apply_explorer_empty_hint_style(window.lbl_explorer_empty)
    window.lbl_explorer_empty.setVisible(False)
    layout.addWidget(window.lbl_explorer_empty)
    window.tree_samples = ExplorerTreeWidget()
    window.tree_samples.setHeaderHidden(True)
    window.tree_samples.setRootIsDecorated(True)
    window.tree_samples.setAlternatingRowColors(False)
    window.tree_samples.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    window.tree_samples.currentItemChanged.connect(window._on_explorer_selection_changed)
    window.tree_samples.itemSelectionChanged.connect(
        window._on_explorer_item_selection_changed,
        Qt.ConnectionType.QueuedConnection,
    )
    window.tree_samples.setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu
    )
    window.tree_samples.customContextMenuRequested.connect(
        window._on_explorer_context_menu
    )
    window.tree_samples.sample_drop_requested.connect(
        window._on_explorer_sample_dropped
    )
    window.tree_samples.sample_reorder_requested.connect(
        window._on_explorer_sample_reordered
    )
    window.tree_samples.external_files_drop_requested.connect(
        window._on_explorer_external_files_dropped
    )
    tree_container = QWidget()
    tree_layout = QVBoxLayout(tree_container)
    apply_explorer_tree_content_margins(tree_layout)
    tree_layout.setSpacing(0)
    tree_layout.addWidget(window.tree_samples)
    layout.addWidget(tree_container, stretch=1)
    return host


def build_samples_panel(window: MainWindow) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    apply_explorer_panel_margins(layout)
    layout.setSpacing(0)
    layout.addWidget(build_explorer_tree_host(window), stretch=1)
    window.combo_filter_group = QComboBox()
    window.combo_filter_group.setVisible(False)
    return panel


def create_metric_mode_widgets(window: MainWindow) -> None:
    """Inspection-mode selector at the top of the Metric Analysis side panel."""
    if hasattr(window, "combo_metric_mode"):
        return
    window.combo_metric_mode = QComboBox()
    window.combo_metric_mode.addItem("Template Tracking", "template")
    window.combo_metric_mode.addItem("Optical Flow", "optical_flow")
    window.combo_metric_mode.addItem("F-actin Orientation", "orientation")
    window.combo_metric_mode.setToolTip(
        "Display / Inspection Mode: Template Tracking and Optical Flow are "
        "motion analyses; F-actin Orientation is structural (persisted R7)."
    )
    apply_workbench_settings_combo(window.combo_metric_mode)
    window.combo_metric_mode.currentIndexChanged.connect(
        window._on_cropped_metric_mode_changed
    )
    window._metric_mode_widgets = ()


def build_metric_mode_selector_section(window: MainWindow) -> QWidget:
    """Inspection-mode selector pinned above metric settings."""
    create_metric_mode_widgets(window)
    section = QWidget()
    layout = QVBoxLayout(section)
    apply_side_panel_inner_margins(layout)
    layout.setSpacing(SIDE_PANEL_LABEL_CONTROL_GAP)
    label = QLabel("Display / Inspection Mode")
    label.setWordWrap(True)
    apply_inspector_field_label_style(label)
    label.setToolTip(window.combo_metric_mode.toolTip())
    layout.addWidget(label)
    layout.addWidget(window.combo_metric_mode)
    return section

def build_workbench_action_mode_slot(window: MainWindow) -> QStackedWidget:
    """Swap Metric Analysis and Return to Full Preview in one fixed slot."""
    slot = QStackedWidget()
    configure_workbench_action_mode_slot(slot)
    slot.addWidget(window.btn_metric_analysis)
    slot.addWidget(window.btn_return_full_preview)
    slot.setCurrentIndex(WORKBENCH_ACTION_MODE_FULL)
    window._workbench_action_mode_slot = slot
    return slot


def build_hidden_preview_mode_banner(window: MainWindow) -> QWidget:
    """Retain preview-mode label for status updates without visible chrome."""
    host = QWidget()
    host.setFixedHeight(0)
    host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    window.lbl_preview_mode = QLabel("")
    window.lbl_preview_mode.hide()
    layout.addWidget(window.lbl_preview_mode)
    return host


def build_center_preview_page(window: MainWindow) -> QWidget:
    preview_page = QWidget()
    preview_page.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    center_layout = QVBoxLayout(preview_page)
    center_layout.setContentsMargins(
        PANEL_MARGIN,
        PANEL_MARGIN,
        PANEL_MARGIN,
        0,
    )
    center_layout.addWidget(build_preview_workspace_host(window), stretch=1)

    window._hidden_preview_mode_host = build_hidden_preview_mode_banner(window)
    center_layout.addWidget(window._hidden_preview_mode_host)
    window._hidden_export_host = build_hidden_export_host(window)
    center_layout.addWidget(window._hidden_export_host)
    window._hidden_orientation_host = build_hidden_orientation_host(window)
    center_layout.addWidget(window._hidden_orientation_host)
    window._hidden_frame_host = build_hidden_frame_controls(window)
    center_layout.addWidget(window._hidden_frame_host)
    return preview_page


def build_preview_workspace_host(window: MainWindow) -> QWidget:
    """Preview images plus status and playback controls."""
    host = QWidget()
    host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(CONTROL_ROW_SPACING)

    layout.addWidget(build_preview_images_panel(window), stretch=1)
    layout.addSpacing(PREVIEW_CONTROLS_DIVIDER_TOP_SPACING)
    layout.addWidget(build_preview_controls_divider())
    build_roi_workflow_strip(window, layout)
    build_metric_status_labels_row(window, layout)
    build_sample_playback_controls(window, layout)

    window._preview_workspace_host = host
    return host


def build_preview_images_panel(window: MainWindow) -> QWidget:
    """Hero microscope canvas and ROI preview side by side."""
    panel = QWidget()
    apply_workspace_preview_panel_style(panel)
    panel.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    images_layout = QHBoxLayout(panel)
    images_layout.setContentsMargins(0, 0, 0, 0)
    images_layout.setSpacing(0)

    window.canvas = ImageCanvas(window)
    window.canvas.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    images_layout.addWidget(window.canvas, stretch=1)
    images_layout.addWidget(build_workbench_vertical_divider())
    images_layout.addWidget(build_sample_results_beside_canvas(window))
    images_layout.addWidget(build_workbench_vertical_divider())

    window._roi_preview_host = build_roi_preview_panel(window)
    window._metric_settings_host = build_metric_settings_host(window)
    window._adjacent_panel_stack = QStackedWidget()
    configure_workbench_adjacent_panel_stack(window._adjacent_panel_stack)
    window._adjacent_panel_stack.addWidget(window._roi_preview_host)
    window._adjacent_panel_stack.addWidget(window._metric_settings_host)
    images_layout.addWidget(window._adjacent_panel_stack)

    window._preview_images_panel = panel
    window._image_workspace_row = panel
    return panel


def build_sample_results_beside_canvas(window: MainWindow) -> QWidget:
    """Current-sample results in the dark column immediately right of the video."""
    host = QWidget()
    apply_inspector_panel_style(host)
    host.setMinimumWidth(SAMPLE_RESULTS_PANEL_MIN_WIDTH)
    host.setMaximumWidth(SAMPLE_RESULTS_PANEL_MAX_WIDTH)
    host.setSizePolicy(
        QSizePolicy.Policy.Fixed,
        QSizePolicy.Policy.Expanding,
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(ROI_HINT_STATUS_SPACING)
    window.lbl_sample_results = QLabel("")
    window.lbl_sample_results.setWordWrap(True)
    window.lbl_sample_results.setAlignment(Qt.AlignmentFlag.AlignTop)
    apply_hint_style(window.lbl_sample_results)
    window.lbl_sample_results.setText("Sample Results\n\nRun Metrics to populate.")
    layout.addWidget(window.lbl_sample_results, stretch=1)
    window._sample_results_host = host
    return host


def build_roi_preview_panel(window: MainWindow) -> QWidget:
    """Far-right setup column: Cell Boundary, Nucleus, Timing, Cutoff."""
    host = QWidget()
    configure_workbench_adjacent_panel(host)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(SIDE_PANEL_FIELD_GROUP_SPACING)

    window.lbl_workflow_next = QLabel("Select a sample to begin.")
    window.lbl_workflow_next.setWordWrap(True)
    apply_hint_style(window.lbl_workflow_next)
    layout.addWidget(window.lbl_workflow_next)
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)

    window.lbl_cell_boundary = QLabel("Cell Boundary")
    apply_inspector_field_label_style(window.lbl_cell_boundary)
    layout.addWidget(window.lbl_cell_boundary)

    sensitivity_row = QHBoxLayout()
    sensitivity_row.setContentsMargins(0, 0, 0, 0)
    sensitivity_row.setSpacing(6)
    window.lbl_cell_boundary_tighter = QLabel("Tighter")
    apply_muted_hint_style(window.lbl_cell_boundary_tighter)
    window.slider_cell_boundary = QSlider(Qt.Orientation.Horizontal)
    window.slider_cell_boundary.setRange(0, 100)
    window.slider_cell_boundary.setValue(50)
    window.slider_cell_boundary.setToolTip(
        "Tighter excludes more weak/background pixels. "
        "Broader retains more dim cell signal."
    )
    window.slider_cell_boundary.valueChanged.connect(
        window._on_cell_boundary_slider_changed
    )
    window.slider_cell_boundary.sliderReleased.connect(
        window._on_cell_boundary_slider_released
    )
    window.lbl_cell_boundary_broader = QLabel("Broader")
    apply_muted_hint_style(window.lbl_cell_boundary_broader)
    sensitivity_row.addWidget(window.lbl_cell_boundary_tighter)
    sensitivity_row.addWidget(window.slider_cell_boundary, stretch=1)
    sensitivity_row.addWidget(window.lbl_cell_boundary_broader)
    layout.addLayout(sensitivity_row)
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)

    window.lbl_nucleus_section = QLabel("Nucleus (optional)")
    apply_inspector_field_label_style(window.lbl_nucleus_section)
    layout.addWidget(window.lbl_nucleus_section)
    window.lbl_nucleus_cutoff_hint = QLabel(
        "Place the Measurement Cutoff through the nucleus, "
        "then select the nucleus center."
    )
    window.lbl_nucleus_cutoff_hint.setWordWrap(True)
    apply_muted_hint_style(window.lbl_nucleus_cutoff_hint)
    layout.addWidget(window.lbl_nucleus_cutoff_hint)

    nucleus_row = QHBoxLayout()
    nucleus_row.setContentsMargins(0, 0, 0, 0)
    nucleus_row.setSpacing(6)
    window.btn_select_nucleus = QPushButton("Select Nucleus")
    window.btn_select_nucleus.setCheckable(True)
    window.btn_select_nucleus.setToolTip(
        "Click the nucleus center. You choose the horizontal position; "
        "the Measurement Cutoff sets the vertical level. Required for "
        "Toward Nucleus and F-actin Orientation."
    )
    window.btn_select_nucleus.clicked.connect(window._on_set_nucleus_mode)
    apply_workbench_action_button(window.btn_select_nucleus, expanding=True)
    window.btn_select_nucleus.setEnabled(False)
    window.btn_clear_nucleus = QPushButton("Clear")
    window.btn_clear_nucleus.setToolTip("Clear the nucleus center.")
    window.btn_clear_nucleus.clicked.connect(window._on_clear_nucleus)
    apply_workbench_action_button(window.btn_clear_nucleus, expanding=True)
    window.btn_clear_nucleus.setEnabled(False)
    nucleus_row.addWidget(window.btn_select_nucleus, stretch=1)
    nucleus_row.addWidget(window.btn_clear_nucleus, stretch=1)
    layout.addLayout(nucleus_row)
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)

    create_tracking_setting_widgets(window)
    layout.addWidget(build_timing_settings_section(window))
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)

    window.lbl_cutoff_section = QLabel("Measurement Cutoff")
    apply_inspector_field_label_style(window.lbl_cutoff_section)
    layout.addWidget(window.lbl_cutoff_section)
    window.btn_advanced_cutoff = QPushButton("Advanced: Adjust Cutoff")
    window.btn_advanced_cutoff.setToolTip(
        "Required horizontal cutoff for Run Metrics. Adjust when the "
        "automatic default is not right."
    )
    window.btn_advanced_cutoff.clicked.connect(window._on_set_cutoff_mode)
    apply_workbench_action_button(window.btn_advanced_cutoff, expanding=True)
    window.btn_advanced_cutoff.setEnabled(False)
    layout.addWidget(window.btn_advanced_cutoff)
    window.btn_clear_cutoff = QPushButton("Clear Cutoff")
    window.btn_clear_cutoff.setToolTip(
        "Clear the Measurement Cutoff. Run Metrics stays disabled until set again."
    )
    window.btn_clear_cutoff.clicked.connect(window._on_clear_cutoff)
    apply_workbench_action_button(window.btn_clear_cutoff, expanding=True)
    window.btn_clear_cutoff.setEnabled(False)
    layout.addWidget(window.btn_clear_cutoff)
    layout.addStretch(1)

    window.lbl_roi_preview_empty = QLabel("")
    window.lbl_roi_preview_empty.hide()
    window.roi_preview_canvas = ImageCanvas(window)
    window.roi_preview_canvas.set_interactive(False)
    window.roi_preview_canvas.hide()
    return host


def build_roi_workflow_strip(window: MainWindow, layout: QVBoxLayout) -> None:
    """Crop save status below the image workspace row."""
    strip = QVBoxLayout()
    strip.setSpacing(ROI_HINT_STATUS_SPACING)

    window.lbl_roi_save_status = QLabel("—")
    window.lbl_roi_save_status.setWordWrap(True)
    window._set_roi_save_status("Select a sample", saved=False)
    strip.addWidget(window.lbl_roi_save_status)

    layout.addLayout(strip)


def build_metric_status_labels_row(window: MainWindow, layout: QVBoxLayout) -> None:
    """Metric freshness labels below the image, outside the ROI preview column."""
    metric_status_labels = QVBoxLayout()
    metric_status_labels.setSpacing(METRIC_STATUS_LABEL_SPACING)
    window.lbl_metric_status = QLabel("Metric status: Not analyzed")
    window.lbl_metric_status.setAlignment(Qt.AlignmentFlag.AlignLeft)
    apply_hint_style(window.lbl_metric_status)
    window.lbl_metric_status.hide()
    metric_status_labels.addWidget(window.lbl_metric_status)
    window.lbl_last_analyzed = QLabel("Last analyzed: —")
    window.lbl_last_analyzed.setAlignment(Qt.AlignmentFlag.AlignLeft)
    apply_hint_style(window.lbl_last_analyzed)
    window.lbl_last_analyzed.hide()
    metric_status_labels.addWidget(window.lbl_last_analyzed)
    layout.addLayout(metric_status_labels)


def create_metric_action_buttons(window: MainWindow) -> tuple[QPushButton, QPushButton]:
    """Metric action buttons placed on the sample playback speed row."""
    window.btn_metric_analysis = window._tool_button(
        METRIC_ANALYSIS_VIEW_LABEL,
        "Open the cropped ROI metric analysis view with Template Tracking "
        "and Optical Flow metrics, overlay, and playback.",
        window._on_show_metric_analysis_view,
    )
    window.btn_run_metrics = window._tool_button(
        "Run Metrics",
        "Compute Template Tracking and Optical Flow metrics for the current "
        "Sample using its cell boundary and nucleus.",
        window._on_run_metrics_clicked,
    )
    window.btn_run_metrics.setEnabled(False)
    window.btn_run_metrics.hide()
    return window.btn_metric_analysis, window.btn_run_metrics


def build_sample_playback_controls(window: MainWindow, parent_layout: QVBoxLayout) -> None:
    host = QWidget()
    apply_workbench_controls_panel_style(host)
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    window.btn_playback_toggle = create_playback_play_button(
        window,
        tooltip="Play or pause preview playback.",
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
    window.chk_playback_loop.setStyleSheet(STYLE_WORKBENCH_CHECKBOX)
    window.chk_playback_loop.setToolTip(
        "When checked, playback restarts at the first frame after the last frame."
    )
    window.chk_playback_loop.setChecked(True)
    create_metric_action_buttons(window)
    window.btn_return_full_preview = QPushButton("Return to Full Preview")
    window.btn_return_full_preview.clicked.connect(window._exit_cropped_preview_mode)
    apply_workbench_action_button(window.btn_return_full_preview)
    window._workbench_action_mode_slot = build_workbench_action_mode_slot(window)
    window._sample_playback_widgets = (
        window.btn_playback_toggle,
        window.lbl_sample_frame,
        window.slider_sample_frame,
        window.lbl_sample_playback_speed,
        window.combo_sample_playback_speed,
        window.chk_playback_loop,
    )
    window._preview_control_widgets = ()
    window._hide_widgets(window._sample_playback_widgets)
    host_layout.addLayout(
        assemble_playback_controls_layout(
            play_button=window.btn_playback_toggle,
            frame_label=window.lbl_sample_frame,
            frame_slider=window.slider_sample_frame,
            speed_label=window.lbl_sample_playback_speed,
            speed_combo=window.combo_sample_playback_speed,
            speed_row_before_stretch=(window.chk_playback_loop,),
            speed_row_after_stretch=(
                window._workbench_action_mode_slot,
                window.btn_run_metrics,
            ),
        )
    )
    window._sample_playback_host = host
    host.hide()
    parent_layout.addWidget(host)


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


def build_analysis_page(window: MainWindow) -> QWidget:
    """Center workbench Analysis view with navigation controls."""
    page = QWidget()
    layout = QVBoxLayout(page)
    apply_panel_margins(layout)
    layout.setSpacing(PANEL_SECTION_SPACING)

    toolbar = QHBoxLayout()
    window.btn_refresh_analysis = QPushButton("Refresh Analysis")
    window.btn_refresh_analysis.setToolTip(
        "Reload analysis tables from saved tracking and motion-index results."
    )
    window.btn_refresh_analysis.clicked.connect(window.refresh_analysis_view)
    toolbar.addWidget(window.btn_refresh_analysis)
    window.btn_return_to_samples = QPushButton("Return to Samples")
    window.btn_return_to_samples.setToolTip(
        "Leave Analysis and return to the sample preview workflow."
    )
    window.btn_return_to_samples.clicked.connect(window._on_return_to_samples)
    toolbar.addWidget(window.btn_return_to_samples)
    toolbar.addStretch()
    layout.addLayout(toolbar)
    layout.addWidget(window._analysis_view, stretch=1)
    return page


def build_metric_settings_host(window: MainWindow) -> QWidget:
    """Metric settings column shown beside the image during Metric Analysis."""
    host = QWidget()
    configure_workbench_adjacent_panel(host)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SIDE_PANEL_SECTION_SPACING)
    layout.addWidget(build_metric_mode_selector_section(window))
    window._metric_settings_stack = build_metric_settings_stack(window)
    layout.addWidget(window._metric_settings_stack, stretch=1)
    return host


def build_metric_settings_stack(window: MainWindow) -> QStackedWidget:
    """Template Tracking and Optical Flow settings (Metric Analysis only)."""
    stack = QStackedWidget()
    stack.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    stack.addWidget(build_tracking_settings_page(window))
    stack.addWidget(build_optical_flow_settings_page(window))
    window._right_stack = stack
    return stack


def build_hidden_orientation_host(window: MainWindow) -> QWidget:
    """Orientation widgets kept for backend sync; not shown in Workbench Stage 1."""
    host = QWidget()
    host.setFixedHeight(0)
    host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
    build_hidden_orientation_controls(window, host)
    return host


def build_hidden_export_host(window: MainWindow) -> QWidget:
    """Export-name widgets kept for backend sync; not shown in Workbench Stage 1."""
    host = QWidget()
    host.setFixedHeight(0)
    host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(build_export_name_panel(window))
    return host


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


def build_hidden_orientation_controls(window: MainWindow, parent: QWidget) -> None:
    """Create orientation widgets for backend sync; hidden in Workbench Stage 1."""
    window.spin_custom_angle = NoWheelDoubleSpinBox(parent)
    window.spin_custom_angle.setRange(-180, 180)
    window.spin_custom_angle.setDecimals(1)
    window.spin_custom_angle.setButtonSymbols(
        QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    configure_orient_roi_control(window.spin_custom_angle)
    window.spin_custom_angle.hide()

    window.btn_apply_custom = QPushButton("Apply", parent)
    window.btn_apply_custom.clicked.connect(window._on_apply_custom_angle)
    configure_orient_roi_control(window.btn_apply_custom)
    window.btn_apply_custom.hide()

    window.chk_mirror_y = QCheckBox("Mirror Y-Axis", parent)
    window.chk_mirror_y.setToolTip("Mirror the data left-right before ROI and tracking.")
    window.chk_mirror_y.toggled.connect(window._on_mirror_y_axis)
    window.chk_mirror_y.hide()

    window.btn_flip = QPushButton("Flip 180°", parent)
    window.btn_flip.clicked.connect(window._on_flip_180)
    configure_orient_panel_action_button(window.btn_flip)
    window.btn_flip.hide()

    window.btn_reset_orientation = QPushButton("Reset Orientation", parent)
    window.btn_reset_orientation.clicked.connect(window._on_reset_orientation)
    configure_orient_panel_action_button(window.btn_reset_orientation)
    window.btn_reset_orientation.hide()


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

    window._tracking_setting_widgets = (
        window.combo_track_method,
        window.spin_track_points,
        window.spin_track_spacing,
        window.spin_track_search,
        window.spin_track_patch,
        window.spin_track_confidence,
        window.spin_track_lookahead,
    )
    for widget in window._tracking_setting_widgets:
        configure_tracking_field(widget, full_column=True)
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.valueChanged.connect(window._on_tracking_setting_changed)
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(window._on_tracking_setting_changed)


def build_timing_settings_section(window: MainWindow) -> QWidget:
    """Per-sample acquisition interval and spatial calibration."""
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SIDE_PANEL_FORM_SPACING)

    interval_host = QWidget()
    interval_layout = QVBoxLayout(interval_host)
    interval_layout.setContentsMargins(0, 0, 0, 0)
    interval_layout.setSpacing(SIDE_PANEL_FORM_SPACING)
    title = QLabel("Acquisition Interval")
    apply_inspector_field_label_style(title)
    interval_layout.addWidget(title)

    interval_row = QHBoxLayout()
    interval_row.setContentsMargins(0, 0, 0, 0)
    interval_row.setSpacing(6)
    window.edit_acquisition_interval = QLineEdit()
    window.edit_acquisition_interval.setText("60")
    window.edit_acquisition_interval.setPlaceholderText("60")
    window.edit_acquisition_interval.setToolTip(
        "Actual time between microscope acquisitions, in seconds per frame. "
        "AVI/MP4 playback FPS is export metadata and does not set this interval."
    )
    apply_inspector_field_style(window.edit_acquisition_interval)
    window.edit_acquisition_interval.editingFinished.connect(
        window._on_acquisition_interval_editing_finished
    )
    interval_suffix = QLabel("seconds/frame")
    apply_muted_hint_style(interval_suffix)
    interval_row.addWidget(window.edit_acquisition_interval, stretch=1)
    interval_row.addWidget(interval_suffix)
    interval_layout.addLayout(interval_row)

    preset_row = QHBoxLayout()
    preset_row.setContentsMargins(0, 0, 0, 0)
    preset_row.setSpacing(6)
    window.btn_interval_30 = QPushButton("30 s")
    window.btn_interval_30.setToolTip("Set acquisition interval to 30 seconds/frame.")
    window.btn_interval_30.clicked.connect(
        lambda: window._apply_acquisition_interval_preset(30.0)
    )
    apply_workbench_action_button(window.btn_interval_30, expanding=True)
    window.btn_interval_60 = QPushButton("60 s")
    window.btn_interval_60.setToolTip("Set acquisition interval to 60 seconds/frame.")
    window.btn_interval_60.clicked.connect(
        lambda: window._apply_acquisition_interval_preset(60.0)
    )
    apply_workbench_action_button(window.btn_interval_60, expanding=True)
    preset_row.addWidget(window.btn_interval_30)
    preset_row.addWidget(window.btn_interval_60)
    interval_layout.addLayout(preset_row)
    window._acquisition_interval_host = interval_host
    layout.addWidget(interval_host)

    window.lbl_timing_detected = QLabel("60 s between frames")
    window.lbl_timing_detected.hide()
    layout.addWidget(window.lbl_timing_detected)

    spatial_host = QWidget()
    spatial_layout = QVBoxLayout(spatial_host)
    spatial_layout.setContentsMargins(0, 0, 0, 0)
    spatial_layout.setSpacing(SIDE_PANEL_FORM_SPACING)
    spatial_title = QLabel("Spatial Calibration")
    apply_inspector_field_label_style(spatial_title)
    spatial_layout.addWidget(spatial_title)
    spatial_row = QHBoxLayout()
    spatial_row.setContentsMargins(0, 0, 0, 0)
    spatial_row.setSpacing(6)
    window.edit_microns_per_pixel = QLineEdit()
    window.edit_microns_per_pixel.setText("0.265")
    window.edit_microns_per_pixel.setPlaceholderText("0.265")
    window.edit_microns_per_pixel.setToolTip(
        "Physical image scale in micrometres per pixel. "
        "This is sample/acquisition metadata; do not infer it from playback FPS, "
        "JPEG DPI, or objective magnification alone."
    )
    apply_inspector_field_style(window.edit_microns_per_pixel)
    window.edit_microns_per_pixel.editingFinished.connect(
        window._on_spatial_calibration_editing_finished
    )
    spatial_suffix = QLabel("µm/pixel")
    apply_muted_hint_style(spatial_suffix)
    spatial_row.addWidget(window.edit_microns_per_pixel, stretch=1)
    spatial_row.addWidget(spatial_suffix)
    spatial_layout.addLayout(spatial_row)
    window._spatial_calibration_host = spatial_host
    layout.addWidget(spatial_host)

    window.lbl_timing_status = QLabel("")
    window.lbl_timing_status.setWordWrap(True)
    apply_hint_style(window.lbl_timing_status)
    window.lbl_timing_status.hide()
    layout.addWidget(window.lbl_timing_status)
    return host


def build_tracking_settings_form(window: MainWindow) -> QWidget:
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
    ]
    form = build_inspector_fields_section(rows)
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SIDE_PANEL_SECTION_SPACING)
    layout.addWidget(form)
    return wrap


def build_tracking_settings_page(window: MainWindow) -> QWidget:
    # Widgets are created with the Workbench setup panel when available.
    if not hasattr(window, "spin_track_points"):
        create_tracking_setting_widgets(window)
    content = QWidget()
    layout = QVBoxLayout(content)
    apply_side_panel_inner_margins(layout)
    layout.setSpacing(SIDE_PANEL_FORM_SPACING)
    layout.addWidget(build_tracking_settings_form(window))
    scroll = build_workbench_side_panel_scroll(content)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(scroll)
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


def build_optical_flow_overlay_section(window: MainWindow) -> QWidget:
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SIDE_PANEL_FORM_SPACING)
    add_tracking_setting_row(
        layout,
        "Arrow Spacing (px)",
        window.spin_of_arrow_spacing,
        "Grid spacing for sampled flow arrows.",
        compact=True,
    )
    add_tracking_setting_row(
        layout,
        "Arrow Scale",
        window.spin_of_arrow_scale,
        "Multiplier for arrow length relative to flow magnitude.",
        compact=True,
    )
    return section


def build_optical_flow_settings_form(window: MainWindow) -> QWidget:
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
    section = build_inspector_fields_section(rows)
    layout = section.layout()
    assert isinstance(layout, QVBoxLayout)
    units_hint = QLabel(
        "Spatial calibration (µm/pixel) and acquisition interval (seconds/frame) "
        "are set per Sample in Sample Setup."
    )
    units_hint.setWordWrap(True)
    apply_muted_hint_style(units_hint)
    layout.addWidget(units_hint)
    return section


def build_optical_flow_settings_page(window: MainWindow) -> QWidget:
    create_optical_flow_setting_widgets(window)
    content = QWidget()
    layout = QVBoxLayout(content)
    apply_side_panel_inner_margins(layout)
    layout.setSpacing(SIDE_PANEL_FORM_SPACING)
    layout.addWidget(build_optical_flow_settings_form(window))
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)
    layout.addWidget(build_optical_flow_overlay_section(window))
    layout.addSpacing(SIDE_PANEL_SECTION_SPACING)
    layout.addWidget(window.lbl_of_qc)
    scroll = build_workbench_side_panel_scroll(content)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.addWidget(scroll)
    return page
