# -*- coding: utf-8 -*-
# Copyright 2026 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run-environment capture and Markdown formatting for the benchmark report."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dapr.ext.workflow._bench_harness import IS_DARWIN, ScenarioMetrics, SustainedMetrics


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return ''


def _cpu_model() -> str:
    """Best-effort CPU model name. Cross-platform; returns a placeholder on failure."""
    if IS_DARWIN:
        sysctl = shutil.which('sysctl')
        if sysctl is not None:
            try:
                out = subprocess.run(
                    [sysctl, '-n', 'machdep.cpu.brand_string'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if out.returncode == 0 and out.stdout.strip():
                    return out.stdout.strip()
            except (subprocess.SubprocessError, OSError):
                pass
    cpuinfo = _read_text('/proc/cpuinfo')
    for line in cpuinfo.splitlines():
        if line.startswith('model name'):
            return line.split(':', 1)[1].strip()
    return platform.processor() or platform.machine() or 'unknown'


def _total_memory_gb() -> float:
    """Best-effort total physical memory in GB. Returns 0 on failure."""
    if IS_DARWIN:
        sysctl = shutil.which('sysctl')
        if sysctl is not None:
            try:
                out = subprocess.run(
                    [sysctl, '-n', 'hw.memsize'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if out.returncode == 0 and out.stdout.strip().isdigit():
                    return int(out.stdout.strip()) / (1024**3)
            except (subprocess.SubprocessError, OSError):
                pass
    meminfo = _read_text('/proc/meminfo')
    for line in meminfo.splitlines():
        if line.startswith('MemTotal:'):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) / (1024**2)
    return 0.0


def _git_commit() -> str:
    """Short git commit hash, or 'unknown' if not in a git repo."""
    git = shutil.which('git')
    if git is None:
        return 'unknown'
    try:
        out = subprocess.run(
            [git, 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).parent,
        )
        if out.returncode == 0:
            commit = out.stdout.strip()
            # Mark dirty if there are uncommitted changes.
            status = subprocess.run(
                [git, 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=2,
                cwd=Path(__file__).parent,
            )
            if status.returncode == 0 and status.stdout.strip():
                return f'{commit}-dirty'
            return commit
    except (subprocess.SubprocessError, OSError):
        pass
    return 'unknown'


@dataclass(slots=True)
class RunEnvironment:
    """Snapshot of the machine the benchmark ran on."""

    timestamp_utc: str
    git_commit: str
    python_version: str
    python_implementation: str
    platform: str
    os_release: str
    cpu_model: str
    cpu_logical_cores: int
    cpu_physical_cores_hint: int
    total_memory_gb: float
    is_ci: bool

    @classmethod
    def capture(cls) -> 'RunEnvironment':
        return cls(
            timestamp_utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            git_commit=_git_commit(),
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            platform=platform.platform(),
            os_release=f'{platform.system()} {platform.release()} ({platform.machine()})',
            cpu_model=_cpu_model(),
            cpu_logical_cores=os.cpu_count() or 0,
            cpu_physical_cores_hint=os.cpu_count() or 0,
            total_memory_gb=_total_memory_gb(),
            is_ci=any(os.environ.get(k) for k in ('CI', 'GITHUB_ACTIONS', 'TRAVIS', 'BUILDKITE')),
        )


def _format_environment_block(env: RunEnvironment) -> str:
    mem_str = f'{env.total_memory_gb:.1f} GB' if env.total_memory_gb > 0 else 'unknown'
    return (
        '## Run environment\n'
        '\n'
        f'- **Timestamp**: {env.timestamp_utc}\n'
        f'- **Git commit**: `{env.git_commit}`\n'
        f'- **Python**: {env.python_implementation} {env.python_version}\n'
        f'- **OS**: {env.os_release}\n'
        f'- **CPU**: {env.cpu_model} ({env.cpu_logical_cores} logical cores)\n'
        f'- **Memory**: {mem_str}\n'
        '\n'
        'Numbers are specific to this machine; the sync-vs-async gap is what transfers across'
        ' hardware, not the absolute values.'
    )


def _speedup_cell(speedup: float) -> str:
    if speedup > 1.2:
        dot = '🟢'
    elif speedup >= 0.8:
        dot = '⚪'
    else:
        dot = '🔴'
    return f'{dot} {speedup:.1f}x'


def _format_comparison_table(
    rows: list[tuple[str, ScenarioMetrics, ScenarioMetrics]],
    key_label: str = 'N',
    show_async_rss: bool = False,
) -> str:
    rss_header = ' Async RAM (MB) |' if show_async_rss else ''
    rss_rule = ' ---: |' if show_async_rss else ''
    header = (
        f'| {key_label} | Sync (s) | Async (s) | Speedup |{rss_header}\n'
        f'| ---: | ---: | ---: | ---: |{rss_rule}\n'
    )
    lines = []
    for key, sync_m, async_m in rows:
        speedup = sync_m.wallclock_s / async_m.wallclock_s if async_m.wallclock_s > 0 else 0.0
        rss = f' {async_m.peak_rss_delta_mb:.0f} |' if show_async_rss else ''
        lines.append(
            f'| {key} | {sync_m.wallclock_s:.2f} | {async_m.wallclock_s:.2f} |'
            f' {_speedup_cell(speedup)} |{rss}'
        )
    return header + '\n'.join(lines)


def _format_sustained_table(sync_m: SustainedMetrics, async_m: SustainedMetrics) -> str:
    def row(label: str, sync_val: str, async_val: str) -> str:
        return f'| {label} | {sync_val} | {async_val} |'

    header = '| Metric | Sync | Async |\n| --- | ---: | ---: |\n'
    rows = [
        row(
            'Effective throughput',
            f'{sync_m.throughput_per_s:.0f}/s',
            f'{async_m.throughput_per_s:.0f}/s',
        ),
        row(
            'p99 latency',
            f'{sync_m.latency_overall.p99_ms:.0f} ms',
            f'{async_m.latency_overall.p99_ms:.0f} ms',
        ),
        row(
            'p99 first quarter',
            f'{sync_m.latency_first_quarter.p99_ms:.0f} ms',
            f'{async_m.latency_first_quarter.p99_ms:.0f} ms',
        ),
        row(
            'p99 last quarter',
            f'{sync_m.latency_last_quarter.p99_ms:.0f} ms',
            f'{async_m.latency_last_quarter.p99_ms:.0f} ms',
        ),
    ]
    return header + '\n'.join(rows)
