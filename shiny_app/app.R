required_packages <- c(
  "shiny", "bslib", "ggplot2", "jsonlite", "png", "base64enc",
  "htmltools", "fontawesome"
)
missing_packages <- required_packages[!vapply(
  required_packages,
  requireNamespace,
  logical(1),
  quietly = TRUE
)]
if (length(missing_packages) > 0) {
  stop("Missing R packages: ", paste(missing_packages, collapse = ", "))
}

library(shiny)
library(bslib)
library(ggplot2)

locate_app_dir <- function() {
  candidates <- c(getwd(), file.path(getwd(), "shiny_app"))
  matches <- candidates[file.exists(file.path(candidates, "app.R"))]
  if (length(matches) == 0) stop("Could not locate the shiny_app directory.")
  normalizePath(matches[[1]], mustWork = TRUE)
}

APP_DIR <- locate_app_dir()
DEFAULT_PROJECT_DIR <- normalizePath(file.path(APP_DIR, ".."), mustWork = FALSE)
source(file.path(APP_DIR, "R", "helpers.R"), local = TRUE)

app_theme <- bs_theme(
  version = 5,
  bg = "#F3F5F6",
  fg = "#17211F",
  primary = "#147A6C",
  secondary = "#5D6866",
  success = "#2F7A4B",
  info = "#2E668E",
  warning = "#A66A16",
  danger = "#B33A3A",
  base_font = font_collection(
    "Inter",
    "Avenir Next",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "sans-serif"
  ),
  heading_font = font_collection(
    "Inter",
    "Avenir Next",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "sans-serif"
  ),
  border_radius = "6px"
)

page_heading <- function(kicker, title, description, actions = NULL) {
  div(
    class = "page-heading",
    div(
      class = "page-heading-copy",
      if (!is.null(kicker) && nzchar(kicker)) div(class = "page-kicker", kicker),
      h1(title),
      p(description)
    ),
    if (!is.null(actions)) div(class = "page-heading-actions", actions)
  )
}

empty_state <- function(icon_name, title, detail) {
  div(
    class = "empty-state",
    fontawesome::fa(icon_name, height = "24px"),
    h4(title),
    p(detail)
  )
}

status_pill <- function(text, tone = "neutral") {
  span(class = paste("status-pill", paste0("status-", tone)), text)
}

metric_value_box <- function(title, value, detail, icon_name, theme = "teal") {
  value_box(
    title = title,
    value = value,
    showcase = fontawesome::fa(icon_name, height = "22px"),
    p(class = "metric-detail", detail),
    class = paste("metric-box", paste0("metric-", theme))
  )
}

workflow_nav_choice <- function(step, icon_name, title, detail) {
  div(
    class = "workflow-nav-item",
    span(class = "workflow-step", step),
    div(
      class = "workflow-nav-copy",
      div(class = "workflow-nav-title", fontawesome::fa(icon_name, height = "14px"), span(title)),
      tags$small(detail)
    )
  )
}

navigation_choices <- list(
  workflow_nav_choice("1", "house", "Project", "Workspace & video"),
  workflow_nav_choice("2", "crosshairs", "Track", "ROI & analysis"),
  workflow_nav_choice("3", "chart-line", "Review", "QC & metrics"),
  workflow_nav_choice("4", "chart-column", "Compare", "By group")
)

reference_navigation <- workflow_nav_choice("·", "layer-group", "Files", "Z-stack inventory")

all_navigation_choices <- c(navigation_choices, list(reference_navigation))
all_section_values <- c("project", "track", "review", "compare", "library")

section_legacy_map <- c(
  workspace = "project",
  tracking = "track",
  results = "review",
  angles = "review",
  analysis = "compare",
  stacks = "library"
)

normalize_section <- function(section) {
  if (!nzchar(section)) return("")
  mapped <- section_legacy_map[[section]]
  if (!is.null(mapped)) mapped else section
}

result_primary_speed <- function(row) {
  if (is.null(row)) return(NA_real_)
  primary <- row$primary_speed_um_s %||% row$primary_speed %||% row$absolute_velocity
  safe_scalar_numeric(primary)
}

result_step_weighted_speed <- function(row) {
  if (is.null(row)) return(NA_real_)
  step_weighted <- row$step_weighted_speed_um_s %||% row$step_weighted_speed %||% row$absolute_velocity
  safe_scalar_numeric(step_weighted)
}

summarize_groups_stratified <- function(results) {
  if (exists("summarize_groups_by_method", mode = "function", inherits = TRUE)) {
    return(summarize_groups_by_method(results))
  }
  if (is.null(results) || nrow(results) == 0) return(data.frame())
  parts <- lapply(c("landmark_tracking", "optical_flow"), function(method) {
    subset <- results[results$analysis_method == method, , drop = FALSE]
    if (nrow(subset) == 0) return(NULL)
    summary <- summarize_groups(subset)
    summary$analysis_method <- method
    summary
  })
  parts <- parts[!vapply(parts, is.null, logical(1))]
  if (length(parts) == 0) return(data.frame())
  do.call(rbind, parts)
}

layout_metric_boxes <- function(boxes) {
  n <- length(boxes)
  if (n <= 4L) {
    widths <- rep(3L, n)
    widths[[1]] <- widths[[1]] + (12L - sum(widths))
    return(do.call(layout_columns, c(list(col_widths = widths), boxes)))
  }
  split_at <- ceiling(n / 2)
  first_widths <- rep(12L %/% split_at, split_at)
  if (sum(first_widths) < 12L) first_widths[[1]] <- first_widths[[1]] + (12L - sum(first_widths))
  second_count <- n - split_at
  second_widths <- rep(12L %/% second_count, second_count)
  if (sum(second_widths) < 12L) second_widths[[1]] <- second_widths[[1]] + (12L - sum(second_widths))
  tagList(
    do.call(layout_columns, c(list(col_widths = first_widths), boxes[seq_len(split_at)])),
    do.call(layout_columns, c(list(col_widths = second_widths), boxes[(split_at + 1L):n]))
  )
}

ui <- page_sidebar(
  title = div(
    class = "topbar-brand",
    span(class = "brand-mark", "AT"),
    div(
      strong("ActinTrackCV"),
      tags$small("F-actin motion analysis")
    )
  ),
  theme = app_theme,
  fillable = TRUE,
  sidebar = sidebar(
    width = 268,
    open = "desktop",
    id = "app_sidebar",
    class = "app-sidebar",
    div(
      class = "sidebar-section sidebar-context",
      div(class = "sidebar-label", "WORKSPACE"),
      uiOutput("sidebar_workspace_chip"),
      uiOutput("sidebar_active_source")
    ),
    div(
      class = "sidebar-section app-navigation",
      div(class = "sidebar-label", "STEPS"),
      radioButtons(
        "section",
        NULL,
        choiceNames = all_navigation_choices,
        choiceValues = all_section_values,
        selected = "project"
      )
    ),
    div(
      class = "sidebar-section sidebar-results is-empty",
      id = "sidebar-results-panel",
      div(class = "sidebar-results-empty", "No saved runs yet"),
      div(class = "sidebar-label", "ACTIVE RUN"),
      tags$small(class = "sidebar-hint", "Review & Compare"),
      selectInput(
        "result_file",
        NULL,
        choices = c("—" = ""),
        width = "100%"
      )
    ),
    div(
      class = "sidebar-section sidebar-quick-action",
      uiOutput("sidebar_quick_action")
    ),
    div(
      class = "sidebar-footer",
      uiOutput("sidebar_footer"),
      tags$details(class = "sidebar-shortcuts", tags$summary("Keyboard shortcuts"), tags$dl(
        tags$dt("1 – 4"), tags$dd("Jump to workflow step"),
        tags$dt("⌘/Ctrl + Enter"), tags$dd("Run analysis on Track")
      ))
    )
  ),
  tags$head(
    tags$link(rel = "stylesheet", type = "text/css", href = "app.css"),
    tags$script(HTML("
      $(document).on('click', '.recent-run-open', function(event) {
        event.preventDefault();
        Shiny.setInputValue('recent_result_open', $(this).data('resultId'), {priority: 'event'});
      });
      $(document).on('click', '.recent-run-compare', function(event) {
        event.preventDefault();
        Shiny.setInputValue('recent_result_compare', true, {priority: 'event'});
      });
      function actintrackTypingTarget(target) {
        return $(target).is('input, textarea, select, [contenteditable=true]');
      }
      $(document).on('keydown', function(event) {
        if (actintrackTypingTarget(event.target)) return;
        var key = event.key;
        if (key >= '1' && key <= '4' && !event.metaKey && !event.ctrlKey && !event.altKey) {
          var sections = ['project', 'track', 'review', 'compare'];
          Shiny.setInputValue('keyboard_nav', sections[parseInt(key, 10) - 1], {priority: 'event'});
          event.preventDefault();
        }
        if ((event.metaKey || event.ctrlKey) && key === 'Enter') {
          var runBtn = document.getElementById('run_tracking');
          if (runBtn && !runBtn.disabled) {
            runBtn.click();
            event.preventDefault();
          }
        }
      });
    "))
  ),
  uiOutput("mobile_context_bar"),
  navset_hidden(
    id = "main_nav",
    nav_panel(
      title = "Project",
      value = "project",
      div(
        class = "app-view",
        page_heading(
          NULL,
          "Project",
          "Open your ActinTrackCV folder and choose a time-lapse video. Confirm the preview before running analysis.",
          uiOutput("project_next_action")
        ),
        card(
          class = "surface-card source-studio-card",
          card_header(
            div(
              strong("Source studio"),
              span(class = "card-subtitle", "Workspace-scoped file browser with live preview")
            )
          ),
          card_body(
            div(
              class = "workspace-bar",
              div(
                class = "workspace-bar-main",
                tags$label(`for` = "project_dir", class = "workspace-bar-label", "Project workspace"),
                textInput(
                  "project_dir",
                  NULL,
                  value = DEFAULT_PROJECT_DIR,
                  placeholder = "/path/to/ActinTrackCV"
                )
              ),
              div(
                class = "workspace-bar-actions",
                actionButton(
                  "apply_workspace",
                  "Open workspace",
                  icon = fontawesome::fa("folder-open"),
                  class = "btn-primary"
                ),
                actionButton(
                  "refresh_workspace",
                  "Refresh",
                  icon = fontawesome::fa("rotate"),
                  class = "btn-outline-secondary"
                )
              ),
              uiOutput("workspace_status")
            ),
            layout_columns(
              col_widths = c(4, 8),
              div(
                class = "source-browser-panel",
                div(
                  class = "source-browser-header",
                  strong("Videos in this workspace"),
                  uiOutput("source_browser_count")
                ),
                uiOutput("source_browser")
              ),
              div(
                class = "source-preview-panel",
                uiOutput("active_source_banner"),
                uiOutput("source_preview_controls"),
                plotOutput("source_preview_plot", height = "420px"),
                uiOutput("source_preview_status")
              )
            )
          )
        ),
        uiOutput("workflow_progress"),
        uiOutput("project_summary_metrics"),
        card(
          class = "surface-card",
          card_header(
            div(
              strong("Recent runs"),
              span(class = "card-subtitle", "Newest outputs first")
            )
          ),
          card_body(uiOutput("recent_results"))
        )
      )
    ),
    nav_panel(
      title = "Track",
      value = "track",
      div(
        class = "app-view track-view",
        page_heading(
          NULL,
          "Track",
          "The active video from Project is used here. Set ROI on the preview frame, then run landmark tracking or optical flow.",
          div(
            class = "page-heading-actions",
            actionButton(
              "go_project",
              "Change video",
              icon = fontawesome::fa("folder-open"),
              class = "btn-outline-secondary"
            ),
            actionButton(
              "refresh_preview",
              "Reload frame",
              icon = fontawesome::fa("rotate"),
              class = "btn-outline-secondary"
            )
          )
        ),
        uiOutput("track_empty_gate"),
        uiOutput("tracking_source_banner"),
        layout_columns(
          col_widths = c(4, 8),
          card(
            class = "surface-card control-card",
            card_header(strong("Analysis setup")),
            card_body(
              div(
                class = "control-section control-section-primary",
                h5("Analysis method"),
                div(
                  class = "method-choice-group",
                  radioButtons(
                    "analysis_method",
                    NULL,
                    choiceNames = c("Landmark tracking", "Optical flow"),
                    choiceValues = c("landmark_tracking", "optical_flow"),
                    selected = "landmark_tracking"
                  )
                ),
                p(
                  class = "control-note",
                  "Landmark tracking follows bright puncta. Optical flow suits dense Lifeact meshwork where points lose identity."
                )
              ),
              div(
                class = "control-section control-section-primary",
                div(
                  class = "control-heading-row",
                  h5("Region of interest"),
                  actionLink("use_full_frame", "Use full frame")
                ),
                p(class = "control-note", "Drag over the preview or enter pixel bounds."),
                div(
                  class = "numeric-grid",
                  numericInput("roi_x", "X", 0, min = 0, step = 1),
                  numericInput("roi_y", "Y", 0, min = 0, step = 1),
                  numericInput("roi_width", "Width", 0, min = 1, step = 1),
                  numericInput("roi_height", "Height", 0, min = 1, step = 1)
                )
              ),
              tags$details(
                class = "control-accordion",
                open = NA,
                tags$summary("Frame and orientation"),
                div(
                  class = "control-section control-section-nested",
                  radioButtons(
                    "rotation",
                    "Rotation",
                    choices = c("0°" = 0, "90°" = 90, "180°" = 180, "270°" = 270),
                    selected = 0,
                    inline = TRUE
                  ),
                  checkboxInput("flip_horizontal", "Mirror horizontally", FALSE),
                  uiOutput("frame_control")
                )
              ),
              conditionalPanel(
                "input.analysis_method == 'landmark_tracking'",
                div(
                  class = "control-section control-section-nested",
                  h5("Point matching"),
                  radioButtons(
                    "tracking_method",
                    "Tracking method",
                    choiceNames = c(
                      "Brightest nearby points",
                      "Template matching"
                    ),
                    choiceValues = c("brightest_local", "template"),
                    selected = "brightest_local"
                  ),
                  div(
                    class = "control-note tracking-method-note",
                    uiOutput("tracking_method_help")
                  )
                ),
                tags$details(
                  class = "control-accordion",
                  tags$summary("Detection parameters"),
                  div(
                    class = "control-section control-section-nested",
                    div(
                      class = "numeric-grid",
                      numericInput("num_points", "Starting points", 10, min = 1, max = 50),
                      numericInput("min_spacing", "Min point spacing (px)", 20, min = 1, max = 200),
                      numericInput("search_radius", "Search radius (px)", 8, min = 1, max = 100),
                      numericInput("min_confidence", "Min match confidence", 0.55, min = 0, max = 1, step = 0.05),
                      numericInput("patch_size", "Patch size (px, odd)", 11, min = 3, max = 101, step = 2)
                    )
                  )
                ),
                tags$details(
                  class = "control-accordion",
                  tags$summary("Advanced matching settings"),
                  div(
                    class = "control-section control-section-nested",
                    div(
                      class = "numeric-grid",
                      numericInput("lookahead_frames", "Lookahead frames", 0, min = 0, max = 3),
                      numericInput("preview_fps", "QC video FPS", 5, min = 1, max = 30),
                      div()
                    )
                  )
                )
              ),
              conditionalPanel(
                "input.analysis_method == 'optical_flow'",
                tags$details(
                  class = "control-accordion",
                  open = NA,
                  tags$summary("Optical flow parameters"),
                  div(
                    class = "control-section control-section-nested",
                    div(
                      class = "numeric-grid",
                      numericInput("mask_percentile", "Brightness mask percentile", 90, min = 50, max = 99, step = 1),
                      numericInput("flow_blur_kernel", "Gaussian blur kernel", 3, min = 0, max = 5, step = 2),
                      numericInput("flow_winsize", "Flow window size", 15, min = 5, max = 51, step = 2),
                      numericInput("flow_arrow_spacing", "Arrow spacing (px)", 8, min = 4, max = 24, step = 1),
                      numericInput("flow_arrow_scale", "Arrow scale", 0.8, min = 0.1, max = 3, step = 0.1)
                    ),
                    p(
                      class = "control-note",
                      "Mask percentile limits flow to bright actin pixels. Blur kernel must be 0, 3, or 5."
                    )
                  )
                )
              ),
              tags$details(
                class = "control-accordion",
                tags$summary(uiOutput("calibration_accordion_title", inline = TRUE)),
                div(
                  class = "control-section control-section-nested",
                  div(
                    class = "numeric-grid two-column",
                    numericInput("microns_per_pixel", "Microns / pixel", 0.265, min = 0.001, step = 0.001),
                    numericInput("seconds_per_frame", "Seconds / frame", 30, min = 0.001, step = 1)
                  ),
                  div(class = "calibration-warning", fontawesome::fa("triangle-exclamation"), " Confirm these values from acquisition metadata.")
                )
              )
            )
          ),
          card(
            class = "surface-card preview-card",
            card_header(
              div(
                strong("ROI preview"),
                uiOutput("preview_status")
              )
            ),
            card_body(
              plotOutput(
                "frame_plot",
                height = "620px",
                brush = brushOpts(
                  id = "roi_brush",
                  fill = "#FFD166",
                  stroke = "#F3B61F",
                  opacity = 0.18,
                  resetOnNew = TRUE
                )
              ),
              div(class = "preview-footer", uiOutput("roi_summary"))
            )
          )
        ),
        card(
          class = "surface-card run-log-card",
          card_header(strong("Run activity")),
          card_body(uiOutput("run_activity"))
        ),
        div(class = "track-run-sticky", uiOutput("track_sticky_run"))
      )
    ),
    nav_panel(
      title = "Review",
      value = "review",
      div(
        class = "app-view",
        page_heading(
          NULL,
          "Review",
          "Inspect QC imagery, motion metrics, and angle dynamics for the active run (selected in the sidebar)."
        ),
        uiOutput("review_empty_gate"),
        uiOutput("review_context_banner"),
        uiOutput("review_method_note"),
        navset_tab(
          id = "review_tab",
          nav_panel(
            "Overview",
            uiOutput("result_metrics"),
            layout_columns(
              col_widths = c(6, 6),
              card(
                class = "surface-card media-card",
                card_header(uiOutput("qc_primary_header")),
                card_body(uiOutput("starting_points_media"))
              ),
              card(
                class = "surface-card media-card",
                card_header(uiOutput("qc_secondary_header")),
                card_body(uiOutput("track_overlay_media"))
              )
            ),
            card(
              class = "surface-card media-card",
              card_header(uiOutput("qc_video_header")),
              card_body(uiOutput("track_video"))
            )
          ),
          nav_panel(
            "Motion",
            layout_columns(
              col_widths = c(6, 6),
              card(
                class = "surface-card plot-card",
                card_header(uiOutput("motion_paths_header")),
                card_body(plotOutput("trajectory_plot", height = "350px"))
              ),
              card(
                class = "surface-card plot-card",
                card_header(uiOutput("motion_velocity_header")),
                card_body(plotOutput("velocity_plot", height = "350px"))
              )
            ),
            card(
              class = "surface-card",
              card_header(
                div(
                  strong("Trajectory data"),
                  div(
                    class = "card-actions",
                    downloadButton("download_trajectory", "CSV", class = "btn-sm"),
                    downloadButton("download_summary", "JSON", class = "btn-sm")
                  )
                )
              ),
              card_body(uiOutput("trajectory_table"))
            )
          ),
          nav_panel(
            title = uiOutput("angles_tab_title", inline = TRUE),
            value = "Angles",
            uiOutput("angles_tab_body")
          )
        )
      )
    ),
    nav_panel(
      title = "Compare",
      value = "compare",
      div(
        class = "app-view",
        page_heading(
          NULL,
          "Compare",
          "Summarize movement across biological groups. Compare runs within the same analysis method only.",
          actionButton("refresh_analysis", "Refresh", icon = fontawesome::fa("rotate"), class = "btn-outline-secondary")
        ),
        uiOutput("compare_empty_gate"),
        conditionalPanel(
          "output.has_results",
          uiOutput("compare_method_note"),
          uiOutput("analysis_metrics"),
          layout_columns(
            col_widths = c(8, 4),
            card(
              class = "surface-card plot-card",
              card_header(strong("Mean velocity by group")),
              card_body(plotOutput("group_plot", height = "420px"))
            ),
            card(
              class = "surface-card",
              card_header(strong("Group summary")),
              card_body(uiOutput("group_table"))
            )
          ),
          card(
            class = "surface-card",
            card_header(strong("Completed runs")),
            card_body(uiOutput("all_results_table"))
          )
        )
      )
    ),
    nav_panel(
      title = "Z-stacks",
      value = "library",
      div(
        class = "app-view",
        page_heading(
          NULL,
          "Z-stacks",
          "Inventory Olympus and TIFF stacks. These files are not part of the current 2D velocity pipeline.",
          status_pill("Reference only", "neutral")
        ),
        p(
          class = "library-note",
          "3D analysis will require metadata extraction and OME conversion before these stacks join the motion workflow."
        ),
        uiOutput("stack_metrics"),
        layout_columns(
          col_widths = c(8, 4),
          card(
            class = "surface-card",
            card_header(strong("Microscopy files")),
            card_body(uiOutput("stack_table"))
          ),
          card(
            class = "surface-card",
            card_header(strong("Selected stack")),
            card_body(
              uiOutput("stack_selector"),
              uiOutput("stack_detail")
            )
          )
        )
      )
    )
  )
)

server <- function(input, output, session) {
  refresh_token <- reactiveVal(0L)
  preview_state <- reactiveVal(NULL)
  preview_error <- reactiveVal("")
  source_probe <- reactiveVal(NULL)
  probe_error <- reactiveVal("")
  run_state <- reactiveVal(list(status = "idle", message = "No tracking run started in this session.", log = character()))
  pending_result <- reactiveVal("")
  requested_section <- reactiveVal("")
  applied_workspace <- reactiveVal(normalize_project_path(DEFAULT_PROJECT_DIR))
  active_source_path <- reactiveVal("")

  project_dir <- reactive(applied_workspace())

  observeEvent(session$clientData$url_search, {
    query <- parseQueryString(session$clientData$url_search)
    requested <- normalize_section(query$section %||% "")
    if (requested %in% all_section_values) {
      requested_section(requested)
      updateRadioButtons(session, "section", selected = requested)
      nav_select("main_nav", selected = requested)
    }
  }, once = TRUE)

  observeEvent(input$refresh_workspace, {
    active_source_path("")
    applied_workspace(normalize_project_path(input$project_dir %||% DEFAULT_PROJECT_DIR))
    refresh_token(refresh_token() + 1L)
    showNotification("Workspace refreshed", type = "message", duration = 2)
  })
  observeEvent(input$apply_workspace, {
    active_source_path("")
    applied_workspace(normalize_project_path(input$project_dir %||% DEFAULT_PROJECT_DIR))
    refresh_token(refresh_token() + 1L)
    showNotification("Workspace opened", type = "message", duration = 2)
  })
  observeEvent(input$refresh_analysis, refresh_token(refresh_token() + 1L))

  sources <- reactive({
    refresh_token()
    discover_video_sources(project_dir())
  })
  results <- reactive({
    refresh_token()
    discover_tracking_results(project_dir())
  })
  stacks <- reactive({
    refresh_token()
    discover_z_stacks(project_dir())
  })

  output$has_results <- reactive({
    nrow(results()) > 0
  })
  outputOptions(output, "has_results", suspendWhenHidden = FALSE)

  observeEvent(input$recent_result_open, {
    rid <- input$recent_result_open
    req(nzchar(rid))
    rows <- results()
    if (!rid %in% rows$result_id) return()
    pending_result(rid)
    updateSelectInput(session, "result_file", selected = rid)
    updateRadioButtons(session, "section", selected = "review")
    nav_select("main_nav", selected = "review")
  }, ignoreInit = TRUE)

  observeEvent(input$recent_result_compare, {
    updateRadioButtons(session, "section", selected = "compare")
    nav_select("main_nav", selected = "compare")
  }, ignoreInit = TRUE)

  observeEvent(input$keyboard_nav, {
    section <- input$keyboard_nav
    if (!section %in% all_section_values) return()
    updateRadioButtons(session, "section", selected = section)
    nav_select("main_nav", selected = section)
  }, ignoreInit = TRUE)

  observeEvent(sources(), {
    data <- sources()
    next_path <- coerce_active_source_path(data, active_source_path())
    if (!identical(next_path, active_source_path())) {
      active_source_path(next_path)
    }
  }, ignoreInit = FALSE)

  observeEvent(input$source_file, {
    selected <- input$source_file %||% ""
    if (nzchar(selected) && !identical(selected, active_source_path())) {
      active_source_path(selected)
    }
  }, ignoreInit = FALSE)

  observeEvent(input$section, {
    target <- requested_section()
    if (!nzchar(target)) target <- input$section
    requested_section("")
    nav_select("main_nav", selected = target)
    if (identical(target, "track") && nzchar(active_source_path())) {
      load_preview_frame(
        as.integer(input$frame_index %||% 0),
        rotation = as.integer(input$rotation %||% 0),
        flip_horizontal = isTRUE(input$flip_horizontal)
      )
    }
  }, ignoreInit = FALSE)

  observeEvent(input$go_tracking, {
    if (!nzchar(active_source_path()) || is.null(selected_source())) {
      showNotification("Select a video in Project before tracking.", type = "warning", duration = 4)
      updateRadioButtons(session, "section", selected = "project")
      nav_select("main_nav", selected = "project")
      return()
    }
    updateRadioButtons(session, "section", selected = "track")
    nav_select("main_nav", selected = "track")
  })

  observeEvent(input$go_project, {
    updateRadioButtons(session, "section", selected = "project")
    nav_select("main_nav", selected = "project")
  })

  observeEvent(input$go_compare, {
    updateRadioButtons(session, "section", selected = "compare")
    nav_select("main_nav", selected = "compare")
  })

  observeEvent(input$go_review, {
    updateRadioButtons(session, "section", selected = "review")
    nav_select("main_nav", selected = "review")
  })

  selected_source <- reactive({
    path <- active_source_path()
    if (!nzchar(path)) return(NULL)
    rows <- sources()[sources()$path == path, , drop = FALSE]
    if (nrow(rows) == 0) NULL else rows[1, , drop = FALSE]
  })

  load_preview_frame <- function(frame_index = 0L, rotation = NULL, flip_horizontal = NULL) {
    path <- active_source_path()
    req(nzchar(path))
    rotation <- as.integer(rotation %||% input$rotation %||% 0)
    flip_horizontal <- isTRUE(flip_horizontal %||% input$flip_horizontal)
    preview_error("")
    old_state <- preview_state()
    output_path <- tempfile("actintrack_frame_", fileext = ".png")
    tryCatch({
      metadata <- extract_source_frame(
        project_dir(),
        path,
        output_path,
        as.integer(frame_index),
        rotation,
        flip_horizontal
      )
      orientation_key <- paste(path, rotation, flip_horizontal)
      old_key <- old_state$orientation_key %||% ""
      preview_state(list(
        path = output_path,
        metadata = metadata,
        orientation_key = orientation_key
      ))
      if (!identical(orientation_key, old_key)) {
        updateNumericInput(session, "roi_x", value = 0, max = metadata$width)
        updateNumericInput(session, "roi_y", value = 0, max = metadata$height)
        updateNumericInput(session, "roi_width", value = metadata$width, max = metadata$width)
        updateNumericInput(session, "roi_height", value = metadata$height, max = metadata$height)
      }
    }, error = function(exc) {
      preview_error(conditionMessage(exc))
      preview_state(NULL)
    })
  }

  observeEvent(active_source_path(), {
    path <- active_source_path()
    if (!nzchar(path)) {
      source_probe(NULL)
      preview_state(NULL)
      probe_error("")
      preview_error("")
      return()
    }
    probe_error("")
    source_probe(NULL)
    tryCatch({
      metadata <- probe_source(project_dir(), path)
      source_probe(metadata)
      load_preview_frame(0L, rotation = 0, flip_horizontal = FALSE)
      updateSliderInput(session, "studio_frame_index", value = 0)
      updateSliderInput(session, "frame_index", value = 0)
    }, error = function(exc) {
      probe_error(conditionMessage(exc))
      preview_state(NULL)
    })
  }, ignoreInit = FALSE)

  workspace_info <- reactive(workspace_state(project_dir()))

  output$workspace_status <- renderUI({
    info <- workspace_info()
    pending <- normalize_project_path(input$project_dir %||% "")
    dirty <- !identical(pending, applied_workspace())
    div(
      class = "workspace-status-row",
      span(class = paste("status-dot", if (info$valid) "dot-ok" else "dot-error")),
      span(info$message),
      if (dirty) span(class = "workspace-pending-note", "Press Open workspace to apply path changes")
    )
  })

  output$sidebar_workspace_chip <- renderUI({
    info <- workspace_info()
    div(
      class = "sidebar-chip",
      fontawesome::fa("folder", height = "12px"),
      div(
        class = "sidebar-chip-copy",
        tags$small("WORKSPACE"),
        span(basename(info$path))
      )
    )
  })

  output$sidebar_active_source <- renderUI({
    row <- selected_source()
    div(
      class = "sidebar-chip",
      fontawesome::fa("film", height = "12px"),
      div(
        class = "sidebar-chip-copy",
        tags$small("ACTIVE VIDEO"),
        span(if (is.null(row)) "None selected" else row$file_name)
      )
    )
  })

  output$sidebar_result_section <- renderUI({
    empty <- nrow(results()) == 0
    tags$script(HTML(paste0(
      "var panel=document.getElementById('sidebar-results-panel');",
      "if(panel){panel.classList.toggle('is-empty',", tolower(empty), ");}"
    )))
  })

  output$sidebar_quick_action <- renderUI({
    section <- input$section %||% "project"
    if (identical(section, "project") && !is.null(selected_source())) {
      return(actionButton(
        "go_tracking",
        "Track this video",
        icon = fontawesome::fa("crosshairs"),
        class = "btn-sidebar btn-sidebar-primary"
      ))
    }
    if (identical(section, "track")) {
      if (is.null(selected_source())) {
        return(actionButton(
          "go_project",
          "Select a video",
          icon = fontawesome::fa("folder-open"),
          class = "btn-sidebar"
        ))
      }
      return(actionButton(
        "go_project",
        "Change video",
        icon = fontawesome::fa("folder-open"),
        class = "btn-sidebar"
      ))
    }
    if (identical(section, "review") && nrow(results()) > 0) {
      return(actionButton(
        "go_compare",
        "Compare groups",
        icon = fontawesome::fa("chart-column"),
        class = "btn-sidebar"
      ))
    }
    if (identical(section, "compare") && nrow(results()) > 0) {
      return(actionButton(
        "go_review",
        "Inspect a run",
        icon = fontawesome::fa("chart-line"),
        class = "btn-sidebar"
      ))
    }
    NULL
  })

  output$mobile_context_bar <- renderUI({
    section <- input$section %||% "project"
    step_label <- switch(
      section,
      project = "Project",
      track = "Track",
      review = "Review",
      compare = "Compare",
      library = "Files",
      section
    )
    video <- selected_source()
    run_row <- selected_result()
    detail <- if (!is.null(video)) {
      video$file_name
    } else if (!is.null(run_row)) {
      run_row$source_name
    } else {
      ""
    }
    div(
      class = "mobile-context-bar",
      span(class = "mobile-context-step", step_label),
      if (nzchar(detail)) span(class = "mobile-context-detail", detail)
    )
  })

  output$source_browser_count <- renderUI({
    count <- nrow(sources())
    span(class = "source-browser-count", paste0(count, " file", if (count == 1) "" else "s"))
  })

  output$source_browser <- renderUI({
    data <- sources()
    info <- workspace_info()
    if (!info$valid) {
      return(empty_state(
        "folder-open",
        "Workspace not found",
        "Enter a valid ActinTrackCV project folder, then click Open workspace."
      ))
    }
    if (nrow(data) == 0) {
      return(empty_state(
        "film",
        "No videos in this workspace",
        "Add AVI or MP4 files under raw/ or processed/, then refresh."
      ))
    }
    active <- active_source_path()
    if (!nzchar(active) || !active %in% data$path) {
      active <- coerce_active_source_path(data, active)
    }
    div(
      class = "source-browser",
      radioButtons(
        "source_file",
        NULL,
        choiceNames = lapply(seq_len(nrow(data)), function(i) {
          source_file_choice_label(data[i, , drop = FALSE], identical(data$path[[i]], active))
        }),
        choiceValues = data$path,
        selected = active
      )
    )
  })

  output$active_source_banner <- renderUI({
    active_source_banner(
      selected_source(),
      source_probe(),
      "Select a video from the workspace list to preview it here."
    )
  })

  output$source_preview_controls <- renderUI({
    row <- selected_source()
    metadata <- source_probe()
    if (is.null(row) || is.null(metadata)) return(NULL)
    sliderInput(
      "studio_frame_index",
      "Preview frame",
      min = 0,
      max = max(0, as.integer(metadata$frame_count) - 1),
      value = min(as.integer(input$studio_frame_index %||% 0), max(0, as.integer(metadata$frame_count) - 1)),
      step = 1,
      ticks = FALSE
    )
  })

  studio_preview_request <- reactive({
    path <- active_source_path()
    req(nzchar(path))
    list(
      path = path,
      frame = as.integer(input$studio_frame_index %||% 0)
    )
  })

  observeEvent(studio_preview_request(), {
    if (isolate(input$section) != "project") return()
    request <- studio_preview_request()
    if (!identical(request$path, active_source_path())) return()
    load_preview_frame(request$frame, rotation = 0, flip_horizontal = FALSE)
  }, ignoreInit = FALSE)

  render_preview_image <- function(show_roi = FALSE) {
    state <- preview_state()
    if (is.null(state) || !file.exists(state$path)) {
      par(mar = c(0, 0, 0, 0), bg = "#111817")
      plot.new()
      text(0.5, 0.54, "Select a video to preview", col = "#DCE4E2", cex = 1.2)
      text(0.5, 0.46, preview_error() %||% probe_error() %||% "A preview frame will appear here.", col = "#83918E", cex = 0.9)
      return()
    }
    image <- png::readPNG(state$path)
    image <- image[dim(image)[1]:1, , , drop = FALSE]
    width <- as.numeric(state$metadata$width)
    height <- as.numeric(state$metadata$height)
    par(mar = c(0, 0, 0, 0), bg = "#111817", xaxs = "i", yaxs = "i")
    plot.new()
    plot.window(xlim = c(0, width), ylim = c(0, height), asp = 1)
    rasterImage(image, 0, 0, width, height, interpolate = TRUE)
    if (show_roi) {
      x <- max(0, min(width, input$roi_x %||% 0))
      y <- max(0, min(height, input$roi_y %||% 0))
      roi_width <- max(1, min(width - x, input$roi_width %||% width))
      roi_height <- max(1, min(height - y, input$roi_height %||% height))
      rect(
        x,
        height - y - roi_height,
        x + roi_width,
        height - y,
        border = "#FFD166",
        lwd = 2
      )
    }
  }

  output$source_preview_plot <- renderPlot({
    render_preview_image(show_roi = FALSE)
  })

  output$source_preview_status <- renderUI({
    row <- selected_source()
    if (is.null(row)) return(NULL)
    if (nzchar(probe_error())) return(status_pill("Probe error", "danger"))
    if (nzchar(preview_error())) return(status_pill("Preview error", "danger"))
    if (is.null(preview_state())) return(status_pill("Loading preview", "neutral"))
    metadata <- source_probe()
    summary <- format_video_probe_summary(metadata)
    div(
      class = "source-preview-meta",
      span(paste0("Frame ", input$studio_frame_index %||% 0)),
      span(paste0(summary$playback_fps, " playback FPS")),
      span(summary$dimensions)
    )
  })

  output$source_sidebar_meta <- renderUI(NULL)

  output$sidebar_footer <- renderUI({
    status <- run_state()
    run_count <- nrow(results())
    label <- if (status$status == "running") {
      "Analysis running…"
    } else if (run_count > 0) {
      paste(run_count, if (run_count == 1) "saved run" else "saved runs")
    } else {
      "No runs yet"
    }
    div(
      class = "session-status",
      div(
        tags$small("STATUS"),
        span(label)
      )
    )
  })

  output$project_next_action <- renderUI({
    if (!workspace_info()$valid || is.null(selected_source())) return(NULL)
    div(
      class = "page-heading-actions",
      actionButton(
        "go_tracking",
        "Continue to Track",
        icon = fontawesome::fa("arrow-right"),
        class = "btn-primary"
      )
    )
  })

  output$workflow_progress <- renderUI({
    info <- workspace_info()
    row <- selected_source()
    has_video <- !is.null(row)
    run_count <- nrow(results())
    ws_state <- if (!info$valid) "current" else "done"
    vid_state <- if (!info$valid) {
      "pending"
    } else if (has_video) {
      "done"
    } else {
      "current"
    }
    res_state <- if (run_count > 0) "done" else if (has_video) "current" else "pending"
    workflow_progress_strip(list(
      workflow_progress_step("Workspace", info$message, ws_state),
      workflow_progress_step(
        "Video",
        if (has_video) row$file_name else "Select a source file",
        vid_state
      ),
      workflow_progress_step(
        "Results",
        if (run_count > 0) paste(run_count, "completed run(s)") else "Run analysis on Track",
        res_state
      )
    ))
  })

  output$project_summary_metrics <- renderUI({
    layout_columns(
      col_widths = c(6, 6),
      metric_value_box("Videos in workspace", nrow(sources()), "AVI and MP4 under raw/ or processed/", "film", "teal"),
      metric_value_box("Completed runs", nrow(results()), "Saved analysis outputs", "route", "blue")
    )
  })

  output$source_empty <- renderUI(NULL)
  output$source_table_inner <- renderTable(data.frame(), rownames = FALSE)

  output$recent_results <- renderUI({
    data <- results()
    if (nrow(data) == 0) {
      return(empty_state(
        "route",
        "No completed runs",
        "Select a video, set an ROI on Track, then run analysis to create your first result."
      ))
    }
    div(class = "recent-run-list", lapply(seq_len(min(5, nrow(data))), function(i) {
      row <- data[i, , drop = FALSE]
      primary <- result_primary_speed(row)
      div(
        class = "recent-run",
        div(
          class = "recent-run-copy",
          strong(row$source_name),
          tags$small(paste(
            row$group,
            analysis_method_label(row$analysis_method),
            row$analyzed_at,
            sep = " · "
          ))
        ),
        div(
          class = "recent-run-actions",
          div(
            class = "recent-run-metric",
            span(format_metric(primary, 3)),
            tags$small("µm/s")
          ),
          tags$button(
            type = "button",
            class = "recent-run-open",
            `data-result-id` = row$result_id,
            "Review"
          ),
          tags$button(
            type = "button",
            class = "recent-run-compare",
            "Compare"
          )
        )
      )
    }))
  })

  output$tracking_method_help <- renderUI({
    method <- input$tracking_method %||% "brightest_local"
    if (identical(method, "template")) {
      return("Matches a patch from the previous frame inside the search window.")
    }
    "Finds the brightest nearby landmark within the search radius (workbench default)."
  })

  output$calibration_accordion_title <- renderUI({
    span(
      "Calibration · ",
      tags$small(
        paste0(
          format_metric(input$microns_per_pixel, 3), " µm/px · ",
          format_metric(input$seconds_per_frame, 0), " s/frame"
        )
      )
    )
  })

  output$track_sticky_run <- renderUI({
    row <- selected_source()
    state <- preview_state()
    ready <- !is.null(row) && !is.null(state)
    method <- input$analysis_method %||% "landmark_tracking"
    label <- if (identical(method, "optical_flow")) "Run optical flow" else "Run landmark tracking"
    roi_label <- if (is.null(state)) {
      "Draw an ROI on the preview"
    } else {
      area <- as.numeric(input$roi_width %||% 0) * as.numeric(input$roi_height %||% 0)
      frame_area <- as.numeric(state$metadata$width) * as.numeric(state$metadata$height)
      coverage <- if (frame_area > 0) 100 * area / frame_area else 0
      paste0(
        input$roi_width %||% 0, " × ", input$roi_height %||% 0,
        " px · ",
        format_metric(coverage, 0),
        "% of frame"
      )
    }
    div(
      class = "track-run-sticky-inner",
      div(
        class = "track-run-sticky-copy",
        strong(if (ready) row$file_name else "Select a video on Project"),
        tags$small(roi_label),
        tags$small(class = "track-run-sticky-hint", "⌘/Ctrl + Enter to run")
      ),
      if (ready) {
        input_task_button(
          "run_tracking",
          label,
          icon = fontawesome::fa("play"),
          class = "btn-run btn-run-sticky"
        )
      } else {
        tags$button(
          type = "button",
          class = "btn btn-run btn-run-sticky",
          disabled = "disabled",
          label
        )
      }
    )
  })

  output$frame_control <- renderUI({
    metadata <- source_probe()
    if (is.null(metadata)) return(NULL)
    sliderInput(
      "frame_index",
      "Preview frame",
      min = 0,
      max = max(0, as.integer(metadata$frame_count) - 1),
      value = 0,
      step = 1,
      ticks = FALSE
    )
  })

  preview_request <- reactive({
    path <- active_source_path()
    req(nzchar(path))
    list(
      source = path,
      frame = as.integer(input$frame_index %||% 0),
      rotation = as.integer(input$rotation %||% 0),
      flip = isTRUE(input$flip_horizontal),
      refresh = input$refresh_preview
    )
  })

  observeEvent(preview_request(), {
    if (isolate(input$section) != "track") return()
    request <- preview_request()
    load_preview_frame(request$frame, rotation = request$rotation, flip_horizontal = request$flip)
  }, ignoreInit = FALSE)

  observeEvent(input$use_full_frame, {
    state <- preview_state()
    req(state)
    updateNumericInput(session, "roi_x", value = 0)
    updateNumericInput(session, "roi_y", value = 0)
    updateNumericInput(session, "roi_width", value = state$metadata$width)
    updateNumericInput(session, "roi_height", value = state$metadata$height)
  })

  observeEvent(input$roi_brush, {
    brush <- input$roi_brush
    state <- preview_state()
    req(brush, state)
    width <- as.integer(state$metadata$width)
    height <- as.integer(state$metadata$height)
    x0 <- max(0, floor(min(brush$xmin, brush$xmax)))
    x1 <- min(width, ceiling(max(brush$xmin, brush$xmax)))
    display_y0 <- max(0, floor(min(brush$ymin, brush$ymax)))
    display_y1 <- min(height, ceiling(max(brush$ymin, brush$ymax)))
    image_y0 <- max(0, height - display_y1)
    updateNumericInput(session, "roi_x", value = x0)
    updateNumericInput(session, "roi_y", value = image_y0)
    updateNumericInput(session, "roi_width", value = max(1, x1 - x0))
    updateNumericInput(session, "roi_height", value = max(1, display_y1 - display_y0))
  })

  output$frame_plot <- renderPlot({
    render_preview_image(show_roi = TRUE)
  })

  output$preview_status <- renderUI({
    if (nzchar(preview_error())) return(status_pill("Preview error", "danger"))
    if (is.null(preview_state())) return(status_pill("Waiting for source", "neutral"))
    status_pill(paste0("Frame ", input$frame_index %||% 0), "success")
  })

  output$track_empty_gate <- renderUI({
    if (!is.null(selected_source())) return(NULL)
    next_step_banner(
      "No video selected",
      "Choose a workspace video on Project before setting an ROI.",
      actionButton("go_project", "Go to Project", icon = fontawesome::fa("folder-open"), class = "btn-sm btn-primary"),
      tone = "muted"
    )
  })

  output$tracking_source_banner <- renderUI({
    if (is.null(selected_source())) {
      return(active_source_banner(NULL, NULL, "Go to Project, open a workspace, and select a video."))
    }
    active_source_banner(selected_source(), source_probe())
  })

  output$roi_summary <- renderUI({
    state <- preview_state()
    if (is.null(state)) return(span("No ROI available"))
    area <- as.numeric(input$roi_width %||% 0) * as.numeric(input$roi_height %||% 0)
    coverage <- 100 * area / (as.numeric(state$metadata$width) * as.numeric(state$metadata$height))
    div(
      span(fontawesome::fa("crop-simple"), paste0(input$roi_width, " × ", input$roi_height, " px")),
      span(paste0(format_metric(coverage, 1), "% of frame")),
      span(paste0("Origin ", input$roi_x, ", ", input$roi_y))
    )
  })

  observeEvent(input$run_tracking, {
    row <- selected_source()
    state <- preview_state()
    req(row, state)
    analysis_method <- input$analysis_method %||% "landmark_tracking"
    if (identical(analysis_method, "landmark_tracking")) {
      if (input$patch_size %% 2 == 0) {
        showNotification("Patch size must be an odd number.", type = "error")
        return()
      }
    } else {
      blur_kernel <- as.integer(input$flow_blur_kernel)
      if (!blur_kernel %in% c(0L, 3L, 5L)) {
        showNotification("Flow blur kernel must be 0, 3, or 5.", type = "error")
        return()
      }
    }
    if (input$roi_width < 3 || input$roi_height < 3) {
      showNotification("Draw a larger ROI before running analysis.", type = "error")
      return()
    }
    timestamp <- format(Sys.time(), "%Y%m%d_%H%M%S")
    export_name <- paste0(tools::file_path_sans_ext(row$file_name), "_", timestamp)
    output_dir <- file.path(
      project_dir(),
      "processed",
      "shiny_runs",
      row$group,
      tools::file_path_sans_ext(row$file_name),
      timestamp
    )
    config <- list(
      source_path = row$path,
      output_dir = output_dir,
      export_name = export_name,
      analysis_method = analysis_method,
      rotation = as.integer(input$rotation),
      flip_horizontal = isTRUE(input$flip_horizontal),
      roi_x = as.integer(input$roi_x),
      roi_y = as.integer(input$roi_y),
      roi_width = as.integer(input$roi_width),
      roi_height = as.integer(input$roi_height),
      microns_per_pixel = as.numeric(input$microns_per_pixel),
      seconds_per_frame = as.numeric(input$seconds_per_frame)
    )
    if (identical(analysis_method, "optical_flow")) {
      config$mask_percentile <- as.numeric(input$mask_percentile)
      config$flow_blur_kernel <- as.integer(input$flow_blur_kernel)
      config$flow_winsize <- as.integer(input$flow_winsize)
      config$flow_arrow_spacing <- as.integer(input$flow_arrow_spacing)
      config$flow_arrow_scale <- as.numeric(input$flow_arrow_scale)
      run_label <- paste("Optical flow on", row$file_name)
      progress_message <- "Running optical flow analysis"
      progress_detail <- "Cropping lossless frames and estimating dense Farnebäck flow..."
    } else {
      config$num_points <- as.integer(input$num_points)
      config$min_spacing <- as.integer(input$min_spacing)
      config$search_radius <- as.integer(input$search_radius)
      config$patch_size <- as.integer(input$patch_size)
      config$min_confidence <- as.numeric(input$min_confidence)
      config$lookahead_frames <- as.integer(input$lookahead_frames)
      config$preview_fps <- as.numeric(input$preview_fps)
      config$tracking_method <- input$tracking_method
      run_label <- paste("Tracking", row$file_name)
      progress_message <- "Running calibrated tracking"
      progress_detail <- "Cropping lossless frames and following bright actin landmarks..."
    }
    run_state(list(status = "running", message = run_label, detail = progress_detail, log = character()))
    tryCatch({
      bridge_result <- withProgress(
        message = progress_message,
        detail = progress_detail,
        value = 0.55,
        run_tracking_bridge(project_dir(), config)
      )
      outputs <- bridge_result$payload$outputs %||% list()
      summary_path <- outputs$summary_json %||% bridge_result$payload$summary_json %||% ""
      refresh_token(refresh_token() + 1L)
      new_results <- results()
      pending_id <- if (nrow(new_results) > 0) new_results$result_id[[1]] else summary_path
      pending_result(pending_id)
      run_state(list(
        status = "success",
        message = paste("Completed", row$file_name),
        detail = "",
        log = bridge_result$log,
        payload = bridge_result$payload
      ))
      updateRadioButtons(session, "section", selected = "review")
      nav_select("main_nav", selected = "review")
      showNotification(
        if (identical(analysis_method, "optical_flow")) "Optical flow run completed" else "Tracking run completed",
        type = "message",
        duration = 4
      )
    }, error = function(exc) {
      run_state(list(status = "error", message = conditionMessage(exc), detail = "", log = character()))
      showNotification(conditionMessage(exc), type = "error", duration = 10)
    })
  })

  output$run_activity <- renderUI({
    state <- run_state()
    icon_name <- if (state$status == "success") "circle-check" else if (state$status == "error") "circle-exclamation" else if (state$status == "running") "spinner" else "clock"
    detail <- state$detail %||% ""
    if (identical(state$status, "idle")) {
      detail <- "Runs started on this page appear here with status and technical logs."
    }
    div(
      class = paste("run-activity", paste0("run-", state$status)),
      fontawesome::fa(icon_name),
      div(
        strong(state$message),
        if (nzchar(detail)) tags$p(class = "run-detail", detail),
        if (length(state$log) > 0) tags$details(tags$summary("Technical log"), tags$pre(paste(state$log, collapse = "\n")))
      )
    )
  })

  observeEvent(results(), {
    data <- results()
    choices <- compact_result_choices(data)
    selected <- pending_result()
    if (!nzchar(selected) || !selected %in% unname(choices)) selected <- input$result_file
    if (length(choices) > 0 && (is.null(selected) || !selected %in% unname(choices))) {
      selected <- unname(choices[[1]])
    }
    updateSelectInput(session, "result_file", choices = choices, selected = selected)
  }, ignoreInit = FALSE)

  output$review_empty_gate <- renderUI({
    if (nrow(results()) > 0) return(NULL)
    next_step_banner(
      "No results to review yet",
      "Open Project, select a video, then run analysis on Track.",
      actionButton("go_tracking", "Go to Track", icon = fontawesome::fa("crosshairs"), class = "btn-sm btn-primary"),
      tone = "muted"
    )
  })

  output$compare_empty_gate <- renderUI({
    if (nrow(results()) > 0) return(NULL)
    next_step_banner(
      "Nothing to compare yet",
      "Complete at least one analysis run. Group charts split landmark tracking and optical flow separately.",
      actionButton("go_tracking", "Run analysis", icon = fontawesome::fa("play"), class = "btn-sm btn-primary"),
      tone = "muted"
    )
  })

  output$qc_primary_header <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(strong("QC image"))
    if (identical(row$analysis_method, "optical_flow")) strong("Flow overlay") else strong("Starting points")
  })

  output$qc_secondary_header <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(strong("QC image"))
    if (identical(row$analysis_method, "optical_flow")) strong("Track paths") else strong("Track overlay")
  })

  output$qc_video_header <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(strong("Preview video"))
    if (identical(row$analysis_method, "optical_flow")) strong("Flow preview") else strong("Tracking preview")
  })

  selected_result <- reactive(selected_row(results(), input$result_file %||% "", "result_id"))
  flow_pairs <- reactive({
    row <- selected_result()
    if (is.null(row)) return(data.frame())
    data <- read_flow_pairs(row$flow_pair_csv)
    if (nrow(data) == 0) return(data.frame())
    data$pair_index <- seq_len(nrow(data))
    data$absolute_velocity_um_s <- px_frame_to_um_s(
      data$mean_magnitude_px_frame,
      row$microns_per_pixel,
      row$seconds_per_frame
    )
    data$downward_velocity_um_s <- px_frame_to_um_s(
      data$mean_downward_px_frame,
      row$microns_per_pixel,
      row$seconds_per_frame
    )
    data
  })
  trajectory <- reactive({
    row <- selected_result()
    if (is.null(row)) return(data.frame())
    read_trajectory(row$trajectory_csv)
  })
  angle_trajectory <- reactive({
    row <- selected_result()
    if (is.null(row)) return(data.frame())
    derive_angle_dynamics(
      read_trajectory(row$trajectory_csv),
      row$seconds_per_frame %||% 1
    )
  })
  angle_summary <- reactive(summarize_angle_dynamics(angle_trajectory()))

  is_flow_result <- reactive({
    row <- selected_result()
    !is.null(row) && identical(row$analysis_method, "optical_flow")
  })

  output$review_context_banner <- renderUI({
    row <- selected_result()
    if (is.null(row)) {
      return(empty_state("file-circle-question", "No analysis result selected", "Choose a completed run above to preview and analyze it."))
    }
    relative_source <- relative_to_project(project_dir(), row$source_path)
    method_label <- tracking_method_label(row)
    div(
      class = "selected-file-banner",
      div(class = "selected-file-icon", fontawesome::fa("file-video")),
      div(
        class = "selected-file-copy",
        div(class = "selected-file-label", "SELECTED RUN"),
        strong(row$source_name),
        p(relative_source)
      ),
      div(
        class = "selected-file-tags",
        status_pill(row$group, "info"),
        status_pill(method_label, if (identical(row$analysis_method, "optical_flow")) "teal" else "neutral"),
        span(class = "selected-file-time", paste("Run", gsub("T", " ", substr(row$analyzed_at, 1, 19), fixed = TRUE)))
      )
    )
  })

  output$review_method_note <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(NULL)
    if (identical(row$analysis_method, "optical_flow")) {
      note <- "Optical flow reports dense meshwork motion. Inspect the flow overlay and per-pair velocity — values are not comparable to landmark runs."
    } else {
      primary <- result_primary_speed(row)
      note <- paste0(
        "Primary speed is the time-weighted mean (",
        format_metric(primary, 3),
        " µm/s). If tracks jump or swap identity, re-run with optical flow or a tighter ROI."
      )
    }
    div(
      class = "analysis-definition-note review-method-note",
      fontawesome::fa("circle-info"),
      note
    )
  })

  output$result_metrics <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(empty_state("route", "No result selected", "Run analysis or choose a saved result."))
    if (identical(row$analysis_method, "optical_flow")) {
      boxes <- list(
        metric_value_box(
          "General movement",
          paste0(format_metric(row$absolute_velocity), " µm/s"),
          "Optical flow primary metric",
          "arrows-up-down-left-right",
          "teal"
        ),
        metric_value_box(
          "Downward motion",
          paste0(format_metric(row$downward_velocity), " µm/s"),
          "Directional secondary metric",
          "arrow-down",
          "blue"
        )
      )
      if (!is.na(row$directionality_ratio)) {
        boxes <- c(boxes, list(metric_value_box(
          "Directionality ratio",
          format_metric(row$directionality_ratio, 2),
          "Downward share of general movement",
          "compass",
          "amber"
        )))
      }
      boxes <- c(boxes, list(metric_value_box(
        "Valid pixel fraction",
        format_metric(row$valid_pixel_fraction, 2),
        "Bright actin mask coverage",
        "mask",
        if (!is.na(row$directionality_ratio)) "gray" else "amber"
      )))
      if ("saturated_pixel_fraction" %in% names(row) && !is.na(row$saturated_pixel_fraction)) {
        boxes <- c(boxes, list(metric_value_box(
          "Saturated pixel fraction",
          format_metric(row$saturated_pixel_fraction, 2),
          "Bright pixels at detector ceiling",
          "sun",
          "gray"
        )))
      } else {
        boxes <- c(boxes, list(metric_value_box(
          "Frame pairs",
          format_metric(row$valid_steps, 0),
          paste0(format_metric(row$frame_count, 0), " frames"),
          "list-check",
          "gray"
        )))
      }
      return(layout_metric_boxes(boxes))
    }

    primary <- result_primary_speed(row)
    step_weighted <- result_step_weighted_speed(row)
    show_step_weighted <- !is.na(primary) && !is.na(step_weighted) &&
      abs(primary - step_weighted) > 0.0005
    boxes <- list(
      metric_value_box(
        "Primary speed (time-weighted)",
        paste0(format_metric(primary), " µm/s"),
        "Recommended landmark scalar speed",
        "arrows-up-down-left-right",
        "teal"
      ),
      metric_value_box(
        "Downward velocity",
        paste0(format_metric(row$downward_velocity), " µm/s"),
        "Directional secondary metric",
        "arrow-down",
        "blue"
      )
    )
    if (show_step_weighted) {
      boxes <- c(boxes, list(metric_value_box(
        "Step-weighted speed",
        paste0(format_metric(step_weighted), " µm/s"),
        "Unweighted mean across valid steps",
        "wave-square",
        "amber"
      )))
    }
    boxes <- c(boxes, list(
      metric_value_box(
        "Valid tracks",
        format_metric(row$valid_tracks, 0),
        paste0(format_metric(row$tracks_started, 0), " started"),
        "route",
        if (show_step_weighted) "gray" else "amber"
      ),
      metric_value_box(
        "Valid steps",
        format_metric(row$valid_steps, 0),
        paste0(format_metric(row$frame_count, 0), " frames"),
        "list-check",
        "gray"
      )
    ))
    layout_metric_boxes(boxes)
  })

  output$motion_paths_header <- renderUI({
    strong(if (is_flow_result()) "Flow velocity by frame pair" else "Track paths")
  })

  output$motion_velocity_header <- renderUI({
    strong(if (is_flow_result()) "Downward velocity by frame pair" else "Absolute velocity by frame")
  })

  output$angles_tab_title <- renderUI({
    if (is_flow_result()) {
      return(tagList("Angles ", span(class = "tab-badge", "landmark")))
    }
    "Angles"
  })

  observeEvent(selected_result(), {
    row <- selected_result()
    if (is.null(row)) return()
    if (identical(row$analysis_method, "optical_flow") && identical(input$review_tab, "Angles")) {
      nav_select("review_tab", selected = "Overview")
    }
  }, ignoreInit = TRUE)

  output$angles_tab_body <- renderUI({
    row <- selected_result()
    if (is.null(row)) {
      return(empty_state("compass", "No result selected", "Run tracking or choose a saved result."))
    }
    if (is_flow_result()) {
      return(empty_state(
        "compass",
        "Angle dynamics require landmark trajectories",
        tagList(
          "Optical flow reports dense motion, not per-point paths. ",
          actionLink(
            "angles_go_track_landmark",
            "Re-run on Track with landmark tracking",
            class = "empty-state-link"
          ),
          " to inspect motion direction and turning."
        )
      ))
    }
    tagList(
      div(
        class = "analysis-definition-note",
        fontawesome::fa("circle-info"),
        " Angle convention: 0° = right, +90° = down, ±180° = left, and -90° = up in image coordinates. Turning is wrapped to -180°…+180°."
      ),
      uiOutput("angle_metrics"),
      layout_columns(
        col_widths = c(7, 5),
        card(
          class = "surface-card media-card angle-preview-card",
          card_header(
            div(
              strong("Full-sequence tracking preview"),
              span(class = "card-subtitle", "Confirms which source and tracks are being analyzed")
            )
          ),
          card_body(uiOutput("angle_preview_media"))
        ),
        card(
          class = "surface-card media-card angle-overlay-card",
          card_header(
            div(
              strong("Trajectory overlay"),
              span(class = "card-subtitle", "All tracked paths for the selected run")
            )
          ),
          card_body(uiOutput("angle_overlay_media"))
        )
      ),
      layout_columns(
        col_widths = c(6, 6),
        card(
          class = "surface-card plot-card",
          card_header(strong("Instantaneous motion angle")),
          card_body(plotOutput("motion_angle_plot", height = "360px"))
        ),
        card(
          class = "surface-card plot-card",
          card_header(strong("Turning angle between steps")),
          card_body(plotOutput("turning_angle_plot", height = "360px"))
        )
      ),
      card(
        class = "surface-card plot-card",
        card_header(strong("Tracked position through time")),
        card_body(plotOutput("position_time_plot", height = "330px"))
      ),
      card(
        class = "surface-card",
        card_header(
          div(
            strong("Per-step angle data"),
            downloadButton("download_angle_data", "CSV", class = "btn-sm")
          )
        ),
        card_body(uiOutput("angle_table"))
      )
    )
  })

  observeEvent(input$angles_go_track_landmark, {
    updateRadioButtons(session, "analysis_method", selected = "landmark_tracking")
    updateRadioButtons(session, "section", selected = "track")
    nav_select("main_nav", selected = "track")
  })

  plot_theme <- function() {
    theme_minimal(base_size = 12) +
      theme(
        plot.background = element_rect(fill = "transparent", color = NA),
        panel.background = element_rect(fill = "transparent", color = NA),
        panel.grid.minor = element_blank(),
        panel.grid.major = element_line(color = "#E3E8E6", linewidth = 0.4),
        axis.title = element_text(color = "#52605D"),
        axis.text = element_text(color = "#687572"),
        legend.position = "bottom",
        legend.title = element_blank()
      )
  }

  output$trajectory_plot <- renderPlot({
    row <- selected_result()
    if (is_flow_result()) {
      data <- flow_pairs()
      validate(need(nrow(data) > 0, "No optical flow pair data for this result."))
      ggplot(data, aes(x = pair_index, y = absolute_velocity_um_s)) +
        geom_line(linewidth = 0.8, color = "#147A6C") +
        geom_point(size = 2, color = "#147A6C") +
        labs(x = "Frame pair", y = "Absolute velocity (µm/s)") +
        plot_theme()
      return()
    }
    data <- trajectory()
    validate(need(nrow(data) > 0, "No trajectory data for this result."))
    data$track_id <- factor(data$track_id)
    ggplot(data, aes(x = x_px, y = y_px, group = track_id, color = track_id)) +
      geom_path(linewidth = 0.8, alpha = 0.8) +
      geom_point(size = 1.6) +
      scale_y_reverse() +
      coord_equal() +
      labs(x = "X position (px)", y = "Y position (px)") +
      plot_theme()
  })

  output$velocity_plot <- renderPlot({
    row <- selected_result()
    if (is_flow_result()) {
      data <- flow_pairs()
      validate(need(nrow(data) > 0, "No optical flow pair data for this result."))
      ggplot(data, aes(x = pair_index, y = downward_velocity_um_s)) +
        geom_hline(yintercept = 0, color = "#AAB5B2", linewidth = 0.4) +
        geom_line(linewidth = 0.8, color = "#D08A2E") +
        geom_point(size = 2, color = "#D08A2E") +
        labs(x = "Frame pair", y = "Downward velocity (µm/s)") +
        plot_theme()
      return()
    }
    data <- trajectory()
    validate(need(nrow(data) > 0, "No trajectory data for this result."))
    validate(need("absolute_velocity_um_per_s" %in% names(data), "Run output does not contain per-step velocity."))
    data <- data[!is.na(data$absolute_velocity_um_per_s), , drop = FALSE]
    data$track_id <- factor(data$track_id)
    ggplot(data, aes(x = frame_index, y = absolute_velocity_um_per_s, group = track_id, color = track_id)) +
      geom_line(linewidth = 0.7, alpha = 0.75) +
      geom_point(size = 1.4) +
      labs(x = "Frame", y = "Absolute velocity (µm/s)") +
      plot_theme()
  })

  output$angle_metrics <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(empty_state("compass", "No result selected", "Run tracking or choose a saved result."))
    if (is_flow_result()) return(NULL)
    summary <- angle_summary()
    layout_columns(
      col_widths = c(3, 3, 3, 3),
      metric_value_box("Dominant direction", paste0(format_metric(summary$circular_mean_deg, 1), "°"), "Circular mean across all steps", "compass", "teal"),
      metric_value_box("Direction stability", format_metric(summary$directional_stability, 2), "0 = dispersed, 1 = aligned", "bullseye", "blue"),
      metric_value_box("Mean absolute turn", paste0(format_metric(summary$mean_absolute_turn_deg, 1), "°"), paste0(summary$reversal_count, " reversal step(s)"), "rotate", "amber"),
      metric_value_box("Motion pattern", summary$pattern, summary$detail, "wave-square", "gray")
    )
  })

  output$motion_angle_plot <- renderPlot({
    if (is_flow_result()) {
      par(mar = c(0, 0, 0, 0), bg = "transparent")
      plot.new()
      return()
    }
    data <- angle_trajectory()
    validate(need(nrow(data) > 0, "No angle trajectory data for this result."))
    data <- data[!is.na(data$motion_angle_deg), , drop = FALSE]
    validate(need(nrow(data) > 0, "No non-zero motion steps are available."))
    data$track_id <- factor(data$track_id)
    ggplot(data, aes(x = elapsed_time_s, y = motion_angle_deg, group = track_id, color = track_id)) +
      geom_hline(yintercept = 0, color = "#AAB5B2", linewidth = 0.4) +
      geom_line(linewidth = 0.65, alpha = 0.65) +
      geom_point(size = 1.5) +
      scale_y_continuous(limits = c(-180, 180), breaks = seq(-180, 180, 90)) +
      labs(x = "Elapsed time (s)", y = "Motion angle (degrees)") +
      plot_theme()
  })

  output$turning_angle_plot <- renderPlot({
    if (is_flow_result()) {
      par(mar = c(0, 0, 0, 0), bg = "transparent")
      plot.new()
      return()
    }
    data <- angle_trajectory()
    validate(need(nrow(data) > 0, "No angle trajectory data for this result."))
    data <- data[!is.na(data$turning_angle_deg), , drop = FALSE]
    validate(need(nrow(data) > 0, "At least three tracked positions are required to calculate turning."))
    data$track_id <- factor(data$track_id)
    ggplot(data, aes(x = elapsed_time_s, y = turning_angle_deg, group = track_id, color = track_id)) +
      geom_hline(yintercept = 0, color = "#7E8B88", linewidth = 0.45) +
      geom_hline(yintercept = c(-135, 135), color = "#B33A3A", linewidth = 0.35, linetype = "dashed") +
      geom_line(linewidth = 0.65, alpha = 0.7) +
      geom_point(size = 1.5) +
      scale_y_continuous(limits = c(-180, 180), breaks = seq(-180, 180, 90)) +
      labs(x = "Elapsed time (s)", y = "Turning angle (degrees)") +
      plot_theme()
  })

  output$position_time_plot <- renderPlot({
    if (is_flow_result()) {
      par(mar = c(0, 0, 0, 0), bg = "transparent")
      plot.new()
      return()
    }
    data <- angle_trajectory()
    validate(need(nrow(data) > 0, "No tracked positions for this result."))
    x_data <- data.frame(
      track_id = data$track_id, elapsed_time_s = data$elapsed_time_s,
      coordinate = "X", position_px = data$x_px
    )
    y_data <- data.frame(
      track_id = data$track_id, elapsed_time_s = data$elapsed_time_s,
      coordinate = "Y", position_px = data$y_px
    )
    position_data <- rbind(x_data, y_data)
    position_data$track_id <- factor(position_data$track_id)
    ggplot(position_data, aes(x = elapsed_time_s, y = position_px, group = track_id, color = track_id)) +
      geom_line(linewidth = 0.7, alpha = 0.75) +
      facet_wrap(~coordinate, scales = "free_y", ncol = 1) +
      labs(x = "Elapsed time (s)", y = "Position (px)") +
      plot_theme()
  })

  output$angle_table <- renderUI({
    data <- angle_trajectory()
    if (nrow(data) == 0) return(empty_state("table", "No angle table", "The selected run has no readable trajectory CSV."))
    div(class = "data-table-wrap trajectory-table-wrap", tableOutput("angle_table_inner"))
  })
  output$angle_table_inner <- renderTable({
    data <- angle_trajectory()
    keep <- intersect(
      c("track_id", "frame_index", "elapsed_time_s", "x_px", "y_px", "motion_angle_deg", "turning_angle_deg", "absolute_velocity_um_per_s"),
      names(data)
    )
    head(data[, keep, drop = FALSE], 250)
  }, striped = TRUE, hover = TRUE, spacing = "s", rownames = FALSE, digits = 3)

  output$download_angle_data <- downloadHandler(
    filename = function() "actintrack_angle_dynamics.csv",
    content = function(file) write.csv(angle_trajectory(), file, row.names = FALSE)
  )

  local_image_ui <- function(path, alt) {
    if (!safe_output_file(path)) return(empty_state("image", "Preview unavailable", "This run does not include the requested QC image."))
    encoded <- base64enc::dataURI(file = path, mime = "image/png")
    tags$img(src = encoded, alt = alt, class = "qc-image")
  }

  output$starting_points_media <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(empty_state("image", "No result selected", "Choose a result to inspect QC imagery."))
    if (identical(row$analysis_method, "optical_flow")) {
      return(local_image_ui(row$flow_overlay, "Optical flow arrow overlay"))
    }
    local_image_ui(row$starting_points, "Detected starting points")
  })
  output$track_overlay_media <- renderUI({
    row <- selected_result()
    if (is.null(row)) return(empty_state("image", "No result selected", "Choose a result to inspect QC imagery."))
    if (identical(row$analysis_method, "optical_flow")) {
      return(empty_state("chart-line", "Trajectory overlay not applicable", "Optical flow reports dense motion rather than individual track paths."))
    }
    local_image_ui(row$track_overlay, "Tracked point paths")
  })
  output$angle_overlay_media <- renderUI({
    row <- selected_result()
    if (is.null(row)) {
      return(empty_state("route", "No result selected", "Choose a tracking result to preview its trajectories."))
    }
    local_image_ui(row$track_overlay, paste("Trajectory overlay for", row$source_name))
  })

  output$trajectory_table <- renderUI({
    row <- selected_result()
    if (is_flow_result()) {
      data <- flow_pairs()
      if (nrow(data) == 0) return(empty_state("table", "No flow pair table", "The selected run has no readable flow pair CSV."))
      keep <- intersect(
        c("frame_a", "frame_b", "valid_pixel_fraction", "mean_magnitude_px_frame", "mean_downward_px_frame", "absolute_velocity_um_s", "downward_velocity_um_s"),
        names(data)
      )
      div(class = "data-table-wrap trajectory-table-wrap", tableOutput("trajectory_table_inner"))
      return()
    }
    data <- trajectory()
    if (nrow(data) == 0) return(empty_state("table", "No trajectory table", "The selected run has no readable CSV output."))
    div(class = "data-table-wrap trajectory-table-wrap", tableOutput("trajectory_table_inner"))
  })
  output$trajectory_table_inner <- renderTable({
    if (is_flow_result()) {
      data <- flow_pairs()
      keep <- intersect(
        c("frame_a", "frame_b", "valid_pixel_fraction", "mean_magnitude_px_frame", "mean_downward_px_frame", "absolute_velocity_um_s", "downward_velocity_um_s"),
        names(data)
      )
      return(head(data[, keep, drop = FALSE], 250))
    }
    data <- trajectory()
    keep <- intersect(
      c("track_id", "frame_index", "x_px", "y_px", "displacement_um", "absolute_velocity_um_per_s", "downward_velocity_um_per_s", "confidence"),
      names(data)
    )
    head(data[, keep, drop = FALSE], 250)
  }, striped = TRUE, hover = TRUE, spacing = "s", rownames = FALSE)

  observeEvent(project_dir(), {
    prefix <- "actintrack-processed"
    if (prefix %in% names(resourcePaths())) removeResourcePath(prefix)
    processed <- file.path(project_dir(), "processed")
    if (dir.exists(processed)) addResourcePath(prefix, processed)
  }, ignoreInit = FALSE)

  processed_media_url <- function(path) {
    if (!safe_output_file(path)) return("")
    relative <- relative_to_project(file.path(project_dir(), "processed"), path)
    parts <- strsplit(relative, .Platform$file.sep, fixed = TRUE)[[1]]
    paste0("actintrack-processed/", paste(vapply(parts, URLencode, character(1), reserved = TRUE), collapse = "/"))
  }

  ensure_browser_preview <- function(row) {
    if (is.null(row)) return("")
    if (safe_output_file(row$track_preview_webm)) return(row$track_preview_webm)
    if (!safe_output_file(row$track_preview)) return("")
    target <- row$track_preview_webm %||% sub(
      "\\.mp4$", ".webm", row$track_preview, ignore.case = TRUE
    )
    if (!nzchar(target) || identical(target, row$track_preview)) return("")
    converted <- tryCatch({
      run_bridge(project_dir(), c("browser-preview", row$track_preview, target))
      target
    }, error = function(...) "")
    if (safe_output_file(converted)) converted else ""
  }

  angle_browser_preview <- reactive(ensure_browser_preview(selected_result()))
  result_browser_preview <- reactive(ensure_browser_preview(selected_result()))

  browser_video_ui <- function(row, webm_path, aria_label) {
    sources <- list()
    if (safe_output_file(webm_path)) {
      sources <- c(sources, list(tags$source(
        src = processed_media_url(webm_path),
        type = "video/webm"
      )))
    }
    mp4_codec <- row$track_preview_mp4_codec %||% ""
    if (safe_output_file(row$track_preview) && mp4_codec %in% c("avc1", "H264")) {
      sources <- c(sources, list(tags$source(
        src = processed_media_url(row$track_preview),
        type = "video/mp4"
      )))
    }
    if (length(sources) == 0) return(NULL)
    tags$video(
      sources,
      controls = NA,
      preload = "metadata",
      class = "track-video angle-track-video",
      `aria-label` = aria_label,
      "This browser cannot play the generated preview. Use the trajectory overlay below."
    )
  }

  output$angle_preview_media <- renderUI({
    row <- selected_result()
    if (is.null(row)) {
      return(empty_state("video", "No result selected", "Choose a tracking result to preview the full sequence."))
    }
    video <- browser_video_ui(
      row,
      angle_browser_preview(),
      paste("Full-sequence tracking preview for", row$source_name)
    )
    if (!is.null(video)) return(video)
    if (safe_output_file(row$track_overlay)) {
      return(local_image_ui(row$track_overlay, paste("Trajectory overlay for", row$source_name)))
    }
    empty_state("video-slash", "Preview unavailable", "This saved run has no preview video or trajectory overlay.")
  })

  output$track_video <- renderUI({
    row <- selected_result()
    if (is.null(row)) {
      return(empty_state("video", "Preview video unavailable", "The tracker may not have produced an MP4 preview for this run."))
    }
    if (identical(row$analysis_method, "optical_flow")) {
      return(empty_state("video-slash", "No preview video", "Optical flow runs save a static flow overlay instead of a tracking preview video."))
    }
    video <- browser_video_ui(
      row,
      result_browser_preview(),
      paste("Tracking preview for", row$source_name)
    )
    if (!is.null(video)) return(video)
    empty_state("video-slash", "Preview video unavailable", "No browser-compatible preview could be generated for this run.")
  })

  output$download_trajectory <- downloadHandler(
    filename = function() {
      row <- selected_result()
      if (is_flow_result()) basename(row$flow_pair_csv %||% "flow_pair_summaries.csv")
      else basename(row$trajectory_csv %||% "trajectory.csv")
    },
    content = function(file) {
      row <- selected_result()
      source_path <- if (is_flow_result()) row$flow_pair_csv else row$trajectory_csv
      file.copy(source_path, file, overwrite = TRUE)
    }
  )
  output$download_summary <- downloadHandler(
    filename = function() basename(selected_result()$summary_json %||% "summary.json"),
    content = function(file) file.copy(selected_result()$summary_json, file, overwrite = TRUE)
  )

  group_summary <- reactive(summarize_groups_stratified(results()))

  output$compare_method_note <- renderUI({
    if (nrow(results()) == 0) return(NULL)
    div(
      class = "analysis-definition-note compare-method-note",
      fontawesome::fa("circle-info"),
      "Landmark tracking and optical flow use different movement scalars. Charts below are split by analysis method — compare within method only."
    )
  })

  output$analysis_metrics <- renderUI({
    data <- results()
    landmark_runs <- sum(data$analysis_method == "landmark_tracking", na.rm = TRUE)
    flow_runs <- sum(data$analysis_method == "optical_flow", na.rm = TRUE)
    layout_columns(
      col_widths = c(4, 4, 4),
      metric_value_box("Landmark runs", landmark_runs, "Bright-point tracking results", "route", "teal"),
      metric_value_box("Optical flow runs", flow_runs, "Dense meshwork flow results", "wind", "blue"),
      metric_value_box("Groups represented", length(unique(data$group)), "Biological categories", "people-group", "amber")
    )
  })

  output$group_plot <- renderPlot({
    summary <- group_summary()
    validate(need(nrow(summary) > 0, "Complete tracking runs to populate group analysis."))
    summary$method_label <- vapply(summary$analysis_method, analysis_method_label, character(1))
    long <- rbind(
      data.frame(
        group = summary$group,
        method_label = summary$method_label,
        metric = "Primary speed",
        value = summary$mean_primary_speed
      ),
      data.frame(
        group = summary$group,
        method_label = summary$method_label,
        metric = "Downward velocity",
        value = summary$mean_downward_velocity
      )
    )
    ggplot(long, aes(x = group, y = value, fill = metric)) +
      geom_col(position = position_dodge(width = 0.75), width = 0.64) +
      facet_wrap(~method_label, scales = "free_y") +
      scale_fill_manual(values = c("Primary speed" = "#147A6C", "Downward velocity" = "#D08A2E")) +
      labs(x = NULL, y = "Mean velocity (µm/s)") +
      plot_theme() +
      theme(axis.text.x = element_text(angle = 20, hjust = 1))
  })

  output$group_table <- renderUI({
    summary <- group_summary()
    if (nrow(summary) == 0) return(empty_state("chart-column", "No group results", "Complete tracking runs to compare groups."))
    div(class = "data-table-wrap", tableOutput("group_table_inner"))
  })
  output$group_table_inner <- renderTable({
    summary <- group_summary()
    summary$mean_primary_speed <- round(summary$mean_primary_speed, 4)
    summary$mean_downward_velocity <- round(summary$mean_downward_velocity, 4)
    summary$mean_net_y_velocity <- round(summary$mean_net_y_velocity, 4)
    summary$method_label <- vapply(summary$analysis_method, analysis_method_label, character(1))
    display <- summary[, c(
      "group", "method_label", "runs", "mean_primary_speed", "mean_downward_velocity",
      "total_valid_tracks", "total_valid_steps"
    ), drop = FALSE]
    names(display) <- c(
      "Group", "Method", "Runs", "Primary µm/s", "Downward µm/s",
      "Valid tracks", "Valid steps"
    )
    display
  }, striped = TRUE, hover = TRUE, spacing = "s", rownames = FALSE)

  output$all_results_table <- renderUI({
    data <- results()
    if (nrow(data) == 0) return(empty_state("flask", "No completed runs", "Run tracking to create analysis data."))
    div(class = "data-table-wrap", tableOutput("all_results_table_inner"))
  })
  output$all_results_table_inner <- renderTable({
    data <- results()
    data$primary_speed <- vapply(seq_len(nrow(data)), function(i) result_primary_speed(data[i, , drop = FALSE]), numeric(1))
    display <- data[, c(
      "group", "source_name", "analysis_method", "primary_speed",
      "downward_velocity", "valid_tracks", "valid_steps", "analyzed_at"
    )]
    display$analysis_method <- vapply(display$analysis_method, analysis_method_label, character(1))
    names(display) <- c("Group", "Source", "Method", "Primary µm/s", "Downward µm/s", "Tracks", "Steps", "Analyzed")
    display
  }, striped = TRUE, hover = TRUE, spacing = "s", rownames = FALSE)

  output$stack_metrics <- renderUI({
    data <- stacks()
    total_size <- if (nrow(data) > 0) sum(data$size_bytes, na.rm = TRUE) else 0
    layout_columns(
      col_widths = c(4, 4, 4),
      metric_value_box("Stack files", nrow(data), "Raw microscopy inputs", "layer-group", "teal"),
      metric_value_box("Total size", format_bytes(total_size), "Local disk footprint", "hard-drive", "blue"),
      metric_value_box("Formats", length(unique(data$extension)), paste(sort(unique(data$extension)), collapse = ", "), "file-waveform", "amber")
    )
  })

  output$stack_table <- renderUI({
    data <- stacks()
    if (nrow(data) == 0) return(empty_state("layer-group", "No z-stacks", "No OIR, OIB, TIFF, or TIF files were found."))
    div(class = "data-table-wrap", tableOutput("stack_table_inner"))
  })
  output$stack_table_inner <- renderTable({
    data <- stacks()[, c("group", "file_name", "extension", "size", "modified", "relative_path")]
    names(data) <- c("Group", "File", "Format", "Size", "Modified", "Location")
    data
  }, striped = TRUE, hover = TRUE, spacing = "s", rownames = FALSE)

  output$stack_selector <- renderUI({
    data <- stacks()
    if (nrow(data) == 0) return(NULL)
    choices <- stats::setNames(data$path, paste(data$group, data$file_name, sep = " / "))
    selectInput("stack_file", "Stack file", choices = choices)
  })
  selected_stack <- reactive({
    req(input$stack_file)
    rows <- stacks()[stacks()$path == input$stack_file, , drop = FALSE]
    if (nrow(rows) == 0) NULL else rows[1, , drop = FALSE]
  })
  output$stack_detail <- renderUI({
    row <- selected_stack()
    if (is.null(row)) return(NULL)
    div(
      class = "stack-detail",
      div(span("Format"), strong(row$extension)),
      div(span("File size"), strong(row$size)),
      div(span("Group"), strong(row$group)),
      div(span("Status"), status_pill("Not in velocity pipeline", "neutral")),
      p(class = "path-text", row$relative_path)
    )
  })

  always_active_outputs <- c(
    "sidebar_workspace_chip", "sidebar_active_source", "sidebar_result_section",
    "mobile_context_bar", "track_empty_gate",
    "workspace_status",
    "source_browser", "source_browser_count", "active_source_banner",
    "source_preview_controls", "source_preview_plot", "source_preview_status",
    "workflow_progress", "project_summary_metrics", "project_next_action",
    "calibration_accordion_title", "track_sticky_run",
    "frame_control", "tracking_source_banner", "frame_plot", "preview_status",
    "roi_summary", "run_activity", "review_empty_gate",
    "compare_empty_gate", "review_context_banner", "angles_tab_title",
    "qc_primary_header", "qc_secondary_header", "qc_video_header",
    "result_metrics", "trajectory_plot", "velocity_plot", "starting_points_media",
    "group_plot",
    "track_overlay_media", "trajectory_table", "track_video",
    "motion_paths_header", "motion_velocity_header", "angles_tab_body",
    "angle_metrics", "motion_angle_plot", "turning_angle_plot", "position_time_plot",
    "angle_table", "angle_preview_media", "angle_overlay_media"
  )
  for (output_name in always_active_outputs) {
    outputOptions(output, output_name, suspendWhenHidden = FALSE)
  }
}

shinyApp(ui, server)
