# NEDT Ontology — National Energy Digital Twin

A modular OWL ontology for the National Energy Digital Twin (NEDT) of the Irish residential energy system.

[![Ontology](https://img.shields.io/badge/format-OWL%2FTurtle-blue)](DT_ontology.ttl)
[![Version](https://img.shields.io/badge/version-1.2.0-green)](DT_ontology.ttl)
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

**[Open in WebVOWL](https://service.tib.eu/webvowl/#iri=https://raw.githubusercontent.com/nedt-ireland/nedt-ontology/main/DT_ontology.ttl)**

Or upload `DT_ontology.ttl` manually at [service.tib.eu/webvowl](https://service.tib.eu/webvowl).

---

## Repository Contents

| File | Description |
|---|---|
| `DT_ontology.ttl` | Core OWL ontology — 92 classes, 95 properties, 10 modules |
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

---

## Namespace

```
Prefix:  nedt:
URI:     https://example.org/nedt#
```

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
pip install rdflib pandas pyshacl
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
    WHERE { ?station a nedt:LVStation ; nedt:ratedKVA ?kva . }
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
Sood, D., Coffee, S., O'Donnell, J. (2026).
A Modular Ontology for the National Energy Digital Twin (NEDT).
https://github.com/nedt-ireland/nedt-ontology
```
