# Project status — summary

## Objective
Optimize garbage-collection routes for Oxxo stores in Chihuahua, Chihuahua (see [README.md](../README.md) for the full problem statement: multi-trip VRP with intermediate landfill disposal, 10 trucks, 8 m³ capacity, 8h shift).

## Data pipeline (in order)

1. **`Code/geocode.py`** — initial geocoding via Nominatim/OSM of the original spreadsheet (`RutaEditado.xlsx`). It stayed partial (87/223 stores, see [geocodificacion_tiendas.md](geocodificacion_tiendas.md)) and was **superseded**: store data was migrated to clean CSVs (`Data/oxxo-stops.csv`, `Data/landfill-and-depot.csv`) with all 218 stores + depot + landfill already geolocated. `geocode.py` remains as historical reference, not an active pipeline step.
2. **`Code/build_time_matrix.py`** — builds `Data/points-index.csv` (depot=row 0, landfill=row 1, 218 stores after) and the full `Data/time-matrix-seconds.csv` / `Data/distance-matrix-meters.csv` matrices via OSRM's `/table` API, in batches (respecting its 10,000-pair-per-request cap).
3. **Solving (solvers)** — consume the matrices + `points-index.csv`, described below.
4. **`Code/visualize_routes.py`** — renders the result as an interactive Folium map at `Data/mapa_rutas.html` (one toggleable layer per truck, numbered markers, real street geometry via OSRM `/route`).
   - **Important**: `visualize_routes.py` hardcodes `SOLUTION_SRC = "Data/routes-solution.csv"`, which is **OR-Tools'** output. The GA's solution (`Data/routes-solution-ga.csv`) is not currently visualized — it would need the path passed as a parameter, or a duplicated script, to show up on the map.

Standalone scripts that are **not** part of the active pipeline (early exploration, no CLI/docstring, hardcoded paths): `Code/geodata.py`, `Code/visualize.py`, `Code/maptest.py`.

## Solvers implemented

| Solver | File | Status | Result (218 stops, 60s limit) |
|---|---|---|---|
| OR-Tools (baseline) | `Code/solve_routes.py` | Feeds the map | 41h58m total, 1185.4 km, 6 trucks used, 28 landfill trips |
| Genetic algorithm (GA) | `Code/solve_ga.py` | Implemented and tested, comparison only | 65h33m total, 2576.0 km, 10 trucks used, 28 landfill trips |

- **`Code/vrp_common.py`** — shared module: data loading, route costing (`summarize_route`), deterministic landfill-dump insertion (`insert_dumps`), and CSV reporting (`report_solution`). Both solvers and the benchmark use it so they compete on the exact same cost definition.
- **`Code/benchmark_solvers.py`** — runs both solvers with the same time budget and prints a comparison table.
- **Comparison result**: at a 60s budget, OR-Tools (mature guided local search) clearly beats the GA (basic implementation: order crossover, swap mutation, no local search or informed initial construction). To improve the GA, the natural next step would be seeding the initial population with a nearest-neighbor heuristic and/or adding 2-opt over the chromosomes, instead of starting from purely random permutations.

## Testing
- `pytest` (pinned `>=9.1` in `requirements.txt`) with 39 tests in `tests/`, covering `solve_routes`, `vrp_common`, `solve_ga`, and `benchmark_solvers`. All passing.
- This was the first test framework introduced in the repo (added alongside `build_time_matrix.py`, per `CLAUDE.md`'s instruction).

## Environment
- `requirements.txt` pins `numpy>=2.4`, `pandas>=3.0`, `pytest>=9.1`, `ortools>=9.15`, `requests>=2.33`, `folium>=0.20`.
- The user's anaconda base environment has other tools (TensorFlow, Streamlit, numba, scipy) that require `numpy<2`, so `requirements.txt` can't be installed there without breaking them.
- A **project-local venv** (`.venv/`, gitignored) was created that installs exactly what `requirements.txt` specifies. All work in this repo (tests, solvers) should run through `.venv/bin/python`, not anaconda's Python.

## Known gaps / discrepancies
- The map (`mapa_rutas.html`) only ever reflects OR-Tools; there's no way to visualize the GA's solution without editing the script.
- The GA has no construction heuristic or local search — it's a baseline implementation for comparison, not yet a competitive alternative.
- `geodata.py`, `visualize.py`, `maptest.py` remain in `Code/` uncleaned; leftovers from early exploration.
