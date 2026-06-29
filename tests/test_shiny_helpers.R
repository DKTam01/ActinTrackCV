#!/usr/bin/env Rscript

# Unit tests for Shiny helper functions used in workspace/source selection.

stopifnot <- function(...) {
  if (!all(...)) stop("Assertion failed", call. = FALSE)
}

assert_equal <- function(actual, expected, label = "") {
  if (!identical(actual, expected)) {
    stop(
      paste0(
        if (nzchar(label)) paste0(label, ": ") else "",
        "expected ", deparse(expected), " but got ", deparse(actual)
      ),
      call. = FALSE
    )
  }
}

assert_true <- function(condition, label = "") {
  if (!isTRUE(condition)) {
    stop(paste0(if (nzchar(label)) paste0(label, ": ") else "", "expected TRUE"), call. = FALSE)
  }
}

locate_repo_root <- function() {
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg) == 0) {
    return(normalizePath(file.path(getwd(), ".."), mustWork = FALSE))
  }
  script_path <- sub("^--file=", "", file_arg[[1]])
  normalizePath(file.path(dirname(script_path), ".."), mustWork = TRUE)
}

ROOT <- locate_repo_root()
source(file.path(ROOT, "shiny_app", "R", "helpers.R"), local = TRUE)

create_fixture_workspace <- function() {
  root <- tempfile("actintrack_workspace_")
  raw_dir <- file.path(root, "raw", "1_WT_218")
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  video_path <- file.path(raw_dir, "WT218_0001.avi")
  writeLines("fake avi placeholder", video_path)
  processed_dir <- file.path(root, "processed", "shiny_runs")
  dir.create(processed_dir, recursive = TRUE, showWarnings = FALSE)
  preview_path <- file.path(processed_dir, "sample_track_preview.mp4")
  writeLines("fake preview", preview_path)
  list(root = root, video_path = normalizePath(video_path, mustWork = FALSE))
}

run_tests <- function() {
  tests_run <- 0L
  run_case <- function(name, expr) {
    tests_run <<- tests_run + 1L
    result <- tryCatch(expr, error = function(exc) exc)
    if (inherits(result, "error")) {
      stop(paste0("[FAIL] ", name, ": ", conditionMessage(result)), call. = FALSE)
    }
    cat("[ok]", name, "\n")
  }

  fixture <- create_fixture_workspace()
  on.exit(unlink(fixture$root, recursive = TRUE, force = TRUE), add = TRUE)

  run_case("workspace_state marks valid project folders", {
    info <- workspace_state(fixture$root)
    assert_true(info$valid, "valid flag")
    assert_equal(info$status, "ready")
    assert_equal(info$path, normalize_project_path(fixture$root))
  })

  run_case("workspace_state marks missing folders", {
    info <- workspace_state(file.path(fixture$root, "missing"))
    assert_true(!info$valid, "missing folder")
    assert_equal(info$status, "missing")
  })

  run_case("discover_video_sources scopes to workspace only", {
    sources <- discover_video_sources(fixture$root)
    assert_true(nrow(sources) == 1L, "one source")
    assert_equal(sources$path[[1]], fixture$video_path)
    assert_equal(sources$group[[1]], "1_WT_218")
    assert_true(!any(grepl("_track_preview\\.mp4$", sources$file_name, ignore.case = TRUE)), "preview excluded")
  })

  run_case("discover_video_sources ignores other workspaces", {
    other <- tempfile("actintrack_other_")
    on.exit(unlink(other, recursive = TRUE, force = TRUE), add = TRUE)
    dir.create(file.path(other, "raw"), recursive = TRUE, showWarnings = FALSE)
    writeLines("x", file.path(other, "raw", "other.avi"))
    sources <- discover_video_sources(fixture$root)
    assert_true(all(startsWith(sources$path, normalize_project_path(fixture$root))), "scoped paths")
  })

  run_case("coerce_active_source_path keeps valid selection", {
    sources <- discover_video_sources(fixture$root)
    assert_equal(coerce_active_source_path(sources, fixture$video_path), fixture$video_path)
  })

  run_case("coerce_active_source_path replaces stale selection", {
    sources <- discover_video_sources(fixture$root)
    assert_equal(coerce_active_source_path(sources, "/tmp/missing.avi"), fixture$video_path)
  })

  run_case("coerce_active_source_path returns empty when no sources", {
    empty <- discover_video_sources(file.path(fixture$root, "missing"))
    assert_equal(coerce_active_source_path(empty, fixture$video_path), "")
  })

  run_case("format_video_probe_summary handles empty metadata", {
    summary <- format_video_probe_summary(NULL)
    assert_equal(summary$frame_count, "--")
    assert_equal(summary$dimensions, "--")
  })

  run_case("format_video_probe_summary formats probe payload", {
    summary <- format_video_probe_summary(list(frame_count = 12, width = 640, height = 480, playback_fps = 5.2))
    assert_equal(summary$frame_count, "12")
    assert_equal(summary$dimensions, "640 × 480 px")
    assert_equal(summary$playback_fps, "5.2")
  })

  run_case("read_analysis_json parses optical flow summaries", {
    flow_json <- file.path(fixture$root, "processed", "sample_optical_flow.json")
    writeLines(
      jsonlite::toJSON(
        list(
          sample_id = "sample_flow",
          analysis_method = "optical_flow",
          analysis_timestamp_utc = "2026-06-29T12:00:00Z",
          optical_flow_general_movement_um_s = 1.23,
          optical_flow_downward_motion_um_s = 0.45,
          optical_flow_net_y_velocity_um_s = 0.12,
          optical_flow_directionality_ratio = 0.8,
          optical_flow_valid_pixel_fraction = 0.67,
          frame_count = 10,
          frame_pair_count = 9,
          outputs = list(
            flow_overlay_png = "processed/sample_flow_overlay.png",
            flow_pair_csv = "processed/sample_flow_pairs.csv"
          ),
          settings = list(seconds_per_frame = 30, microns_per_pixel = 0.265)
        ),
        auto_unbox = TRUE
      ),
      flow_json
    )
    row <- read_analysis_json(flow_json, fixture$root)
    assert_equal(row$analysis_method, "optical_flow")
    assert_equal(row$absolute_velocity, 1.23)
    assert_equal(row$downward_velocity, 0.45)
    assert_equal(row$valid_steps, 9)
    assert_true(nzchar(row$flow_overlay), "flow overlay path")
    assert_equal(row$primary_speed_um_s, 1.23)
    assert_equal(row$step_weighted_speed_um_s, 1.23)
  })

  run_case("read_analysis_json prefers time-weighted landmark speed", {
    landmark_json <- file.path(fixture$root, "processed", "sample_motion_index.json")
    writeLines(
      jsonlite::toJSON(
        list(
          sample_id = "sample_landmark",
          analysis_method = "landmark_tracking",
          analysis_timestamp_utc = "2026-06-29T12:30:00Z",
          time_weighted_mean_speed_um_per_s = 2.5,
          absolute_velocity_index_um_per_s = 1.8,
          general_movement_index_um_per_s = 1.8,
          downward_velocity_index_um_per_s = 0.9,
          num_tracks_started = 5,
          num_tracks_with_valid_steps = 4,
          total_valid_steps = 20,
          frame_count = 12,
          outputs = list(trajectory_csv = "processed/sample_trajectory.csv"),
          settings = list(seconds_per_frame = 30, microns_per_pixel = 0.265)
        ),
        auto_unbox = TRUE
      ),
      landmark_json
    )
    row <- read_analysis_json(landmark_json, fixture$root)
    assert_equal(row$analysis_method, "landmark_tracking")
    assert_equal(row$primary_speed_um_s, 2.5)
    assert_equal(row$step_weighted_speed_um_s, 1.8)
    assert_equal(row$absolute_velocity, 2.5)
    assert_true(is_landmark_result(row), "landmark helper")
    assert_true(!is_flow_result_row(row), "not flow helper")
  })

  run_case("derive_angle_dynamics reads CSV angles when present", {
    trajectory <- data.frame(
      track_id = c(0, 0, 0, 0),
      frame_index = c(0, 1, 2, 3),
      x_px = c(10, 11, 11, 10),
      y_px = c(10, 10, 11, 11),
      dt_s = c("", 30, 30, 30),
      motion_angle_deg = c("", 0, 90, 180),
      turning_angle_deg = c("", "", 90, 90),
      stringsAsFactors = FALSE
    )
    derived <- derive_angle_dynamics(trajectory, seconds_per_frame = 30)
    assert_equal(derived$motion_angle_deg, c(NA, 0, 90, 180))
    assert_equal(derived$turning_angle_deg, c(NA, NA, 90, 90))
    assert_equal(derived$elapsed_time_s, c(0, 30, 60, 90))
  })

  run_case("summarize_groups_by_method splits landmark vs flow", {
    results <- data.frame(
      group = c("1_WT_218", "1_WT_218", "2_WT_550"),
      analysis_method = c("landmark_tracking", "optical_flow", "landmark_tracking"),
      primary_speed_um_s = c(2.0, 1.5, 3.0),
      downward_velocity = c(0.5, 0.4, 0.6),
      net_y_velocity = c(NA_real_, 0.1, NA_real_),
      valid_tracks = c(4, NA_real_, 2),
      valid_steps = c(20, 9, 10),
      stringsAsFactors = FALSE
    )
    by_method <- summarize_groups_by_method(results)
    assert_true(nrow(by_method) == 3L, "three group-method rows")
    landmark_row <- by_method[
      by_method$group == "1_WT_218" & by_method$analysis_method == "landmark_tracking",
      ,
      drop = FALSE
    ]
    flow_row <- by_method[
      by_method$group == "1_WT_218" & by_method$analysis_method == "optical_flow",
      ,
      drop = FALSE
    ]
    assert_equal(landmark_row$runs, 1L)
    assert_equal(landmark_row$mean_primary_speed, 2.0)
    assert_equal(landmark_row$total_valid_tracks, 4)
    assert_equal(flow_row$runs, 1L)
    assert_equal(flow_row$mean_primary_speed, 1.5)
    assert_equal(flow_row$total_valid_steps, 9)
    grouped <- summarize_groups(results)
    assert_equal(grouped$landmark_runs[[1]], 1L)
    assert_equal(grouped$flow_runs[[1]], 1L)
    assert_equal(grouped$mean_absolute_velocity[[1]], mean(c(2.0, 1.5)))
  })

  tests_run
}

count <- run_tests()
cat(sprintf("\nAll %d Shiny helper tests passed.\n", count))
