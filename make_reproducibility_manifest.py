#!/usr/bin/env python3
"""Write a content-addressed manifest for the Scenario 1 reproducibility bundle."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = Path(__file__).resolve().parent
FILES = [
    PAPER / "rerun_percatchment.py",
    PAPER / "scenario1_percatchment.py",
    PAPER / "results" / "scenario1" / "lv_scenario1.csv",
    PAPER / "results" / "scenario1" / "asset_reconciliation_exceptions.csv",
    PAPER / "results" / "scenario1" / "scenario1_summary.json",
    PAPER / "export_scenario_results_to_rdf.py",
    PAPER / "run_competency_queries.py",
    ROOT / "ontology" / "DT_ontology.ttl",
    ROOT / "ontology" / "DT_shapes.ttl",
    ROOT / "ontology" / "test_entailment.py",
    ROOT / "ontology" / "test_rollup_entailment.ttl",
    ROOT / "ontology" / "scenario1_results.ttl",
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
    manifest = {
        "bundle": "NEDT Scenario 1 RDF reproducibility bundle",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "files": [{"path": str(p.relative_to(ROOT)), "sha256": checksum(p)} for p in FILES],
        "commands": [
            "python3 AEI-2006-PredictiveEnergyModelling/rerun_percatchment.py --out AEI-2006-PredictiveEnergyModelling/rerun_out",
            "python3 AEI-2006-PredictiveEnergyModelling/scenario1_percatchment.py",
            "python3 AEI-2006-PredictiveEnergyModelling/export_scenario_results_to_rdf.py --input AEI-2006-PredictiveEnergyModelling/results/scenario1/lv_scenario1.csv",
            "python3 AEI-2006-PredictiveEnergyModelling/run_competency_queries.py",
            "python3 ontology/validate_shapes.py",
            "python3 ontology/test_entailment.py",
        ],
    }
    target = PAPER / "results" / "scenario1" / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
