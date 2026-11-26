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
    """Run reproducible successful and unsuccessful chaining lookups."""
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise TypeError("capacity must be an integer")
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    if not target_loads:
        raise ValueError("target_loads must not be empty")

    key_counts = []
    for target_load in target_loads:
        if isinstance(target_load, bool) or not isinstance(target_load, (int, float)):
            raise TypeError("load factors must be numbers")
        if not 0 < target_load < 1:
            raise ValueError("target load factors must be between 0 and 1")
        key_counts.append(max(1, round(target_load * capacity)))

    max_key_count = max(key_counts)
    stored_key_samples = _make_key_samples(
        "stored-", max_key_count, KEY_SEED, capacity
    )
    missing_key_samples = _make_key_samples(
        "missing-", max_key_count, MISSING_KEY_SEED, capacity
    )

    results = []
    for key_count in key_counts:
        table = HashTable(initial_capacity=capacity, max_load=None)
        stored_keys = stored_key_samples[:key_count]
        missing_keys = missing_key_samples[:key_count]

        for index, key in enumerate(stored_keys):
            table.put(key, index)

        successful_comparisons = 0
        for key in stored_keys:
            value, comparisons = table.get_with_comparisons(key)
            if value is None:
                raise RuntimeError(f"inserted key was not found: {key}")
            successful_comparisons += comparisons

        unsuccessful_comparisons = 0
        for key in missing_keys:
            value, comparisons = table.get_with_comparisons(key)
            if value is not None:
                raise RuntimeError(f"missing key unexpectedly found: {key}")
            unsuccessful_comparisons += comparisons

        actual_load = key_count / capacity
        successful_theory = 1 + (key_count - 1) / (2 * capacity)
        unsuccessful_theory = actual_load
        results.extend(
            (
                ExperimentResult(
                    collision_resolution="separate_chaining",
                    capacity=capacity,
                    key_count=key_count,
                    load_factor=actual_load,
                    search_type="successful",
                    search_count=len(stored_keys),
                    measurement_unit="key_comparisons",
                    measured_average=successful_comparisons / len(stored_keys),
                    theoretical_average=successful_theory,
                ),
                ExperimentResult(
                    collision_resolution="separate_chaining",
                    capacity=capacity,
                    key_count=key_count,
                    load_factor=actual_load,
                    search_type="unsuccessful",
                    search_count=len(missing_keys),
                    measurement_unit="key_comparisons",
                    measured_average=unsuccessful_comparisons / len(missing_keys),
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
        writer = csv.writer(csv_file)
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
    """Write a standard-library SVG chart for measured and theoretical costs."""
    if not results:
        raise ValueError("results must not be empty")

    width = 900
    height = 560
    left = 90
    right = 40
    top = 45
    bottom = 90
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_value = max(
        result.measured_average for result in results
    )
    max_value = max(
        max_value,
        max(result.theoretical_average for result in results),
        1.0,
    ) * 1.15

    def x_position(load_factor: float) -> float:
        return left + load_factor * plot_width

    def y_position(value: float) -> float:
        return top + plot_height - (value / max_value) * plot_height

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<title>Separate chaining lookup comparison experiment</title>",
        (
            "<desc>Measured and theoretical successful and unsuccessful search "
            "costs, expressed as average key comparisons.</desc>"
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            f'<text x="{width / 2:g}" y="25" text-anchor="middle" '
            'font-family="sans-serif" font-size="16">'
            "Separate chaining lookup costs</text>"
        ),
    ]

    tick_count = 5
    for tick in range(tick_count + 1):
        load_factor = tick / tick_count
        x = x_position(load_factor)
        elements.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" '
            f'y2="{top + plot_height}" stroke="#e0e0e0"/>'
        )
        elements.append(
            f'<text x="{x:.2f}" y="{top + plot_height + 22}" '
            'text-anchor="middle" font-family="sans-serif" font-size="12">'
            f"{load_factor:.1f}</text>"
        )

    for tick in range(tick_count + 1):
        value = max_value * tick / tick_count
        y = y_position(value)
        elements.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" '
            f'y2="{y:.2f}" stroke="#e0e0e0"/>'
        )
        elements.append(
            f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" '
            'font-family="sans-serif" font-size="12">'
            f"{value:.1f}</text>"
        )

    elements.extend(
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" '
            f'y2="{top + plot_height}" stroke="#333"/>',
            f'<line x1="{left}" y1="{top + plot_height}" '
            f'x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333"/>',
            (
                f'<text x="{left + plot_width / 2:g}" y="{height - 20}" '
                'text-anchor="middle" font-family="sans-serif" font-size="14">'
                "Load factor (alpha)</text>"
            ),
            (
                f'<text x="22" y="{top + plot_height / 2:g}" '
                f'transform="rotate(-90 22 {top + plot_height / 2:g})" '
                'text-anchor="middle" font-family="sans-serif" font-size="14">'
                "Average key comparisons</text>"
            ),
        )
    )

    series = (
        ("successful", "measured", "#1769aa", ""),
        ("successful", "theoretical", "#1769aa", "7 5"),
        ("unsuccessful", "measured", "#d1495b", ""),
        ("unsuccessful", "theoretical", "#d1495b", "7 5"),
    )
    for search_type, metric, color, dash_pattern in series:
        points = []
        for result in results:
            if result.search_type != search_type:
                continue
            value = (
                result.measured_average
                if metric == "measured"
                else result.theoretical_average
            )
            points.append(
                f"{x_position(result.load_factor):.2f},{y_position(value):.2f}"
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

    legend_x = left + 10
    legend_y = top + 18
    legend_items = (
        ("Successful Measured", "#1769aa", ""),
        ("Successful Theoretical", "#1769aa", "7 5"),
        ("Unsuccessful Measured", "#d1495b", ""),
        ("Unsuccessful Theoretical", "#d1495b", "7 5"),
    )
    for index, (label, color, dash_pattern) in enumerate(legend_items):
        column = index % 2
        row = index // 2
        x1 = legend_x + column * 250
        y = legend_y + row * 22
        dash_attribute = (
            f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        )
        elements.append(
            f'<line x1="{x1}" y1="{y}" x2="{x1 + 28}" y2="{y}" '
            f'stroke="{color}" stroke-width="2.5"{dash_attribute}/>'
        )
        elements.append(
            f'<text x="{x1 + 36}" y="{y + 4}" font-family="sans-serif" '
            f'font-size="12">{escape(label)}</text>'
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
