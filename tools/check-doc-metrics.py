#!/usr/bin/env python3
"""Validate P2 documentation facts, evidence paths and relative links."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "docs" / "project_metrics.json"
P2_DOCS = [
    ROOT / "README.md",
    ROOT / "docs" / "PROJECT_METRICS.md",
    ROOT / "docs" / "EVIDENCE_INDEX.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "MotionEdge-F103-technical-report.md",
    ROOT / "docs" / "TERMINOLOGY.md",
    ROOT / "docs" / "project-highlights.md",
    ROOT / "docs" / "project-evolution.md",
    ROOT / "docs" / "code-tour.md",
    ROOT / "docs" / "current-project-status-and-roadmap.md",
    *sorted((ROOT / "docs" / "interview").glob("*.md")),
    *sorted((ROOT / "docs" / "demo").glob("*.md")),
    *sorted((ROOT / "docs" / "resume").glob("*.md")),
]


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    metrics = data.get("metrics", [])
    by_id = {item.get("id"): item for item in metrics}

    if len(metrics) < 70:
        fail(errors, f"expected at least 70 metrics, found {len(metrics)}")
    if len(by_id) != len(metrics) or None in by_id:
        fail(errors, "metric IDs must be present and unique")

    required_fields = {"id", "category", "label", "value", "source", "phase", "test_type", "status", "limit"}
    for item in metrics:
        missing = required_fields - item.keys()
        if missing:
            fail(errors, f"{item.get('id', '<unknown>')}: missing {sorted(missing)}")
        source = ROOT / str(item.get("source", ""))
        if not source.exists():
            fail(errors, f"{item.get('id')}: evidence does not exist: {source.relative_to(ROOT)}")

    for check in data.get("consistency_checks", []):
        metric_id = check.get("metric_id")
        token = str(check.get("token", ""))
        if metric_id not in by_id:
            fail(errors, f"consistency check references unknown metric: {metric_id}")
            continue
        display = str(by_id[metric_id].get("display", ""))
        if token not in display and display not in token:
            fail(errors, f"{metric_id}: token {token!r} disagrees with display {display!r}")
        for relative in check.get("files", []):
            path = ROOT / relative
            if not path.exists():
                fail(errors, f"required document does not exist: {relative}")
            elif token not in path.read_text(encoding="utf-8"):
                fail(errors, f"{relative}: required token missing: {token}")

    reduction = (5.555 - 2.535) / 5.555 * 100
    if round(reduction, 1) != 54.4:
        fail(errors, f"PWM reduction formula changed: {reduction:.3f}%")

    stale_patterns = {
        "old R-squared 0.946": re.compile(r"R(?:²|\^2)\s*=?\s*0\.946"),
        "old sigma 2.33": re.compile(r"σ\s*=?\s*2\.33"),
        "old two-hour claim": re.compile(r"(?<!\w)2\s*h(?:ours?)?(?!\w)", re.I),
        "rounded 217 ms RTT": re.compile(r"(?<!\d)217\s*ms", re.I),
        "old 90.8 degree value": re.compile(r"90\.8°"),
    }
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for path in P2_DOCS:
        if not path.exists():
            fail(errors, f"P2 document missing: {path.relative_to(ROOT)}")
            continue
        content = path.read_text(encoding="utf-8")
        for name, pattern in stale_patterns.items():
            if pattern.search(content):
                fail(errors, f"{path.relative_to(ROOT)}: contains {name}")
        if ("0.352°" in content or "0.375°" in content) and "REFERENCE_LIMITED" not in content:
            fail(errors, f"{path.relative_to(ROOT)}: attitude MAE lacks REFERENCE_LIMITED boundary")
        for target in link_pattern.findall(content):
            target = target.strip().split("#", 1)[0]
            if not target or re.match(r"^(?:https?://|mailto:)", target):
                continue
            target = target.strip("<>")
            if not (path.parent / target).resolve().exists():
                fail(errors, f"{path.relative_to(ROOT)}: broken relative link: {target}")

    required_tokens = ["100 Hz", "0.352°", "0.375°", "1450", "1550", "5.555", "2.535", "54.4%", "4934", "2 ms", "2.80 s", "59240 B", "3068 B"]
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in P2_DOCS if path.exists())
    for token in required_tokens:
        if token not in corpus:
            fail(errors, f"P2 corpus missing required token: {token}")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print(f"Documentation metrics check failed: {len(errors)} issue(s).")
        return 1

    print(f"[PASS] schema and {len(metrics)} metric records")
    print(f"[PASS] {len(metrics)} evidence paths")
    print(f"[PASS] {len(data.get('consistency_checks', []))} cross-document checks")
    print(f"[PASS] {len(P2_DOCS)} P2 documents, stale-value scan and relative links")
    print("[PASS] PWM reduction formula and required presentation tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
