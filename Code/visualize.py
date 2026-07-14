import pandas as pd
import folium
from folium.plugins import MarkerCluster

df = pd.read_excel(
    "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/RutaEditado_coordenadas2.xlsx"
)

df = df.dropna(subset=["latitud", "longitud"])

mapa = folium.Map(
    location=[df["latitud"].mean(), df["longitud"].mean()],
    zoom_start=7,
    tiles="OpenStreetMap",
)

cluster = MarkerCluster().add_to(mapa)

for _, row in df.iterrows():
    popup = f"<b>{row['tienda']}</b><br>{row['direccion'] if pd.notna(row['direccion']) else ''}<br>{row['ciudad'] if pd.notna(row['ciudad']) else ''}"
    folium.Marker(
        location=[row["latitud"], row["longitud"]],
        popup=folium.Popup(popup, max_width=250),
        tooltip=row["tienda"],
    ).add_to(cluster)

OUT = "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/mapa_tiendas.html"
mapa.save(OUT)
print(f"Mapa guardado en: {OUT}")
