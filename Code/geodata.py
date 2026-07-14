import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

df = pd.read_excel(
    "/Users/patrickbustamante/Library/Mobile Documents/com~apple~CloudDocs/Random/Routes/Data/RutaEditado_coordenadas.xlsx"
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

    # Longitude, Latitude
    # lons = [-122.4194, -74.0060, 2.3522]  # SF, NYC, Paris
    # lats = [37.7749, 40.7128, 48.8566]

    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})
    ax.scatter(lons, lats, color="red", transform=ccrs.PlateCarree())
    ax.coastlines()
    ax.gridlines(draw_labels=True)
    plt.show()


lats = df["latitud"].to_numpy()
lons = df["longitud"].to_numpy()

carto(lons, lats)
