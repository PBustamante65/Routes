"""
Draws the solved trash-collection routes on an interactive map: one
toggleable colored layer per truck, numbered stop markers, and distinct
depot/landfill icons. Route lines follow the real road geometry from
OSRM's /route service, falling back to straight segments if unreachable.

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
MAP_DST = "Data/mapa_rutas.html"

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
REQUEST_DELAY_SECONDS = 1

TRUCK_COLORS = [
    "red", "blue", "green", "purple", "orange",
    "darkred", "cadetblue", "darkgreen", "darkpurple", "black",
]


def truck_color(truck):
    return TRUCK_COLORS[truck % len(TRUCK_COLORS)]


def build_truck_path(solution, points, truck):
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


def fetch_road_geometry(path):
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


def route_line_coords(path, use_roads=True):
    """Road geometry for the route, or the straight-line path as fallback."""
    if use_roads:
        geometry = fetch_road_geometry(path)
        if geometry:
            return geometry
    return [(lat, lon) for lat, lon, _ in path]


def format_minutes(seconds):
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def build_map(solution, points, use_roads=True):
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
        color = truck_color(truck)
        stops = (visits["tipo"] == "STOP").sum()
        group = folium.FeatureGroup(name=f"Camion {truck} ({stops} paradas)")

        path = build_truck_path(solution, points, truck)
        line = folium.PolyLine(
            route_line_coords(path, use_roads),
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
                f"Llegada: {format_minutes(int(visit['arrival_seconds']))}<br>"
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

    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa


def main():
    points = pd.read_csv(POINTS_INDEX_SRC)
    solution = pd.read_csv(SOLUTION_SRC)

    mapa = build_map(solution, points)
    mapa.save(MAP_DST)
    print(f"Mapa guardado en: {MAP_DST}")


if __name__ == "__main__":
    main()
