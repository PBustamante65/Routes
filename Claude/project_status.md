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

## Interactive add-stop pipeline (`Code/pipeline/`)
A second, class-based pipeline was added alongside the original flat scripts: `TimeMatrixBuilder` (`time_matrix.py`), `Solution` (`solve_routes.py`), and `Map` (`visualize_routes.py`) are mechanical refactors of `build_time_matrix.py` / `solve_routes.py` / `visualize_routes.py` into classes with identical logic, plus a new `add_points.py` entrypoint that:
1. Loads `Data/oxxo-stops.csv`, interactively prompts for new stops (tienda/direccion/ciudad/lat/lon), and appends them to a working copy at `Data/oxxo-stopsTEST.csv`.
2. Re-runs `time_matrix.main() -> solve_routes.main() -> visualize_routes.main()` end to end.

This was built and merged via PRs [#8](../../pull/8) and [#9](../../pull/9) (both squashed into `main` as merge commits) after fixing a bug: submitting the same stop name twice via `add_points.py` produced two rows with the same generated id in `points-index.csv`, which made `points.set_index("id").loc[id]` in `visualize_routes.py` return a DataFrame instead of a Series — silently unpacking `lat, lon = ...` into the literal strings `"latitud"`/`"longitud"` instead of real coordinates, breaking both the OSRM request and the straight-line fallback. Fixed by having `TimeMatrixBuilder.load_points()` drop duplicate ids (keep-first), covered by `tests/test_time_matrix_pipeline.py`.

## Testing
- `pytest` (pinned `>=9.1` in `requirements.txt`) with 46 tests in `tests/`, covering `solve_routes`, `vrp_common`, `solve_ga`, `benchmark_solvers`, and the new pipeline's duplicate-id guard (`test_time_matrix_pipeline.py`). All passing.
- This was the first test framework introduced in the repo (added alongside `build_time_matrix.py`, per `CLAUDE.md`'s instruction).
- Note: this repo lives under iCloud Drive, and `pytest` runs here can take minutes (file-provider I/O on `.pytest_cache` and test fixtures), not seconds — a slow run is not a hang.

## Environment
- `requirements.txt` pins `numpy>=2.4`, `pandas>=3.0`, `pytest>=9.1`, `ortools>=9.15`, `requests>=2.33`, `folium>=0.20`.
- The user's anaconda base environment has other tools (TensorFlow, Streamlit, numba, scipy) that require `numpy<2`, so `requirements.txt` can't be installed there without breaking them.
- A **project-local venv** (`.venv/`, gitignored) was created that installs exactly what `requirements.txt` specifies. All work in this repo (tests, solvers) should run through `.venv/bin/python`, not anaconda's Python.
- `gh` (GitHub CLI) is now installed via Homebrew and authenticated as `PBustamante65`, for creating/merging PRs from the command line.

## Known gaps / discrepancies
- The map (`mapa_rutas.html`) only ever reflects OR-Tools; there's no way to visualize the GA's solution without editing the script.
- The GA has no construction heuristic or local search — it's a baseline implementation for comparison, not yet a competitive alternative.
- `geodata.py`, `visualize.py`, `maptest.py` remain in `Code/` uncleaned; leftovers from early exploration.
- **The flat and `pipeline/` scripts collide on output filenames.** `Code/build_time_matrix.py` reads `Data/oxxo-stops.csv` (218 clean production stores) while `Code/pipeline/time_matrix.py` reads `Data/oxxo-stopsTEST.csv` (219 stores — includes a leftover `Test1` placeholder from testing `add_points.py`), but both write to the same `Data/points-index.csv`, and both solvers write to the same `Data/routes-solution.csv`. Whichever pipeline ran most recently wins. As of this write-up, the committed `points-index.csv` / `routes-solution.csv` / matrices reflect the **pipeline** run against the TEST data (219 stops, 6 trucks, 1204.5 km, 42h24m total), not a clean run of the original 218-store production set. Running `Code/build_time_matrix.py` + `Code/solve_routes.py` again would overwrite them back to the clean baseline in the table above. Worth giving each pipeline its own output paths (or removing the flat scripts) before this causes confusion.
- `Data/oxxo-stopsTEST.csv` still carries the `Test1` placeholder row used to catch the duplicate-id bug; it's harmless for `pipeline/` runs but shouldn't be mistaken for real store data.
