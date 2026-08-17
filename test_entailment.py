#!/usr/bin/env python3
"""Demonstrate that the NEDT T-Box performs non-trivial OWL 2 DL reasoning.

Asserts only two one-step parent links:
    lv1 -hasParentMVFeeder->     mv1
    mv1 -hasParentHVSubstation-> hv1

and checks that a reasoner entails the two-step closure
    lv1 -hasUpstreamAsset->      hv1

via the transitive super-property. This is the mechanism that lets demand be
rolled up to any voltage tier without materialising the closure in the A-Box,
and it is the claim made in the paper's ontology-design section.

Also checks the T-Box is OWL 2 DL conformant (HermiT loads it) and consistent
(no unsatisfiable classes).

Requires: rdflib, owlready2, Java.
"""
import sys
from pathlib import Path
from rdflib import Graph
from owlready2 import get_ontology, sync_reasoner_hermit, default_world

HERE = Path(__file__).parent


def main() -> int:
    g = Graph()
    g.parse(HERE / "DT_ontology.ttl", format="turtle")
    g.parse(HERE / "test_rollup_entailment.ttl", format="turtle")
    tmp = "/tmp/nedt_entailment.owl"
    g.serialize(destination=tmp, format="xml")

    onto = get_ontology("file://" + tmp).load()
    with onto:
        sync_reasoner_hermit(infer_property_values=True, debug=0)

    unsat = [c.name for c in default_world.inconsistent_classes()]
    if unsat:
        print("FAIL: unsatisfiable classes:", unsat)
        return 1
    print("OK: T-Box loads under HermiT and is consistent (OWL 2 DL conformant).")

    lv1 = onto.search_one(iri="*test#lv1")
    hv1 = onto.search_one(iri="*test#hv1")
    upstream = list(lv1.hasUpstreamAsset)
    names = sorted(x.name for x in upstream)
    print(f"   inferred lv1 hasUpstreamAsset = {names}")
    if hv1 not in upstream:
        print("FAIL: two-step LV -> MV -> HV closure was not entailed.")
        return 1
    print("OK: two-step LV -> MV -> HV roll-up entailed by transitivity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
