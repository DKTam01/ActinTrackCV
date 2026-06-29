`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || all(is.na(x)) || identical(x, "")) y else x
}

safe_numeric <- function(x) {
  if (is.null(x) || length(x) == 0) return(NA_real_)
  suppressWarnings(as.numeric(x))
}

safe_scalar_numeric <- function(x) {
  value <- safe_numeric(x)
  if (length(value) == 0) return(NA_real_)
  value[[1]]
}

safe_mean <- function(x) {
  values <- safe_numeric(x)
  if (length(values) == 0 || all(is.na(values))) return(NA_real_)
  mean(values, na.rm = TRUE)
}

format_metric <- function(value, digits = 3) {
  value <- safe_scalar_numeric(value)
  if (length(value) == 0 || is.na(value)) return("--")
  formatC(value, digits = digits, format = "f")
}

format_bytes <- function(bytes) {
  bytes <- safe_scalar_numeric(bytes)
  if (length(bytes) == 0 || is.na(bytes)) return("--")
  units <- c("B", "KB", "MB", "GB", "TB")
  power <- if (bytes <= 0) 0 else min(floor(log(bytes, 1024)), length(units) - 1)
  paste0(formatC(bytes / (1024 ^ power), digits = 1, format = "f"), " ", units[[power + 1]])
}

normalize_project_path <- function(path) {
  normalizePath(path.expand(trimws(path)), mustWork = FALSE)
}

relative_to_project <- function(project_dir, path) {
  project <- paste0(normalize_project_path(project_dir), .Platform$file.sep)
  normalized <- normalizePath(path, mustWork = FALSE)
  if (startsWith(normalized, project)) substring(normalized, nchar(project) + 1) else normalized
}

resolve_result_path <- function(project_dir, value) {
  value <- trimws(as.character(value %||% ""))
  if (!nzchar(value)) return("")
  if (grepl("^(/|[A-Za-z]:[\\\\/])", value)) return(value)
  normalizePath(file.path(project_dir, value), mustWork = FALSE)
}

infer_group_from_path <- function(project_dir, path) {
  relative <- relative_to_project(project_dir, path)
  parts <- strsplit(relative, .Platform$file.sep, fixed = TRUE)[[1]]
  known <- c("1_WT_218", "2_WT_550", "3_Mutant_515", "4_Mutant_175")
  match <- parts[parts %in% known]
  if (length(match) > 0) match[[1]] else "Unassigned"
}

discover_video_sources <- function(project_dir) {
  project_dir <- normalize_project_path(project_dir)
  if (!dir.exists(project_dir)) return(data.frame())
  search_roots <- file.path(project_dir, c("raw", "processed"))
  search_roots <- search_roots[dir.exists(search_roots)]
  if (length(search_roots) == 0) return(data.frame())
  paths <- unlist(lapply(search_roots, function(root) {
    list.files(
      root,
      pattern = "\\.(avi|mp4)$",
      recursive = TRUE,
      full.names = TRUE,
      ignore.case = TRUE
    )
  }), use.names = FALSE)
  paths <- paths[!grepl("_track_preview\\.mp4$", paths, ignore.case = TRUE)]
  paths <- sort(unique(normalizePath(paths, mustWork = FALSE)))
  if (length(paths) == 0) return(data.frame())
  info <- file.info(paths)
  relative <- vapply(paths, function(path) relative_to_project(project_dir, path), character(1))
  location <- vapply(strsplit(relative, .Platform$file.sep, fixed = TRUE), function(parts) parts[[1]], character(1))
  groups <- vapply(paths, function(path) infer_group_from_path(project_dir, path), character(1))
  data.frame(
    source_id = as.character(seq_along(paths)),
    file_name = basename(paths),
    group = groups,
    location = location,
    size_bytes = info$size,
    size = vapply(info$size, format_bytes, character(1)),
    modified = format(info$mtime, "%Y-%m-%d %H:%M"),
    relative_path = relative,
    path = paths,
    stringsAsFactors = FALSE,
    row.names = NULL
  )
}

source_choices <- function(sources) {
  if (is.null(sources) || nrow(sources) == 0) return(character())
  labels <- paste(sources$group, sources$file_name, sep = "  /  ")
  stats::setNames(sources$path, labels)
}

workspace_state <- function(project_dir) {
  path <- normalize_project_path(project_dir)
  valid <- dir.exists(path)
  list(
    path = path,
    valid = isTRUE(valid),
    status = if (isTRUE(valid)) "ready" else "missing",
    message = if (isTRUE(valid)) "Workspace ready" else "Folder not found"
  )
}

coerce_active_source_path <- function(sources, current_path = "") {
  current_path <- trimws(as.character(current_path %||% ""))
  if (is.null(sources) || nrow(sources) == 0) return("")
  if (nzchar(current_path) && current_path %in% sources$path) return(current_path)
  sources$path[[1]]
}

source_file_choice_label <- function(row, is_active = FALSE) {
  htmltools::div(
    class = paste("source-file-row", if (isTRUE(is_active)) "is-active"),
    htmltools::div(class = "source-file-icon", fontawesome::fa("file-video", height = "14px")),
    htmltools::div(
      class = "source-file-copy",
      htmltools::strong(row$file_name),
      htmltools::tags$small(paste(row$group, "·", row$location))
    ),
    htmltools::div(
      class = "source-file-meta",
      htmltools::span(row$size),
      htmltools::tags$small(row$modified)
    )
  )
}

format_video_probe_summary <- function(metadata) {
  if (is.null(metadata) || length(metadata) == 0) {
    return(list(
      frame_count = "--",
      dimensions = "--",
      playback_fps = "--"
    ))
  }
  list(
    frame_count = as.character(metadata$frame_count %||% "--"),
    dimensions = paste0(metadata$width %||% "--", " × ", metadata$height %||% "--", " px"),
    playback_fps = format_metric(metadata$playback_fps, 1)
  )
}

active_source_banner <- function(row, metadata = NULL, empty_message = "Select a video from the list.") {
  if (is.null(row)) {
    return(htmltools::div(
      class = "active-source-banner active-source-banner-empty",
      fontawesome::fa("circle-question", height = "18px"),
      htmltools::div(
        htmltools::strong("No active video"),
        htmltools::p(empty_message)
      )
    ))
  }
  summary <- format_video_probe_summary(metadata)
  htmltools::div(
    class = "active-source-banner",
    htmltools::div(class = "active-source-icon", fontawesome::fa("film", height = "18px")),
    htmltools::div(
      class = "active-source-copy",
      htmltools::div(class = "active-source-label", "ACTIVE VIDEO"),
      htmltools::strong(row$file_name),
      htmltools::p(row$relative_path)
    ),
    htmltools::div(
      class = "active-source-tags",
      htmltools::span(class = "active-source-tag", row$group),
      htmltools::span(class = "active-source-tag", toupper(tools::file_ext(row$file_name))),
      htmltools::span(class = "active-source-tag", row$size),
      htmltools::span(class = "active-source-tag", paste0(summary$frame_count, " frames")),
      htmltools::span(class = "active-source-tag", summary$dimensions)
    )
  )
}

discover_z_stacks <- function(project_dir) {
  project_dir <- normalize_project_path(project_dir)
  if (!dir.exists(project_dir)) return(data.frame())
  paths <- list.files(
    project_dir,
    pattern = "\\.(oir|oib|tif|tiff)$",
    recursive = TRUE,
    full.names = TRUE,
    ignore.case = TRUE,
    include.dirs = FALSE
  )
  paths <- sort(unique(normalizePath(paths, mustWork = FALSE)))
  if (length(paths) == 0) return(data.frame())
  info <- file.info(paths)
  data.frame(
    stack_id = as.character(seq_along(paths)),
    file_name = basename(paths),
    group = vapply(paths, function(path) infer_group_from_path(project_dir, path), character(1)),
    extension = toupper(tools::file_ext(paths)),
    size = vapply(info$size, format_bytes, character(1)),
    size_bytes = info$size,
    modified = format(info$mtime, "%Y-%m-%d %H:%M"),
    relative_path = vapply(paths, function(path) relative_to_project(project_dir, path), character(1)),
    path = paths,
    stringsAsFactors = FALSE,
    row.names = NULL
  )
}

bridge_python <- function(project_dir) {
  candidates <- c(
    file.path(project_dir, ".venv", "bin", "python"),
    file.path(project_dir, "venv", "bin", "python"),
    Sys.which("python3")
  )
  candidates <- candidates[nzchar(candidates) & file.exists(candidates)]
  if (length(candidates) == 0) stop("No Python interpreter was found for the tracking bridge.")
  candidates[[1]]
}

run_bridge <- function(project_dir, arguments) {
  project_dir <- normalize_project_path(project_dir)
  script <- file.path(project_dir, "scripts", "shiny_bridge.py")
  if (!file.exists(script)) stop("Missing scripts/shiny_bridge.py in the selected project.")
  command <- bridge_python(project_dir)
  args <- c(shQuote(script), vapply(as.character(arguments), shQuote, character(1)))
  output <- system2(command, args, stdout = TRUE, stderr = TRUE)
  status <- attr(output, "status") %||% 0L
  json_lines <- output[grepl("^\\{.*\\}$", output)]
  payload <- if (length(json_lines) > 0) {
    jsonlite::fromJSON(tail(json_lines, 1), simplifyVector = FALSE)
  } else {
    list(ok = FALSE, error = paste(output, collapse = "\n"))
  }
  if (!identical(as.integer(status), 0L) || !isTRUE(payload$ok)) {
    stop(payload$error %||% paste(output, collapse = "\n"))
  }
  list(payload = payload, log = output)
}

probe_source <- function(project_dir, source_path) {
  run_bridge(project_dir, c("probe", source_path))$payload
}

extract_source_frame <- function(
  project_dir,
  source_path,
  output_path,
  frame_index,
  rotation,
  flip_horizontal
) {
  args <- c(
    "frame", source_path, output_path,
    "--frame-index", as.integer(frame_index),
    "--rotation", as.integer(rotation)
  )
  if (isTRUE(flip_horizontal)) args <- c(args, "--flip-horizontal")
  run_bridge(project_dir, args)$payload
}

run_analysis_bridge <- function(project_dir, config) {
  args <- c(
    "run", config$source_path, config$output_dir,
    "--export-name", config$export_name,
    "--analysis-method", config$analysis_method,
    "--rotation", config$rotation,
    "--roi-x", config$roi_x,
    "--roi-y", config$roi_y,
    "--roi-width", config$roi_width,
    "--roi-height", config$roi_height,
    "--microns-per-pixel", config$microns_per_pixel,
    "--seconds-per-frame", config$seconds_per_frame
  )
  if (identical(config$analysis_method, "optical_flow")) {
    args <- c(
      args,
      "--mask-percentile", config$mask_percentile,
      "--flow-blur-kernel", config$flow_blur_kernel,
      "--flow-winsize", config$flow_winsize,
      "--flow-arrow-spacing", config$flow_arrow_spacing,
      "--flow-arrow-scale", config$flow_arrow_scale
    )
  } else {
    args <- c(
      args,
      "--num-points", config$num_points,
      "--min-spacing", config$min_spacing,
      "--search-radius", config$search_radius,
      "--patch-size", config$patch_size,
      "--min-confidence", config$min_confidence,
      "--lookahead-frames", config$lookahead_frames,
      "--preview-fps", config$preview_fps,
      "--tracking-method", config$tracking_method
    )
  }
  if (isTRUE(config$flip_horizontal)) args <- c(args, "--flip-horizontal")
  run_bridge(project_dir, args)
}

run_tracking_bridge <- function(project_dir, config) {
  config$analysis_method <- config$analysis_method %||% "landmark_tracking"
  run_analysis_bridge(project_dir, config)
}

is_landmark_result <- function(row) {
  identical(as.character(row$analysis_method), "landmark_tracking")
}

is_flow_result_row <- function(row) {
  identical(as.character(row$analysis_method), "optical_flow")
}

read_analysis_json <- function(path, project_dir) {
  data <- tryCatch(
    jsonlite::fromJSON(path, simplifyVector = FALSE),
    error = function(...) NULL
  )
  if (is.null(data)) return(NULL)
  outputs <- data$outputs %||% list()
  context <- data$run_context %||% list()
  source_path <- context$source_path %||% data$source_path %||% ""
  analysis_method <- as.character(
    data$analysis_method %||% context$analysis_method %||% "landmark_tracking"
  )
  is_flow <- identical(analysis_method, "optical_flow")

  step_weighted_speed_um_s <- if (is_flow) {
    safe_scalar_numeric(data$optical_flow_general_movement_um_s)
  } else {
    safe_scalar_numeric(data$absolute_velocity_index_um_per_s %||% data$general_movement_index_um_per_s)
  }
  primary_speed_um_s <- if (is_flow) {
    safe_scalar_numeric(data$optical_flow_general_movement_um_s)
  } else {
    time_weighted <- safe_scalar_numeric(data$time_weighted_mean_speed_um_per_s)
    if (is.na(time_weighted)) step_weighted_speed_um_s else time_weighted
  }
  absolute_velocity <- primary_speed_um_s
  downward_velocity <- if (is_flow) {
    safe_scalar_numeric(data$optical_flow_downward_motion_um_s)
  } else {
    safe_scalar_numeric(data$downward_velocity_index_um_per_s)
  }

  track_preview_mp4 <- if (is_flow) "" else resolve_result_path(
    project_dir,
    outputs$track_preview_mp4 %||% data$track_preview_video
  )
  inferred_webm <- if (nzchar(track_preview_mp4)) {
    sub("\\.mp4$", ".webm", track_preview_mp4, ignore.case = TRUE)
  } else ""

  data.frame(
    result_id = normalizePath(path, mustWork = FALSE),
    sample_id = as.character(data$sample_id %||% tools::file_path_sans_ext(basename(path))),
    source_name = basename(source_path),
    source_path = source_path,
    group = infer_group_from_path(project_dir, source_path),
    analyzed_at = as.character(data$analysis_timestamp_utc %||% context$created_at_utc %||% ""),
    analysis_method = analysis_method,
    primary_speed_um_s = primary_speed_um_s,
    step_weighted_speed_um_s = step_weighted_speed_um_s,
    absolute_velocity = absolute_velocity,
    downward_velocity = downward_velocity,
    net_y_velocity = if (is_flow) safe_scalar_numeric(data$optical_flow_net_y_velocity_um_s %||% data$optical_flow_net_y_velocity_um_per_s) else NA_real_,
    directionality_ratio = if (is_flow) safe_scalar_numeric(data$optical_flow_directionality_ratio) else NA_real_,
    valid_pixel_fraction = if (is_flow) safe_scalar_numeric(data$optical_flow_valid_pixel_fraction) else NA_real_,
    tracks_started = if (is_flow) NA_real_ else safe_scalar_numeric(data$num_tracks_started),
    valid_tracks = if (is_flow) NA_real_ else safe_scalar_numeric(data$num_tracks_with_valid_steps),
    valid_steps = if (is_flow) safe_scalar_numeric(data$frame_pair_count) else safe_scalar_numeric(data$total_valid_steps),
    frame_count = safe_scalar_numeric(data$frame_count),
    trajectory_csv = if (is_flow) "" else resolve_result_path(project_dir, outputs$trajectory_csv %||% data$trajectory_csv),
    flow_pair_csv = if (is_flow) resolve_result_path(project_dir, outputs$flow_pair_csv %||% "") else "",
    summary_json = normalizePath(path, mustWork = FALSE),
    starting_points = if (is_flow) "" else resolve_result_path(project_dir, outputs$starting_points_png %||% data$start_points_preview),
    track_overlay = if (is_flow) "" else resolve_result_path(project_dir, outputs$track_overlay_png %||% data$tracks_overlay_preview),
    flow_overlay = if (is_flow) resolve_result_path(project_dir, outputs$flow_overlay_png %||% "") else "",
    track_preview = track_preview_mp4,
    track_preview_webm = if (is_flow) "" else resolve_result_path(
      project_dir,
      outputs$track_preview_webm %||% data$track_preview_webm %||% inferred_webm
    ),
    track_preview_mp4_codec = if (is_flow) "" else as.character(outputs$track_preview_mp4_codec %||% ""),
    track_preview_webm_codec = if (is_flow) "" else as.character(outputs$track_preview_webm_codec %||% ""),
    output_dir = as.character(data$output_dir %||% dirname(path)),
    tracking_method = if (is_flow) {
      "optical_flow"
    } else {
      as.character((data$parameters %||% list())$tracking_method %||% "unknown")
    },
    seconds_per_frame = safe_scalar_numeric((data$settings %||% data$parameters %||% list())$seconds_per_frame),
    microns_per_pixel = safe_scalar_numeric((data$settings %||% data$parameters %||% list())$microns_per_pixel),
    stringsAsFactors = FALSE
  )
}

read_tracking_json <- function(path, project_dir) {
  read_analysis_json(path, project_dir)
}

discover_tracking_results <- function(project_dir) {
  project_dir <- normalize_project_path(project_dir)
  processed <- file.path(project_dir, "processed")
  if (!dir.exists(processed)) return(data.frame())
  paths <- c(
    list.files(
      processed,
      pattern = "_motion_index\\.json$",
      recursive = TRUE,
      full.names = TRUE,
      ignore.case = TRUE
    ),
    list.files(
      processed,
      pattern = "_optical_flow\\.json$",
      recursive = TRUE,
      full.names = TRUE,
      ignore.case = TRUE
    )
  )
  paths <- unique(normalizePath(paths, mustWork = FALSE))
  if (length(paths) == 0) return(data.frame())
  rows <- lapply(paths, read_analysis_json, project_dir = project_dir)
  rows <- rows[!vapply(rows, is.null, logical(1))]
  if (length(rows) == 0) return(data.frame())
  result <- do.call(rbind, rows)
  result <- result[order(result$analyzed_at, decreasing = TRUE), , drop = FALSE]
  rownames(result) <- NULL
  result
}

result_choices <- function(results) {
  if (is.null(results) || nrow(results) == 0) return(character())
  label <- paste(results$group, results$source_name, results$analyzed_at, sep = "  /  ")
  stats::setNames(results$result_id, label)
}

angle_result_choices <- function(results) {
  if (is.null(results) || nrow(results) == 0) return(character())
  source <- ifelse(nzchar(results$source_name), results$source_name, "Unnamed source")
  method <- ifelse(
    results$analysis_method == "optical_flow",
    "Optical flow",
    ifelse(
      results$tracking_method == "brightest_local",
      "Brightest points",
      ifelse(results$tracking_method == "template", "Template", results$tracking_method)
    )
  )
  analyzed <- gsub("T", " ", substr(results$analyzed_at, 1, 19), fixed = TRUE)
  labels <- paste(source, results$group, method, analyzed, sep = "  •  ")
  stats::setNames(results$result_id, labels)
}

selected_row <- function(df, id, key) {
  if (is.null(df) || nrow(df) == 0 || is.null(id) || !nzchar(id)) return(NULL)
  rows <- df[df[[key]] == id, , drop = FALSE]
  if (nrow(rows) == 0) NULL else rows[1, , drop = FALSE]
}

read_trajectory <- function(path) {
  if (is.null(path) || !nzchar(path) || !file.exists(path)) return(data.frame())
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

read_flow_pairs <- function(path) {
  if (is.null(path) || !nzchar(path) || !file.exists(path)) return(data.frame())
  read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
}

px_frame_to_um_s <- function(px_frame, microns_per_pixel, seconds_per_frame) {
  px_frame * safe_scalar_numeric(microns_per_pixel) / safe_scalar_numeric(seconds_per_frame)
}

analysis_method_label <- function(method) {
  if (identical(method, "optical_flow")) {
    "Optical flow"
  } else if (identical(method, "landmark_tracking")) {
    "Landmark tracking"
  } else {
    as.character(method %||% "Unknown")
  }
}

tracking_method_label <- function(row) {
  if (is.null(row)) return("Unknown")
  if (identical(row$analysis_method, "optical_flow")) {
    return("Optical flow")
  }
  if (identical(row$tracking_method, "brightest_local")) {
    "Brightest nearby points"
  } else if (identical(row$tracking_method, "template")) {
    "Template matching"
  } else {
    as.character(row$tracking_method %||% "Unknown")
  }
}

wrap_angle_change <- function(angle_deg) {
  ((angle_deg + 180) %% 360) - 180
}

csv_angle_value <- function(value) {
  if (is.null(value) || length(value) == 0 || identical(value, "")) return(NA_real_)
  numeric_value <- safe_scalar_numeric(value)
  if (length(numeric_value) == 0 || is.na(numeric_value)) NA_real_ else numeric_value
}

derive_angle_dynamics <- function(trajectory, seconds_per_frame = 1) {
  if (is.null(trajectory) || nrow(trajectory) == 0) return(data.frame())
  required <- c("track_id", "frame_index", "x_px", "y_px")
  if (!all(required %in% names(trajectory))) return(data.frame())

  data <- trajectory
  data$track_id <- as.character(data$track_id)
  data$frame_index <- safe_numeric(data$frame_index)
  data$x_px <- safe_numeric(data$x_px)
  data$y_px <- safe_numeric(data$y_px)
  spf <- safe_scalar_numeric(seconds_per_frame %||% 1)

  if ("motion_angle_deg" %in% names(data)) {
    data$motion_angle_deg <- vapply(data$motion_angle_deg, csv_angle_value, numeric(1))
  } else {
    data$motion_angle_deg <- NA_real_
  }
  if ("turning_angle_deg" %in% names(data)) {
    data$turning_angle_deg <- vapply(data$turning_angle_deg, csv_angle_value, numeric(1))
  } else {
    data$turning_angle_deg <- NA_real_
  }

  groups <- split(seq_len(nrow(data)), data$track_id)
  for (indices in groups) {
    indices <- indices[order(data$frame_index[indices])]
    if ("dt_s" %in% names(data)) {
      dt_values <- vapply(data$dt_s[indices], csv_angle_value, numeric(1))
      dt_values[is.na(dt_values)] <- 0
      data$elapsed_time_s[indices] <- cumsum(dt_values)
    } else {
      data$elapsed_time_s[indices] <- data$frame_index[indices] * spf
    }
  }
  if (!"elapsed_time_s" %in% names(data)) {
    data$elapsed_time_s <- data$frame_index * spf
  }

  for (indices in groups) {
    indices <- indices[order(data$frame_index[indices])]
    need_motion <- is.na(data$motion_angle_deg[indices])
    need_turning <- is.na(data$turning_angle_deg[indices])
    if (!any(need_motion) && !any(need_turning)) next

    x <- data$x_px[indices]
    y <- data$y_px[indices]
    dx <- c(NA_real_, diff(x))
    dy <- c(NA_real_, diff(y))
    angle <- atan2(dy, dx) * 180 / pi
    angle[is.na(dx) | is.na(dy) | sqrt(dx ^ 2 + dy ^ 2) <= .Machine$double.eps] <- NA_real_

    turning <- rep(NA_real_, length(angle))
    valid <- which(!is.na(angle))
    if (length(valid) >= 2) {
      turning[valid[-1]] <- wrap_angle_change(diff(angle[valid]))
    }
    if (any(need_motion)) {
      motion_values <- data$motion_angle_deg[indices]
      motion_values[need_motion] <- angle[need_motion]
      data$motion_angle_deg[indices] <- motion_values
    }
    if (any(need_turning)) {
      turning_values <- data$turning_angle_deg[indices]
      turning_values[need_turning] <- turning[need_turning]
      data$turning_angle_deg[indices] <- turning_values
    }
  }

  data[order(data$track_id, data$frame_index), , drop = FALSE]
}

summarize_angle_dynamics <- function(angle_data) {
  empty <- list(
    circular_mean_deg = NA_real_, directional_stability = NA_real_,
    mean_absolute_turn_deg = NA_real_, reversal_count = 0L,
    pattern = "No motion", detail = "No valid consecutive motion steps."
  )
  if (is.null(angle_data) || nrow(angle_data) == 0) return(empty)
  angles <- safe_numeric(angle_data$motion_angle_deg)
  angles <- angles[!is.na(angles)]
  if (length(angles) == 0) return(empty)

  radians <- angles * pi / 180
  mean_sin <- mean(sin(radians))
  mean_cos <- mean(cos(radians))
  circular_mean <- atan2(mean_sin, mean_cos) * 180 / pi
  stability <- sqrt(mean_sin ^ 2 + mean_cos ^ 2)
  turns <- safe_numeric(angle_data$turning_angle_deg)
  turns <- turns[!is.na(turns)]
  mean_absolute_turn <- if (length(turns) > 0) mean(abs(turns)) else NA_real_
  reversals <- sum(abs(turns) >= 135, na.rm = TRUE)
  significant <- turns[abs(turns) >= 10]
  sign_changes <- if (length(significant) >= 2) {
    sum(sign(significant[-1]) != sign(significant[-length(significant)]))
  } else 0L
  oscillation_ratio <- if (length(significant) >= 2) sign_changes / (length(significant) - 1) else 0
  net_turn <- if (length(turns) > 0) sum(turns) else 0
  total_turn <- if (length(turns) > 0) sum(abs(turns)) else 0

  if (reversals > 0) {
    pattern <- "Reversing"
    detail <- "At least one step changes direction by 135° or more."
  } else if (stability >= 0.90 && (is.na(mean_absolute_turn) || mean_absolute_turn <= 15)) {
    pattern <- "Stable"
    detail <- "Step directions remain tightly concentrated."
  } else if (length(significant) >= 3 && oscillation_ratio >= 0.50 && abs(net_turn) < 0.50 * total_turn) {
    pattern <- "Oscillating"
    detail <- "Turning repeatedly alternates between clockwise and counterclockwise."
  } else if (abs(net_turn) >= 45) {
    pattern <- "Drifting"
    detail <- "Direction accumulates at least 45° of net turning."
  } else {
    pattern <- "Variable"
    detail <- "Direction varies without a dominant stable, drifting, oscillating, or reversing pattern."
  }

  list(
    circular_mean_deg = circular_mean,
    directional_stability = stability,
    mean_absolute_turn_deg = mean_absolute_turn,
    reversal_count = as.integer(reversals),
    pattern = pattern,
    detail = detail
  )
}

summarize_groups_by_method <- function(results) {
  if (is.null(results) || nrow(results) == 0) return(data.frame())
  keys <- interaction(results$group, results$analysis_method, drop = TRUE, lex.order = TRUE)
  groups <- split(results, keys)
  rows <- lapply(groups, function(group_df) {
    is_landmark <- group_df$analysis_method == "landmark_tracking"
    data.frame(
      group = group_df$group[[1]],
      analysis_method = group_df$analysis_method[[1]],
      runs = nrow(group_df),
      mean_primary_speed = safe_mean(group_df$primary_speed_um_s),
      mean_downward_velocity = safe_mean(group_df$downward_velocity),
      mean_net_y_velocity = safe_mean(group_df$net_y_velocity),
      total_valid_tracks = sum(group_df$valid_tracks[is_landmark], na.rm = TRUE),
      total_valid_steps = sum(group_df$valid_steps, na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  })
  result <- do.call(rbind, rows)
  rownames(result) <- NULL
  result[order(result$group, result$analysis_method), , drop = FALSE]
}

summarize_groups <- function(results) {
  if (is.null(results) || nrow(results) == 0) return(data.frame())
  groups <- split(results, results$group)
  rows <- lapply(names(groups), function(group_name) {
    group_df <- groups[[group_name]]
    data.frame(
      group = group_name,
      samples = nrow(group_df),
      mean_absolute_velocity = safe_mean(group_df$primary_speed_um_s),
      mean_downward_velocity = safe_mean(group_df$downward_velocity),
      mean_net_y_velocity = safe_mean(group_df$net_y_velocity),
      landmark_runs = sum(group_df$analysis_method == "landmark_tracking", na.rm = TRUE),
      flow_runs = sum(group_df$analysis_method == "optical_flow", na.rm = TRUE),
      total_valid_tracks = sum(group_df$valid_tracks, na.rm = TRUE),
      total_valid_steps = sum(group_df$valid_steps, na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

safe_output_file <- function(path) {
  is.character(path) && length(path) == 1 && nzchar(path) && file.exists(path)
}
