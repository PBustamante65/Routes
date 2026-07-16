import pandas as pd
from time_matrix import TimeMatrixBuilder
from solve_routes import Solution
from visualize_routes import Map


CSV_PATH = "Data/oxxo-stops.csv"
CSV_PATH2 = "Data/pipeline/oxxo-stops.csv"
tmb = TimeMatrixBuilder()
sol = Solution()
map = Map()


def prompt_new_stop():
    print("\nEnter new stop (leave blank to cancel):")
    tienda = input("  tienda: ").strip()
    if not tienda:
        return None
    direccion = input("  direccion: ").strip()
    ciudad = input("  ciudad: ").strip()
    latitud = float(input("  latitud: ").strip())
    longitud = float(input("  longitud: ").strip())
    return {
        "tienda": tienda,
        "direccion": direccion,
        "ciudad": ciudad,
        "latitud": latitud,
        "longitud": longitud,
    }


df = pd.read_csv(CSV_PATH)
print(f"Loaded {len(df)} stops.")

while True:
    new = prompt_new_stop()
    if new is None:
        break
    df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
    print(f"Added '{new['tienda']}'. Total stops: {len(df)}")

df.to_csv(CSV_PATH2, index=False)
print("Saved.")

tmb.main()
sol.main()
map.main()
