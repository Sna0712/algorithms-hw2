import csv
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from experiments.probe_experiment import (
    DEFAULT_CAPACITY,
    DEFAULT_LOADS,
    collect_results,
    write_csv,
    write_svg,
)


class SeparateChainingExperimentTests(unittest.TestCase):
    def test_default_experiment_settings_cover_multiple_load_factors(self):
        self.assertEqual(DEFAULT_CAPACITY, 128)
        self.assertGreaterEqual(len(DEFAULT_LOADS), 4)
        self.assertEqual(tuple(sorted(DEFAULT_LOADS)), DEFAULT_LOADS)
        self.assertTrue(all(0 < load < 1 for load in DEFAULT_LOADS))

    def test_collect_results_reports_success_and_failure_measurements(self):
        results = collect_results(capacity=20, target_loads=(0.2, 0.5))

        self.assertEqual(len(results), 4)
        self.assertEqual(
            {(result.load_factor, result.search_type) for result in results},
            {
                (0.2, "successful"),
                (0.2, "unsuccessful"),
                (0.5, "successful"),
                (0.5, "unsuccessful"),
            },
        )
        for result in results:
            with self.subTest(result=result):
                self.assertEqual(result.collision_resolution, "separate_chaining")
                self.assertEqual(result.capacity, 20)
                self.assertEqual(result.measurement_unit, "key_comparisons")
                self.assertGreater(result.search_count, 0)
                self.assertGreaterEqual(result.measured_average, 0)

    def test_load_factor_and_theoretical_averages_use_actual_entry_count(self):
        results = collect_results(capacity=20, target_loads=(0.2, 0.5))

        for result in results:
            with self.subTest(result=result):
                self.assertAlmostEqual(
                    result.load_factor,
                    result.key_count / result.capacity,
                )
                if result.search_type == "successful":
                    expected = 1 + (result.key_count - 1) / (
                        2 * result.capacity
                    )
                else:
                    expected = result.load_factor
                self.assertAlmostEqual(result.theoretical_average, expected)

    def test_results_are_reproducible_for_identical_input(self):
        first_run = collect_results(capacity=32, target_loads=(0.25, 0.75))
        second_run = collect_results(capacity=32, target_loads=(0.25, 0.75))

        self.assertEqual(first_run, second_run)

    def test_default_unsuccessful_searches_do_not_use_a_correlated_key_pattern(self):
        high_load_failure = next(
            result
            for result in collect_results()
            if result.search_type == "unsuccessful" and result.load_factor > 0.85
        )

        self.assertLess(
            abs(
                high_load_failure.measured_average
                - high_load_failure.theoretical_average
            ),
            0.25,
        )

    def test_csv_contains_measurements_and_theoretical_values(self):
        results = collect_results(capacity=20, target_loads=(0.25,))
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "results.csv"

            write_csv(results, output_path)

            with output_path.open(newline="", encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            set(rows[0]),
            {
                "collision_resolution",
                "capacity",
                "key_count",
                "load_factor",
                "search_type",
                "search_count",
                "measurement_unit",
                "measured_average",
                "theoretical_average",
            },
        )
        self.assertEqual(
            {row["search_type"] for row in rows},
            {"successful", "unsuccessful"},
        )

    def test_svg_is_valid_and_labels_axes_and_four_series(self):
        results = collect_results(capacity=20, target_loads=(0.25, 0.5))
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "results.svg"

            write_svg(results, output_path)

            svg_root = ET.parse(output_path).getroot()
            svg_text = output_path.read_text(encoding="utf-8")
        self.assertEqual(svg_root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("Load factor", svg_text)
        self.assertIn("Average key comparisons", svg_text)
        self.assertIn("Successful", svg_text)
        self.assertIn("Unsuccessful", svg_text)
        self.assertIn("Measured", svg_text)
        self.assertIn("Theoretical", svg_text)
        self.assertGreaterEqual(
            len(svg_root.findall(".//{http://www.w3.org/2000/svg}polyline")),
            4,
        )


if __name__ == "__main__":
    unittest.main()
