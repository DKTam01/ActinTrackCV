"""Sample registry per breed (v2 module name; implementation in batch_manager)."""

from __future__ import annotations

from actintrack_app.batch_manager import (  # noqa: F401
    BATCHES_JSON,
    LEGACY_BATCH_NAME,
    allocate_next_batch as allocate_next_sample,
    all_workspace_condition_groups as all_workspace_breeds,
    batch_has_samples as sample_has_data_files,
    batch_has_video as sample_has_video_data,
    clear_batches_registry_for_groups as clear_sample_registry_for_breeds,
    create_batch as create_sample,
    create_batch_for_video_import as create_sample_for_data_import,
    delete_empty_batch as delete_empty_sample,
    display_batch_name as display_default_sample_name,
    display_sample_label,
    ensure_batch_dirs as ensure_sample_dirs,
    ensure_default_batch as ensure_default_sample,
    get_batch_by_name as get_sample_by_name,
    get_batch_by_number as get_sample_by_number,
    list_batches as list_samples,
    list_empty_batches as list_empty_samples,
    next_frame_number_in_batch as next_frame_number_in_sample,
    parse_batch_number_from_name as parse_sample_number_from_name,
    prune_all_groups_without_samples,
    prune_registry_batches_without_samples as prune_registry_samples_without_data,
    refresh_batch_stats as refresh_sample_stats,
    register_batch_from_samples as register_sample_from_data_files,
    remove_batch_folders as remove_sample_folders,
    remove_batch_from_registry as remove_sample_from_registry,
    rename_batch as rename_sample,
    repair_batch_registry as repair_sample_registry,
    reset_batches_registry_workspace as reset_sample_registry_workspace,
    sanitize_batch_name as sanitize_sample_name,
    sync_registry_from_samples as sync_registry_from_data_files,
)

# Registry file constant (v2 on-disk name).
SAMPLE_REGISTRY_JSON = "sample_registry.json"
