"""
Populate example A-Box instances for every v1.1 class in the CDT ontology.

Purpose
-------
Demonstrate the triple patterns required by competency questions CQ1-CQ12
(DT_ontology_paper.md Appendix A) using one realistic Louth 2035 scenario
run.  The notebook can later replace these examples with per-building
outputs keyed on the same predicates.

Outputs
-------
  - DT_instances_v11.ttl          instances-only Turtle (human-readable)
  - DT_kg_full.ttl                T-Box + pre-existing A-Box + v1.1 ABox
"""
from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

ROOT = Path(__file__).parent
NEDT = Namespace("https://example.org/nedt#")
INST = Namespace("https://example.org/nedt/inst/")
SSN  = Namespace("http://www.w3.org/ns/ssn/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
TIME = Namespace("http://www.w3.org/2006/time#")
PROV = Namespace("http://www.w3.org/ns/prov#")

g = Graph()
g.bind("nedt", CDT)
g.bind("inst", INST)
g.bind("prov", PROV)
g.bind("sosa", SOSA)
g.bind("time", TIME)

def T(s, p, o):
    g.add((s, p, o))

# -----------------------------------------------------------------------------
# Typed archetype descriptors (CQ1)
# -----------------------------------------------------------------------------
# Two Louth archetypes with typed BER / dwelling type / construction period.
T(INST.BER_B2,        RDF.type, NEDT.BERRating)
T(INST.BER_B2,        RDFS.label, Literal("B2", lang="en"))
T(INST.BER_D1,        RDF.type, NEDT.BERRating)
T(INST.BER_D1,        RDFS.label, Literal("D1", lang="en"))

T(INST.DType_Detached, RDF.type, NEDT.DwellingType)
T(INST.DType_Detached, RDFS.label, Literal("Detached", lang="en"))
T(INST.DType_Terraced, RDF.type, NEDT.DwellingType)
T(INST.DType_Terraced, RDFS.label, Literal("Terraced", lang="en"))

T(INST.Period_post2011, RDF.type, NEDT.ConstructionPeriod)
T(INST.Period_post2011, RDFS.label, Literal("post-2011", lang="en"))
T(INST.Period_1971_1990, RDF.type, NEDT.ConstructionPeriod)
T(INST.Period_1971_1990, RDFS.label, Literal("1971-1990", lang="en"))

# Two archetypes typed up with the new descriptors
T(INST.Arch_SD_B2_post2011, RDF.type, NEDT.Archetype)
T(INST.Arch_SD_B2_post2011, RDFS.label, Literal("Detached·B2·post-2011·HP", lang="en"))
T(INST.Arch_SD_B2_post2011, NEDT.hasDescriptor, INST.BER_B2)
T(INST.Arch_SD_B2_post2011, NEDT.hasDescriptor, INST.DType_Detached)
T(INST.Arch_SD_B2_post2011, NEDT.hasDescriptor, INST.Period_post2011)

T(INST.Arch_TH_D1_1971, RDF.type, NEDT.Archetype)
T(INST.Arch_TH_D1_1971, RDFS.label, Literal("Terraced·D1·1971-1990·Oil", lang="en"))
T(INST.Arch_TH_D1_1971, NEDT.hasDescriptor, INST.BER_D1)
T(INST.Arch_TH_D1_1971, NEDT.hasDescriptor, INST.DType_Terraced)
T(INST.Arch_TH_D1_1971, NEDT.hasDescriptor, INST.Period_1971_1990)

# -----------------------------------------------------------------------------
# End-use load decomposition (CQ2, CQ4, CQ6)
# -----------------------------------------------------------------------------
for end_use, label in [("space_heat","Space Heat"),("dhw","DHW"),
                       ("appliance","Appliance"),("lighting","Lighting"),
                       ("cooking","Cooking"),("ev","EV Charging"),
                       ("hp_replace","HP Replacement")]:
    iri = INST[f"EndUse_{end_use}"]
    T(iri, RDF.type, NEDT.EndUseLoad)
    T(iri, NEDT.endUse, Literal(end_use))
    T(iri, RDFS.label, Literal(label, lang="en"))

# -----------------------------------------------------------------------------
# Scenario parameterisation (CQ3)
# -----------------------------------------------------------------------------
# Scenario S2_2035: 40% HP uptake for Arch_TH_D1_1971 in year 2035.
T(INST.Scenario_S2_2035, RDF.type, NEDT.Scenario)
T(INST.Scenario_S2_2035, RDFS.label, Literal("S2_2035", lang="en"))

T(INST.SP_HP_TH_D1_2035, RDF.type, NEDT.ScenarioParameter)
T(INST.SP_HP_TH_D1_2035, RDFS.label, Literal("HP uptake", lang="en"))
T(INST.SP_HP_TH_D1_2035, NEDT.forArchetype, INST.Arch_TH_D1_1971)
T(INST.SP_HP_TH_D1_2035, NEDT.forYear, Literal("2035", datatype=XSD.gYear))
T(INST.SP_HP_TH_D1_2035, NEDT.uptakeValue, Literal("0.40", datatype=XSD.decimal))
T(INST.Scenario_S2_2035, NEDT.hasScenarioParameter, INST.SP_HP_TH_D1_2035)

# Provenance: assumption behind the 40% figure
T(INST.Assumption_CAP_HP, RDF.type, NEDT.ScenarioAssumption)
T(INST.Assumption_CAP_HP, RDFS.label, Literal("CAP 2024 HP uptake target (Ch. 7)", lang="en"))
T(INST.SP_HP_TH_D1_2035, PROV.wasDerivedFrom, INST.Assumption_CAP_HP)

# Second scenario parameter: PV 4 kWp for Detached archetype
T(INST.SP_PV_SD_2035, RDF.type, NEDT.ScenarioParameter)
T(INST.SP_PV_SD_2035, RDFS.label, Literal("PV installed kWp", lang="en"))
T(INST.SP_PV_SD_2035, NEDT.forArchetype, INST.Arch_SD_B2_post2011)
T(INST.SP_PV_SD_2035, NEDT.forYear, Literal("2035", datatype=XSD.gYear))
T(INST.SP_PV_SD_2035, NEDT.uptakeValue, Literal("4.0", datatype=XSD.decimal))
T(INST.Scenario_S2_2035, NEDT.hasScenarioParameter, INST.SP_PV_SD_2035)

# -----------------------------------------------------------------------------
# LV aggregation (CQ5)
# -----------------------------------------------------------------------------
T(INST.LV_Louth_0412, RDF.type, NEDT.LVStation)
T(INST.LV_Louth_0412, RDFS.label, Literal("LV_Louth_0412", lang="en"))

T(INST.LVAgg_Louth_0412_S2_2035, RDF.type, NEDT.LVAggregation)
T(INST.LVAgg_Louth_0412_S2_2035, RDFS.label,
  Literal("Aggregation LV_Louth_0412 / S2_2035", lang="en"))

# -----------------------------------------------------------------------------
# Overload event + end-use attribution (CQ6)
# -----------------------------------------------------------------------------
T(INST.OE_Louth_0412_20350118_1800, RDF.type, NEDT.OverloadEvent)
T(INST.OE_Louth_0412_20350118_1800, NEDT.occursAt,
  Literal("2035-01-18T18:00:00", datatype=XSD.dateTime))
T(INST.OE_Louth_0412_20350118_1800, NEDT.overloadMagnitude_kW,
  Literal("48.2", datatype=XSD.decimal))
T(INST.LV_Louth_0412, RDF.type, NEDT.OverloadedStation)
T(INST.LV_Louth_0412, NEDT.hasAttribution, INST.Att_Louth_0412_20350118_1800)
T(INST.Att_Louth_0412_20350118_1800, RDF.type, NEDT.OverloadAttribution)

# HP drove 62%, EV 24%, baseline 14%
for eu, share in [("hp_replace", 62.0), ("ev", 24.0), ("space_heat", 14.0)]:
    c = INST[f"Contrib_Louth_0412_20350118_1800_{eu}"]
    T(c, RDF.type, NEDT.EndUseContribution)
    T(c, NEDT.attributedToEndUse, INST[f"EndUse_{eu}"])
    T(c, NEDT.contributionPercent, Literal(str(share), datatype=XSD.decimal))
    T(INST.Att_Louth_0412_20350118_1800, NEDT.ranksBy, c)

# -----------------------------------------------------------------------------
# PV self-consumption KPIs (CQ7)
# -----------------------------------------------------------------------------
T(INST.PV_SD_B2_post2011_4kWp, RDF.type, NEDT.PVSystem)
T(INST.PV_SD_B2_post2011_4kWp, NEDT.installedCapacity_kWp,
  Literal("4.0", datatype=XSD.decimal))
T(INST.Arch_SD_B2_post2011, NEDT.hasPVSystem, INST.PV_SD_B2_post2011_4kWp)

T(INST.SCR_SD_B2_post2011_S2_2035, RDF.type, NEDT.SelfConsumptionRatio)
T(INST.SCR_SD_B2_post2011_S2_2035, NEDT.hasKPIEvaluatedObject, INST.PV_SD_B2_post2011_4kWp)
T(INST.SCR_SD_B2_post2011_S2_2035, NEDT.derivedUnder, INST.Scenario_S2_2035)
T(INST.SCR_SD_B2_post2011_S2_2035, SOSA.hasSimpleResult,
  Literal("0.52", datatype=XSD.decimal))

T(INST.Exp_SD_B2_post2011_S2_2035, RDF.type, NEDT.ExportedEnergy)
T(INST.Exp_SD_B2_post2011_S2_2035, NEDT.hasKPIEvaluatedObject, INST.PV_SD_B2_post2011_4kWp)
T(INST.Exp_SD_B2_post2011_S2_2035, NEDT.derivedUnder, INST.Scenario_S2_2035)
T(INST.Exp_SD_B2_post2011_S2_2035, SOSA.hasSimpleResult,
  Literal("2104.5", datatype=XSD.decimal))

# Three example reverse-flow hours at the transformer
for i, ts in enumerate([
    "2035-05-12T13:00:00","2035-06-14T14:00:00","2035-07-21T12:00:00"
]):
    r = INST[f"RevFlow_Louth_0412_{i}"]
    T(r, RDF.type, NEDT.ReversePowerFlowHour)
    T(r, NEDT.derivedUnder, INST.Scenario_S2_2035)
    T(r, TIME.inXSDDateTimeStamp, Literal(ts, datatype=XSD.dateTimeStamp))

# -----------------------------------------------------------------------------
# County / national KPI scope (CQ8, CQ9, CQ10)
# -----------------------------------------------------------------------------
T(INST.County_Louth, RDF.type, NEDT.County)
T(INST.County_Louth, RDFS.label, Literal("Co. Louth", lang="en"))

T(INST.KPI_CountyPeak, RDF.type, NEDT.CountyKPI)
T(INST.KPI_CountyPeak, RDFS.label, Literal("County coincident peak demand", lang="en"))
T(INST.KPI_NatPeak,    RDF.type, NEDT.NationalKPI)
T(INST.KPI_NatPeak,    RDFS.label, Literal("National coincident peak demand", lang="en"))

# Coincident peak KPI value for Louth 2035
T(INST.Peak_Louth_2035_S2, RDF.type, NEDT.CoincidentPeak)
T(INST.Peak_Louth_2035_S2, RDFS.label, Literal("peak_Louth_2035_S2", lang="en"))
T(INST.Peak_Louth_2035_S2, NEDT.evaluatesCounty, INST.County_Louth)
T(INST.Peak_Louth_2035_S2, NEDT.evaluatesYear, Literal("2035", datatype=XSD.gYear))
T(INST.Peak_Louth_2035_S2, NEDT.derivedUnder, INST.Scenario_S2_2035)
T(INST.Peak_Louth_2035_S2, SOSA.hasSimpleResult,
  Literal("214.3", datatype=XSD.decimal))
T(INST.Peak_Louth_2035_S2, TIME.inXSDDateTimeStamp,
  Literal("2035-01-18T18:00:00", datatype=XSD.dateTimeStamp))

# Reinforcement-need flag for the overloaded station
T(INST.RN_Louth_0412_2035, RDF.type, NEDT.ReinforcementNeed)
T(INST.RN_Louth_0412_2035, NEDT.hasKPIEvaluatedObject, INST.LV_Louth_0412)
T(INST.RN_Louth_0412_2035, NEDT.firstBreachYear,
  Literal("2033", datatype=XSD.gYear))
T(INST.RN_Louth_0412_2035, NEDT.evaluatesYear,
  Literal("2035", datatype=XSD.gYear))
T(INST.RN_Louth_0412_2035, NEDT.breachHours, Literal(127, datatype=XSD.integer))
T(INST.RN_Louth_0412_2035, NEDT.derivedUnder, INST.Scenario_S2_2035)

# -----------------------------------------------------------------------------
# Provenance: DTRun links datasets to KPIs (CQ12)
# -----------------------------------------------------------------------------
# Pre-existing datasets (as prov:Entity via nedt:DatumSource)
for ds, label in [
    ("DS_SEAI_BER_2024",   "SEAI BER Research v2024"),
    ("DS_CSO_SAPS_2022",   "CSO SAPS 2022"),
    ("DS_ESB_LV_2024",     "ESB LV substation geojson 2024"),
    ("DS_Nexsys_2024",     "Nexsys archetype profile catalogue 2024"),
]:
    iri = INST[ds]
    T(iri, RDF.type, NEDT.DatumSource)
    T(iri, RDFS.label, Literal(label, lang="en"))

T(INST.DTRun_Louth_S2_2035, RDF.type, NEDT.DTRun)
T(INST.DTRun_Louth_S2_2035, RDFS.label,
  Literal("DT run: Louth · S2 · 2035", lang="en"))
for ds in ["DS_SEAI_BER_2024","DS_CSO_SAPS_2022","DS_ESB_LV_2024","DS_Nexsys_2024"]:
    T(INST.DTRun_Louth_S2_2035, PROV.used, INST[ds])
T(INST.DTRun_Louth_S2_2035, PROV.used, INST.Assumption_CAP_HP)
T(INST.DTRun_Louth_S2_2035, PROV.generated, INST.Peak_Louth_2035_S2)
T(INST.DTRun_Louth_S2_2035, PROV.generated, INST.RN_Louth_0412_2035)
T(INST.DTRun_Louth_S2_2035, PROV.generated, INST.SCR_SD_B2_post2011_S2_2035)
T(INST.Peak_Louth_2035_S2, PROV.wasGeneratedBy, INST.DTRun_Louth_S2_2035)

# Sensitivity run (CQ11)
T(INST.SensRun_S2_2035_HPvsEV, RDF.type, NEDT.SensitivityRun)
T(INST.SensRun_S2_2035_HPvsEV, RDFS.label,
  Literal("Sensitivity: HP% vs EV% vs PV kWp · S2 · 2035", lang="en"))
T(INST.SensRun_S2_2035_HPvsEV, PROV.used, INST.Scenario_S2_2035)

# -----------------------------------------------------------------------------
# Serialize
# -----------------------------------------------------------------------------
g.serialize(destination=str(ROOT / "DT_instances_v11.ttl"), format="turtle")

# Merge with TBox + prior A-Box for a single self-contained graph
full = Graph()
full.bind("cdt", CDT)
full.bind("inst", INST)
full.bind("prov", PROV)
full.parse(ROOT / "DT_kg.ttl", format="turtle")         # TBox + baseline instances
full.parse(ROOT / "DT_instances_v11.ttl", format="turtle")
full.serialize(destination=str(ROOT / "DT_kg_full.ttl"), format="turtle")

print(f"v1.1 instance triples only : {len(g):,}")
print(f"Merged KG triples          : {len(full):,}")
print(f"Wrote: DT_instances_v11.ttl, DT_kg_full.ttl")
