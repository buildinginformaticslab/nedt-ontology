# A Modular Ontology for the National Energy Digital Twin (NEDT)

**Author:** Divyanshu Sood
**Version:** 1.0.0 — 2026-04-20
**Artefacts:** `DT_ontology.ttl` (OWL/Turtle), `ontology_diagrams.html` (9 SVG figures)

---

## Abstract

We present the National Energy Digital Twin (NEDT) ontology, a modular OWL specification describing the entities, observations, calculations and scenarios that underpin a residential energy digital twin for Ireland. The ontology binds together (i) a national archetype-count dataset (2.1 M dwellings, 702 archetype signatures), (ii) hourly Nexsys profiles providing electricity, heat, EV-charging and rooftop-PV generation at archetype granularity, (iii) ESB Networks low-voltage substation geometries and capacities, and (iv) SEAI domestic-PV grant records. It reuses SSN/SOSA for observations, OWL-Time for temporal intervals, OM-2 for units of measure, and GeoSPARQL for spatial geometries. Its structural backbone follows the Li et al. (2019) EM-KPI pattern, with KPI classes linked to KPI-evaluated objects through calculation procedures. Ten modules are defined: KPI, Archetype, Scenario, Energy Load, LV Network, Attribution, Heat Density, Visualisation, Geography, and Rooftop PV.

## 1. Motivation

A digital twin of the Irish residential electricity system must reconcile heterogeneous inputs — statistical archetype counts, simulation-derived hourly profiles, network geometry, and evolving policy scenarios — within a single machine-interpretable model. An ontology supplies the shared vocabulary required for (a) reproducibility of scenario runs, (b) cross-county comparability of KPIs, (c) downstream SPARQL-style queries over archetype–substation–scenario joins, and (d) publication of the model as a FAIR research object.

## 2. Design principles

1. **Modularity.** Ten module boundaries separate concerns (KPI, Archetype, Scenario, Load, LV, Attribution, Heat Density, Visualisation, Geography, PV) so each can evolve independently.
2. **Reuse over reinvention.** Where a W3C ontology exists, we subclass or directly reference it (e.g., `cdt:KPICalculation ⊑ ssn:Procedure`, `cdt:County ⊑ geo:Feature`).
3. **Provenance by construction.** Every `HourlyProfile` is linked to the `DatumSource` that produced it, and every `Scenario` to the `TransitionLedger` that records its allocation.
4. **Policy-facing vocabulary.** Class names (`HPScenario`, `EVScenario`, `PVAdoptionScenario`, `BERFallbackRule`) map directly to instruments used by Irish stakeholders (SEAI, CRU, ESB Networks, DoE).

## 3. Module specification

### 3.1 KPI module
Built from the Li et al. EM-KPI skeleton: `Stakeholder → PerformanceGoal → KPI → KPICalculation → KPIValue`. Strategic, Tactical and Operational KPIs form a three-tier hierarchy. KPIs evaluate a `KPIEvaluatedObject` — either a `County`, an `LVStation`, an `Archetype`, or a `Scenario`. Evaluation intervals reuse `time:Interval`; values carry `om:Unit_of_measure`.

### 3.2 Archetype module
An `Archetype` is identified by five descriptors: `BuildType × BER × Occupancy × HeatingSystem × WeatherClassification`. `ArchetypeCount` instances are county-scoped observations (`ArchCount_original`, `ArchCount_EV`, `ArchCount_NoEV`). A `BERFallbackRule` encodes substitutions when no direct profile exists (e.g., F/G folded onto E). A `ProfileKey` maps each archetype to the appropriate Nexsys profile. 702 archetype signatures are present across the 26-county archetype-count dataset; of these, 42 have a direct Nexsys match, 36.3% require occupancy fallback, and 19.6% (chiefly F/G BER) use a further BER fallback.

### 3.3 Scenario module
`HPScenario`, `EVScenario` and the new `PVAdoptionScenario` are subclasses of `Scenario`. `EVMode` distinguishes uncontrolled / Tier-3 / Tier-4 / V1H / V2H charging policies. A `TransitionLedger` records how dwellings migrate between archetypes under a scenario, with `LargestRemainderAlloc` as the default allocation procedure for integer-preserving rounding across the 26 counties.

### 3.4 Energy Load module
`ElectricLoad ⊑ EnergyLoad` and `HeatLoad ⊑ EnergyLoad` carry hourly time series derived from `NexsysProfile` observations. `CO2Emission` is an observation value attached to `EnergyLoad` via `hasCO2`. `LoadCalculation` procedures orchestrate the join between `ArchetypeCount`, `NexsysProfile`, `EVScenario`, `HPScenario` and (new) `PVSystem`.

### 3.5 LV Network module
An `LVStation` has a `HullPolygon` geometry (assigned from ESB Networks records), a `StationCapacity`, and hourly `StationLoad`. `Utilisation = Load / Capacity` is bucketed into a `UtilisationStatus` (green ≤ 80%, yellow 80–100%, red-maroon > 100%). `BuildingShare` captures the proportion of each archetype assigned to the station.

### 3.6 Attribution module
`OverloadedStation ⊑ LVStation` instances are explained by `OverloadAttribution`, which ranks per-hour contributions of `EV`, `HP` and `PV` via `ContribRank` and `DominantDriver`. A `RiskTable` enumerates all overloaded stations per scenario.

### 3.7 Heat Density module
`HeatDensityGDF` carries per-cell `HeatDensity` observations with fuel-specific components (`HeatFuelComponent`) — supporting district-heating feasibility analyses at county scale.

### 3.8 Visualisation module
`FigCollector` is an in-memory buffer aggregating `DeckGLMap` and `ChartJSChart` outputs. `HTMLReport` composes `ReportSection` instances with a consistent `ColourPalette`. All maps are bound to `GeoLocation ⊑ geo:Feature`.

### 3.9 Geography module
`County ⊑ geo:Feature` is the top-level spatial anchor. `County contains LVStation`; `County hasArchetype Archetype`.

### 3.10 Rooftop PV module (new)
A `PVSystem` is a dwelling-mounted photovoltaic installation characterised by `installedCapacity_kWp` and one `PVGenerationProfile`. Empirical analysis of 69 archetype-resolved Nexsys PV columns (pairwise shape-correlation ≥ 0.88, cosine similarity of per-bin mean shapes ≥ 0.96) justifies collapsing the profile family into a single `PVReferenceShape` — the mean, normalised, 1 kWp curve (~1095 kWh/yr). Per-dwelling generation is therefore computed as `reference_shape × installedCapacity_kWp`. Apartments are excluded; all BER letters A–E are admitted. The `PVCapacityMix` distribution defaults to the 2017 Irish reference: 10 / 47 / 23 / 6 / 11 / 3 % at 1–6 kWp. A `PVAdoptionScenario` either (a) inherits `adoptionFraction` from the cumulative `SEAIGrantRecord` for "as-is" runs or (b) accepts a user-supplied fraction in scenario runs. A `NettingProcedure` subtracts PV generation from electric load per dwelling and clamps the result at zero (no-export assumption), producing a `NetLoad ⊑ ElectricLoad`.

### 3.11 Methodology overview (Fig 2)

The eight-stage methodology that delivers the NEDT — CQ elicitation, reuse survey, gap analysis, T-Box + SHACL formalisation, A-Box population, SHACL gating, DT execution, and stakeholder delivery — is summarised in **Fig 2** (`fig_methodology.html`). The figure is composed in the convention of Kämpf et al. (2025, *J Build Perf Simul*) and Hao et al. (2024, *Sustain Cities Soc*): the **upper tier** is a horizontal BPMN-style pipeline of the eight stages (S1 – S8), with a dashed feedback arc that makes the v1.1 → v1.2 refinement loop explicit — supervisor priorities on district-heating viability and LV flexibility elicited in 2026 introduced CQ13·14·15, triggered a re-pass through S2–S4, and added 7 classes, 6 properties and 5 SHACL shapes without disturbing any v1.1 artefact. The **lower tier** is the cross-scale rollup (Dwelling → Archetype → LV station → SA / thermal cluster → County → National) adapted from Hao et al.'s building → district → city nesting to the Irish DSO/TSO scale stack; vertical dashed arrows show where each scale enters the upper-tier pipeline, and per-scale chips label the CQs answered at that scale. Fig 2 thereby serves as the single traceable diagram from research question to stakeholder KPI.

## 4. External ontology alignment

| External ontology | Imported concepts |
|---|---|
| SSN / SOSA (W3C) | `ssn:Observation`, `ssn:ObservationValue`, `ssn:Procedure`, `ssn:hasInput`, `ssn:hasOutput` |
| OWL-Time (W3C) | `time:Interval`, `time:Instant`, `time:hasBegin`, `time:hasEnd` |
| OM-2 | `om:Unit_of_measure` |
| GeoSPARQL (OGC) | `geo:Feature`, `geo:Geometry` |
| DCT | `dct:identifier`, `dct:title`, `dct:creator` |
| BOT (W3C-CG) | `bot:Building` (re-used for the dwelling level of `cdt:Archetype`) |
| SARAGON | `saragon:Transformer` (`owl:equivalentClass cdt:LVStation`), `saragon:DistributionNode`, `saragon:hasServiceArea` |
| GeoDirectory (An Post / OSi) | `gd:GeoAddress`, `gd:Building` (re-used at the dwelling / county anchor) |
| OSi | `osi:County` |

## 4.1 Contribution layering — existing shared KG vs. DT-model extension

The NEDT ontology is explicitly layered against the **utility-aware knowledge-graph (UA-KG)** framework of Hoare, Coffee, Sood, Margaria & O'Donnell (EC3 2026), which federates GeoDirectory, SEAI BER, CSO SAPS and OSi/OSNI through a shared core-context spine (DDIM-brokered, `owl:sameAs` horizontal, `owl:part-of` vertical). Every class in `cdt:` therefore carries a `cdt:layer` annotation (an `owl:AnnotationProperty`) whose value is one of:

- **`core-KG-framework`** — the class already exists in the UA-KG backbone or in an aligned standard ontology (BOT, SARAGON, GeoSPARQL, GeoDirectory, OSi). For these classes, `owl:equivalentClass` or `rdfs:seeAlso` cross-references are asserted so that an OWL reasoner can federate the two graphs.
- **`DT-model-extension`** — the class is contributed by this work and would not appear in a purely UA-KG deployment.

Table 1 summarises the split across the ten NEDT modules.

| Module | Core KG framework (existing) | DT-model extension (this work) |
|---|---|---|
| KPI | `Stakeholder`, `DatumSource` | `PerformanceGoal`, `KPI`, `StrategicKPI`, `TacticalKPI`, `OperationalKPI`, `KPIEvaluatedObject`, `KPICalculation`, `KPIValue` |
| Archetype | `Archetype` (≡ `bot:Building` / `gd:Building`), `ArchetypeDescriptor` | `ArchetypeCount`, `ProfileKey`, `BERFallbackRule`, `TransitionKey` |
| Scenario | — | `Scenario`, `HPScenario`, `EVScenario`, `EVMode`, `HPTransition`, `TransitionLedger`, `LargestRemainderAlloc`, `PVAdoptionScenario` |
| Energy Load | — | `EnergyLoad`, `ElectricLoad`, `HeatLoad`, `NetLoad`, `CO2Emission`, `LoadMetric`, `LoadCalculation`, `HourlyProfile`, `NexsysProfile`, `DeltaSeries` |
| LV Network | `LVStation` (≡ `saragon:Transformer`), `HullPolygon` (↔ `geo:Geometry` / `saragon:hasServiceArea`), `BuildingShare` | `StationCapacity`, `StationLoad`, `Utilisation`, `UtilisationStatus` |
| Attribution | — | `OverloadedStation`, `OverloadAttribution`, `ContribRank`, `DominantDriver`, `RiskTable`, `StationTransition`, `TopTransitions` |
| Heat Density | — | `HeatDensityGDF`, `HeatFuelComponent`, `HeatDensity`, `CountySummary` |
| Visualisation | — | `FigCollector`, `DeckGLMap`, `ChartJSChart`, `HTMLReport`, `ReportSection`, `ColourPalette` |
| Geography | `County` (↔ `osi:County` / `gd:GeoAddress`), `GeoLocation` (≡ `geo:Feature`) | — |
| Rooftop PV | — | `PVSystem`, `PVGenerationProfile`, `PVReferenceShape`, `PVCapacityBin`, `PVCapacityMix`, `SEAIGrantRecord`, `NettingProcedure`, `NetLoad` |

**Tallies.** 9 classes (13 %) are re-used from the UA-KG core; 59 classes (87 %) are NEDT extensions. The instance viewer (`DT_kg_viewer.html`) renders the two layers with distinct colour and shape (blue dots = core KG framework; orange diamonds = DT extension) and a fixed legend, so that reviewers can see at a glance which part of the graph is novel to this paper and which part is inherited from the shared Irish digital-twin fabric.

**Why this matters.** The UA-KG paper establishes a minimum-viable, utility-aware backbone for the Irish residential sector: buildings, addresses, meters, LV transformers and their service areas. The NEDT ontology layers on top of that backbone the **simulation, scenario, attribution, KPI and visualisation semantics** needed to answer county-scale policy questions about heat pumps, EVs and rooftop PV. Keeping the two layers explicit means the NEDT schema remains compatible with any downstream consumer that speaks BOT / SARAGON / GeoDirectory, while also being publishable as a stand-alone FAIR research object.

## 5. Use cases

1. **SPARQL querying.** "List all LV stations whose overload is dominated by HP uptake under the 2030 HP80 scenario in Co. Clare." — joinable via `OverloadAttribution → DominantDriver → HPScenario → County`.
2. **KPI evaluation across scenarios.** "Peak LV utilisation (≤ 85 %) evaluated hourly per substation under Scenario X." — anchored in `KPI → KPICalculation → KPIValue`.
3. **Policy trade-offs.** "Does PV adoption at 30 % of eligible dwellings offset HP-driven winter peaks in Co. Wicklow?" — joins `PVAdoptionScenario` with `HPScenario` under the shared `LoadCalculation`.
4. **Data provenance audit.** Every `KPIValue` is traceable through `KPICalculation → DatumSource` back to the originating CSV/GeoJSON.

## 6. Reproducibility and FAIR notes

The Turtle file (`DT_ontology.ttl`) is suitable for direct consumption by OWL reasoners (HermiT, ELK). The 10 module diagrams (`ontology_diagrams.html`) render as SVG and PNG for inclusion as paper figures. An instance-level graph populated from the 26-county archetype counts and the Nexsys profile catalogue is the next deliverable, suitable for serialisation as JSON-LD or loading into Neo4j for interactive exploration.

## 7. Limitations

- Archetype-level granularity stops short of individual dwellings; address-level joining to SEAI grants is left for future work.
- The PV module assumes a single climate zone for Ireland; future regional disaggregation would require multiple `PVReferenceShape` instances.
- BER F/G classes are represented structurally but their profiles are derived via `BERFallbackRule` rather than from simulation, a known limitation inherited from the Nexsys input set.

## 8. Competency questions

Following Grüninger & Fox (1995), the ontology is scoped and evaluated against a fixed list of **competency questions (CQs)** the populated knowledge graph must be able to answer. Each CQ is grounded in an output produced by the reference implementation (`Trials_andthen_intoMAIN.ipynb`) and is answered by a SPARQL query in Appendix A.

**Archetype & building layer**
- **CQ1** — For county *X*, what dwelling archetypes exist (BER class × dwelling type × floor-area band × construction period), and how many buildings fall in each?
- **CQ2** — For a given archetype under baseline conditions, what is the 8760-hour electrical and thermal load profile decomposed into space heat, DHW, appliance, cooking, lighting?

**Scenario & transition layer**
- **CQ3** — Under scenario *S* in year *Y*, what fraction of archetype *A* has converted to heat-pump heating, EV ownership, and rooftop PV kWp, and which source justifies each parameter?
- **CQ4** — For a specific building under scenario *S* year *Y*, what is the net hourly electrical demand after HP replacement of fossil heat, EV charging, and PV self-consumption?

**LV network layer**
- **CQ5** — For LV station *T* in county *X* at hour *H* under scenario *S* / year *Y*, what is the aggregate demand, and which archetypes dominate it (kWh share)?
- **CQ6** — Which LV stations exceed nameplate capacity at any hour of year *Y* under scenario *S*, and what fraction of the overload is attributable to HP / EV / PV reverse-flow / baseline?
- **CQ7** — For archetype *A* with PV system *P* under scenario *S*, what is the annual self-consumption ratio, grid export, and number of hours of reverse-power flow at the LV transformer?

**County and national KPI layer**
- **CQ8** — For county *X*, scenario *S*, year *Y*: what is the coincident electrical peak (MW, date-time) and annual CO₂ (tCO₂), broken down by end-use?
- **CQ9** — What is the national peak demand, annual energy and CO₂ under scenario *S* / year *Y*, and which counties contribute most to the national peak?
- **CQ10** — Which LV stations / counties require reinforcement (sustained overload > *N* h / yr) between baseline and 2050 under scenario *S*, and in which year do they first breach capacity?

**Sensitivity & provenance**
- **CQ11** — Which input parameter (HP uptake %, EV uptake %, PV kWp, occupancy) has the largest marginal effect on county peak and CO₂ for scenario *S* in year *Y*?
- **CQ12** — For a given KPI value (e.g. Louth 2035 peak under S2), which datasets, transformation steps, and scenario assumptions produced it?

**Heat-density and flexibility layer (supervisor-priority CQs, added v1.2)**
- **CQ13** — *Which areas are district-heating viable?* For each grid cell / SA-cluster in county *X* under scenario *S* / year *Y*, is the annual thermal-demand density ≥ the viability threshold (default 120 kWh/m²·yr, EU Heat Roadmap 4 convention), and which contiguous clusters satisfy it?
- **CQ14** — *Which areas would benefit from group heating schemes?* Which contiguous archetype clusters have (i) high shared-heat potential (annual thermal demand 50–120 kWh/m²·yr), (ii) compact footprint (compactness ratio ≥ 0.6), and (iii) dwelling-type / period compatibility suitable for a shared boiler / heat-pump plant?
- **CQ15** — *What is the flexibility for each LV node?* For LV station *T* under scenario *S* / year *Y*, what fraction of aggregate load is controllable (HP + EV), what is the shiftable kW over a 2-hour demand-response window, and what is the resulting demand-response capacity headroom against nameplate?


## 9. Gap analysis — existing ontologies vs. competency questions

NEDT does not attempt to re-invent the utility-aware knowledge-graph backbone. Each CQ is first mapped against coverage offered by existing standard ontologies (BOT, SARAGON / SAREF4ENER, GeoDirectory, OSi, GeoSPARQL, QUDT, OWL-Time, PROV-O). Only where those ontologies cannot answer a CQ does NEDT contribute a new class or property.

Legend: ● full (s=2) · ◐ partial (s=1) · ○ none (s=0). Row `% coverage` is `Σs / (2 × n_CQ) × 100` with `n_CQ = 15` (max 30 score points per row, including CQ13–15 added in v1.2). Earlier drafts over-credited QUDT and OWL-Time as "full" on every CQ involving units or time; the revised scoring below tests substantive contribution to the CQ (not mere re-use of a datatype).

| CQ | BOT | SARAGON / SAREF4ENER | GeoDirectory / OSi | GeoSPARQL | QUDT | OWL-Time | PROV-O | Best-of existing | Gap filled by NEDT |
|----|-----|----------------------|--------------------|-----------|------|----------|--------|------------------|--------------------|
| CQ1 | ◐ topology | ○ | ● address, admin area | ◐ | ○ | ○ | ○ | ● | typed archetype descriptors (BER, dwelling, period) |
| CQ2 | ○ | ◐ undifferentiated load | ○ | ○ | ○ | ◐ interval | ○ | ◐ | end-use-typed load decomposition |
| CQ3 | ○ | ○ | ○ | ○ | ○ | ◐ instant | ◐ | ◐ | scenario parameter + transition ledger |
| CQ4 | ◐ | ◐ no netting | ○ | ○ | ○ | ◐ | ○ | ◐ | PV-netted load (`cdt:NetLoad`) + end-use composition |
| CQ5 | ◐ | ● transformer / service area | ● | ● | ○ | ◐ | ○ | ● | `cdt:LVAggregation` + alignment to `saragon:Transformer` |
| CQ6 | ○ | ◐ nameplate only | ○ | ○ | ◐ kW unit | ◐ | ○ | ◐ | overload-event + end-use attribution |
| CQ7 | ○ | ◐ generation only | ○ | ○ | ○ | ◐ | ○ | ◐ | self-consumption / export / reverse-flow KPI values |
| CQ8 | ○ | ◐ | ● county boundary | ● | ◐ MW unit | ◐ | ○ | ● | county-scoped KPI + end-use split |
| CQ9 | ○ | ○ | ● national | ● | ◐ MW unit | ◐ | ○ | ● | national rollup + county contribution |
| CQ10 | ○ | ◐ | ● | ● | ○ | ◐ multi-year | ○ | ● | reinforcement-need + first-breach-year |
| CQ11 | ○ | ○ | ○ | ○ | ○ | ○ | ◐ | ◐ | sensitivity run + marginal-effect ranking |
| CQ12 | ○ | ○ | ○ | ○ | ○ | ◐ | ● entity / activity | ● | **reuse PROV-O** with only typing axioms |
| CQ13 | ○ | ○ | ◐ SA boundary | ◐ spatial join | ◐ kWh/m² unit | ○ | ○ | ◐ | `cdt:HeatDensity` · `cdt:ThermalDemandCluster` · `cdt:DHViabilityKPI` |
| CQ14 | ○ | ○ | ◐ SA cluster | ◐ compactness via geom. | ○ | ○ | ○ | ◐ | `cdt:GroupHeatingCandidate` · `cdt:clusterCompactness` |
| CQ15 | ○ | ◐ SAREF4ENER shiftable | ○ | ○ | ◐ kW unit | ◐ DR window interval | ○ | ◐ | `cdt:FlexibleLoad` · `cdt:FlexibilityKPI` · `cdt:DemandResponseCapacity` |
| **% coverage** | **10.0 %** | **30.0 %** | **40.0 %** | **36.7 %** | **16.7 %** | **36.7 %** | **13.3 %** | **70.0 %** | **100.0 %** |

Reading the "Best-of existing" column as the per-CQ maximum across every reused ontology, the union leaves a residual of 30 % — the CQs that require Irish administrative framing (CQ1), load decomposition (CQ2, CQ4, CQ6, CQ7), scenario trajectories (CQ3), sensitivity ranking (CQ11), **and the supervisor-priority trio CQ13–CQ15 covering district-heating viability, group-heating candidates, and LV-node flexibility**. These are the cells the NEDT extension fills. A companion matrix is distributed alongside the ontology in `ontology_positioning.html` (coverage-matrix view).

The seven gap clusters are:

1. **Irish-specific archetype semantics** — BOT provides topology; no standard ontology types BER classes, SEAI dwelling types, or construction-period bands.
2. **End-use load decomposition & PV netting** — SAREF4ENER gives monolithic consumption and generation; it does not decompose load into space-heat, DHW, appliance, cooking, lighting, EV and HP-replacement components keyed to an archetype.
3. **Scenario / transition ledger** — SAREF4ENER models energy systems, not uptake trajectories. NEDT contributes `cdt:Scenario`, `cdt:TransitionLedger`, `cdt:UptakeFraction`, `cdt:ScenarioParameter`.
4. **LV aggregation and causal attribution** — SARAGON describes the asset and its service area; it does not describe which archetypes caused which feeder to exceed capacity in which hour. NEDT contributes `cdt:LVAggregation`, `cdt:OverloadEvent`, `cdt:EndUseContribution`.
5. **Administrative-area KPIs** — OSi / GeoDirectory provide geography; NEDT ties energy KPIs to counties, scenarios and years via `cdt:CountyKPI`, `cdt:CoincidentPeak`, `cdt:ReinforcementNeed`, etc.
6. **Heat-density & district-heating viability (CQ13–CQ14)** — no reused ontology connects annual thermal demand (kWh/m²·yr) to administrative clusters nor encodes a viability verdict. NEDT contributes `cdt:HeatDensity`, `cdt:ThermalDemandCluster`, `cdt:DHViabilityKPI`, `cdt:GroupHeatingCandidate` and the `clusterCompactness` / `viabilityThreshold_kWh_per_m2_yr` / `isDHViable` properties. The threshold literal carries provenance back to the EU Heat Roadmap 4 assumption.
7. **LV-node flexibility (CQ15)** — SAREF4ENER models a shiftable-load profile at *device* scale; it does not carry an LV-node flexibility KPI or demand-response capacity scoped to county / scenario / year. NEDT contributes `cdt:FlexibleLoad` (⊑ `cdt:EndUseLoad`), `cdt:FlexibilityKPI` and `cdt:DemandResponseCapacity`.

Provenance (CQ12) is handled by **reusing PROV-O** with only two typing axioms (`cdt:DTRun ⊑ prov:Activity`, `cdt:ScenarioAssumption ⊑ prov:Entity`); no new provenance vocabulary is introduced.

### 9.1 NEDT classes and properties introduced for CQ coverage

The following classes and properties are proposed as NEDT additions required for the CQs above. They are marked *new in v1.1* relative to the v1.0.0 Turtle file.

**New classes (18)**

| IRI | Parent | Purpose | Answers |
|-----|--------|---------|---------|
| `cdt:BERRating` | `cdt:ArchetypeDescriptor` | Typed BER letter (A1…G) | CQ1 |
| `cdt:DwellingType` | `cdt:ArchetypeDescriptor` | Detached / semi-d / terrace / apartment | CQ1 |
| `cdt:ConstructionPeriod` | `cdt:ArchetypeDescriptor` | Pre-1919, 1919–1945, … post-2011 | CQ1 |
| `cdt:EndUseLoad` | `cdt:EnergyLoad` | Load tagged by end-use (space_heat, DHW, appliance, lighting, cooking, EV, HP_replace) | CQ2, CQ4, CQ6 |
| `cdt:ScenarioParameter` | — | One parameter (HP % / EV % / PV kWp) per archetype per year; value via `cdt:uptakeValue` | CQ3 |
| `cdt:LVAggregation` | `ssn:Procedure` | Procedure that aggregates building-level load to an LV station | CQ5 |
| `cdt:OverloadEvent` | — | Single-hour exceedance of station capacity | CQ6, CQ10 |
| `cdt:EndUseContribution` | `cdt:ContribRank` | Share of an overload attributable to an end-use | CQ6 |
| `cdt:SelfConsumptionRatio` | `cdt:KPIValue` | Annual PV self-consumption | CQ7 |
| `cdt:ExportedEnergy` | `cdt:KPIValue` | Annual PV export to grid | CQ7 |
| `cdt:ReversePowerFlowHour` | — | Hour with negative net flow at transformer | CQ7 |
| `cdt:CoincidentPeak` | `cdt:KPIValue` | County / national peak MW and time-stamp | CQ8, CQ9 |
| `cdt:CountyKPI` | `cdt:KPI` | KPI scoped to a county | CQ8 |
| `cdt:NationalKPI` | `cdt:KPI` | KPI scoped to national rollup | CQ9 |
| `cdt:ReinforcementNeed` | `cdt:KPIValue` | Indicates station / county needs reinforcement | CQ10 |
| `cdt:SensitivityRun` | `prov:Activity` | A parameter-sweep execution | CQ11 |
| `cdt:DTRun` | `prov:Activity` | A single notebook execution producing KPIs | CQ12 |
| `cdt:ScenarioAssumption` | `prov:Entity` | A sourced assumption underpinning a scenario parameter | CQ12 |

**New classes added in v1.2 (7 — heat-density & flexibility)**

| IRI | Parent | Purpose | Answers |
|-----|--------|---------|---------|
| `cdt:HeatDensity` | `sosa:ObservableProperty` | Annual thermal demand per unit area (kWh/m²·yr) at grid cell / SA / cluster | CQ13, CQ14 |
| `cdt:ThermalDemandCluster` | — (seeAlso `bot:Zone`) | Contiguous group of cells / archetypes above a density threshold | CQ13, CQ14 |
| `cdt:DHViabilityKPI` | `cdt:KPIValue` | Carries the DH viability verdict + threshold used | CQ13 |
| `cdt:GroupHeatingCandidate` | `cdt:ThermalDemandCluster` | Mid-density cluster suitable for a shared-plant scheme | CQ14 |
| `cdt:FlexibleLoad` | `cdt:EndUseLoad` | Controllable subset of an end-use (HP, EV, DHW, space_heat) | CQ15 |
| `cdt:FlexibilityKPI` | `cdt:KPIValue` | Shiftable kW at an LV station under a stated DR window | CQ15 |
| `cdt:DemandResponseCapacity` | `cdt:KPIValue` | LV-node head-room available to a DR programme | CQ15 |

**New properties (14 in v1.1 + 6 in v1.2 = 20 total)**

| IRI | Domain → Range | Purpose |
|-----|----------------|---------|
| `cdt:endUse` | `cdt:EndUseLoad` → `xsd:string` | End-use enum |
| `cdt:hasScenarioParameter` | `cdt:Scenario` → `cdt:ScenarioParameter` | Binds a parameter to its scenario |
| `cdt:forArchetype` | `cdt:ScenarioParameter` → `cdt:Archetype` | Parameter applies to this archetype |
| `cdt:forYear` | `cdt:ScenarioParameter` → `xsd:gYear` | Parameter applies to this year |
| `cdt:uptakeValue` | `cdt:ScenarioParameter` → `xsd:decimal` | Numeric fraction 0–1 (or kWp for PV) |
| `cdt:occursAt` | `cdt:OverloadEvent` → `xsd:dateTime` | Hour of exceedance |
| `cdt:overloadMagnitude_kW` | `cdt:OverloadEvent` → `xsd:decimal` | kW over capacity |
| `cdt:attributedToEndUse` | `cdt:EndUseContribution` → `cdt:EndUseLoad` | Which end-use drove it |
| `cdt:contributionPercent` | `cdt:EndUseContribution` → `xsd:decimal` | 0–100 share |
| `cdt:evaluatesCounty` | `cdt:KPIValue` → `cdt:County` | County scope of the measurement |
| `cdt:evaluatesYear` | `cdt:KPIValue` → `xsd:gYear` | Year scope of the measurement |
| `cdt:derivedUnder` | `cdt:KPIValue` → `cdt:Scenario` | Scenario that produced the value |
| `cdt:firstBreachYear` | `cdt:ReinforcementNeed` → `xsd:gYear` | First year station overloaded |
| `cdt:breachHours` | `cdt:ReinforcementNeed` → `xsd:integer` | Hours of overload in year |
| `cdt:heatDemand_kWh_per_m2_yr` *(v1.2)* | `cdt:HeatDensity` → `xsd:decimal` | Annual thermal demand per m² |
| `cdt:viabilityThreshold_kWh_per_m2_yr` *(v1.2)* | `cdt:DHViabilityKPI` → `xsd:decimal` | Threshold literal (default 120, EU Heat Roadmap 4) |
| `cdt:isDHViable` *(v1.2)* | `cdt:DHViabilityKPI` → `xsd:boolean` | Viability verdict |
| `cdt:clusterCompactness` *(v1.2)* | `cdt:ThermalDemandCluster` → `xsd:decimal` | Compactness ratio (0–1), used by CQ14 |
| `cdt:flexibilityKW` *(v1.2)* | `cdt:FlexibilityKPI` → `xsd:decimal` | Shiftable kW at the LV node |
| `cdt:controllableFraction` *(v1.2)* | `cdt:FlexibleLoad` → `xsd:decimal` | Fraction of end-use that is DR-addressable |

Provenance associations (`prov:used`, `prov:generated`, `prov:wasDerivedFrom`) are **reused directly** from PROV-O and do not require new properties.

### 9.2 Classes reused from the v1.0.0 ontology

The majority of the triple patterns in Appendix A resolve against classes that already exist in the published Turtle file: `cdt:Archetype`, `cdt:ArchetypeCount`, `cdt:County`, `cdt:LVStation`, `cdt:StationCapacity`, `cdt:StationLoad`, `cdt:Utilisation`, `cdt:Scenario` (and the HP / EV / PV subclasses), `cdt:TransitionLedger`, `cdt:ElectricLoad`, `cdt:HeatLoad`, `cdt:NetLoad`, `cdt:CO2Emission`, `cdt:HourlyProfile`, `cdt:NexsysProfile`, `cdt:PVSystem`, `cdt:PVGenerationProfile`, `cdt:OverloadedStation`, `cdt:OverloadAttribution`, `cdt:DominantDriver`, `cdt:RiskTable`, `cdt:DatumSource`, `cdt:SEAIGrantRecord`, `cdt:KPI` and its subclasses, `cdt:KPICalculation`, `cdt:KPIValue`, `cdt:DeltaSeries`.


## Appendix A. SPARQL skeletons for the competency questions

All queries assume the NEDT namespace and shared prefixes:

```sparql
PREFIX cdt:  <https://example.org/cdt#>
PREFIX ssn:  <http://www.w3.org/ns/ssn/>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX time: <http://www.w3.org/2006/time#>
PREFIX geo:  <http://www.opengis.net/ont/geosparql#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
```

**CQ1 — Archetypes per county**

```sparql
SELECT ?county ?ber ?dwelling ?period (SUM(?n) AS ?buildings) WHERE {
  ?c a cdt:County ; rdfs:label ?county .
  ?ac a cdt:ArchetypeCount ; cdt:inCounty ?c ; sosa:hasSimpleResult ?n .
  ?arch cdt:hasCount ?ac ; cdt:hasDescriptor ?bR, ?dT, ?cP .
  ?bR a cdt:BERRating       ; rdfs:label ?ber .
  ?dT a cdt:DwellingType    ; rdfs:label ?dwelling .
  ?cP a cdt:ConstructionPeriod ; rdfs:label ?period .
  FILTER (?county = "Louth")
} GROUP BY ?county ?ber ?dwelling ?period
```

**CQ2 — Baseline 8760 h load decomposition for an archetype**

```sparql
SELECT ?hour ?endUse ?kWh WHERE {
  ?arch a cdt:Archetype ; rdfs:label "SD_B1_fam_HP_mild" .
  ?calc a cdt:LoadCalculation ; cdt:computesLoad ?load ;
        cdt:usesProfile ?prof .
  ?load a cdt:EndUseLoad ; cdt:endUse ?endUse ;
        sosa:hasSimpleResult ?kWh .
  ?prof time:inTemporalPosition ?hour .
}
```

**CQ3 — Scenario uptake fractions for an archetype**

```sparql
SELECT ?archLabel ?param ?year ?fraction ?source WHERE {
  ?s a cdt:Scenario ; rdfs:label "S2_2035" ;
     cdt:hasScenarioParameter ?p .
  ?p cdt:forArchetype ?arch ;
     cdt:forYear ?year ;
     rdfs:label ?param ;
     cdt:uptakeValue ?uf ;
     prov:wasDerivedFrom ?source .
  ?uf cdt:uptakeValue ?fraction .
  ?arch rdfs:label ?archLabel .
}
```

**CQ4 — PV-netted hourly demand for one building**

```sparql
SELECT ?hour ?netKWh WHERE {
  ?b a bot:Building ; rdfs:label "B_12345" ;
     cdt:hasArchetype ?arch .
  ?calc a cdt:LoadCalculation ; cdt:computesLoad ?nl ;
        cdt:usesProfile ?prof .
  ?nl a cdt:NetLoad ; cdt:derivedUnder ?s ;
      sosa:hasSimpleResult ?netKWh .
  ?s rdfs:label "S2_2035" .
  ?prof time:inTemporalPosition ?hour .
}
```

**CQ5 — LV station aggregate + dominant archetype share at one hour**

```sparql
SELECT ?station ?hour ?archLabel ?shareKWh WHERE {
  ?lv a cdt:LVStation ; rdfs:label ?station ;
      cdt:hasLoad ?sload ; cdt:hasBldgShare ?bs .
  ?sload cdt:derivedUnder ?s ; sosa:hasSimpleResult ?lvKwh ;
         time:inTemporalPosition ?hour .
  ?bs cdt:forArchetype ?arch ; sosa:hasSimpleResult ?shareKWh .
  ?arch rdfs:label ?archLabel .
  ?s rdfs:label "S2_2035" .
  FILTER (?station = "LV_Louth_0412")
} ORDER BY DESC(?shareKWh)
```

**CQ6 — Overloaded stations and end-use attribution**

```sparql
SELECT ?station ?hour ?endUse ?share WHERE {
  ?lv a cdt:OverloadedStation ; rdfs:label ?station ;
      cdt:hasAttribution ?att .
  ?ev a cdt:OverloadEvent ;
      cdt:occursAt ?hour ;
      cdt:overloadMagnitude_kW ?kW .
  ?att cdt:ranksBy ?rank ; cdt:derivedUnder ?s .
  ?rank a cdt:EndUseContribution ;
        cdt:attributedToEndUse/cdt:endUse ?endUse ;
        cdt:contributionPercent ?share .
  ?s rdfs:label "S2_2035" .
  FILTER (?kW > 0)
} ORDER BY ?station ?hour DESC(?share)
```

**CQ7 — PV self-consumption, export and reverse-flow hours**

```sparql
SELECT ?archLabel ?scr ?exported ?reverseHours WHERE {
  ?arch a cdt:Archetype ; rdfs:label ?archLabel ;
        cdt:hasPVSystem ?pv .
  ?k1 a cdt:SelfConsumptionRatio ; cdt:hasKPIEvaluatedObject ?pv ;
      cdt:derivedUnder ?s ; sosa:hasSimpleResult ?scr .
  ?k2 a cdt:ExportedEnergy ; cdt:hasKPIEvaluatedObject ?pv ;
      cdt:derivedUnder ?s ; sosa:hasSimpleResult ?exported .
  SELECT (COUNT(?r) AS ?reverseHours) WHERE {
    ?r a cdt:ReversePowerFlowHour ; cdt:derivedUnder ?s .
  }
  ?s rdfs:label "S2_2035" .
}
```

**CQ8 — County coincident peak and CO₂ split**

```sparql
SELECT ?county ?peakMW ?peakTime ?endUse ?co2 WHERE {
  ?c a cdt:County ; rdfs:label ?county .
  ?k1 a cdt:CoincidentPeak ; cdt:evaluatesCounty ?c ;
      cdt:evaluatesYear "2035"^^xsd:gYear ; cdt:derivedUnder ?s ;
      sosa:hasSimpleResult ?peakMW ; time:inTemporalPosition ?peakTime .
  ?k2 a cdt:CountyKPI ; cdt:evaluatesCounty ?c ;
      cdt:evaluatesYear "2035"^^xsd:gYear ; cdt:derivedUnder ?s ;
      cdt:hasDisaggregation ?d .
  ?d cdt:attributedToEndUse/cdt:endUse ?endUse ;
     sosa:hasSimpleResult ?co2 .
  ?s rdfs:label "S2_2035" .
}
```

**CQ9 — National rollup and top-contributing counties**

```sparql
SELECT ?county ?countyPeakMW WHERE {
  ?nk a cdt:NationalKPI ; cdt:evaluatesYear "2035"^^xsd:gYear ;
      cdt:derivedUnder ?s ;
      cdt:hasDisaggregation ?ck .
  ?ck a cdt:CountyKPI ; cdt:evaluatesCounty ?c ;
      sosa:hasSimpleResult ?countyPeakMW .
  ?c rdfs:label ?county .
  ?s rdfs:label "S2_2035" .
} ORDER BY DESC(?countyPeakMW) LIMIT 5
```

**CQ10 — Reinforcement-need register with first-breach year**

```sparql
SELECT ?station ?firstYear ?hours2050 WHERE {
  ?lv a cdt:LVStation ; rdfs:label ?station .
  ?r a cdt:ReinforcementNeed ; cdt:hasKPIEvaluatedObject ?lv ;
     cdt:firstBreachYear ?firstYear ;
     cdt:evaluatesYear "2050"^^xsd:gYear ;
     cdt:breachHours ?hours2050 ;
     cdt:derivedUnder ?s .
  ?s rdfs:label "S2" .
  FILTER (?hours2050 > 50)
} ORDER BY ?firstYear
```

**CQ11 — Sensitivity ranking of scenario parameters**

```sparql
SELECT ?param ?dPeak ?dCO2 WHERE {
  ?sr a cdt:SensitivityRun ; cdt:derivedUnder ?s ;
      prov:generated ?m .
  ?m a cdt:KPIValue ; cdt:hasKPIDefinition "marginal_effect" ;
     rdfs:label ?param ;
     cdt:hasDisaggregation ?peakD , ?co2D .
  ?peakD cdt:hasKPIDefinition "d_peak_MW"  ; sosa:hasSimpleResult ?dPeak .
  ?co2D  cdt:hasKPIDefinition "d_CO2_tCO2" ; sosa:hasSimpleResult ?dCO2 .
  ?s rdfs:label "S2_2035" .
} ORDER BY DESC(?dPeak)
```

**CQ12 — Provenance for a specific KPI value**

```sparql
SELECT ?run ?dataset ?assumption WHERE {
  ?kv a cdt:KPIValue ; rdfs:label "peak_Louth_2035_S2" ;
      prov:wasGeneratedBy ?run .
  ?run a cdt:DTRun ; prov:used ?dataset , ?assumption .
  ?dataset a cdt:DatumSource .
  ?assumption a cdt:ScenarioAssumption .
}
```

**CQ13 — District-heating-viable clusters under scenario `?s`, year `?y`**

```sparql
SELECT ?cluster ?county ?heatDensity ?viable WHERE {
  ?kpi a cdt:DHViabilityKPI ;
       cdt:derivedUnder    ?s ;
       cdt:evaluatesYear   ?y ;
       cdt:evaluatesCounty ?county ;
       cdt:isDHViable      true ;
       cdt:viabilityThreshold_kWh_per_m2_yr ?thr ;
       sosa:hasSimpleResult ?heatDensity ;
       cdt:scopedToCluster ?cluster .
  ?cluster a cdt:ThermalDemandCluster .
  FILTER (?heatDensity >= ?thr)
  BIND (true AS ?viable)
}
ORDER BY DESC(?heatDensity)
```

**CQ14 — Group-heating candidates (mid-density, compact, dwelling-mix compatible)**

```sparql
SELECT ?candidate ?county ?heatDensity ?compactness WHERE {
  ?candidate a cdt:GroupHeatingCandidate ;
             cdt:evaluatesCounty   ?county ;
             cdt:clusterCompactness ?compactness ;
             cdt:hasHeatDensity    ?hd .
  ?hd cdt:heatDemand_kWh_per_m2_yr ?heatDensity .
  FILTER (?heatDensity >= 50.0 && ?heatDensity < 120.0)
  FILTER (?compactness >= 0.6)
}
ORDER BY ?county DESC(?heatDensity)
```

**CQ15 — LV-node flexibility and demand-response capacity**

```sparql
SELECT ?station ?flexKW ?drHeadroomKW ?controllableFrac WHERE {
  ?fkpi a cdt:FlexibilityKPI ;
        cdt:derivedUnder    ?s ;
        cdt:evaluatesYear   ?y ;
        cdt:atStation       ?station ;
        cdt:flexibilityKW   ?flexKW .
  OPTIONAL {
    ?drc a cdt:DemandResponseCapacity ;
         cdt:atStation ?station ;
         cdt:evaluatesYear ?y ;
         sosa:hasSimpleResult ?drHeadroomKW .
  }
  OPTIONAL {
    ?fl a cdt:FlexibleLoad ;
        cdt:atStation ?station ;
        cdt:controllableFraction ?controllableFrac .
  }
  ?s rdfs:label "S2_2035" .
}
ORDER BY DESC(?flexKW)
```


## References

- Li, S. et al. (2019). An Ontology for Energy Management KPIs (EM-KPI). *Applied Energy*.
- Grüninger, M. & Fox, M. S. (1995). Methodology for the Design and Evaluation of Ontologies. *IJCAI Workshop on Basic Ontological Issues in Knowledge Sharing*.
- W3C SSN / SOSA: https://www.w3.org/TR/vocab-ssn/
- OWL-Time: https://www.w3.org/TR/owl-time/
- GeoSPARQL: https://www.ogc.org/standards/geosparql
- PROV-O: https://www.w3.org/TR/prov-o/
- BOT (Building Topology Ontology): https://w3id.org/bot
- SAREF4ENER: https://saref.etsi.org/saref4ener/
- SEAI Domestic PV Grants Statistics, 2018–2026.
- Connolly, D. et al. (2014). Heat Roadmap Europe: Combining district heating with heat savings to decarbonise the EU energy system. *Energy Policy*, 65, 475–489. (Viability threshold convention ≈ 120 kWh/m²·yr.)
- Nielsen, S. & Möller, B. (2013). GIS based analysis of future district heating potential in Denmark. *Energy*, 57, 458–468.
- Kämpf, J. et al. (2025). Development and demonstration of a digital twin platform leveraging ontologies and data-driven simulation models. *Journal of Building Performance Simulation*. https://www.tandfonline.com/doi/full/10.1080/19401493.2025.2504005 — cited here for the layered methodology convention (information · integration · simulation · application tiers) adopted in Fig 2 (upper tier).
- Hao, Y. et al. (2024). An ontology-driven method for urban building energy modelling across scales. *Sustainable Cities and Society*. https://www.sciencedirect.com/science/article/pii/S2210670724002221 — cited here for the building → district → city cross-scale rollup convention adapted in Fig 2 (lower tier).
