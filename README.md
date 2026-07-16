# NEDT Ontology — National Energy Digital Twin

A modular OWL ontology for the National Energy Digital Twin (NEDT) of the Irish residential energy system.

[![Ontology](https://img.shields.io/badge/format-OWL%2FTurtle-blue)](DT_ontology.ttl)
[![Version](https://img.shields.io/badge/version-1.3.0-green)](DT_ontology.ttl)
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

### Option 1 — WebVOWL (ontology class diagram, no install)

WebVOWL renders the ontology as an interactive node-link diagram showing all classes and properties.

**Step 1 — Open WebVOWL**
Go to [service.tib.eu/webvowl](https://service.tib.eu/webvowl) in your browser.

**Step 2 — Load the ontology**
- Click **`Ontology`** in the bottom bar
- Select **`Upload local ontology file`**
- Choose `DT_ontology.ttl` from this repo

**Step 3 — Explore**
- Pan and zoom the class graph
- Click any node to see its properties and relationships
- Use the **Filter** panel (bottom bar) to show/hide modules
- Use **Search** (top bar) to jump to a specific class e.g. `LVStation`

**Step 4 — Share with your team**
- Click **`Export`** → **`Share current ontology`**
- Copy the permalink URL — anyone with it sees the same view instantly, no account needed

---

### Option 2 — Interactive HTML viewers (GitHub Pages)

Once GitHub Pages is enabled on this repo, open these directly in any browser:

| Viewer | What it shows |
|---|---|
| [DT_kg_viewer.html](DT_kg_viewer.html) | Full interactive knowledge graph — click nodes, filter by class |
| [DT_kg_visualiser.html](DT_kg_visualiser.html) | Alternative KG layout |
| [ontology_diagrams.html](ontology_diagrams.html) | 9 SVG panels — one per ontology module |
| [ontology_positioning.html](ontology_positioning.html) | Coverage matrix vs existing ontologies |
| [ontology_relations.html](ontology_relations.html) | Class relations view |

**To enable GitHub Pages:**
1. Go to the repo on GitHub → **Settings** → **Pages**
2. Source: `main` branch, folder `/` (root) → click **Save**
3. Your viewers will be live at `https://buildinginformaticslab.github.io/nedt-ontology/`

---

## Repository Contents

| File | Description |
|---|---|
| `DT_ontology.ttl` | Core OWL ontology — 92 classes, 95 properties, 11 modules (incl. IEC CIM alignment) |
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

### Standards Alignment

Module 11 of `DT_ontology.ttl` provides bridge axioms mapping the NEDT network vocabulary to the IEC Common Information Model — [IEC 61970-301](https://webstore.iec.ch/publication/62698) (Core/Wires/Meas) and IEC 61968 (Common, Metering) — using the CIM100 namespace published with CGMES 3.0. The module asserts terminological alignment (e.g. `nedt:LVStation ⊑ cim:Substation`, `nedt:StationCapacity` ↔ `cim:PowerTransformerEnd.ratedS` / `cim:ApparentPowerLimit`) and explicitly declares NEDT's scenario, utilisation-banding, and overload-attribution classes as contributions beyond CIM scope. It is an alignment of vocabulary only — no CGMES profile conformance or IEC 61968 message-interface compliance is claimed.

---

## Authors

- Divyanshu Sood
- Cathal Hoare
- Sharon Coffee
- James O'Donnell

---

## Citation

If you use this ontology, please cite:

```
Sood, D., Coffee, S., O'Donnell, J. (2026).
A Modular Ontology for the National Energy Digital Twin (NEDT).
https://github.com/buildinginformaticslab/nedt-ontology
```
