#!/usr/bin/env python3
"""Execute all fifteen NEDT competency questions and report rows and timing.

Supersedes run_competency_queries.py, which covered four.

Each query is written against the shape the A-Box actually has. Where that
differs from the SPARQL skeleton printed in the paper's appendix, the
divergence is recorded in the `skeleton_divergence` field so the paper can be
corrected rather than the difference being hidden.

Usage:
    python3 run_all_competency_queries.py [--repeats 3] [--output results.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from rdflib import Graph

HERE = Path(__file__).resolve().parent
PREFIX = """
PREFIX nedt: <https://example.org/nedt#>
PREFIX inst: <https://example.org/nedt/inst/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
"""

# (id, description, query, divergence-from-paper-skeleton or None)
CQ: list[tuple[str, str, str, str | None]] = [
    ("CQ1", "Dwelling archetype cohorts per county", """
        SELECT ?county (SUM(?n) AS ?dwellings) (COUNT(?c) AS ?cohorts)
        WHERE { ?c a nedt:ArchetypeCount ; nedt:inCounty ?county ; nedt:dwellingCount ?n . }
        GROUP BY ?county ORDER BY DESC(?dwellings)""",
     "Paper uses nedt:forCounty and nedt:hasCount; the graph uses nedt:inCounty and "
     "nedt:dwellingCount. nedt:hasCount is an ObjectProperty (Archetype -> ArchetypeCount) "
     "and cannot carry a literal."),

    ("CQ2", "Building-stock attributes for an archetype", """
        SELECT ?archetype ?buildType ?berClass ?occupancy ?heatingSystem
        WHERE { ?archetype a nedt:Archetype ;
                  nedt:hasBuildType ?buildType ; nedt:hasBERCategory ?berClass ;
                  nedt:hasOccupancyCategory ?occupancy ;
                  nedt:usesHeatingSystem ?heatingSystem . }
        LIMIT 50""", None),

    ("CQ3", "Scenario parameters", """
        SELECT ?scenario ?year ?hp ?ev ?pv
        WHERE { ?scenario a nedt:Scenario ; nedt:hasScenarioYear ?year ;
                  nedt:hasHPAdoptionFraction ?hp ; nedt:hasEVAdoptionFraction ?ev ;
                  nedt:hasPVAdoptionFraction ?pv . }""", None),

    ("CQ4", "Technology transitions in the scenario", """
        SELECT ?transition ?from ?to ?count
        WHERE { ?scenario nedt:appliesScenarioOperator ?op .
                ?op nedt:changesTechnologyState ?transition .
                ?transition nedt:fromArchetype ?from ; nedt:toArchetype ?to ;
                            nedt:transitionCount ?count . }
        ORDER BY DESC(?count)""", None),

    ("CQ5", "Archetype breakdown for an LV station", """
        SELECT ?station ?archetype ?n
        WHERE { ?c a nedt:ArchetypeCount ; nedt:forLVStation ?station ;
                  nedt:countsArchetype ?archetype ; nedt:dwellingCount ?n . }
        ORDER BY DESC(?n) LIMIT 100""",
     "Paper uses nedt:instantiatesArchetype, whose domain is nedt:Dwelling; applying it to a "
     "cohort would entail cohorts are dwellings. Graph uses nedt:countsArchetype."),

    ("CQ6", "Over-capacity LV stations under the scenario", """
        SELECT ?station ?peak ?capacity ?u
        WHERE { ?kpi a nedt:CapacityKPI ; nedt:forLVStation ?station ;
                  nedt:hasPeakDemandKW ?peak ; nedt:hasRatedCapacityKVA ?capacity ;
                  nedt:hasUtilisation ?un . ?un sosa:hasSimpleResult ?u .
                FILTER(?u > 1.0) }
        ORDER BY DESC(?u)""",
     "Paper reads nedt:hasUtilisation as a literal; the graph reifies it as a "
     "nedt:Utilisation node carrying sosa:hasSimpleResult."),

    ("CQ7", "Rooftop PV self-consumption and export by archetype", """
        SELECT ?archetype ?scr ?export ?reverseHours
        WHERE { ?s a nedt:FlexibilityState ; nedt:forArchetype ?archetype ;
                  nedt:hasSelfConsumptionRatio ?scr ; nedt:hasGridExport ?export ;
                  nedt:hasReverseFlowHours ?reverseHours . }
        ORDER BY DESC(?reverseHours)""", None),

    ("CQ8", "County peak demand, energy and emissions", """
        SELECT ?county ?peakMW ?energyGWh ?co2kt
        WHERE { ?agg a nedt:CountyDemandAggregate ; nedt:forCounty ?county ;
                  nedt:hasPeakDemandMW ?peakMW ; nedt:hasAnnualEnergyUse ?energyGWh ;
                  nedt:hasAnnualCO2 ?co2kt . }
        ORDER BY DESC(?energyGWh)""", None),

    ("CQ9", "National demand and contributing counties", """
        SELECT ?nationalPeak ?county ?contribution
        WHERE { ?nat a nedt:NationalDemandAggregate ;
                  nedt:hasPeakDemandMW ?nationalPeak ;
                  nedt:aggregatesDemandFrom ?agg .
                ?agg nedt:forCounty ?county ;
                     nedt:hasContributionToNationalPeak ?contribution . }
        ORDER BY DESC(?contribution)""", None),

    ("CQ10", "At-risk stations requiring reinforcement", """
        SELECT ?station ?u ?overloadHours
        WHERE { ?kpi a nedt:CapacityKPI ; nedt:forLVStation ?station ;
                  nedt:hasUtilisation ?un . ?un sosa:hasSimpleResult ?u .
                OPTIONAL { ?kpi nedt:hasOverloadHours ?overloadHours . }
                FILTER(?u >= 0.9) }
        ORDER BY DESC(?u)""", None),

    ("CQ11", "Sensitivity of outcomes to a scenario parameter", """
        SELECT ?parameter ?dPeak ?dCO2 ?perturbation
        WHERE { ?s a nedt:SensitivityResult ; nedt:forParameter ?p ;
                  nedt:hasMarginalEffectOnPeak ?dPeak ;
                  nedt:hasMarginalEffectOnCO2 ?dCO2 ;
                  nedt:hasPerturbation ?perturbation .
                ?p rdfs:label ?parameter . }
        ORDER BY DESC(?dPeak)""", None),

    ("CQ12", "Provenance and assumptions behind a KPI", """
        SELECT ?kpi ?activity ?dataset ?assumption
        WHERE { ?kpi a nedt:CapacityKPI ; prov:wasGeneratedBy ?activity .
                OPTIONAL { ?activity prov:used ?dataset . }
                OPTIONAL { ?kpi nedt:evaluatedUnderScenario ?scn .
                           ?scn nedt:hasScenarioAssumption ?assumption . } }
        LIMIT 100""",
     "Paper attaches assumptions directly to the KPI; the graph attaches them to the "
     "scenario the KPI was evaluated under, which avoids repeating them 37,287 times."),

    ("CQ13", "Dwellings assigned to an LV station", """
        SELECT ?station ?dwelling ?archetype ?distance
        WHERE { ?dwelling a nedt:Dwelling ; nedt:isServedBy ?station ;
                  nedt:instantiatesArchetype ?archetype .
                OPTIONAL { ?dwelling nedt:hasAssignmentDistanceM ?distance . } }
        ORDER BY DESC(?distance) LIMIT 200""", None),

    ("CQ14", "MV roll-up from downstream LV stations", """
        SELECT ?parent (SUM(?peak) AS ?rolledUpPeak) (COUNT(?lv) AS ?children)
        WHERE { ?kpi a nedt:CapacityKPI ; nedt:forLVStation ?lv ;
                  nedt:hasPeakDemandKW ?peak .
                ?lv nedt:hasParentMVFeeder ?parent . }
        GROUP BY ?parent ORDER BY DESC(?rolledUpPeak)""",
     "Sum of child peaks, not the coincident roll-up. The coincident value needs the "
     "summed hourly series, which the graph does not carry."),

    ("CQ15", "Validation observation linked to a modelled profile", """
        SELECT ?profile ?observation ?measured ?timestamp
        WHERE { ?profile a nedt:DemandProfile ;
                  nedt:validatedAgainstObservation ?observation .
                ?observation nedt:hasMeasuredValue ?measured ;
                             nedt:hasTimestamp ?timestamp . }
        ORDER BY DESC(?measured)""", None),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--output", type=Path, default=HERE / "competency_queries_all.json")
    args = ap.parse_args()

    sources = [HERE / "DT_ontology.ttl", HERE / "DT_kg.ttl",
               HERE / "scenario1_results.ttl", HERE / "cq_test_abox.ttl"]
    g = Graph()
    for s in sources:
        if not s.exists():
            print(f"missing: {s}")
            return 1
        t0 = time.perf_counter()
        g.parse(s, format="turtle")
        print(f"loaded {s.name:28s} -> {len(g):>9,} triples  ({time.perf_counter()-t0:.1f}s)")
    print()

    summary = {"triples": len(g), "sources": [s.name for s in sources],
               "repeats": args.repeats, "queries": {}}
    ok = 0
    print(f"{'CQ':<6}{'rows':>9}{'median ms':>12}  description")
    print("-" * 78)
    for cid, desc, q, div in CQ:
        times, rows = [], 0
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            res = list(g.query(PREFIX + q))
            times.append((time.perf_counter() - t0) * 1000)
            rows = len(res)
        med = statistics.median(times)
        summary["queries"][cid] = {
            "description": desc, "rows": rows, "median_ms": round(med, 2),
            "answered": rows > 0, "skeleton_divergence": div,
            "sample": [[str(x) for x in r] for r in res[:3]],
        }
        ok += rows > 0
        flag = "" if rows > 0 else "   <-- NO ROWS"
        print(f"{cid:<6}{rows:>9,}{med:>12.1f}  {desc}{flag}")
    print("-" * 78)
    print(f"answered with data: {ok}/15")
    div_n = sum(1 for c in summary["queries"].values() if c["skeleton_divergence"])
    print(f"queries whose paper skeleton diverges from the graph: {div_n}/15")
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {args.output}")
    return 0 if ok == 15 else 2


if __name__ == "__main__":
    raise SystemExit(main())
