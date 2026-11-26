"""Measure separate-chaining lookup costs and write CSV and SVG results."""

import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.hash_table import HashTable
from src.linear_probing import LinearProbingHashTable


DEFAULT_CAPACITY = 128
DEFAULT_LOADS = (0.1, 0.25, 0.5, 0.75, 0.9)
KEY_SEED = 2026
MISSING_KEY_SEED = 2027
KEY_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
RESULTS_CSV = Path(__file__).with_name("results.csv")
RESULTS_SVG = Path(__file__).with_name("results.svg")

CSV_COLUMNS = (
    "collision_resolution",
    "capacity",
    "key_count",
    "load_factor",
    "search_type",
    "search_count",
    "measurement_unit",
    "measured_average",
    "theoretical_average",
)


@dataclass(frozen=True)
class ExperimentResult:
    """Aggregated result for one load factor and lookup type."""

    collision_resolution: str
    capacity: int
    key_count: int
    load_factor: float
    search_type: str
    search_count: int
    measurement_unit: str
    measured_average: float
    theoretical_average: float


def collect_results(
    capacity: int = DEFAULT_CAPACITY,
    target_loads: Sequence[float] = DEFAULT_LOADS,
) -> list[ExperimentResult]:
    """Compare reproducible successful and unsuccessful lookups in both tables."""
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise TypeError("capacity must be an integer")
    if capacity < 2:
        raise ValueError("capacity must be at least 2 for linear probing")
    if not target_loads:
        raise ValueError("target_loads must not be empty")

    key_counts = []
    for target_load in target_loads:
        if isinstance(target_load, bool) or not isinstance(target_load, (int, float)):
            raise TypeError("load factors must be numbers")
        if not 0 < target_load < 1:
            raise ValueError("target load factors must be between 0 and 1")
        key_counts.append(min(max(1, round(target_load * capacity)), capacity - 1))

    max_key_count = max(key_counts)
    stored_key_samples = _make_key_samples(
        "stored-", max_key_count, KEY_SEED, capacity
    )
    missing_key_samples = _make_key_samples(
        "missing-", max_key_count, MISSING_KEY_SEED, capacity
    )

    results = []
    for key_count in key_counts:
        stored_keys = stored_key_samples[:key_count]
        missing_keys = missing_key_samples[:key_count]
        actual_load = key_count / capacity
        for resolution in ("separate_chaining", "linear_probing"):
            if resolution == "separate_chaining":
                table: HashTable | LinearProbingHashTable = HashTable(
                    initial_capacity=capacity,
                    max_load=None,
                )
                measurement_unit = "key_comparisons"
            else:
                table = LinearProbingHashTable(
                    initial_capacity=capacity,
                    max_load=None,
                )
                measurement_unit = "slot_probes"

            for index, key in enumerate(stored_keys):
                table.put(key, index)

            successful_total = 0
            for key in stored_keys:
                if isinstance(table, HashTable):
                    value, cost = table.get_with_comparisons(key)
                else:
                    value, cost = table.get_with_probes(key)
                if value is None:
                    raise RuntimeError(f"inserted key was not found: {key}")
                successful_total += cost

            unsuccessful_total = 0
            for key in missing_keys:
                if isinstance(table, HashTable):
                    value, cost = table.get_with_comparisons(key)
                else:
                    value, cost = table.get_with_probes(key)
                if value is not None:
                    raise RuntimeError(f"missing key unexpectedly found: {key}")
                unsuccessful_total += cost

            if resolution == "separate_chaining":
                successful_theory = 1 + (key_count - 1) / (2 * capacity)
                unsuccessful_theory = actual_load
            else:
                successful_theory = 0.5 * (1 + 1 / (1 - actual_load))
                unsuccessful_theory = 0.5 * (
                    1 + 1 / (1 - actual_load) ** 2
                )

            results.extend(
                (
                    ExperimentResult(
                        collision_resolution=resolution,
                        capacity=capacity,
                        key_count=key_count,
                        load_factor=actual_load,
                        search_type="successful",
                        search_count=len(stored_keys),
                        measurement_unit=measurement_unit,
                        measured_average=successful_total / len(stored_keys),
                        theoretical_average=successful_theory,
                    ),
                    ExperimentResult(
                        collision_resolution=resolution,
                        capacity=capacity,
                        key_count=key_count,
                        load_factor=actual_load,
                        search_type="unsuccessful",
                        search_count=len(missing_keys),
                        measurement_unit=measurement_unit,
                        measured_average=unsuccessful_total / len(missing_keys),
                        theoretical_average=unsuccessful_theory,
                    ),
                )
            )

    return results


def _make_key_samples(
    prefix: str,
    count: int,
    seed: int,
    capacity: int,
) -> list[str]:
    """Create unique, deterministic keys with varied character sequences."""
    generator = random.Random(seed)
    seen_keys = HashTable(initial_capacity=capacity, max_load=None)
    keys = []
    while len(keys) < count:
        suffix = "".join(generator.choices(KEY_ALPHABET, k=12))
        key = prefix + suffix
        if seen_keys.get(key) is None:
            seen_keys.put(key, True)
            keys.append(key)
    return keys


def write_csv(results: Sequence[ExperimentResult], path: str | Path) -> None:
    """Write observed and theoretical averages as CSV rows."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for result in results:
            writer.writerow(
                (
                    result.collision_resolution,
                    result.capacity,
                    result.key_count,
                    f"{result.load_factor:.6f}",
                    result.search_type,
                    result.search_count,
                    result.measurement_unit,
                    f"{result.measured_average:.6f}",
                    f"{result.theoretical_average:.6f}",
                )
            )


def write_svg(results: Sequence[ExperimentResult], path: str | Path) -> None:
    """Write separate, unit-labeled charts for both probing strategies."""
    if not results:
        raise ValueError("results must not be empty")

    width = 1100
    height = 660
    outer_left = 70
    outer_right = 35
    panel_gap = 85
    panel_width = (width - outer_left - outer_right - panel_gap) / 2
    top = 100
    plot_height = 425
    plot_bottom = top + plot_height
    tick_count = 5
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<title>Separate chaining and linear probing lookup experiment</title>",
        (
            "<desc>Measured and theoretical lookup costs by load factor. "
            "Separate chaining counts key comparisons; linear probing counts "
            "inspected slots. The panels use independent vertical scales.</desc>"
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            f'<text x="{width / 2:g}" y="27" text-anchor="middle" '
            'font-family="sans-serif" font-size="16">'
            "Hash-table collision resolution comparison</text>"
        ),
    ]

    method_settings = (
        ("separate_chaining", "Separate chaining", "Average key comparisons"),
        ("linear_probing", "Linear probing", "Average slot probes"),
    )
    series = (
        ("successful", "measured", "#1769aa", ""),
        ("successful", "theoretical", "#1769aa", "7 5"),
        ("unsuccessful", "measured", "#d1495b", ""),
        ("unsuccessful", "theoretical", "#d1495b", "7 5"),
    )
    legend_items = (
        ("Successful Measured", "#1769aa", ""),
        ("Successful Theoretical", "#1769aa", "7 5"),
        ("Unsuccessful Measured", "#d1495b", ""),
        ("Unsuccessful Theoretical", "#d1495b", "7 5"),
    )

    for panel_index, (method, title, unit_label) in enumerate(method_settings):
        panel_left = outer_left + panel_index * (panel_width + panel_gap)
        plot_left = panel_left + 52
        plot_right = panel_left + panel_width
        plot_width = plot_right - plot_left
        method_results = [
            result for result in results
            if result.collision_resolution == method
        ]
        if not method_results:
            continue
        max_value = max(
            max(result.measured_average, result.theoretical_average)
            for result in method_results
        )
        max_value = max(max_value, 1.0) * 1.15

        def x_position(load_factor: float) -> float:
            return plot_left + load_factor * plot_width

        def y_position(value: float) -> float:
            return plot_bottom - (value / max_value) * plot_height

        elements.append(
            f'<text x="{(plot_left + plot_right) / 2:g}" y="58" '
            'text-anchor="middle" font-family="sans-serif" font-size="15">'
            f"{escape(title)} - {escape(unit_label)}</text>"
        )

        for tick in range(tick_count + 1):
            load_factor = tick / tick_count
            x = x_position(load_factor)
            elements.extend(
                (
                    f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" '
                    f'y2="{plot_bottom}" stroke="#e0e0e0"/>',
                    f'<text x="{x:.2f}" y="{plot_bottom + 20}" '
                    'text-anchor="middle" font-family="sans-serif" font-size="11">'
                    f"{load_factor:.1f}</text>",
                )
            )

        for tick in range(tick_count + 1):
            value = max_value * tick / tick_count
            y = y_position(value)
            elements.extend(
                (
                    f'<line x1="{plot_left}" y1="{y:.2f}" '
                    f'x2="{plot_right}" y2="{y:.2f}" stroke="#e0e0e0"/>',
                    f'<text x="{plot_left - 8}" y="{y + 4:.2f}" '
                    'text-anchor="end" font-family="sans-serif" font-size="11">'
                    f"{value:.1f}</text>",
                )
            )

        elements.extend(
            (
                f'<line x1="{plot_left}" y1="{top}" x2="{plot_left}" '
                f'y2="{plot_bottom}" stroke="#333"/>',
                f'<line x1="{plot_left}" y1="{plot_bottom}" '
                f'x2="{plot_right}" y2="{plot_bottom}" stroke="#333"/>',
                (
                    f'<text x="{(plot_left + plot_right) / 2:g}" '
                    f'y="{plot_bottom + 42}" text-anchor="middle" '
                    'font-family="sans-serif" font-size="13">'
                    "Load factor (alpha)</text>"
                ),
                (
                    f'<text x="{panel_left + 15}" y="{top + plot_height / 2:g}" '
                    f'transform="rotate(-90 {panel_left + 15} '
                    f'{top + plot_height / 2:g})" text-anchor="middle" '
                    'font-family="sans-serif" font-size="12">'
                    f"{escape(unit_label)}</text>"
                ),
            )
        )

        for search_type, metric, color, dash_pattern in series:
            points = []
            for result in method_results:
                if result.search_type != search_type:
                    continue
                value = (
                    result.measured_average
                    if metric == "measured"
                    else result.theoretical_average
                )
                points.append(
                    f"{x_position(result.load_factor):.2f},"
                    f"{y_position(value):.2f}"
                )
            dash_attribute = (
                f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
            )
            elements.append(
                f'<polyline points="{" ".join(points)}" fill="none" '
                f'stroke="{color}" stroke-width="2.5"{dash_attribute}/>'
            )
            for point in points:
                x, y = point.split(",")
                elements.append(
                    f'<circle cx="{x}" cy="{y}" r="3.5" fill="{color}"/>'
                )

        for index, (label, color, dash_pattern) in enumerate(legend_items):
            column = index % 2
            row = index // 2
            x1 = plot_left + 8 + column * (plot_width / 2)
            y = 610 + row * 20
            dash_attribute = (
                f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
            )
            elements.append(
                f'<line x1="{x1:.2f}" y1="{y}" x2="{x1 + 22:.2f}" y2="{y}" '
                f'stroke="{color}" stroke-width="2.5"{dash_attribute}/>'
            )
            elements.append(
                f'<text x="{x1 + 28:.2f}" y="{y + 4}" '
                'font-family="sans-serif" font-size="10">'
                f"{escape(label)}</text>"
            )

    elements.append("</svg>")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(elements), encoding="utf-8")


def main() -> None:
    """Run the default experiment and write its CSV and SVG outputs."""
    results = collect_results()
    write_csv(results, RESULTS_CSV)
    write_svg(results, RESULTS_SVG)
    print(f"Capacity: {DEFAULT_CAPACITY}")
    print(f"Target load factors: {', '.join(f'{load:.2f}' for load in DEFAULT_LOADS)}")
    print(f"Results CSV: {RESULTS_CSV}")
    print(f"Results SVG: {RESULTS_SVG}")


if __name__ == "__main__":
    main()
