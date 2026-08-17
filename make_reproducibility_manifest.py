#!/usr/bin/env python3
"""Write a content-addressed manifest for the Scenario 1 reproducibility bundle."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent
# The script works both in the manuscript workspace (where ontology/ is a
# sibling of the paper directory) and in the public repository root.
ROOT = (PAPER if (PAPER / "DT_ontology.ttl").exists()
        else PAPER.parent if (PAPER.parent / "ontology").exists()
        else PAPER)
ONTOLOGY = ROOT / "ontology" if (ROOT / "ontology").exists() else ROOT
FILES = [
    PAPER / "rerun_percatchment.py",
    PAPER / "scenario1_percatchment.py",
    PAPER / "REPRODUCIBILITY.md",
    PAPER / "requirements.txt",
    PAPER / "verify_release.py",
    PAPER / "results" / "scenario1" / "lv_scenario1.csv",
    PAPER / "results" / "scenario1" / "asset_reconciliation_exceptions.csv",
    PAPER / "results" / "scenario1" / "scenario1_summary.json",
    PAPER / "export_scenario_results_to_rdf.py",
    PAPER / "run_competency_queries.py",
    ONTOLOGY / "DT_ontology.ttl",
    ONTOLOGY / "DT_shapes.ttl",
    ONTOLOGY / "test_entailment.py",
    ONTOLOGY / "test_rollup_entailment.ttl",
    ONTOLOGY / "scenario1_results.ttl",
    PAPER / "results" / "scenario1" / "competency_queries.json",
]


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    missing = [str(p) for p in FILES if not p.exists()]
    if missing:
        raise FileNotFoundError("missing bundle inputs: " + ", ".join(missing))
    relative_paper = PAPER.relative_to(ROOT)
    command_prefix = "" if str(relative_paper) == "." else f"{relative_paper.as_posix()}/"
    manifest = {
        "bundle": "NEDT Scenario 1 RDF reproducibility bundle",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "files": [{"path": str(p.relative_to(ROOT)), "sha256": checksum(p)} for p in FILES],
        "commands": [
            f"python3 {command_prefix}rerun_percatchment.py --out {command_prefix}rerun_out",
            f"python3 {command_prefix}scenario1_percatchment.py",
            f"python3 {command_prefix}export_scenario_results_to_rdf.py --input {command_prefix}results/scenario1/lv_scenario1.csv",
            f"python3 {command_prefix}run_competency_queries.py",
            "python3 ontology/validate_shapes.py",
            "python3 ontology/test_entailment.py",
            f"python3 {command_prefix}verify_release.py",
        ],
    }
    target = PAPER / "results" / "scenario1" / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
