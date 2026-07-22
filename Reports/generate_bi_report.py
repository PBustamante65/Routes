"""
Generates a multi-page BI-style PDF summarizing the VRP solver results:
OR-Tools vs GA headline KPIs, per-truck breakdown, and the GA hyperparameter
tuning sweep. Reads the CSV outputs already produced by the solving pipeline
(Code/solve_routes.py, Code/solve_ga.py, Code/tune_ga.py) -- it doesn't solve
anything itself.

Usage:
    python3 generate_bi_report.py [--out Reports/bi_report.pdf]
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

OR_TOOLS_SRC = "Data/routes-solution-summary.csv"
OR_TOOLS_ROUTES_SRC = "Data/routes-solution.csv"
GA_SRC = "Data/routes-solution-ga-summary.csv"
TUNING_SRC = "Data/ga-tuning-trials.csv"
POINTS_SRC = "Data/points-index.csv"
DEFAULT_OUT = "Reports/bi_report.pdf"

NUM_TRUCKS = 10
TRUCK_CAPACITY_CBM = 8.0
STOP_DEMAND_CBM = 0.9
STOP_SERVICE_SECONDS = 180
DUMP_SERVICE_SECONDS = 900
SHIFT_CAP_SECONDS = 8 * 3600

PAGE_SIZE = (11, 8.5)

# Reference palette (see dataviz skill): categorical slots assigned by fixed
# order/identity (OR-Tools = slot 1, GA = slot 2), never swapped or cycled.
SURFACE = "#fcfcfb"
PAGE_PLANE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

OR_TOOLS_COLOR = "#2a78d6"  # categorical slot 1 (blue)
GA_COLOR = "#008300"  # categorical slot 2 (green)
TUNING_COLORS = ["#2a78d6", "#008300", "#e87ba4", "#eda100"]  # slots 1-4

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "text.color": INK_PRIMARY,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "figure.facecolor": PAGE_PLANE,
        "axes.facecolor": SURFACE,
    }
)


def load_kpis():
    or_tools = pd.read_csv(OR_TOOLS_SRC)
    ga = pd.read_csv(GA_SRC)
    kpis = {}
    for name, df in [("OR-Tools", or_tools), ("GA", ga)]:
        kpis[name] = {
            "trucks_used": df["truck"].nunique(),
            "stops": int(df["stops"].sum()),
            "dumps": int(df["dumps"].sum()),
            "total_hours": df["total_seconds"].sum() / 3600,
            "total_km": df["total_meters"].sum() / 1000,
            "per_truck": df,
        }
    return kpis


def draw_kpi_tile(ax, title, or_value, ga_value, fmt, unit=""):
    ax.set_facecolor(SURFACE)
    for spine in ax.spines.values():
        spine.set_color(GRIDLINE)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.06, 0.82, title, fontsize=11, color=INK_SECONDARY, transform=ax.transAxes)
    ax.text(
        0.06,
        0.52,
        fmt.format(or_value) + unit,
        fontsize=20,
        color=OR_TOOLS_COLOR,
        fontweight="bold",
        transform=ax.transAxes,
    )
    ax.text(0.06, 0.38, "OR-Tools", fontsize=9, color=INK_MUTED, transform=ax.transAxes)
    ax.text(
        0.06,
        0.20,
        fmt.format(ga_value) + unit,
        fontsize=20,
        color=GA_COLOR,
        fontweight="bold",
        transform=ax.transAxes,
    )
    ax.text(0.06, 0.06, "GA", fontsize=9, color=INK_MUTED, transform=ax.transAxes)
    delta_pct = (ga_value - or_value) / or_value * 100
    ax.text(
        0.94,
        0.52,
        f"{delta_pct:+.1f}%",
        fontsize=11,
        color=INK_SECONDARY,
        ha="right",
        transform=ax.transAxes,
    )


def page_cover(pdf, kpis):
    fig = plt.figure(figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.text(0.06, 0.93, "VRP Solver Comparison", fontsize=26, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.885,
        "Chihuahua Oxxo garbage-collection routing -- OR-Tools vs. genetic algorithm, 218 stops",
        fontsize=12,
        color=INK_SECONDARY,
    )

    stops = kpis["OR-Tools"]["stops"]
    fig.text(
        0.06,
        0.845,
        f"{stops} stops served by both solvers under the same shift cap, capacity, and landfill-dump model.",
        fontsize=10,
        color=INK_MUTED,
    )

    gs = fig.add_gridspec(1, 4, left=0.06, right=0.96, top=0.78, bottom=0.55, wspace=0.06)
    tiles = [
        ("Total time", "total_hours", "{:.1f}", "h"),
        ("Total distance", "total_km", "{:.1f}", " km"),
        ("Trucks used", "trucks_used", "{:.0f}", ""),
        ("Landfill trips", "dumps", "{:.0f}", ""),
    ]
    for i, (title, key, fmt, unit) in enumerate(tiles):
        ax = fig.add_subplot(gs[0, i])
        draw_kpi_tile(ax, title, kpis["OR-Tools"][key], kpis["GA"][key], fmt, unit)

    fig.text(
        0.06,
        0.47,
        "Read this report as:",
        fontsize=11,
        fontweight="bold",
        color=INK_PRIMARY,
    )
    body = (
        "OR-Tools remains the stronger baseline on this instance (fewer km, less total drive+service "
        "time), but the GA -- after adding nearest-neighbor + 2-opt construction and a tuned hyperparameter "
        "set (Code/tune_ga.py) -- closes most of the gap while matching OR-Tools on trucks used and "
        "landfill trips. Pages 2-4 compare the two solutions; page 5 shows the tuning sweep behind the "
        "GA's current defaults; pages 6-7 cover the pipeline/problem setup and open next steps."
    )
    fig.text(0.06, 0.43, body, fontsize=10.5, color=INK_SECONDARY, wrap=True, va="top")

    fig.text(
        0.06,
        0.04,
        "Source: Data/routes-solution-summary.csv, Data/routes-solution-ga-summary.csv, Data/ga-tuning-trials.csv",
        fontsize=8,
        color=INK_MUTED,
    )
    pdf.savefig(fig)
    plt.close(fig)


def page_comparison(pdf, kpis):
    fig, axes = plt.subplots(1, 2, figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.subplots_adjust(top=0.82, bottom=0.14, left=0.08, right=0.96, wspace=0.28)
    fig.text(0.06, 0.93, "Headline result", fontsize=18, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.885,
        "Same cost model, same instance, 60s solve budget each -- lower is better on both charts.",
        fontsize=10.5,
        color=INK_SECONDARY,
    )

    solvers = ["OR-Tools", "GA"]
    colors = [OR_TOOLS_COLOR, GA_COLOR]

    ax = axes[0]
    values = [kpis[s]["total_hours"] for s in solvers]
    bars = ax.bar(solvers, values, color=colors, width=0.55)
    ax.set_title("Total time (fleet-hours)", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.set_ylabel("hours")
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.6, f"{v:.1f}h", ha="center", fontsize=10, color=INK_PRIMARY)

    ax = axes[1]
    values = [kpis[s]["total_km"] for s in solvers]
    bars = ax.bar(solvers, values, color=colors, width=0.55)
    ax.set_title("Total distance (km)", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.set_ylabel("km")
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 8, f"{v:.0f} km", ha="center", fontsize=10, color=INK_PRIMARY)

    fig.text(
        0.06,
        0.03,
        "Both solvers use 6 trucks and 28 landfill trips for this instance -- fleet size and dump count are identical.",
        fontsize=9,
        color=INK_MUTED,
    )
    pdf.savefig(fig)
    plt.close(fig)


def page_per_truck(pdf, kpis):
    fig, axes = plt.subplots(2, 1, figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.subplots_adjust(top=0.86, bottom=0.08, left=0.07, right=0.97, hspace=0.4)
    fig.text(0.06, 0.94, "Per-truck breakdown", fontsize=18, fontweight="bold", color=INK_PRIMARY)

    or_df = kpis["OR-Tools"]["per_truck"].sort_values("truck")
    ga_df = kpis["GA"]["per_truck"].sort_values("truck")
    trucks = or_df["truck"].astype(str)
    x = range(len(trucks))
    width = 0.35

    ax = axes[0]
    ax.bar([i - width / 2 for i in x], or_df["total_meters"] / 1000, width, color=OR_TOOLS_COLOR, label="OR-Tools")
    ax.bar([i + width / 2 for i in x], ga_df["total_meters"] / 1000, width, color=GA_COLOR, label="GA")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Truck {t}" for t in trucks])
    ax.set_ylabel("km")
    ax.set_title("Distance per truck", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper right", fontsize=9)

    ax = axes[1]
    ax.bar([i - width / 2 for i in x], or_df["stops"], width, color=OR_TOOLS_COLOR, label="OR-Tools")
    ax.bar([i + width / 2 for i in x], ga_df["stops"], width, color=GA_COLOR, label="GA")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Truck {t}" for t in trucks])
    ax.set_ylabel("stops")
    ax.set_title("Stops assigned per truck", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper right", fontsize=9)

    pdf.savefig(fig)
    plt.close(fig)


def page_route_snapshot(pdf):
    points = pd.read_csv(POINTS_SRC).set_index("id")
    routes = pd.read_csv(OR_TOOLS_ROUTES_SRC)
    depot_id = points[points["tipo"] == "DEPOT"].index[0]
    depot_xy = (points.loc[depot_id, "longitud"], points.loc[depot_id, "latitud"])

    trucks = sorted(routes["truck"].unique())
    fig, axes = plt.subplots(2, 3, figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.subplots_adjust(top=0.80, bottom=0.06, left=0.05, right=0.97, hspace=0.35, wspace=0.25)
    fig.text(0.06, 0.94, "Route snapshot -- OR-Tools solution", fontsize=18, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.90,
        "Stop sequence per truck, straight-line (schematic, not street geometry). Depot = square,\n"
        "landfill dump = triangle, stop = dot. Full turn-by-turn detail: Data/mapa_rutas.html.",
        fontsize=10,
        color=INK_SECONDARY,
    )

    for ax, truck in zip(axes.flat, trucks):
        leg = routes[routes["truck"] == truck].sort_values("seq")
        lons = [depot_xy[0]] + [points.loc[i, "longitud"] for i in leg["id"]] + [depot_xy[0]]
        lats = [depot_xy[1]] + [points.loc[i, "latitud"] for i in leg["id"]] + [depot_xy[1]]
        ax.plot(lons, lats, color=OR_TOOLS_COLOR, linewidth=1, alpha=0.6, zorder=1)

        stop_mask = leg["tipo"] == "STOP"
        dump_mask = leg["tipo"] == "LANDFILL"
        stop_lons = [points.loc[i, "longitud"] for i in leg.loc[stop_mask, "id"]]
        stop_lats = [points.loc[i, "latitud"] for i in leg.loc[stop_mask, "id"]]
        dump_lons = [points.loc[i, "longitud"] for i in leg.loc[dump_mask, "id"]]
        dump_lats = [points.loc[i, "latitud"] for i in leg.loc[dump_mask, "id"]]

        ax.scatter(stop_lons, stop_lats, s=14, color=OR_TOOLS_COLOR, zorder=2)
        ax.scatter(dump_lons, dump_lats, s=45, marker="^", color=INK_SECONDARY, zorder=3)
        ax.scatter([depot_xy[0]], [depot_xy[1]], s=60, marker="s", color=INK_PRIMARY, zorder=4)

        stops_n = int(stop_mask.sum())
        dumps_n = int(dump_mask.sum())
        ax.set_title(f"Truck {truck}  --  {stops_n} stops, {dumps_n} dumps", fontsize=10, color=INK_PRIMARY, loc="left")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(GRIDLINE)
        ax.set_aspect("equal")

    pdf.savefig(fig)
    plt.close(fig)


def page_methodology(pdf):
    fig = plt.figure(figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.text(0.06, 0.94, "Methodology & problem setup", fontsize=18, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.895,
        "Multi-trip vehicle routing problem (VRP) with intermediate landfill disposal, "
        "218 Oxxo convenience stores in Chihuahua, Chihuahua, Mexico.",
        fontsize=10.5,
        color=INK_SECONDARY,
    )

    fig.text(0.06, 0.83, "Problem constraints", fontsize=12, fontweight="bold", color=INK_PRIMARY)
    constraints = [
        ("Fleet size", f"{NUM_TRUCKS} trucks available"),
        ("Truck capacity", f"{TRUCK_CAPACITY_CBM:.0f} m3 per truck"),
        ("Shift cap", f"{SHIFT_CAP_SECONDS // 3600}h per truck per day"),
        ("Stop demand", f"{STOP_DEMAND_CBM} m3 collected per stop"),
        ("Stop service time", f"{STOP_SERVICE_SECONDS}s per stop"),
        ("Landfill dump time", f"{DUMP_SERVICE_SECONDS // 60} min per dump"),
    ]
    gs = fig.add_gridspec(2, 3, left=0.06, right=0.96, top=0.79, bottom=0.60, hspace=0.15, wspace=0.06)
    for i, (label, value) in enumerate(constraints):
        ax = fig.add_subplot(gs[i // 3, i % 3])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(GRIDLINE)
        ax.text(0.08, 0.68, label, fontsize=9.5, color=INK_SECONDARY, transform=ax.transAxes)
        ax.text(0.08, 0.30, value, fontsize=13, color=INK_PRIMARY, fontweight="bold", transform=ax.transAxes)
    fig.text(
        0.06,
        0.575,
        "A truck returns to the landfill to empty its load whenever the next stop would exceed capacity "
        "(vrp_common.insert_dumps), so dump count is a consequence of the route, not a solver input.",
        fontsize=9,
        color=INK_MUTED,
    )

    fig.text(0.06, 0.51, "Data pipeline", fontsize=12, fontweight="bold", color=INK_PRIMARY)
    steps = [
        ("1. Geocode", "Store addresses -> lat/lon\n(Data/oxxo-stops.csv)"),
        ("2. Build matrices", "OSRM /table -> time + distance\nmatrices (build_time_matrix.py)"),
        ("3. Solve", "OR-Tools baseline and GA\n(solve_routes.py, solve_ga.py)"),
        ("4. Visualize", "Interactive Folium map, real\nstreet geometry (visualize_routes.py)"),
    ]
    box_w, gap, start_x, box_y, box_h = 0.21, 0.025, 0.06, 0.34, 0.14
    for i, (title, desc) in enumerate(steps):
        x0 = start_x + i * (box_w + gap)
        rect = plt.Rectangle(
            (x0, box_y), box_w, box_h, transform=fig.transFigure,
            facecolor=SURFACE, edgecolor=BASELINE, linewidth=1, zorder=1,
        )
        fig.add_artist(rect)
        fig.text(x0 + 0.012, box_y + box_h - 0.03, title, fontsize=10, fontweight="bold", color=INK_PRIMARY, va="top")
        fig.text(x0 + 0.012, box_y + box_h - 0.065, desc, fontsize=8, color=INK_SECONDARY, va="top")
        if i < len(steps) - 1:
            fig.text(
                x0 + box_w + gap / 2, box_y + box_h / 2, ">",
                fontsize=14, color=INK_MUTED, ha="center", va="center",
            )

    fig.text(0.06, 0.27, "Solvers & validation", fontsize=12, fontweight="bold", color=INK_PRIMARY)
    body = (
        "Both solvers consume the same points index and time/distance matrices and share one cost "
        "definition (vrp_common.py: summarize_route, insert_dumps, report_solution), so they compete on "
        "identical terms. OR-Tools is Google's constraint-programming VRP solver, run as a fixed-budget "
        "baseline. The GA builds each chromosome as a permutation of stops, seeds part of its initial "
        "population with nearest-neighbor tours refined by 2-opt, and reapplies 2-opt to elites each "
        "generation -- its hyperparameters were chosen by a 47-trial grid search (Code/tune_ga.py, see "
        "the tuning page). Correctness is covered by 46 pytest tests across both solvers, the shared cost "
        "model, and the benchmark harness."
    )
    fig.text(0.06, 0.235, body, fontsize=9.5, color=INK_SECONDARY, wrap=True, va="top")

    fig.text(
        0.06,
        0.04,
        "Source: Claude/project_status.md, Code/vrp_common.py, Code/tune_ga.py",
        fontsize=8,
        color=INK_MUTED,
    )
    pdf.savefig(fig)
    plt.close(fig)


def page_recommendations(pdf, kpis):
    fig = plt.figure(figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.text(0.06, 0.94, "Recommendations & next steps", fontsize=18, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.895,
        "Open items from the current pipeline (Claude/project_status.md) worth acting on next.",
        fontsize=10.5,
        color=INK_SECONDARY,
    )

    km_delta = (kpis["GA"]["total_km"] - kpis["OR-Tools"]["total_km"]) / kpis["OR-Tools"]["total_km"] * 100
    hours_delta = (
        (kpis["GA"]["total_hours"] - kpis["OR-Tools"]["total_hours"]) / kpis["OR-Tools"]["total_hours"] * 100
    )

    items = [
        (
            "High",
            "Expose the GA's tuned hyperparameters on the CLI.",
            "population_size, mutation_rate, tournament_k, nn_seed_fraction, two_opt_max_passes, and "
            "elite_size are solve()'s defaults but not CLI flags -- re-tuning or A/B-testing them today "
            "means editing source, which is also what caused the earlier CLI/default-drift bug.",
        ),
        (
            "Medium",
            "Bring Code/pipeline/visualize_routes.py to parity with the flat script.",
            "The flat Code/visualize_routes.py overlays OR-Tools and GA on one map; the class-based "
            "pipeline/ copy is still OR-Tools-only. Either port the overlay or document the divergence "
            "so it isn't mistaken for a bug.",
        ),
        (
            "Medium",
            "Clean up or remove the uncleaned exploratory scripts.",
            "Code/geodata.py, visualize.py, and maptest.py have no CLI or docstring and aren't part of "
            "the active pipeline -- they're easy to mistake for live code by a new contributor.",
        ),
        (
            "Low",
            "Strip the Test1 placeholder row from Data/pipeline/oxxo-stops.csv.",
            "Left over from the duplicate-id bug fix; harmless for pipeline/ runs but should not be "
            "mistaken for a real store when that directory's output is reviewed.",
        ),
        (
            "Watch",
            "GA is a validated fallback, not yet a replacement for OR-Tools.",
            f"Tuned, it trails OR-Tools by {km_delta:+.1f}% km and {hours_delta:+.1f}% time on this "
            "instance -- worth keeping as a backup path (e.g. if OR-Tools' solve budget or licensing "
            "becomes a constraint) rather than switching over by default.",
        ),
    ]

    y = 0.82
    for priority, title, detail in items:
        fig.text(0.06, y, priority.upper(), fontsize=8.5, color=INK_MUTED, fontweight="bold")
        fig.text(0.145, y, title, fontsize=11.5, color=INK_PRIMARY, fontweight="bold")
        fig.text(0.06, y - 0.035, detail, fontsize=9.5, color=INK_SECONDARY, wrap=True, va="top")
        y -= 0.145

    pdf.savefig(fig)
    plt.close(fig)


def page_tuning(pdf):
    df = pd.read_csv(TUNING_SRC)
    stage1 = df[df["stage"] == "stage1_nn_seed_and_2opt"]
    stage2 = df[df["stage"] == "stage2_population_mutation_tournament"]
    best = df.loc[df["total_seconds"].idxmin()]

    fig, axes = plt.subplots(1, 2, figsize=PAGE_SIZE, facecolor=PAGE_PLANE)
    fig.subplots_adjust(top=0.80, bottom=0.30, left=0.08, right=0.96, wspace=0.3)
    fig.text(0.06, 0.93, "GA hyperparameter tuning", fontsize=18, fontweight="bold", color=INK_PRIMARY)
    fig.text(
        0.06,
        0.885,
        "Sequential grid search, 47 trials at a 60s budget each, real 218-stop instance (Code/tune_ga.py).",
        fontsize=10.5,
        color=INK_SECONDARY,
    )

    ax = axes[0]
    for i, passes in enumerate(sorted(stage1["two_opt_max_passes"].unique())):
        sub = stage1[stage1["two_opt_max_passes"] == passes].sort_values("nn_seed_fraction")
        color = TUNING_COLORS[i % len(TUNING_COLORS)]
        ax.plot(
            sub["nn_seed_fraction"],
            sub["total_meters"] / 1000,
            marker="o",
            markersize=5,
            linewidth=2,
            color=color,
            label=f"2-opt passes = {passes}",
        )
    ax.set_xlabel("nearest-neighbor seed fraction")
    ax.set_ylabel("km")
    ax.set_title("Stage 1: construction beats loop tuning", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.grid(color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(frameon=False, loc="upper right", fontsize=8)

    ax = axes[1]
    grouped = stage2.groupby("population_size")["total_meters"].agg(["mean", "min", "max"]) / 1000
    grouped = grouped.sort_index()
    x = list(range(len(grouped)))
    yerr_low = grouped["mean"] - grouped["min"]
    yerr_high = grouped["max"] - grouped["mean"]
    ax.errorbar(
        x,
        grouped["mean"],
        yerr=[yerr_low, yerr_high],
        fmt="o",
        color=OR_TOOLS_COLOR,
        ecolor=INK_SECONDARY,
        markersize=8,
        capsize=5,
        linewidth=1.4,
    )
    for xi, v in zip(x, grouped["mean"]):
        ax.text(xi, v + 3.5, f"{v:.0f} km", ha="center", fontsize=9, color=INK_PRIMARY)
    ax.set_xlim(-0.5, len(x) - 0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in grouped.index])
    ax.set_xlabel("population size")
    ax.set_ylabel("km (mean +/- range across mutation_rate x tournament_k)")
    ax.set_title("Stage 2: loop knobs barely move the result", fontsize=11, color=INK_PRIMARY, loc="left")
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.text(
        0.06,
        0.20,
        "Winning configuration (minimizes total time; now solve()'s default):",
        fontsize=11,
        fontweight="bold",
        color=INK_PRIMARY,
    )
    config_line = (
        f"population_size={int(best['population_size'])}   mutation_rate={best['mutation_rate']}   "
        f"tournament_k={int(best['tournament_k'])}   nn_seed_fraction={best['nn_seed_fraction']}   "
        f"two_opt_max_passes={int(best['two_opt_max_passes'])}"
    )
    fig.text(0.06, 0.155, config_line, fontsize=10, color=GA_COLOR, family="monospace")
    result_line = (
        f"-> {best['total_seconds'] / 3600:.2f}h total, {best['total_meters'] / 1000:.1f} km, "
        f"{int(best['trucks_used'])} trucks, {int(best['total_dumps'])} landfill trips"
    )
    fig.text(0.06, 0.115, result_line, fontsize=10, color=INK_SECONDARY)
    fig.text(
        0.06,
        0.06,
        "Across the full grid, results span only ~43h07m-43h46m -- the 2-opt-refined construction step "
        "dominates solution quality far more than crossover/mutation/selection at this problem's scale.",
        fontsize=9,
        color=INK_MUTED,
    )

    pdf.savefig(fig)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    kpis = load_kpis()
    with PdfPages(args.out) as pdf:
        page_cover(pdf, kpis)
        page_comparison(pdf, kpis)
        page_route_snapshot(pdf)
        page_per_truck(pdf, kpis)
        page_tuning(pdf)
        page_methodology(pdf)
        page_recommendations(pdf, kpis)

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
