"""
Draws the solved trash-collection routes on an interactive map: one
toggleable colored layer per truck, numbered stop markers, and distinct
depot/landfill icons. Route lines follow the real road geometry from
OSRM's /route service, falling back to straight segments if unreachable.
Per-truck distance/time totals (from the solver's summary CSV) are shown
in each layer's label and in a fleet-wide stats panel on the map.

Usage:
    python3 visualize_routes.py
"""

import time

import folium
import pandas as pd
import requests
from folium.plugins import PolyLineTextPath

POINTS_INDEX_SRC = "Data/points-index.csv"
SOLUTION_SRC = "Data/routes-solution.csv"
SUMMARY_SRC = "Data/routes-solution-summary.csv"
MAP_DST = "Data/mapa_rutasTEST.html"

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
REQUEST_DELAY_SECONDS = 1

TRUCK_COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
    "darkpurple",
    "black",
]

class Map:
    def __init__(self):
        pass

    def truck_color(self, truck):
        return TRUCK_COLORS[truck % len(TRUCK_COLORS)]


    def build_truck_path(self, solution, points, truck):
        """Returns the truck's visit sequence as (lat, lon, label) tuples,
        with the depot prepended and appended to close the loop."""
        coords_by_id = points.set_index("id")[["latitud", "longitud"]]
        depot = points[points["tipo"] == "DEPOT"].iloc[0]

        visits = solution[solution["truck"] == truck].sort_values("seq")
        path = [(depot["latitud"], depot["longitud"], "DEPOT")]
        for _, visit in visits.iterrows():
            lat, lon = coords_by_id.loc[visit["id"]]
            path.append((lat, lon, visit["id"]))
        path.append((depot["latitud"], depot["longitud"], "DEPOT"))
        return path


    def fetch_road_geometry(self, path):
        """Asks OSRM for the driving geometry through the path's waypoints.
        Returns (lat, lon) tuples, or None if the request fails."""
        coords = ";".join(f"{lon},{lat}" for lat, lon, _ in path)
        url = OSRM_ROUTE_URL.format(coords=coords)
        try:
            response = requests.get(
                url, params={"overview": "full", "geometries": "geojson"}, timeout=30
            )
            response.raise_for_status()
            geometry = response.json()["routes"][0]["geometry"]["coordinates"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            print(f"OSRM /route fallo ({exc}); usando lineas rectas.")
            return None
        return [(lat, lon) for lon, lat in geometry]


    def route_line_coords(self, path, use_roads=True):
        """Road geometry for the route, or the straight-line path as fallback."""
        if use_roads:
            geometry = self.fetch_road_geometry(path)
            if geometry:
                return geometry
        return [(lat, lon) for lat, lon, _ in path]


    def format_minutes(self, seconds):
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


    def stats_panel_html(self, summary):
        """Floating box with the fleet totals: trucks used, distance, time, dumps."""
        total_meters = summary["total_meters"].sum()
        total_seconds = int(summary["total_seconds"].sum())
        total_stops = int(summary["stops"].sum())
        total_dumps = int(summary["dumps"].sum())
        trucks_used = summary["truck"].nunique()

        return f"""
        <div style="
            position: fixed; top: 10px; left: 10px; z-index: 9999;
            background: white; padding: 10px 14px; border: 2px solid #444;
            border-radius: 6px; font-size: 14px; line-height: 1.5;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        ">
            <b>Resumen de la flota</b><br>
            Camiones usados: {trucks_used}<br>
            Paradas totales: {total_stops}<br>
            Viajes al relleno: {total_dumps}<br>
            Distancia total: {total_meters / 1000:.1f} km<br>
            Tiempo total: {self.format_minutes(total_seconds)}
        </div>
        """


    def build_map(self, solution, points, use_roads=True, summary=None):
        depot = points[points["tipo"] == "DEPOT"].iloc[0]
        landfill = points[points["tipo"] == "LANDFILL"].iloc[0]

        mapa = folium.Map(
            location=[points["latitud"].mean(), points["longitud"].mean()],
            zoom_start=12,
            tiles="OpenStreetMap",
        )

        folium.Marker(
            [depot["latitud"], depot["longitud"]],
            tooltip=f"DEPOT: {depot['tienda']}",
            icon=folium.Icon(color="gray", icon="home"),
        ).add_to(mapa)
        folium.Marker(
            [landfill["latitud"], landfill["longitud"]],
            tooltip=f"LANDFILL: {landfill['tienda']}",
            icon=folium.Icon(color="gray", icon="trash", prefix="fa"),
        ).add_to(mapa)

        for truck in sorted(solution["truck"].unique()):
            visits = solution[solution["truck"] == truck].sort_values("seq")
            if visits.empty:
                continue
            color = self.truck_color(truck)
            stops = (visits["tipo"] == "STOP").sum()
            label = f"Camion {truck} ({stops} paradas)"
            if summary is not None:
                truck_summary = summary[summary["truck"] == truck]
                if not truck_summary.empty:
                    km = truck_summary["total_meters"].iloc[0] / 1000
                    shift = self.format_minutes(int(truck_summary["total_seconds"].iloc[0]))
                    label = f"Camion {truck} ({stops} paradas, {km:.1f} km, {shift})"
            group = folium.FeatureGroup(name=label)

            path = self.build_truck_path(solution, points, truck)
            line = folium.PolyLine(
                self.route_line_coords(path, use_roads),
                color=color,
                weight=3,
                opacity=0.7,
            )
            line.add_to(group)
            if use_roads:
                time.sleep(REQUEST_DELAY_SECONDS)
            PolyLineTextPath(
                line,
                "  ➤  ",
                repeat=True,
                offset=5,
                attributes={"fill": color, "font-size": "14"},
            ).add_to(group)

            for _, visit in visits.iterrows():
                lat, lon = path[visit["seq"] + 1][0], path[visit["seq"] + 1][1]
                popup = (
                    f"<b>{visit['tienda']}</b><br>"
                    f"Camion {truck}, visita {visit['seq'] + 1}<br>"
                    f"Llegada: {self.format_minutes(int(visit['arrival_seconds']))}<br>"
                    f"Carga al salir: {visit['load_after_cbm']} cbm"
                )
                if visit["tipo"] == "LANDFILL":
                    folium.CircleMarker(
                        [lat, lon],
                        radius=8,
                        color=color,
                        fill=True,
                        fill_opacity=0.9,
                        popup=folium.Popup(popup, max_width=250),
                        tooltip=f"Camion {truck}: descarga",
                    ).add_to(group)
                else:
                    folium.CircleMarker(
                        [lat, lon],
                        radius=4,
                        color=color,
                        fill=True,
                        fill_opacity=0.7,
                        popup=folium.Popup(popup, max_width=250),
                        tooltip=f"{visit['seq'] + 1}. {visit['tienda']}",
                    ).add_to(group)

            group.add_to(mapa)

        if summary is not None and not summary.empty:
            mapa.get_root().html.add_child(folium.Element(self.stats_panel_html(summary)))

        folium.LayerControl(collapsed=False).add_to(mapa)
        return mapa


    def main(self):
        points = pd.read_csv(POINTS_INDEX_SRC)
        solution = pd.read_csv(SOLUTION_SRC)
        try:
            summary = pd.read_csv(SUMMARY_SRC)
        except FileNotFoundError:
            summary = None

        mapa = self.build_map(solution, points, summary=summary)
        mapa.save(MAP_DST)
        print(f"Mapa guardado en: {MAP_DST}")

