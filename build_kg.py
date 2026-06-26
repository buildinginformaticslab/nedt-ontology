"""
Build instance-level knowledge graph for the National Energy Digital Twin (NEDT).

Inputs:
  - DT_ontology.ttl                                          (schema / TBox)
  - CountyAnalysis/ArchetypeCounts_CountyLevel2024/*.csv    (archetype counts per county)
  - CountyAnalysis/PV.csv                                    (SEAI grant records)
  - Nexsys data_to divyanshu/modified_V1H_results_dynamic/  (69 archetype profiles)

Outputs:
  - DT_kg.ttl      Turtle serialization (schema + instances)
  - DT_kg.jsonld   JSON-LD serialization (for web tooling, Neo4j import)
  - DT_kg_viewer.html  Interactive pyvis HTML viewer
"""
from pathlib import Path
import csv, re
from collections import defaultdict, Counter

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import OWL, RDF, RDFS, XSD, DCTERMS

ROOT = Path("/Users/divyanshusood/Documents/DT_Model")
NEDT = Namespace("https://example.org/nedt#")
INST = Namespace("https://example.org/nedt/inst/")

g = Graph()
g.parse(ROOT / "DT_ontology.ttl", format="turtle")
g.bind("nedt", CDT)
g.bind("inst", INST)

# -----------------------------------------------------------------------------
# 1) Counties + PV grant records (from CountyAnalysis/PV.csv)
# -----------------------------------------------------------------------------
def slug(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")

counties = set()
pv_rows  = defaultdict(list)  # county -> list of (year, count, funding)
with open(ROOT / "CountyAnalysis" / "PV.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        county = row["County"].replace("Co. ", "").strip()
        counties.add(county)
        yr   = int(row["Year"])
        cnt  = int(row["# Property Upgrades"])
        fund = float(row["Amount Funded"].replace("€", "").replace(",", "").strip() or 0)
        pv_rows[county].append((yr, cnt, fund))

for c in sorted(counties):
    cu = INST[f"County_{slug(c)}"]
    g.add((cu, RDF.type, NEDT.County))
    g.add((cu, RDFS.label, Literal(f"Co. {c}")))

for county, entries in pv_rows.items():
    for yr, cnt, fund in entries:
        gr = INST[f"SEAIGrant_{slug(county)}_{yr}"]
        g.add((gr, RDF.type, NEDT.SEAIGrantRecord))
        g.add((gr, NEDT.grantYear,       Literal(yr, datatype=XSD.gYear)))
        g.add((gr, NEDT.grantCount,      Literal(cnt, datatype=XSD.integer)))
        g.add((gr, NEDT.grantFundingEUR, Literal(fund, datatype=XSD.decimal)))
        g.add((INST[f"County_{slug(county)}"], NEDT.hasGrantRecord, gr))

# -----------------------------------------------------------------------------
# 2) Archetype + ArchetypeCount (from per-county archetype CSVs)
# -----------------------------------------------------------------------------
HEAT_MAP = {"Heat Pump": "HeatPump", "Heating Oil": "Oilboiler",
            "gasboiler": "gasboiler", "Solar Thermal": "SolarThermal"}
DTYPE_MAP = {"Apartment": "Apartment", "Detached": "Detached", "SemiD": "SemiD",
             "Terraced": "Terraced", "Terraced house": "Terraced", "Bungalow": "Bungalow"}

arch_seen   = set()
arch_county = defaultdict(int)   # (arch_key, county) -> count
dir_ = ROOT / "CountyAnalysis" / "ArchetypeCounts_CountyLevel2024"
for fn in sorted(dir_.iterdir()):
    if not fn.name.endswith(".csv"): continue
    if "National" in fn.name: continue  # aggregate file, no County column
    with open(fn, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            dtype = DTYPE_MAP.get(row["Build Type"], row["Build Type"])
            ber   = row["BER"] or "Unknown"
            occ   = row["Occupancy"]
            heat  = HEAT_MAP.get(row["HeatingSystem"], row["HeatingSystem"])
            cty   = row["County"]
            try:
                cnt = int(row.get(f"ArchCount_original_2024_{cty}", 0) or 0)
            except ValueError:
                cnt = 0
            if cnt == 0: continue
            key = (dtype, ber, occ, heat)
            arch_seen.add(key)
            arch_county[(key, cty)] += cnt

# Create Archetype instances
for key in sorted(arch_seen):
    dtype, ber, occ, heat = key
    aid = f"Arch_{dtype}_{ber}_{occ}_{heat}"
    au  = INST[aid]
    g.add((au, RDF.type, NEDT.Archetype))
    g.add((au, RDFS.label, Literal(f"{dtype}·BER {ber}·occ {occ}·{heat}")))
    g.add((au, NEDT.buildType,     Literal(dtype)))
    g.add((au, NEDT.berRating,     Literal(ber)))
    g.add((au, NEDT.occupancy,     Literal(occ)))
    g.add((au, NEDT.heatingSystem, Literal(heat)))

# ArchetypeCount per (archetype, county) — aggregate counts
for (key, cty), cnt in arch_county.items():
    dtype, ber, occ, heat = key
    aid = f"Arch_{dtype}_{ber}_{occ}_{heat}"
    cid = f"AC_{aid}_{slug(cty)}"
    ac  = INST[cid]
    g.add((ac, RDF.type, NEDT.ArchetypeCount))
    g.add((ac, NEDT.dwellingCount, Literal(cnt, datatype=XSD.integer)))
    g.add((ac, NEDT.inCounty,      INST[f"County_{slug(cty)}"]))
    g.add((INST[aid], NEDT.hasCount, ac))
    g.add((INST[f"County_{slug(cty)}"], NEDT.hasArchetype, INST[aid]))

# -----------------------------------------------------------------------------
# 3) NexsysProfile instances (69 files)
# -----------------------------------------------------------------------------
nex_dir = ROOT / "Nexsys data_to divyanshu" / "modified_V1H_results_dynamic"
for fn in sorted(nex_dir.iterdir()):
    if not fn.name.endswith(".csv"): continue
    stem = fn.stem
    parts = stem.split("_")
    if len(parts) < 4: continue
    dtype, ber, occ, heat = parts[0], parts[1], parts[2], parts[3]
    pu = INST[f"NexsysProfile_{stem}"]
    g.add((pu, RDF.type, NEDT.NexsysProfile))
    g.add((pu, RDFS.label, Literal(f"Nexsys·{stem}")))
    g.add((pu, NEDT.sourceFile, Literal(str(fn.relative_to(ROOT)))))
    # link to archetype if direct match exists
    aid = f"Arch_{dtype}_{ber}_{occ}_{heat}"
    if (dtype, ber, occ, heat) in arch_seen:
        g.add((INST[aid], NEDT.usesProfile, pu))

# -----------------------------------------------------------------------------
# 4) PV module instances (reference shape, capacity bins, mix, scenarios)
# -----------------------------------------------------------------------------
ref = INST["PVReferenceShape_IE_mean"]
g.add((ref, RDF.type, NEDT.PVReferenceShape))
g.add((ref, RDFS.label, Literal("Ireland mean PV reference shape (1 kWp, 8760h)")))
g.add((ref, NEDT.annualYield_kWh_per_kWp, Literal(1095, datatype=XSD.decimal)))

for kwp, pct in [(1,10),(2,47),(3,23),(4,6),(5,11),(6,3)]:
    b = INST[f"PVCapacityBin_{kwp}kWp"]
    g.add((b, RDF.type, NEDT.PVCapacityBin))
    g.add((b, RDFS.label, Literal(f"{kwp} kWp")))
    g.add((b, NEDT.installedCapacity_kWp, Literal(kwp, datatype=XSD.decimal)))
    g.add((b, NEDT.referenceShare_pct,    Literal(pct, datatype=XSD.decimal)))

mix = INST["PVCapacityMix_IE2017"]
g.add((mix, RDF.type, NEDT.PVCapacityMix))
g.add((mix, RDFS.label, Literal("Irish 2017 reference capacity mix")))
for kwp in range(1,7):
    g.add((mix, NEDT.hasCapacityBin, INST[f"PVCapacityBin_{kwp}kWp"]))

asis = INST["PVAdoptionScenario_AsIs_2025"]
g.add((asis, RDF.type, NEDT.PVAdoptionScenario))
g.add((asis, RDFS.label, Literal("AS-IS PV adoption (SEAI 2018–2025 cumulative)")))
g.add((asis, NEDT.hasCapacityMix, mix))

# -----------------------------------------------------------------------------
# 5) KPI hierarchy skeleton
# -----------------------------------------------------------------------------
for sk, lbl in [("PeakLVUtilisation", "Peak LV Utilisation"),
                ("AnnualCO2",         "Annual CO2 Emissions"),
                ("PVSelfConsumption", "PV Self-Consumption Rate")]:
    k = INST[f"KPI_{sk}"]
    g.add((k, RDF.type, NEDT.KPI))
    g.add((k, RDFS.label, Literal(lbl)))

# -----------------------------------------------------------------------------
# Serialize
# -----------------------------------------------------------------------------
g.serialize(destination=str(ROOT / "DT_kg.ttl"),    format="turtle")
g.serialize(destination=str(ROOT / "DT_kg.jsonld"), format="json-ld", indent=2)
print(f"KG built: {len(g):,} triples")
print(f"  Counties:             {len(counties)}")
print(f"  Archetypes:           {len(arch_seen)}")
print(f"  ArchetypeCounts:      {len(arch_county):,}")
print(f"  SEAI grant records:   {sum(len(v) for v in pv_rows.values())}")
print(f"  Nexsys profiles:      69")
print(f"  PV capacity bins:     6")

# -----------------------------------------------------------------------------
# Interactive HTML viewer (pyvis)
# -----------------------------------------------------------------------------
from pyvis.network import Network
net = Network(height="900px", width="100%", bgcolor="#fafbfd", font_color="#222",
              directed=True, notebook=False, cdn_resources="remote")

# palette per ontology module (secondary hue), overridden per layer below
MODULE_SIZE = {
  NEDT.County: 22, NEDT.LVStation: 14, NEDT.Archetype: 11,
  NEDT.ArchetypeCount: 8, NEDT.NexsysProfile: 10, NEDT.SEAIGrantRecord: 7,
  NEDT.PVReferenceShape: 16, NEDT.PVCapacityBin: 13, NEDT.PVCapacityMix: 15,
  NEDT.PVAdoptionScenario: 17, NEDT.KPI: 15,
}

# Two-colour layer scheme (requested: show what is existing KG framework
# vs what is my DT-model contribution). Shape reinforces the distinction
# for colour-blind readers.
LAYER_STYLE = {
  "core-KG-framework":  {"color": "#185FA5", "shape": "dot",     "border": "#0D3E6E"},
  "DT-model-extension": {"color": "#D98E2B", "shape": "diamond", "border": "#8A5612"},
}

# Build a class URI -> layer lookup from the ontology annotations
CLASS_LAYER = {}
for cls, _, lit in g.triples((None, NEDT.layer, None)):
    CLASS_LAYER[cls] = str(lit)

def short(u):
    s = str(u)
    return s.split("#")[-1].split("/")[-1]

# Instance graph only (skip pure ontology TBox triples from viewer to avoid clutter)
instance_uris = set()
for s, p, o in g:
    if isinstance(s, URIRef) and str(s).startswith(str(INST)):
        instance_uris.add(s)
    if isinstance(o, URIRef) and str(o).startswith(str(INST)):
        instance_uris.add(o)

# sample to keep viewer responsive: all counties, top-15 archetypes by total count, all PV, all KPIs
top_archs = Counter()
for (key, _), cnt in arch_county.items():
    top_archs[key] += cnt
top_arch_ids = {f"Arch_{d}_{b}_{o}_{h}" for (d,b,o,h),_ in top_archs.most_common(15)}

keep = set()
for u in instance_uris:
    name = short(u)
    if name.startswith("County_"):              keep.add(u)
    elif name.startswith("Arch_") and name in top_arch_ids: keep.add(u)
    elif name.startswith("AC_") and any(name.startswith(f"AC_{aid}_") for aid in top_arch_ids): keep.add(u)
    elif name.startswith("NexsysProfile_") and any((d in name and b in name and o in name and h in name)
                                                   for (d,b,o,h) in top_archs.keys()
                                                   if f"Arch_{d}_{b}_{o}_{h}" in top_arch_ids): keep.add(u)
    elif name.startswith(("PVCapacityBin_","PVCapacityMix_","PVReferenceShape_",
                          "PVAdoptionScenario_","KPI_")): keep.add(u)

# Add nodes + build a details map for the click-panel
details_map = {}
for u in keep:
    types = list(g.objects(u, RDF.type))
    t = types[0] if types else None
    layer = CLASS_LAYER.get(t, "DT-model-extension")
    style = LAYER_STYLE[layer]
    color = style["color"]
    shape = style["shape"]
    border = style["border"]
    size = MODULE_SIZE.get(t, 10)
    lbl = str(next(g.objects(u, RDFS.label), short(u)))
    node_id = str(u)
    props, out_rel, in_rel = [], [], []
    for p, o in g.predicate_objects(u):
        if p in (RDF.type, RDFS.label): continue
        if isinstance(o, Literal):
            props.append({"p": short(p), "v": str(o)})
        elif isinstance(o, URIRef):
            out_rel.append({"p": short(p), "target": str(o), "target_label": short(o)})
    for s, p in g.subject_predicates(u):
        if p in (RDF.type, RDFS.label): continue
        if isinstance(s, URIRef):
            in_rel.append({"p": short(p), "source": str(s), "source_label": short(s)})
    details_map[node_id] = {
        "id": short(u),
        "label": lbl,
        "type": short(t) if t else "Instance",
        "layer": layer,
        "color": color,
        "props": props,
        "out_rel": out_rel[:200],
        "in_rel":  in_rel[:200],
    }
    tooltip = f"{lbl} — {layer} — click for details"
    net.add_node(node_id, label=lbl, color={"background": color, "border": border},
                 size=size, shape=shape, title=tooltip)

# Add edges
for s, p, o in g:
    if s in keep and o in keep and p not in (RDF.type, RDFS.label):
        net.add_edge(str(s), str(o), label=short(p), arrows="to", font={"size":9,"color":"#666"})

net.set_options("""var options = {
  "interaction": {"hover": true, "tooltipDelay": 120, "navigationButtons": true, "keyboard": true, "dragNodes": true},
  "physics": {
    "enabled": true,
    "solver": "forceAtlas2Based",
    "forceAtlas2Based": {"gravitationalConstant": -80, "centralGravity": 0.012, "springLength": 160, "springConstant": 0.08, "damping": 0.9, "avoidOverlap": 1},
    "maxVelocity": 30,
    "minVelocity": 2.0,
    "timestep": 0.35,
    "stabilization": {"enabled": true, "iterations": 800, "updateInterval": 50, "fit": true},
    "adaptiveTimestep": true
  },
  "nodes":     {"scaling": {"min": 8, "max": 40}},
  "edges":     {"smooth": {"enabled": true, "type": "dynamic"}}
}""")
out = ROOT / "DT_kg_viewer.html"
net.save_graph(str(out))

# Inject: freeze physics once stable + click-to-inspect side panel
import json as _json
details_json = _json.dumps(details_map)
panel_css = """
<style>
  #kg_panel { position: fixed; top: 0; right: 0; width: 380px; height: 100vh;
              background: #fff; border-left: 1px solid #ddd; box-shadow: -2px 0 8px rgba(0,0,0,.06);
              padding: 18px; overflow-y: auto; font-family: -apple-system, Arial, sans-serif;
              font-size: 13px; color: #222; z-index: 9999; display: none; }
  #kg_panel h2 { font-size: 15px; margin: 0 0 4px; }
  #kg_panel .type { display: inline-block; padding: 2px 8px; border-radius: 10px;
                    font-size: 11px; font-weight: 600; color: #fff; margin-bottom: 12px; }
  #kg_panel h3 { font-size: 12px; text-transform: uppercase; color: #666;
                 border-top: 1px solid #eee; padding-top: 12px; margin-top: 14px; }
  #kg_panel table { width: 100%; border-collapse: collapse; margin-top: 4px; }
  #kg_panel td { padding: 3px 4px; vertical-align: top; font-size: 12px; }
  #kg_panel td.k { color: #555; font-weight: 600; width: 40%; word-break: break-word; }
  #kg_panel td.v { color: #111; word-break: break-word; }
  #kg_panel a.linknode { color: #185FA5; cursor: pointer; text-decoration: none; }
  #kg_panel a.linknode:hover { text-decoration: underline; }
  #kg_panel .empty { color: #999; font-style: italic; font-size: 12px; }
  #kg_close { position: absolute; top: 8px; right: 12px; border: none; background: none;
              font-size: 22px; color: #888; cursor: pointer; }
  #kg_hint { position: fixed; top: 10px; left: 14px; background: #fff8e6;
             padding: 8px 14px; border-radius: 6px; font-family: Arial; font-size: 12px;
             color: #774; z-index: 9999; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  #kg_legend { position: fixed; bottom: 14px; left: 14px; background: #fff;
               padding: 10px 14px; border-radius: 6px; font-family: Arial; font-size: 12px;
               color: #222; z-index: 9999; box-shadow: 0 1px 4px rgba(0,0,0,.1);
               border: 1px solid #e3e3e3; line-height: 1.6; }
  #kg_legend .sw { display: inline-block; width: 12px; height: 12px; margin-right: 6px;
                   vertical-align: middle; border: 1px solid #444; }
  #kg_legend .sw.dot { border-radius: 50%; background: #185FA5; border-color: #0D3E6E; }
  #kg_legend .sw.dmd { background: #D98E2B; border-color: #8A5612; transform: rotate(45deg); }
  #kg_legend h4 { margin: 0 0 6px; font-size: 12px; color: #555; text-transform: uppercase; letter-spacing: .03em; }
  #kg_panel .layer-tag { display: inline-block; padding: 2px 8px; border-radius: 10px;
                         font-size: 10px; font-weight: 600; margin-left: 6px;
                         background: #eef; color: #335; border: 1px solid #ccd; }
</style>
"""
panel_html = """
<div id="kg_hint">Click any node to see its properties and links →</div>
<div id="kg_legend">
  <h4>Contribution layer</h4>
  <div><span class="sw dot"></span>Core KG framework <span style="color:#777">(Hoare et al. 2026 · BOT · SARAGON · GeoDirectory · OSI)</span></div>
  <div><span class="sw dmd"></span>DT model extension <span style="color:#777">(this work — scenarios, profiles, KPIs, PV)</span></div>
</div>
<div id="kg_panel">
  <button id="kg_close">&times;</button>
  <h2 id="kg_label"></h2>
  <span id="kg_type" class="type"></span><span id="kg_layer" class="layer-tag"></span>
  <div id="kg_id" style="color:#888;font-size:11px;margin-bottom:10px;"></div>
  <h3>Data properties</h3>
  <div id="kg_props"></div>
  <h3>Outgoing links (this → …)</h3>
  <div id="kg_out"></div>
  <h3>Incoming links (… → this)</h3>
  <div id="kg_in"></div>
</div>
"""
panel_js = """
<script>
  window.__KG_DETAILS__ = %s;
  function kgRenderTable(rows, keyFn, valFn) {
    if (!rows || rows.length === 0) return '<div class="empty">none</div>';
    var h = '<table>';
    rows.forEach(function(r){ h += '<tr><td class="k">' + keyFn(r) + '</td><td class="v">' + valFn(r) + '</td></tr>'; });
    return h + '</table>';
  }
  function kgShow(id) {
    var d = window.__KG_DETAILS__[id]; if (!d) return;
    document.getElementById('kg_label').textContent = d.label;
    var tEl = document.getElementById('kg_type');
    tEl.textContent = d.type; tEl.style.background = d.color;
    var lEl = document.getElementById('kg_layer');
    lEl.textContent = d.layer;
    lEl.style.background = (d.layer === 'core-KG-framework') ? '#dbe7f5' : '#fbe7d0';
    lEl.style.color     = (d.layer === 'core-KG-framework') ? '#0D3E6E' : '#8A5612';
    document.getElementById('kg_id').textContent = d.id;
    document.getElementById('kg_props').innerHTML =
      kgRenderTable(d.props, function(r){return r.p;}, function(r){return r.v;});
    document.getElementById('kg_out').innerHTML =
      kgRenderTable(d.out_rel, function(r){return r.p;},
        function(r){return '<a class="linknode" data-id="'+r.target+'">'+r.target_label+'</a>';});
    document.getElementById('kg_in').innerHTML =
      kgRenderTable(d.in_rel, function(r){return r.p;},
        function(r){return '<a class="linknode" data-id="'+r.source+'">'+r.source_label+'</a>';});
    document.getElementById('kg_panel').style.display = 'block';
    document.getElementById('kg_hint').style.display = 'none';
    document.querySelectorAll('#kg_panel a.linknode').forEach(function(a){
      a.onclick = function(){
        var tid = a.getAttribute('data-id');
        if (typeof network !== 'undefined') {
          network.selectNodes([tid]); network.focus(tid, {scale: 1.1, animation: true});
        }
        kgShow(tid);
      };
    });
  }
  document.addEventListener('DOMContentLoaded', function () {
    if (typeof network === 'undefined') return;
    network.once('stabilizationIterationsDone', function () { network.setOptions({ physics: false }); });
    setTimeout(function () { try { network.setOptions({ physics: false }); } catch(e){} }, 6000);
    network.on('click', function (p) {
      if (p.nodes && p.nodes.length) { kgShow(p.nodes[0]); }
      else { document.getElementById('kg_panel').style.display = 'none'; }
    });
    document.getElementById('kg_close').onclick = function () {
      document.getElementById('kg_panel').style.display = 'none';
    };
  });
</script>
""" % details_json

html = out.read_text()
html = html.replace("</head>", panel_css + "\n</head>")
html = html.replace("</body>", panel_html + panel_js + "\n</body>")
out.write_text(html)
print(f"\nInteractive viewer: {out}")
print(f"  Nodes in viewer: {len(details_map)}")
