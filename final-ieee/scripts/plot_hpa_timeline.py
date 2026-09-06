#!/usr/bin/env python3
"""Generate simple PNG figures from parsed HPA CSV files without matplotlib."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "final-ieee" / "data"
FIGURE_DIR = ROOT / "final-ieee" / "figures"

WIDTH = 1200
HEIGHT = 720
MARGIN_LEFT = 90
MARGIN_RIGHT = 40
MARGIN_TOP = 60
MARGIN_BOTTOM = 90
COLORS = {
    "minikube_hpa_timeline_20260825_023826": "#1f77b4",
    "minikube_hpa_timeline_20260906_124119_aggressive": "#9467bd",
    "minikube_hpa_timeline_20260906_125821_fast_scaledown": "#ff7f0e",
    "minikube_hpa_timeline_20260906_154758_baseline_rerun": "#1f77b4",
    "eks_hpa_timeline_20260826_005559": "#d62728",
    "eks_hpa_timeline_20260826_010657": "#2ca02c",
}


def load_runs() -> dict[str, list[dict[str, str]]]:
    runs: dict[str, list[dict[str, str]]] = {}
    for path in sorted(DATA_DIR.glob("*_hpa_timeline_*.csv")):
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            runs[path.stem] = rows
    return runs


def number(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return 0.0 if value == "" else float(value)


def label_for(run_id: str) -> str:
    if "baseline_rerun" in run_id:
        return "Minikube baseline rerun"
    if "aggressive" in run_id:
        return "Minikube aggressive"
    if "fast_scaledown" in run_id:
        return "Minikube fast scale-down"
    if run_id.startswith("minikube"):
        return "Minikube baseline"
    if run_id.endswith("005559"):
        return "EKS run 005559"
    if run_id.endswith("010657"):
        return "EKS run 010657"
    return run_id


def draw_chart(
    runs: dict[str, list[dict[str, str]]],
    metric: str,
    title: str,
    ylabel: str,
    output: Path,
    y_max: float | None = None,
) -> None:
    font = ImageFont.load_default()
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)

    plot_left = MARGIN_LEFT
    plot_top = MARGIN_TOP
    plot_right = WIDTH - MARGIN_RIGHT
    plot_bottom = HEIGHT - MARGIN_BOTTOM
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    max_x = max(number(row, "elapsed_s") for rows in runs.values() for row in rows)
    if y_max is None:
        y_max = max(number(row, metric) for rows in runs.values() for row in rows)
    y_max = max(y_max, 1.0)

    def x_coord(elapsed_s: float) -> int:
        return int(plot_left + (elapsed_s / max_x) * plot_width)

    def y_coord(value: float) -> int:
        return int(plot_bottom - (value / y_max) * plot_height)

    # Axes and grid.
    draw.rectangle([plot_left, plot_top, plot_right, plot_bottom], outline="#222222", width=2)
    for tick in range(0, 7):
        y = plot_top + int((plot_height / 6) * tick)
        value = y_max - (y_max / 6) * tick
        draw.line([plot_left, y, plot_right, y], fill="#e6e6e6")
        draw.text((15, y - 7), f"{value:.0f}", fill="#222222", font=font)
    for tick in range(0, 7):
        x = plot_left + int((plot_width / 6) * tick)
        value = (max_x / 60 / 6) * tick
        draw.line([x, plot_top, x, plot_bottom], fill="#eeeeee")
        draw.text((x - 12, plot_bottom + 18), f"{value:.1f}", fill="#222222", font=font)

    draw.text((MARGIN_LEFT, 25), title, fill="#111111", font=font)
    draw.text((WIDTH // 2 - 50, HEIGHT - 45), "Elapsed time (min)", fill="#111111", font=font)
    draw.text((15, 25), ylabel, fill="#111111", font=font)

    # Load window shading for each run, kept light because windows overlap.
    for rows in runs.values():
        active = [row for row in rows if row["phase"] == "active_load"]
        if not active:
            continue
        end = number(active[-1], "elapsed_s")
        draw.rectangle([plot_left, plot_top, x_coord(end), plot_bottom], fill="#fff8dc")
        break

    # Redraw axes after shading.
    draw.rectangle([plot_left, plot_top, plot_right, plot_bottom], outline="#222222", width=2)

    legend_y = MARGIN_TOP + 10
    for run_id, rows in runs.items():
        color = COLORS.get(run_id, "#333333")
        points = [(x_coord(number(row, "elapsed_s")), y_coord(number(row, metric))) for row in rows]
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
        for point in points:
            x, y = point
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)

        draw.rectangle([WIDTH - 260, legend_y, WIDTH - 240, legend_y + 10], fill=color)
        draw.text((WIDTH - 232, legend_y - 3), label_for(run_id), fill="#111111", font=font)
        legend_y += 22

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(f"Wrote {output.relative_to(ROOT)}")


def main() -> None:
    runs = load_runs()
    if not runs:
        raise SystemExit("No parsed CSV files found. Run parse_hpa_timeline.py first.")
    minikube_tuning_runs = {
        run_id: rows
        for run_id, rows in runs.items()
        if run_id.startswith("minikube") and "20260906" in run_id
    }

    draw_chart(
        runs,
        metric="hpa_replicas",
        title="HPA desired replicas over time",
        ylabel="Replicas",
        output=FIGURE_DIR / "baseline_hpa_replicas.png",
        y_max=10,
    )
    draw_chart(
        runs,
        metric="php_pending",
        title="Pending php-apache pods over time",
        ylabel="Pending pods",
        output=FIGURE_DIR / "baseline_pending_pods.png",
        y_max=5,
    )
    draw_chart(
        runs,
        metric="cpu_pct",
        title="Observed CPU utilization reported to HPA",
        ylabel="CPU utilization (%)",
        output=FIGURE_DIR / "baseline_cpu_utilization.png",
        y_max=260,
    )
    draw_chart(
        minikube_tuning_runs,
        metric="hpa_replicas",
        title="Minikube HPA behavior variants",
        ylabel="Replicas",
        output=FIGURE_DIR / "minikube_hpa_tuning_replicas.png",
        y_max=10,
    )


if __name__ == "__main__":
    main()
