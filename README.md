# NEDT Ontology — National Energy Digital Twin

A modular OWL ontology for the National Energy Digital Twin (NEDT) of the Irish residential energy system.

[![Ontology](https://img.shields.io/badge/format-OWL%2FTurtle-blue)](DT_ontology.ttl)
[![Version](https://img.shields.io/badge/version-1.4.0-green)](DT_ontology.ttl)
[![SHACL](https://img.shields.io/badge/SHACL-validated-brightgreen)](DT_shapes.ttl)
[![License](https://img.shields.io/badge/license-CC%20BY%204.0-orange)](https://creativecommons.org/licenses/by/4.0/)

---

## Overview

The NEDT ontology provides a shared, machine-interpretable vocabulary for a national-scale residential energy digital twin for Ireland. It connects:

- **2.1 million dwellings** across 26 counties, encoded as 702 building archetypes
- **Hourly Nexsys energy profiles** for electricity, heat, EV charging and rooftop PV
- **ESB Networks LV substation** geometries and capacities
- **SEAI domestic-PV grant records** and scenario trajectories (heat pumps, EVs, PV adoption)
- **KPI evaluation** from dwelling level up to national level

---

## Visualise

Explore the ontology interactively (no install needed):

**[Open in WebVOWL](https://service.tib.eu/webvowl/#iri=https://raw.githubusercontent.com/buildinginformaticslab/nedt-ontology/main/DT_ontology.ttl)**

Or upload `DT_ontology.ttl` manually at [service.tib.eu/webvowl](https://service.tib.eu/webvowl).

---

## Repository Contents

| File | Description |
|---|---|
| `DT_ontology.ttl` | Core OWL ontology — 116 classes and 139 object/datatype properties |
| `DT_instances_v11.ttl` | Example A-Box instances (v11) |
| `DT_shapes.ttl` | SHACL validation shapes |
| `DT_kg.ttl` | Generated knowledge graph (Turtle) |
| `DT_kg_full.ttl` | Full knowledge graph with all triples |
| `DT_kg.jsonld` | Knowledge graph in JSON-LD format |
| `queries.rq` | Ready-to-run SPARQL queries |
| `build_kg.py` | Script to build the knowledge graph from source data |
| `populate_v11_instances.py` | Script to populate A-Box instances |
| `Ontology.ipynb` | Ontology diagram generator (SVG) |
| `ontology_query.ipynb` | SPARQL query workbench |
| `DT_ontology_paper.md` | Full ontology specification and design rationale |
| `scenario1_percatchment.py` | Portable Scenario 1 workflow (`--data-root` for licensed inputs) |
| `REPRODUCIBILITY.md` | Restricted-data layout, commands and interpretation boundary |

This update does not include manuscript files or newly generated Scenario 1
results. They are generated locally from licensed inputs and written to
`results/scenario1/`; generated artefacts should not be mixed with the
ontology source files tracked here. Any root-level Scenario 1 artefacts in
the repository are retained unchanged as legacy material.

---

## Namespace

```
Prefix:  nedt:
URI:     https://example.org/nedt#
```

The namespace is provisional pending registration of a durable PURL. Do not
mint new production identifiers against a replacement namespace without an
explicit migration plan.

---

## Ten Ontology Modules

| Module | Key Classes |
|---|---|
| KPI | `KPI`, `KPIValue`, `KPICalculation`, `StrategicKPI`, `TacticalKPI`, `OperationalKPI` |
| Archetype | `Archetype`, `ArchetypeCount`, `BERRating`, `DwellingType`, `ConstructionPeriod` |
| Scenario | `Scenario`, `HPScenario`, `EVScenario`, `TransitionLedger`, `ScenarioParameter` |
| Energy Load | `ElectricLoad`, `HeatLoad`, `CO2Emission`, `HourlyProfile`, `NexsysProfile` |
| LV Network | `LVStation`, `StationCapacity`, `Utilisation`, `UtilisationStatus`, `BuildingShare` |
| Attribution | `OverloadedStation`, `OverloadAttribution`, `DominantDriver`, `RiskTable` |
| Heat Density | `HeatDensity`, `ThermalDemandCluster`, `DHViabilityKPI`, `GroupHeatingCandidate` |
| Visualisation | `FigCollector`, `DeckGLMap`, `HTMLReport`, `ColourPalette` |
| Geography | `County`, `GeoLocation`, `HullPolygon` |
| Rooftop PV | `PVSystem`, `PVGenerationProfile`, `PVReferenceShape`, `PVAdoptionScenario` |

---

## Quick Start

```bash
pip install -r requirements.txt
```

```python
from rdflib import Graph

# Load ontology + instances
g = Graph()
g.parse("DT_ontology.ttl", format="turtle")
g.parse("DT_instances_v11.ttl", format="turtle")
print(f"Loaded {len(g)} triples")

# Run a SPARQL query
results = g.query("""
    PREFIX nedt: <https://example.org/nedt#>
    SELECT ?station ?kva
    WHERE { ?station a nedt:LVStation ; nedt:hasCapacityValue ?kva . }
    ORDER BY DESC(?kva)
""")
for row in results:
    print(row)
```

### SHACL Validation

```python
from pyshacl import validate
conforms, results_graph, _ = validate(g, shacl_graph="DT_shapes.ttl")
print("Conforms:", conforms)
```

### Scenario 1 reproducibility

The public repository does not contain licensed building, profile or network
source data. Follow [REPRODUCIBILITY.md](REPRODUCIBILITY.md) and supply a
licensed DT_Model workspace through `--data-root` or `NEDT_DATA_ROOT`:

```bash
python3 rerun_percatchment.py --data-root /path/to/DT_Model
python3 scenario1_percatchment.py --data-root /path/to/DT_Model
python3 export_scenario_results_to_rdf.py --input results/scenario1/lv_scenario1.csv
python3 run_competency_queries.py
python3 validate_shapes.py
python3 test_entailment.py
python3 verify_release.py
```

Scenario capacity results are conditional residential infrastructure-exposure
indicators. They must not be interpreted as observed transformer-overload
labels; extreme records are retained locally for reconciliation.

---

## External Ontologies Reused

| Ontology | Usage |
|---|---|
| [SSN/SOSA](https://www.w3.org/TR/vocab-ssn/) | Observations, procedures, observation values |
| [OWL-Time](https://www.w3.org/TR/owl-time/) | Temporal intervals and timestamps |
| [GeoSPARQL](https://www.ogc.org/standards/geosparql) | Spatial features and geometries |
| [BOT](https://w3id.org/bot) | Building topology |
| [PROV-O](https://www.w3.org/TR/prov-o/) | Provenance of DT runs and datasets |
| [Dublin Core Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) | Ontology metadata |

---

## Authors

- Divyanshu Sood
- Sharon Coffee
- James O'Donnell

---

## Citation

If you use this ontology, please cite:

```
Sood, D., Hoare, C., Coffee, S., O'Donnell, J. (2026).
A Knowledge-Graph Framework for Transformer-Level Planning under
Residential Technology-Adoption Scenarios. Manuscript in preparation.
https://github.com/buildinginformaticslab/nedt-ontology
```
