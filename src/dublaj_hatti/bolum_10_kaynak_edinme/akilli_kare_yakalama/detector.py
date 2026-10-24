from __future__ import annotations

import cv2
import numpy as np

VERTICAL_ACTIVITY_OUTSIDE_RATIO_MAX = 0.05
VERTICAL_PRESENCE_OUTSIDE_RATIO_MAX = 0.72


def normalize_profile(values):
    values = np.asarray(values, dtype=np.float32)
    minimum = float(values.min())
    maximum = float(values.max())
    if maximum - minimum < 1e-6:
        return np.zeros_like(values)
    return (values - minimum) / (maximum - minimum)


def build_profiles(samples):
    grayscale_frames = [cv2.cvtColor(sample["frame"], cv2.COLOR_BGR2GRAY) for sample in samples]
    if len(grayscale_frames) > 1:
        motion_values = np.mean(
            [
                np.mean(cv2.absdiff(previous, current), axis=1)
                for previous, current in zip(grayscale_frames, grayscale_frames[1:], strict=False)
            ],
            axis=0,
        )
    else:
        motion_values = np.zeros(grayscale_frames[0].shape[0], dtype=np.float32)
    edge_values = np.mean(
        [np.mean(cv2.Canny(frame, 60, 150), axis=1) / 255.0 for frame in grayscale_frames],
        axis=0,
    )
    motion_profile = normalize_profile(motion_values)
    edge_profile = normalize_profile(edge_values)
    activity_profile = 0.65 * motion_profile + 0.35 * edge_profile
    return motion_profile, edge_profile, activity_profile


def build_presence_profiles(samples):
    row_profiles = []
    column_profiles = []
    for sample in samples:
        frame = sample["frame"]
        grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        saturation = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1]
        presence = 0.7 * (grayscale > 12).astype(np.float32) + 0.3 * (saturation > 15).astype(np.float32)
        row_profiles.append(np.mean(presence, axis=1))
        column_profiles.append(np.mean(presence, axis=0))
    row_profile = np.percentile(np.stack(row_profiles), 90, axis=0)
    column_profile = np.median(np.stack(column_profiles), axis=0)
    row_profile = np.convolve(row_profile, np.ones(15, dtype=np.float32) / 15.0, mode="same")
    column_profile = np.convolve(column_profile, np.ones(15, dtype=np.float32) / 15.0, mode="same")
    return row_profile, column_profile


def build_luminance_profile(samples):
    row_profiles = []
    for sample in samples:
        grayscale = cv2.cvtColor(sample["frame"], cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        row_profiles.append(np.mean(grayscale, axis=1))
    row_profile = np.mean(np.stack(row_profiles), axis=0)
    return np.convolve(row_profile, np.ones(15, dtype=np.float32) / 15.0, mode="same")


def find_runs(profile, threshold, minimum_length):
    mask = np.asarray(profile) >= threshold
    runs = []
    start = None
    for index, active in enumerate(np.r_[mask, False]):
        if active and start is None:
            start = index
        if not active and start is not None:
            end = index
            if end - start >= minimum_length:
                runs.append((start, end - 1, end - start))
            start = None
    return runs


def select_profile_run(profile, thresholds, minimum_length, fallback_length):
    for threshold in thresholds:
        runs = find_runs(profile, threshold, minimum_length)
        if runs:
            return max(runs, key=lambda run: run[2]), threshold
    return (0, len(profile) - 1, fallback_length), None


def select_presence_run(profile, thresholds, minimum_length, fallback_length):
    initial_run = None
    initial_threshold = None
    for threshold in thresholds:
        runs = find_runs(profile, threshold, minimum_length)
        if not runs:
            continue
        current_run = max(runs, key=lambda run: run[2])
        if initial_run is None:
            initial_run = current_run
            initial_threshold = threshold
            continue
        initial_mean = float(np.mean(profile[initial_run[0] : initial_run[1] + 1]))
        current_mean = float(np.mean(profile[current_run[0] : current_run[1] + 1]))
        if current_run[2] >= round(initial_run[2] * 1.15) and current_mean >= initial_mean * 0.75:
            return current_run, threshold
    if initial_run is not None:
        return initial_run, initial_threshold
    return (0, len(profile) - 1, fallback_length), None


def select_luminance_run(profile, minimum_length):
    baseline = float(np.percentile(profile, 20))
    peak = float(np.percentile(profile, 90))
    spread = max(peak - baseline, 0.0)
    thresholds = (
        baseline + max(0.01, spread * 0.2),
        baseline + max(0.006, spread * 0.1),
        baseline + max(0.003, spread * 0.04),
    )
    return select_profile_run(profile, thresholds, minimum_length, len(profile))


def select_activity_run(profile, minimum_length):
    smoothed_profile = np.convolve(profile, np.ones(15, dtype=np.float32) / 15.0, mode="same")
    baseline = float(np.percentile(smoothed_profile, 20))
    peak = float(np.percentile(smoothed_profile, 90))
    spread = max(peak - baseline, 0.0)
    thresholds = (
        baseline + max(0.01, spread * 0.2),
        baseline + max(0.006, spread * 0.1),
        baseline + max(0.003, spread * 0.04),
    )
    return select_profile_run(smoothed_profile, thresholds, minimum_length, len(smoothed_profile))


def has_stable_symmetric_sidebars(column_profile, column_run, frame_width):
    left, right, detected_width = column_run
    left_margin = left
    right_margin = frame_width - 1 - right
    minimum_margin = max(8, round(frame_width * 0.04))
    margin_difference_tolerance = max(6, round(frame_width * 0.03))
    if detected_width < round(frame_width * 0.5):
        return False
    if left_margin < minimum_margin or right_margin < minimum_margin:
        return False
    if abs(left_margin - right_margin) > margin_difference_tolerance:
        return False
    profile_values = np.asarray(column_profile)
    inside_presence = float(np.mean(profile_values[left : right + 1]))
    outside_presence = float(np.mean(np.concatenate((profile_values[:left], profile_values[right + 1 :]))))
    return outside_presence <= inside_presence * 0.2


def detect_content_box(
    row_profile,
    column_profile,
    frame_width,
    frame_height,
    luminance_profile=None,
    activity_profile=None,
):
    row_run, row_threshold = select_presence_run(
        row_profile,
        (0.55, 0.45, 0.35, 0.25),
        round(frame_width * 0.3),
        frame_height,
    )
    row_detection_source = "temporal_presence"
    row_was_expanded = row_threshold not in (None, 0.55)
    if row_threshold is None and luminance_profile is not None:
        row_run, row_threshold = select_luminance_run(luminance_profile, round(frame_width * 0.3))
        row_detection_source = "temporal_luminance"
        row_was_expanded = False
    column_run, column_threshold = select_profile_run(
        column_profile,
        (0.25, 0.18, 0.12, 0.08),
        round(frame_height * 0.2),
        frame_width,
    )
    top, bottom, _ = row_run
    left, right, _ = column_run
    initial_column_threshold = column_threshold
    stable_symmetric_sidebars = column_threshold is not None and has_stable_symmetric_sidebars(
        column_profile,
        column_run,
        frame_width,
    )
    detected_width = right - left + 1
    if bottom - top + 1 > round(frame_width * 0.5) and (
        row_was_expanded or detected_width < round(frame_width * 0.85)
    ):
        lower_runs = find_runs(row_profile, 0.25, round(frame_width * 0.3))
        if lower_runs:
            lower_run = max(lower_runs, key=lambda run: run[2])
            if lower_run[0] <= top and lower_run[1] >= bottom:
                top = lower_run[0]
                bottom = lower_run[1]
        left = 0
        right = frame_width - 1
        row_detection_source = "temporal_presence_horizontal_full_width"
        column_threshold = "full_width"
    if (
        row_detection_source == "temporal_luminance"
        and right - left + 1 < round(frame_width * 0.85)
        and bottom - top + 1 < round(frame_width * 0.5)
    ):
        target_height = min(frame_height, round(frame_width / (16 / 9)))
        center = (top + bottom) / 2.0
        top = round(center - target_height / 2.0)
        top = max(0, min(top, frame_height - target_height))
        bottom = top + target_height - 1
        left = 0
        right = frame_width - 1
        row_detection_source = "temporal_luminance_horizontal_16_9"
        row_threshold = "16:9"
        column_threshold = "full_width"
    if activity_profile is not None:
        activity_run, activity_threshold = select_activity_run(activity_profile, round(frame_width * 0.3))
        activity_top, activity_bottom, activity_length = activity_run
        activity_inside = float(np.mean(np.asarray(activity_profile)[activity_top : activity_bottom + 1]))
        activity_outside_parts = []
        if activity_top > 0:
            activity_outside_parts.append(np.asarray(activity_profile)[:activity_top])
        if activity_bottom + 1 < frame_height:
            activity_outside_parts.append(np.asarray(activity_profile)[activity_bottom + 1 :])
        activity_outside = (
            float(np.mean(np.concatenate(activity_outside_parts))) if activity_outside_parts else 0.0
        )
        presence_values = np.asarray(row_profile)
        presence_inside = float(np.mean(presence_values[activity_top : activity_bottom + 1]))
        presence_outside_parts = []
        if activity_top > 0:
            presence_outside_parts.append(presence_values[:activity_top])
        if activity_bottom + 1 < frame_height:
            presence_outside_parts.append(presence_values[activity_bottom + 1 :])
        presence_outside = (
            float(np.mean(np.concatenate(presence_outside_parts))) if presence_outside_parts else 0.0
        )
        selected_height = bottom - top + 1
        activity_is_horizontal = frame_width / max(1, activity_length) >= 1.15
        activity_is_localized = activity_threshold is not None and activity_outside <= activity_inside * 0.12
        activity_is_vertical_or_square_inner_band = (
            activity_threshold is not None
            and activity_inside >= 0.3
            and activity_outside <= activity_inside * VERTICAL_ACTIVITY_OUTSIDE_RATIO_MAX
            and presence_outside <= presence_inside * VERTICAL_PRESENCE_OUTSIDE_RATIO_MAX
        )
        activity_can_replace_full_frame = (
            selected_height >= round(frame_height * 0.75)
            and activity_length <= round(frame_height * 0.72)
        )
        activity_can_refine_presence_band = (
            row_detection_source in (
                "temporal_presence",
                "temporal_presence_horizontal_full_width",
            )
            and selected_height >= round(frame_height * 0.45)
            and activity_length <= round(selected_height * 0.9)
        )
        if (activity_can_replace_full_frame or activity_can_refine_presence_band) and (
            activity_is_horizontal and activity_is_localized
            or activity_is_vertical_or_square_inner_band
        ):
            top = activity_top
            bottom = activity_bottom
            left = 0
            right = frame_width - 1
            row_threshold = activity_threshold
            column_threshold = "full_width"
            row_detection_source = (
                "temporal_activity_horizontal_full_width"
                if activity_is_horizontal
                else "temporal_activity_localized_full_width"
            )
    if stable_symmetric_sidebars:
        left, right, _ = column_run
        column_threshold = initial_column_threshold
        if row_detection_source.endswith("_full_width"):
            row_detection_source = row_detection_source[: -len("_full_width")] + "_symmetric_sidebars"
    edge_tolerance = max(4, round(frame_width * 0.02))
    if left <= edge_tolerance and right >= frame_width - 1 - edge_tolerance:
        left = 0
        right = frame_width - 1
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": int(right - left + 1),
        "height": int(bottom - top + 1),
        "aspect_ratio": round((right - left + 1) / (bottom - top + 1), 6),
        "row_threshold": row_threshold,
        "column_threshold": column_threshold,
        "row_detection_source": row_detection_source,
    }


def analysis_has_credible_crop(analysis):
    support = analysis["support"]
    area_fraction = float(analysis["box_area_fraction"])
    return (
        area_fraction < 0.95
        and (
            area_fraction >= 0.15
            or (
                area_fraction >= 0.08
                and (
                    float(support["sample_support_fraction"]) >= 0.5
                    or float(support["inside_outside_contrast"]) >= 0.12
                )
            )
        )
    )


def analysis_has_strong_alternative_crop(analysis):
    source = str(analysis["selected_box"]["row_detection_source"])
    support = analysis["support"]
    return analysis_has_credible_crop(analysis) and (
        (
            "activity" in source
            and float(support["sample_support_fraction"]) >= 0.75
        )
        or float(support["inside_outside_contrast"]) >= 0.2
    )


def build_full_frame_box(analysis_width, analysis_height):
    return {
        "left": 0,
        "top": 0,
        "right": analysis_width - 1,
        "bottom": analysis_height - 1,
        "width": analysis_width,
        "height": analysis_height,
        "aspect_ratio": round(analysis_width / analysis_height, 6),
        "row_threshold": None,
        "column_threshold": "full_width",
        "row_detection_source": "temporal_consensus_conservative_full_frame",
    }


def lock_box_to_full_width(selected_box, analysis_width):
    locked_box = dict(selected_box)
    locked_box["left"] = 0
    locked_box["right"] = analysis_width - 1
    locked_box["width"] = analysis_width
    locked_box["aspect_ratio"] = round(analysis_width / int(locked_box["height"]), 6)
    locked_box["column_threshold"] = "source_width_locked"
    return locked_box


def choose_temporal_consensus_box(primary_analysis, validation_analysis):
    if analysis_has_credible_crop(primary_analysis):
        return primary_analysis["selected_box"], "primary_credible"
    if analysis_has_strong_alternative_crop(validation_analysis):
        return validation_analysis["selected_box"], "validation_credible"
    return build_full_frame_box(
        primary_analysis["analysis_width"],
        primary_analysis["analysis_height"],
    ), "conservative_full_frame"


def calculate_source_crop(selected_box, analysis_width, analysis_height, source_width, source_height):
    scale_x = source_width / analysis_width
    scale_y = source_height / analysis_height
    crop_left = int(round(selected_box["left"] * scale_x))
    crop_top = int(round(selected_box["top"] * scale_y))
    crop_end_x = int(round((selected_box["right"] + 1) * scale_x))
    crop_end_y = int(round((selected_box["bottom"] + 1) * scale_y))
    crop_left = max(0, min(source_width - 2, crop_left - crop_left % 2))
    crop_top = max(0, min(source_height - 2, crop_top - crop_top % 2))
    crop_end_x = max(crop_left + 2, min(source_width, crop_end_x + crop_end_x % 2))
    crop_end_y = max(crop_top + 2, min(source_height, crop_end_y + crop_end_y % 2))
    crop_width = crop_end_x - crop_left
    crop_height = crop_end_y - crop_top
    crop_width -= crop_width % 2
    crop_height -= crop_height % 2
    return {
        "source_crop_left": crop_left,
        "source_crop_top": crop_top,
        "source_crop_width": crop_width,
        "source_crop_height": crop_height,
        "filter": f"crop={crop_width}:{crop_height}:{crop_left}:{crop_top}",
    }
