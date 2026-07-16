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

| Solver | File | Status | Result (218 stops) |
|---|---|---|---|
| OR-Tools (baseline) | `Code/solve_routes.py` | Feeds the map | 41h58m total, 1185.4 km, 6 trucks used, 28 landfill trips (60s limit) |
| Genetic algorithm (GA) | `Code/solve_ga.py` | Implemented and tested, feeds the map alongside OR-Tools | 43h07m total, 1236.0 km, 6 trucks used, 28 landfill trips (60s limit, tuned params, seed=0) |

- **`Code/vrp_common.py`** — shared module: data loading, route costing (`summarize_route`), deterministic landfill-dump insertion (`insert_dumps`), and CSV reporting (`report_solution`). Both solvers and the benchmark use it so they compete on the exact same cost definition.
- **`Code/benchmark_solvers.py`** — runs both solvers with the same time budget and prints a comparison table.
- **Comparison result**: after seeding part of the initial population with nearest-neighbor-constructed tours (`nearest_neighbor_tour`) refined by 2-opt (`two_opt`, also reapplied to the elites carried over each generation), the GA closed most of the gap to OR-Tools: at a 60s budget, 43h26m/1248.9km/6 trucks vs. OR-Tools' 41h58m/1185.4km/6 trucks (previously 66h12m/2619.5km/10 trucks with pure-random init and no local search). Bumping the GA's budget to 120s barely moved the result (43h39m/1270.3km) -- it plateaus well before then, so more time alone wasn't the lever.
- **Hyperparameter tuning (`Code/tune_ga.py`)**: a sequential grid search (stage 1: `nn_seed_fraction` x `two_opt_max_passes`, holding the rest fixed; stage 2: `population_size` x `mutation_rate` x `tournament_k`, holding stage 1's winner fixed -- 47 trials total at a 60s budget each against the real 218-stop instance, seed=0) found `population_size=60, mutation_rate=0.15, tournament_k=5, nn_seed_fraction=1.0, two_opt_max_passes=3` best: 43h07m/1236.0km, a further improvement over the untuned 43h26m/1248.9km. `nn_seed_fraction=1.0` (fully NN+2-opt-constructed initial population, no random individuals) winning was the biggest surprise -- across the whole grid, results only spanned about a 40-minute band (43h07m-43h46m), meaning the 2-opt-refined construction step dominates solution quality far more than any of the generational-loop knobs (crossover/mutation/selection barely move the needle at this problem's scale). These are now `solve()`'s defaults, still not exposed on the CLI (same as `elite_size`). Trial-by-trial results are in `Data/ga-tuning-trials.csv`; rerun with `python3 tune_ga.py` if the data changes significantly.
- **Gotcha fixed**: `solve_ga.py`'s and `benchmark_solvers.py`'s `main()` CLI parsers had their own argparse defaults for `--population`/`--mutation-rate`, separate from `solve()`'s own defaults, and always passed them explicitly -- so tuning `solve()`'s defaults silently had no effect unless the matching CLI flags were also passed. Fixed by keeping both in sync and exposing `--tournament-k` on both entrypoints.

## Interactive add-stop pipeline (`Code/pipeline/`)
A second, class-based pipeline was added alongside the original flat scripts: `TimeMatrixBuilder` (`time_matrix.py`), `Solution` (`solve_routes.py`), and `Map` (`visualize_routes.py`) are mechanical refactors of `build_time_matrix.py` / `solve_routes.py` / `visualize_routes.py` into classes with identical logic, plus a new `add_points.py` entrypoint that:
1. Loads `Data/oxxo-stops.csv`, interactively prompts for new stops (tienda/direccion/ciudad/lat/lon), and appends them to a working copy at `Data/pipeline/oxxo-stops.csv`.
2. Re-runs `time_matrix.main() -> solve_routes.main() -> visualize_routes.main()` end to end, reading/writing all its intermediate outputs (`points-index.csv`, matrices, `routes-solution.csv`, its summary, `mapa_rutas.html`) under `Data/pipeline/`, isolated from the flat scripts' `Data/` outputs.

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
- **Fixed**: the flat `Code/visualize_routes.py` now overlays both solvers on the same map when `Data/routes-solution-ga.csv` exists -- OR-Tools solid lines, GA dashed, same per-truck color in both, plus a side-by-side comparison panel (trucks/dumps/distance/time) instead of the single-solver stats panel. Falls back to OR-Tools-only if the GA file is missing. The `Code/pipeline/` copy of `visualize_routes.py` is unchanged (still OR-Tools-only).
- The GA has no construction heuristic or local search — it's a baseline implementation for comparison, not yet a competitive alternative.
- `geodata.py`, `visualize.py`, `maptest.py` remain in `Code/` uncleaned; leftovers from early exploration.
- **Fixed: the flat and `pipeline/` scripts used to collide on output filenames.** They previously both wrote `Data/points-index.csv` and `Data/routes-solution.csv`, so whichever pipeline ran most recently silently won. Fixed by giving `Code/pipeline/*` its own `Data/pipeline/` directory (own copy of `oxxo-stops.csv`, `points-index.csv`, both matrices, `routes-solution.csv` + summary, `mapa_rutas.html`); the flat scripts still read/write `Data/` directly. `Code/pipeline/add_points.py` still reads its base stop list from the top-level `Data/oxxo-stops.csv` (218 clean stores) and appends new stops into `Data/pipeline/oxxo-stops.csv` only.
- Both pipelines have since been rerun end to end against the fixed paths: the flat scripts regenerated `Data/`'s genuine 218-store baseline (41h58m, 1185.4 km, 6 trucks, 28 landfill trips — matches the table above exactly), and `Code/pipeline/*` regenerated `Data/pipeline/`'s 219-store result (42h24m, 1204.5 km, 6 trucks, 28 landfill trips — matches the table above exactly). Each directory is now self-consistent and reflects its own pipeline only.
- `Data/pipeline/oxxo-stops.csv` still carries the `Test1` placeholder row used to catch the duplicate-id bug; it's harmless for `pipeline/` runs but shouldn't be mistaken for real store data.
