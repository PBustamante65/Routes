import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from sklearn.metrics.pairwise import haversine_distances
import numpy as np

EARTH_RADIUS = 6371


df = pd.read_excel(
    "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/RutaEditado_coordenadas2.xlsx"
)


df.drop(
    ["costo_mensual", "direccion_geocodificar", "direccion_aproximada"],
    axis=1,
    inplace=True,
)

df = df.dropna(subset=["latitud", "longitud"])

print(df.head(10))
print(f"Hay {len(df)} tiendas con coordenadas")


def carto(lons, lats):

    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})
    ax.scatter(lons, lats, color="red", transform=ccrs.PlateCarree())
    ax.coastlines()
    ax.gridlines(draw_labels=True)
    plt.show()


# lats = df["latitud"].to_numpy()
# lons = df["longitud"].to_numpy()

# coords_rad = np.radians(np.column_stack([lats, lons]))
# dist_matrix = haversine_distances(coords_rad) * EARTH_RADIUS

# dist_df = pd.DataFrame(dist_matrix, index=df["tienda"], columns=df["tienda"])
