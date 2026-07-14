import matplotlib.pyplot as plt
import cartopy.crs as ccrs

# Longitude, Latitude
lons = [-122.4194, -74.0060, 2.3522]  # SF, NYC, Paris
lats = [37.7749, 40.7128, 48.8566]

fig, ax = plt.subplots(subplot_kw={"projection": ccrs.PlateCarree()})
ax.scatter(lons, lats, color="red", transform=ccrs.PlateCarree())
ax.coastlines()
ax.gridlines(draw_labels=True)
plt.show()
