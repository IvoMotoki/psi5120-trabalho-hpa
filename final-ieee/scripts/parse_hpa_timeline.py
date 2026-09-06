#!/usr/bin/env python3
"""Parse raw HPA timeline logs into CSV files and compact run summaries."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "final-ieee" / "data"
LOG_DIRS = {
    "minikube": ROOT / "evidencias" / "minikube",
    "eks": ROOT / "evidencias" / "eks",
}

BLOCK_RE = re.compile(r"^---- (?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ----$")
HPA_RE = re.compile(
    r"^php-apache\s+Deployment/php-apache\s+cpu:\s+(?P<cpu>\d+)%/(?P<target>\d+)%\s+"
    r"(?P<min>\d+)\s+(?P<max>\d+)\s+(?P<replicas>\d+)\s+"
)


@dataclass
class Sample:
    environment: str
    run_id: str
    timestamp: datetime
    elapsed_s: int
    phase: str
    cpu_pct: int | None
    target_cpu_pct: int | None
    hpa_replicas: int | None
    hpa_min_replicas: int | None
    hpa_max_replicas: int | None
    php_running: int
    php_pending: int
    php_total: int
    load_running: int
    load_pending: int
    load_total: int


def iter_blocks(path: Path) -> Iterable[tuple[datetime, list[str]]]:
    current_timestamp: datetime | None = None
    current_lines: list[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            match = BLOCK_RE.match(line)
            if match:
                if current_timestamp is not None:
                    yield current_timestamp, current_lines
                current_timestamp = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H:%M:%S")
                current_lines = []
                continue
            if current_timestamp is not None:
                current_lines.append(line)

    if current_timestamp is not None:
        yield current_timestamp, current_lines


def parse_block(environment: str, run_id: str, first_ts: datetime, timestamp: datetime, lines: list[str]) -> Sample:
    cpu_pct = None
    target_cpu_pct = None
    replicas = None
    min_replicas = None
    max_replicas = None
    php_running = 0
    php_pending = 0
    php_total = 0
    load_running = 0
    load_pending = 0
    load_total = 0

    in_pod_table = False
    for line in lines:
        hpa_match = HPA_RE.match(line)
        if hpa_match:
            cpu_pct = int(hpa_match.group("cpu"))
            target_cpu_pct = int(hpa_match.group("target"))
            min_replicas = int(hpa_match.group("min"))
            max_replicas = int(hpa_match.group("max"))
            replicas = int(hpa_match.group("replicas"))
            continue

        if line.startswith("NAME ") and "READY" in line and "STATUS" in line:
            in_pod_table = True
            continue
        if line.startswith("NAME ") and "CPU(cores)" in line:
            in_pod_table = False
            continue
        if not in_pod_table or not line.strip():
            continue

        parts = line.split()
        if len(parts) < 3:
            continue
        pod_name = parts[0]
        status = parts[2]

        if pod_name.startswith("php-apache-"):
            php_total += 1
            if status == "Running":
                php_running += 1
            elif status == "Pending":
                php_pending += 1
        elif pod_name.startswith("load-generator-"):
            load_total += 1
            if status == "Running":
                load_running += 1
            elif status in {"Pending", "ContainerCreating"}:
                load_pending += 1

    phase = "active_load" if (load_running + load_pending) > 0 else "post_load"
    return Sample(
        environment=environment,
        run_id=run_id,
        timestamp=timestamp,
        elapsed_s=int((timestamp - first_ts).total_seconds()),
        phase=phase,
        cpu_pct=cpu_pct,
        target_cpu_pct=target_cpu_pct,
        hpa_replicas=replicas,
        hpa_min_replicas=min_replicas,
        hpa_max_replicas=max_replicas,
        php_running=php_running,
        php_pending=php_pending,
        php_total=php_total,
        load_running=load_running,
        load_pending=load_pending,
        load_total=load_total,
    )


def parse_log(environment: str, path: Path) -> list[Sample]:
    blocks = list(iter_blocks(path))
    if not blocks:
        return []
    first_ts = blocks[0][0]
    run_id = path.stem
    return [parse_block(environment, run_id, first_ts, ts, lines) for ts, lines in blocks]


def write_samples(path: Path, samples: list[Sample]) -> None:
    fieldnames = list(Sample.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for sample in samples:
            row = sample.__dict__.copy()
            row["timestamp"] = sample.timestamp.isoformat(sep=" ")
            writer.writerow(row)


def sample_pairs(samples: list[Sample]) -> Iterable[tuple[Sample, Sample]]:
    for previous, current in zip(samples, samples[1:]):
        yield previous, current


def summarize(samples: list[Sample]) -> dict[str, str | int | float | None]:
    if not samples:
        return {}

    first = samples[0]
    baseline_replicas = first.hpa_replicas or 0
    active_samples = [sample for sample in samples if sample.phase == "active_load"]
    post_samples = [sample for sample in samples if sample.phase == "post_load"]
    peak_replicas = max((sample.hpa_replicas or 0) for sample in samples)
    peak_pending = max(sample.php_pending for sample in samples)
    peak_php_total = max(sample.php_total for sample in samples)
    peak_cpu = max((sample.cpu_pct or 0) for sample in samples)

    first_scale_up = next(
        (sample.elapsed_s for sample in samples if (sample.hpa_replicas or 0) > baseline_replicas),
        None,
    )
    first_above_target = next(
        (
            sample.elapsed_s
            for sample in samples
            if sample.cpu_pct is not None
            and sample.target_cpu_pct is not None
            and sample.cpu_pct > sample.target_cpu_pct
        ),
        None,
    )
    time_to_peak = next(
        (sample.elapsed_s for sample in samples if (sample.hpa_replicas or 0) == peak_replicas),
        None,
    )
    load_end = post_samples[0].elapsed_s if post_samples else None
    scale_down_complete = None
    if load_end is not None:
        scale_down_complete = next(
            (
                sample.elapsed_s
                for sample in post_samples
                if (sample.hpa_replicas or 0) <= baseline_replicas
            ),
            None,
        )

    replica_seconds = 0
    under_target_seconds = 0
    over_target_seconds = 0
    for previous, current in sample_pairs(samples):
        dt = current.elapsed_s - previous.elapsed_s
        replicas = previous.hpa_replicas or 0
        replica_seconds += replicas * dt
        if previous.cpu_pct is not None and previous.target_cpu_pct is not None:
            if previous.cpu_pct > previous.target_cpu_pct:
                under_target_seconds += dt
            elif previous.cpu_pct < previous.target_cpu_pct:
                over_target_seconds += dt

    return {
        "environment": first.environment,
        "run_id": first.run_id,
        "samples": len(samples),
        "duration_s": samples[-1].elapsed_s,
        "load_window_s": active_samples[-1].elapsed_s if active_samples else None,
        "baseline_replicas": baseline_replicas,
        "peak_hpa_replicas": peak_replicas,
        "peak_php_total": peak_php_total,
        "peak_php_pending": peak_pending,
        "peak_cpu_pct": peak_cpu,
        "first_above_target_s": first_above_target,
        "first_scale_up_s": first_scale_up,
        "time_to_peak_s": time_to_peak,
        "load_end_s": load_end,
        "scale_down_complete_s": scale_down_complete,
        "scale_down_after_load_s": None
        if load_end is None or scale_down_complete is None
        else scale_down_complete - load_end,
        "replica_seconds": replica_seconds,
        "above_target_seconds": under_target_seconds,
        "below_target_seconds": over_target_seconds,
    }


def write_latex_summary(path: Path, summaries: list[dict[str, str | int | float | None]]) -> None:
    def value(row: dict[str, str | int | float | None], key: str) -> str:
        item = row.get(key)
        return "--" if item is None or item == "" else str(item)

    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Baseline HPA metrics extracted from raw experiment logs}",
        r"\label{tab:baseline-generated}",
        r"\resizebox{\linewidth}{!}{%",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Environment & First scale-up (s) & Peak replicas & Pending pods & Scale-down after load (s) & Replica-s \\",
        r"\midrule",
    ]

    for row in summaries:
        environment = str(row["environment"]).capitalize()
        if row["environment"] == "eks":
            environment = f"EKS ({str(row['run_id']).split('_')[-1]})"
        lines.append(
            " & ".join(
                [
                    environment,
                    value(row, "first_scale_up_s"),
                    value(row, "peak_hpa_replicas"),
                    value(row, "peak_php_pending"),
                    value(row, "scale_down_after_load_s"),
                    value(row, "replica_seconds"),
                ]
            )
            + r" \\"
        )

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"}",
            r"\end{table}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, str | int | float | None]] = []

    for environment, log_dir in LOG_DIRS.items():
        for log_path in sorted(log_dir.glob("hpa_timeline_*.log")):
            samples = parse_log(environment, log_path)
            if not samples:
                continue
            csv_path = DATA_DIR / f"{environment}_{log_path.stem}.csv"
            write_samples(csv_path, samples)
            summaries.append(summarize(samples))
            print(f"Wrote {csv_path.relative_to(ROOT)} ({len(samples)} samples)")

    if summaries:
        summary_path = DATA_DIR / "summary.csv"
        fieldnames = list(summaries[0].keys())
        with summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summaries)
        print(f"Wrote {summary_path.relative_to(ROOT)} ({len(summaries)} runs)")
        latex_path = DATA_DIR / "baseline_summary_table.tex"
        write_latex_summary(latex_path, summaries)
        print(f"Wrote {latex_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
