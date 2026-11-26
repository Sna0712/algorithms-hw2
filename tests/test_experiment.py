import csv
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from experiments.probe_experiment import (
    CHAINING_CAPACITY,
    CHAINING_LOADS,
    CHAINING_RESULTS_CSV,
    CHAINING_RESULTS_SVG,
    DEFAULT_CAPACITY,
    DEFAULT_LOADS,
    collect_chaining_results,
    collect_results,
    write_csv,
    write_svg,
)


class SeparateChainingExperimentTests(unittest.TestCase):
    def test_default_experiment_settings_cover_multiple_load_factors(self):
        self.assertEqual(DEFAULT_CAPACITY, 4093)
        self.assertEqual(DEFAULT_LOADS, (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9))
        self.assertEqual(tuple(sorted(DEFAULT_LOADS)), DEFAULT_LOADS)
        self.assertTrue(all(0 < load < 1 for load in DEFAULT_LOADS))
        self.assertEqual(CHAINING_CAPACITY, 4093)
        self.assertEqual(CHAINING_LOADS[0], 0.25)
        self.assertEqual(CHAINING_LOADS[-1], 4.0)
        self.assertTrue(all(0.25 <= load <= 4 for load in CHAINING_LOADS))
        self.assertNotEqual(CHAINING_RESULTS_CSV, Path("experiments/results.csv"))
        self.assertNotEqual(CHAINING_RESULTS_SVG, Path("experiments/results.svg"))

    def test_chaining_only_experiment_supports_loads_above_one(self):
        results = collect_chaining_results(
            capacity=8,
            target_loads=(0.25, 4.0),
        )

        self.assertEqual(len(results), 4)
        self.assertTrue(
            all(result.collision_resolution == "separate_chaining" for result in results)
        )
        self.assertEqual(
            {(result.key_count, result.load_factor) for result in results},
            {(2, 0.25), (32, 4.0)},
        )
        self.assertTrue(
            all(result.measurement_unit == "key_comparisons" for result in results)
        )
        for result in results:
            if result.search_type == "successful":
                expected = 1 + (result.key_count - 1) / (2 * result.capacity)
            else:
                expected = result.load_factor
            self.assertAlmostEqual(result.theoretical_average, expected)

    def test_chaining_only_experiment_outputs_separate_csv_and_svg(self):
        results = collect_chaining_results(capacity=8, target_loads=(0.5, 4.0))
        with tempfile.TemporaryDirectory() as temporary_directory:
            csv_path = Path(temporary_directory) / "chaining.csv"
            svg_path = Path(temporary_directory) / "chaining.svg"

            write_csv(results, csv_path)
            write_svg(results, svg_path)

            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                rows = list(csv.DictReader(csv_file))
            svg_text = svg_path.read_text(encoding="utf-8")

        self.assertEqual(len(rows), 4)
        self.assertTrue(
            all(row["collision_resolution"] == "separate_chaining" for row in rows)
        )
        self.assertIn("Average key comparisons", svg_text)
        self.assertIn(">4.00</text>", svg_text)

    def test_collect_results_reports_success_and_failure_measurements(self):
        results = collect_results(capacity=20, target_loads=(0.2, 0.5))

        self.assertEqual(len(results), 8)
        self.assertEqual(
            {
                (
                    result.collision_resolution,
                    result.load_factor,
                    result.search_type,
                )
                for result in results
            },
            {
                (method, load, search_type)
                for method in ("separate_chaining", "linear_probing")
                for load in (0.2, 0.5)
                for search_type in ("successful", "unsuccessful")
            },
        )
        for result in results:
            with self.subTest(result=result):
                self.assertEqual(result.capacity, 20)
                expected_unit = (
                    "key_comparisons"
                    if result.collision_resolution == "separate_chaining"
                    else "slot_probes"
                )
                self.assertEqual(result.measurement_unit, expected_unit)
                self.assertGreater(result.search_count, 0)
                self.assertGreaterEqual(result.measured_average, 0)
                self.assertLess(result.load_factor, 1)

    def test_both_methods_use_matching_search_counts_and_probing_theory(self):
        results = collect_results(capacity=20, target_loads=(0.5,))

        for search_type in ("successful", "unsuccessful"):
            chaining = next(
                result
                for result in results
                if result.collision_resolution == "separate_chaining"
                and result.search_type == search_type
            )
            probing = next(
                result
                for result in results
                if result.collision_resolution == "linear_probing"
                and result.search_type == search_type
            )
            self.assertEqual(chaining.key_count, probing.key_count)
            self.assertEqual(chaining.search_count, probing.search_count)
            alpha = probing.load_factor
            if search_type == "successful":
                expected = 0.5 * (1 + 1 / (1 - alpha))
            else:
                expected = 0.5 * (1 + 1 / (1 - alpha) ** 2)
            self.assertAlmostEqual(probing.theoretical_average, expected)

    def test_load_factor_and_theoretical_averages_use_actual_entry_count(self):
        results = collect_results(capacity=20, target_loads=(0.2, 0.5))

        for result in results:
            with self.subTest(result=result):
                self.assertAlmostEqual(
                    result.load_factor,
                    result.key_count / result.capacity,
                )
                if result.collision_resolution == "linear_probing":
                    if result.search_type == "successful":
                        expected = 0.5 * (
                            1 + 1 / (1 - result.load_factor)
                        )
                    else:
                        expected = 0.5 * (
                            1 + 1 / (1 - result.load_factor) ** 2
                        )
                elif result.search_type == "successful":
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

    def test_generated_samples_are_reproducible_url_strings(self):
        from experiments.probe_experiment import (
            KEY_SEED,
            MISSING_KEY_SEED,
            _make_key_samples,
        )

        stored_first = _make_key_samples("stored-", 10, KEY_SEED, 64)
        stored_again = _make_key_samples("stored-", 10, KEY_SEED, 64)
        missing = _make_key_samples("missing-", 10, MISSING_KEY_SEED, 64)

        self.assertEqual(stored_first, stored_again)
        self.assertTrue(all(url.startswith("https://") for url in stored_first + missing))
        self.assertTrue(all(url not in stored_first for url in missing))

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

        self.assertEqual(len(rows), 4)
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
        self.assertEqual(
            {row["collision_resolution"] for row in rows},
            {"separate_chaining", "linear_probing"},
        )
        self.assertEqual(
            {
                row["measurement_unit"]
                for row in rows
                if row["collision_resolution"] == "linear_probing"
            },
            {"slot_probes"},
        )

    def test_svg_is_valid_and_labels_both_units_and_all_series(self):
        results = collect_results(capacity=20, target_loads=(0.25, 0.5))
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "results.svg"

            write_svg(results, output_path)

            svg_root = ET.parse(output_path).getroot()
            svg_text = output_path.read_text(encoding="utf-8")
        self.assertEqual(svg_root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("Load factor", svg_text)
        self.assertIn("Average key comparisons", svg_text)
        self.assertIn("Average slot probes", svg_text)
        self.assertIn("Successful", svg_text)
        self.assertIn("Unsuccessful", svg_text)
        self.assertIn("Measured", svg_text)
        self.assertIn("Theoretical", svg_text)
        self.assertGreaterEqual(
            len(svg_root.findall(".//{http://www.w3.org/2000/svg}polyline")),
            8,
        )


if __name__ == "__main__":
    unittest.main()
