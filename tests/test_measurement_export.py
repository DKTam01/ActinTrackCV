"""Persisted measurement clipboard/CSV serialization. No metric recomputation."""

from __future__ import annotations

import csv
import tempfile
import unittest
from io import StringIO
from pathlib import Path

import numpy as np

from actintrack_app.measurement_export import (
    PROVENANCE_HEADERS,
    csv_table,
    ensure_csv_extension,
    measurement_table,
    measurements_to_csv,
    measurements_to_tsv,
    serialize_measurement_value,
    suggested_measurements_csv_name,
    write_measurements_csv,
)
from actintrack_app.measurement_series import (
    MeasurementColumn,
    MetricMeasurementSeries,
    aggregate_orientation_median_deg,
)
from actintrack_app.media_capabilities import MetricId


def _orientation_series(
    rows: list[dict],
    *,
    summary: float | None = 20.0,
    sample_label: str = "Sample 1",
    condition_group: str = "WT",
    analysis_run_id: str = "run-o",
) -> MetricMeasurementSeries:
    return MetricMeasurementSeries(
        metric_id=MetricId.ORIENTATION,
        sample_id="S1",
        sample_label=sample_label,
        condition_group=condition_group,
        analysis_run_id=analysis_run_id,
        summary_value=summary,
        summary_unit="°",
        row_kind="orientation_sample",
        columns=[
            MeasurementColumn("n", "Measurement #", sort_kind="int"),
            MeasurementColumn("angle_deg", "Angle (°)", sort_kind="float"),
            MeasurementColumn("x_px", "x (px)", sort_kind="float"),
            MeasurementColumn("y_px", "y (px)", sort_kind="float"),
            MeasurementColumn("coherence", "Coherence", sort_kind="float"),
        ],
        rows=rows,
    )


def _movement_series() -> MetricMeasurementSeries:
    return MetricMeasurementSeries(
        metric_id=MetricId.GENERAL_MOVEMENT,
        sample_id="S9",
        sample_label="Video sample",
        condition_group="Mutant",
        analysis_run_id="run-gm",
        summary_value=1.5,
        summary_unit="µm/s",
        row_kind="step",
        columns=[
            MeasurementColumn("n", "Measurement #", sort_kind="int"),
            MeasurementColumn("um_per_s", "Velocity (µm/s)", sort_kind="float"),
            MeasurementColumn("sign", "Sign", sort_kind="text"),
        ],
        rows=[
            {"n": 1, "um_per_s": 1.0, "sign": "toward"},
            {"n": 2, "um_per_s": 2.0, "sign": "away"},
        ],
    )


class SerializeValueTests(unittest.TestCase):
    def test_integers_strings_and_missing_values(self) -> None:
        self.assertEqual(serialize_measurement_value(10), "10")
        self.assertEqual(serialize_measurement_value(np.int64(7)), "7")
        self.assertEqual(serialize_measurement_value("away"), "away")
        self.assertEqual(serialize_measurement_value(None), "")
        self.assertEqual(serialize_measurement_value(float("nan")), "nan")
        self.assertEqual(serialize_measurement_value(float("inf")), "inf")
        self.assertEqual(serialize_measurement_value(float("-inf")), "-inf")
        self.assertNotIn(",", serialize_measurement_value(1.25))

    def test_float_repr_round_trips_beyond_display_formatting(self) -> None:
        value = 12.345678901234567
        text = serialize_measurement_value(value)
        self.assertNotEqual(text, f"{value:.6g}")
        self.assertEqual(float(text), value)
        self.assertEqual(float(serialize_measurement_value(np.float64(value))), value)


class OrientationExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.angle = 12.345678901234567
        self.series = _orientation_series(
            [
                {
                    "n": 2,
                    "angle_deg": 30.0,
                    "x_px": 1,
                    "y_px": 2.5,
                    "coherence": None,
                    "local_orientation_deg": 180.0,
                },
                {
                    "n": 1,
                    "angle_deg": self.angle,
                    "x_px": 4.0,
                    "y_px": None,
                    "coherence": float("nan"),
                    "local_orientation_deg": 90.0,
                },
                {
                    "n": 3,
                    "angle_deg": 10.0,
                    "x_px": 8,
                    "y_px": 9,
                    "coherence": 0.5,
                },
            ],
            summary=999.0,
            sample_label="Plant, A",
        )

    def test_tsv_is_persisted_order_with_full_precision(self) -> None:
        text = measurements_to_tsv(self.series)
        lines = text.split("\n")
        self.assertEqual(
            lines[0],
            "Measurement #\tAngle (°)\tx (px)\ty (px)\tCoherence",
        )
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[1].startswith("2\t30.0\t"))
        self.assertIn(serialize_measurement_value(self.angle), lines[2])
        self.assertTrue(lines[3].startswith("3\t"))
        self.assertNotIn("local_orientation", text)
        self.assertNotIn("180", lines[1])
        self.assertNotIn("Sample", lines[0])
        parsed = [float(line.split("\t")[1]) for line in lines[1:]]
        self.assertEqual(parsed, [30.0, self.angle, 10.0])
        self.assertNotEqual(parsed, sorted(parsed))

    def test_export_does_not_recompute_or_follow_a_sorted_copy(self) -> None:
        headers, rows = measurement_table(self.series)
        self.assertEqual(headers[1], "Angle (°)")
        angles = [float(row[1]) for row in rows]
        self.assertEqual(angles, [30.0, self.angle, 10.0])
        self.assertNotEqual(aggregate_orientation_median_deg(angles), self.series.summary_value)
        self.assertNotIn("999", measurements_to_tsv(self.series))

    def test_csv_provenance_precision_and_degree_symbol(self) -> None:
        text = measurements_to_csv(self.series)
        self.assertIn("°", text)
        reader = csv.reader(StringIO(text))
        header = next(reader)
        body = list(reader)
        self.assertEqual(header[:4], list(PROVENANCE_HEADERS))
        self.assertEqual(header[4:], ["Measurement #", "Angle (°)", "x (px)", "y (px)", "Coherence"])
        self.assertEqual(len(body), 3)
        self.assertEqual([row[4] for row in body], ["2", "1", "3"])
        self.assertTrue(all(row[0] == "Plant, A" for row in body))
        self.assertTrue(all(row[1] == "WT" for row in body))
        self.assertTrue(all(row[2] == "F-actin Orientation" for row in body))
        self.assertTrue(all(row[3] == "run-o" for row in body))
        self.assertEqual(body[0][8], "")
        self.assertEqual(body[1][8], "nan")
        angles = [float(row[5]) for row in body]
        self.assertEqual(angles[1], self.angle)
        reproduced = aggregate_orientation_median_deg([10.0, 30.0, self.angle])
        self.assertEqual(reproduced, float(np.median([10.0, 30.0, self.angle])))
        self.assertNotIn("local_orientation", text)

    def test_exported_angles_reproduce_the_persisted_median(self) -> None:
        angles = [10.0, 90.0, 20.0]
        series = _orientation_series(
            [
                {"n": 1, "angle_deg": angles[0], "x_px": 1, "y_px": 1, "coherence": 0.4},
                {"n": 2, "angle_deg": angles[1], "x_px": 2, "y_px": 2, "coherence": 0.5},
                {"n": 3, "angle_deg": angles[2], "x_px": 3, "y_px": 3, "coherence": 0.6},
            ],
            summary=float(np.median(angles)),
        )
        _headers, rows = csv_table(series)
        exported = [float(row[5]) for row in rows]
        self.assertEqual(exported, angles)
        self.assertEqual(aggregate_orientation_median_deg(exported), series.summary_value)

    def test_csv_file_is_utf8_and_matches_serializer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "angles.csv"
            write_measurements_csv(self.series, path)
            raw = path.read_bytes()
            self.assertTrue(raw.startswith("Sample,".encode("utf-8")))
            text = raw.decode("utf-8")
            self.assertEqual(text, measurements_to_csv(self.series))
            self.assertIn("°".encode("utf-8"), raw)


class GenericMetricExportTests(unittest.TestCase):
    def test_general_movement_uses_same_path(self) -> None:
        series = _movement_series()
        headers, rows = csv_table(series)
        self.assertEqual(
            headers[4:],
            ("Measurement #", "Velocity (µm/s)", "Sign"),
        )
        self.assertEqual(rows[0][2], "General Movement")
        self.assertEqual(rows[0][6], "toward")
        self.assertEqual(measurements_to_tsv(series).split("\n")[1], "1\t1.0\ttoward")
        self.assertEqual(
            suggested_measurements_csv_name(series),
            "Video_sample_General_Movement_measurements.csv",
        )

    def test_filename_is_safe_and_csv_suffix_is_added_once(self) -> None:
        series = _orientation_series([], sample_label="A/B sample")
        name = suggested_measurements_csv_name(series)
        self.assertEqual(name, "A_B_sample_F-actin_Orientation_measurements.csv")
        self.assertNotIn("/", name)
        self.assertEqual(ensure_csv_extension("results"), "results.csv")
        self.assertEqual(ensure_csv_extension("results.CSV"), "results.CSV")
        self.assertEqual(ensure_csv_extension(""), "")


if __name__ == "__main__":
    unittest.main()
