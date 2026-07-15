import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Code"))

import visualize_routes as vr


@pytest.fixture
def points():
    return pd.DataFrame(
        {
            "id": ["DEPOT::D", "LANDFILL::L", "STOP::A", "STOP::B"],
            "tienda": ["D", "L", "A", "B"],
            "tipo": ["DEPOT", "LANDFILL", "STOP", "STOP"],
            "latitud": [28.69, 28.70, 28.63, 28.64],
            "longitud": [-106.12, -106.03, -106.07, -106.08],
        }
    )


@pytest.fixture
def solution():
    return pd.DataFrame(
        {
            "truck": [0, 0, 0, 1, 1],
            "seq": [0, 1, 2, 0, 1],
            "id": ["STOP::A", "STOP::B", "LANDFILL::L", "STOP::B", "LANDFILL::L"],
            "tienda": ["A", "B", "L", "B", "L"],
            "tipo": ["STOP", "STOP", "LANDFILL", "STOP", "LANDFILL"],
            "arrival_seconds": [300, 700, 2000, 400, 1500],
            "load_after_cbm": [0.9, 1.8, 0.0, 0.9, 0.0],
        }
    )


def test_build_truck_path_closes_loop_at_depot(points, solution):
    path = vr.build_truck_path(solution[solution["truck"] == 0], points, 0)

    assert path[0][:2] == (28.69, -106.12)
    assert path[-1][:2] == (28.69, -106.12)
    assert [label for _, _, label in path] == [
        "DEPOT", "STOP::A", "STOP::B", "LANDFILL::L", "DEPOT",
    ]


def test_truck_color_cycles():
    assert vr.truck_color(0) == vr.truck_color(len(vr.TRUCK_COLORS))
    assert vr.truck_color(1) != vr.truck_color(2)


def test_format_minutes():
    assert vr.format_minutes(0) == "0h00m"
    assert vr.format_minutes(3900) == "1h05m"


def test_build_map_has_layer_per_active_truck(points, solution):
    html = vr.build_map(solution, points, use_roads=False).get_root().render()

    assert "Camion 0 (2 paradas)" in html
    assert "Camion 1 (1 paradas)" in html
    assert "DEPOT: D" in html
    assert "LANDFILL: L" in html


def test_build_map_draws_direction_arrows_per_truck(points, solution):
    html = vr.build_map(solution, points, use_roads=False).get_root().render()

    assert html.count("setText") == solution["truck"].nunique()
    # folium serializes the arrow glyph as a JS unicode escape
    assert "\\u27a4" in html


@pytest.fixture
def summary():
    return pd.DataFrame(
        {
            "truck": [0, 1],
            "stops": [2, 1],
            "dumps": [1, 1],
            "total_seconds": [2500, 1900],
            "total_meters": [12000.0, 5000.0],
        }
    )


def test_build_map_shows_per_truck_distance_and_time(points, solution, summary):
    html = vr.build_map(solution, points, use_roads=False, summary=summary).get_root().render()

    assert "12.0 km" in html
    assert "5.0 km" in html


def test_build_map_shows_fleet_totals_panel(points, solution, summary):
    html = vr.build_map(solution, points, use_roads=False, summary=summary).get_root().render()

    assert "Resumen de la flota" in html
    assert "17.0 km" in html
    assert vr.format_minutes(4400) in html


def test_build_map_without_summary_has_no_stats_panel(points, solution):
    html = vr.build_map(solution, points, use_roads=False).get_root().render()

    assert "Resumen de la flota" not in html


def test_stats_panel_html_aggregates_fleet_totals(summary):
    html = vr.stats_panel_html(summary)

    assert "Camiones usados: 2" in html
    assert "Paradas totales: 3" in html
    assert "Viajes al relleno: 2" in html
    assert "17.0 km" in html
    assert vr.format_minutes(4400) in html


def test_build_map_written_to_file(tmp_path, points, solution):
    out = tmp_path / "mapa.html"
    vr.build_map(solution, points, use_roads=False).save(str(out))
    assert out.exists() and out.stat().st_size > 0


PATH = [(28.69, -106.12, "DEPOT"), (28.63, -106.07, "STOP::A"), (28.69, -106.12, "DEPOT")]


def test_fetch_road_geometry_converts_lonlat_to_latlon():
    fake_json = {
        "routes": [
            {"geometry": {"coordinates": [[-106.12, 28.69], [-106.09, 28.66], [-106.07, 28.63]]}}
        ]
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_json

    with patch.object(vr.requests, "get", return_value=FakeResponse()) as mock_get:
        geometry = vr.fetch_road_geometry(PATH)

    assert geometry == [(28.69, -106.12), (28.66, -106.09), (28.63, -106.07)]
    assert "-106.12,28.69;-106.07,28.63;-106.12,28.69" in mock_get.call_args.args[0]


def test_route_line_falls_back_to_straight_lines_on_error():
    with patch.object(vr.requests, "get", side_effect=vr.requests.ConnectionError("down")):
        coords = vr.route_line_coords(PATH, use_roads=True)

    assert coords == [(28.69, -106.12), (28.63, -106.07), (28.69, -106.12)]


def test_route_line_skips_network_when_roads_disabled():
    with patch.object(vr.requests, "get") as mock_get:
        coords = vr.route_line_coords(PATH, use_roads=False)

    mock_get.assert_not_called()
    assert coords == [(28.69, -106.12), (28.63, -106.07), (28.69, -106.12)]
