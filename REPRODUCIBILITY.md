# Reproducing the NEDT Scenario 1 artefact

The source data are restricted by third-party licences and are intentionally
not included in this repository. The analysis scripts are portable: point
them to a licensed DT_Model data workspace with `--data-root` or the
`NEDT_DATA_ROOT` environment variable.

## Required data layout

`DATA_ROOT` must contain the following paths:

```text
CountyAnalysis/ArchetypeCounts_CountyLevel2024/ArchetypeCounts_LV_heating.csv
CountyAnalysis/2024_disaggregated/total_electricity copy 2/
LV_analysis/LV Network Creation/station_capacities_2024_filled.csv
catchment_methods_study/data/esb_lv_availability_2024.csv
catchment_methods_study/data/BuildingMaster_LV_Assigned_2024.csv
lv_mv_hv/lv_stations_2024.csv
EV_profiles/modified_uncontrolled_results_dynamic.xlsx
CountyAnalysis/private_car_stock_county.csv
```

The scripts check the shared inputs at start-up and stop with the missing
paths rather than silently substituting data. The PV workbook and car-stock
file are additionally checked when running Scenario 1.

## Commands

From the directory containing these scripts:

```bash
python3 -m pip install -r requirements.txt
python3 rerun_percatchment.py --data-root /path/to/DT_Model
python3 scenario1_percatchment.py --data-root /path/to/DT_Model
python3 export_scenario_results_to_rdf.py --input results/scenario1/lv_scenario1.csv
python3 run_competency_queries.py
python3 validate_shapes.py
python3 test_entailment.py
python3 make_reproducibility_manifest.py
python3 verify_release.py
```

The final two commands record SHA-256 checksums and verify the locally
generated Scenario 1 table, reconciliation audit, competency-query output,
RDF graph, and SHACL conformance. Generated files are written to
`results/scenario1/` and are intentionally retained only in the licensed local
workspace; they are not part of this public source repository.

## Interpretation boundary

The workflow produces scenario-dependent residential infrastructure-exposure
indicators. It is not a predictor of observed transformer overloads: the
public ESB availability extract is an asset-register source rather than
time-aligned transformer metering. The 46 highest-extreme results are kept in
`asset_reconciliation_exceptions.csv` for asset-record and connectivity
review, not promoted as ordinary reinforcement candidates.
