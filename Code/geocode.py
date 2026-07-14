"""
Pipeline de geocodificación para RutaEditado.xlsx (hoja "RELACION TIENDAS").

Carga el excel de tiendas, construye una dirección de búsqueda por fila
(dirección completa, o nombre de tienda + ciudad si falta la dirección),
geocodifica con Nominatim/OpenStreetMap y guarda latitud/longitud.

Uso:
    python3 geocode.py            # corre la primera pasada completa
    python3 geocode.py --retry    # reintenta solo las filas sin coordenadas
                                   # del archivo de salida ya generado
"""

import sys
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

SRC = "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/RutaEditado.xlsx"
DST = "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/RutaEditado_coordenadas.xlsx"


def build_query(row):
    ciudad = row["ciudad"] if pd.notna(row["ciudad"]) else "CHIHUAHUA"
    if pd.notna(row["direccion"]):
        return f"{row['direccion']}, {ciudad}, MEXICO"
    return f"{row['tienda']}, {ciudad}, MEXICO"


def primera_pasada():
    df = pd.read_excel(SRC, sheet_name="RELACION TIENDAS", header=2)
    df.columns = ["tienda", "direccion", "ciudad", "costo_mensual"]

    # Quitar filas completamente vacías (separadores en el archivo original)
    df = df.dropna(subset=["tienda"]).reset_index(drop=True)

    df["direccion_geocodificar"] = df.apply(build_query, axis=1)
    df["direccion_aproximada"] = df["direccion"].isna()

    # timeout=10: el default de geopy (1s) causa muchos falsos timeouts
    # contra el servidor público de Nominatim.
    geolocator = Nominatim(user_agent="rutas_tiendas_chihuahua", timeout=10)
    geocode = RateLimiter(
        geolocator.geocode, min_delay_seconds=1, max_retries=3, error_wait_seconds=5
    )

    print(f"Geocodificando {len(df)} tiendas, esto tardará ~{len(df)} segundos...")
    df["location"] = df["direccion_geocodificar"].apply(geocode)

    df["latitud"] = df["location"].apply(lambda loc: loc.latitude if loc else None)
    df["longitud"] = df["location"].apply(lambda loc: loc.longitude if loc else None)

    sin_coords = df["latitud"].isna().sum()
    print(f"Tiendas sin coordenadas: {sin_coords} de {len(df)}")

    df.drop(columns=["location"]).to_excel(DST, index=False)
    print(f"Guardado en: {DST}")


def reintento():
    """Reintenta solo las filas sin coordenadas, con un ritmo más lento
    para evitar los 429 (rate limit) del servidor público de Nominatim."""
    df = pd.read_excel(DST)
    pendientes = df["latitud"].isna()
    print(f"Reintentando {pendientes.sum()} tiendas sin coordenadas...")

    geolocator = Nominatim(user_agent="rutas_tiendas_chihuahua_retry", timeout=15)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=2.5,
        max_retries=4,
        error_wait_seconds=8,
        swallow_exceptions=True,
    )

    for idx in df[pendientes].index:
        query = df.at[idx, "direccion_geocodificar"]
        loc = geocode(query)
        if loc:
            df.at[idx, "latitud"] = loc.latitude
            df.at[idx, "longitud"] = loc.longitude
            print(f"OK  : {df.at[idx, 'tienda']}")
        else:
            print(f"FAIL: {df.at[idx, 'tienda']}  ({query})")

    sin_coords = df["latitud"].isna().sum()
    print(f"\nTiendas sin coordenadas tras el reintento: {sin_coords} de {len(df)}")

    df.to_excel(DST, index=False)
    print(f"Guardado en: {DST}")


if __name__ == "__main__":
    if "--retry" in sys.argv:
        reintento()
    else:
        primera_pasada()
