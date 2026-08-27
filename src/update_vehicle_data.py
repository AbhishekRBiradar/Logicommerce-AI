import pandas as pd
import random

vehicles = pd.read_csv(
    "data/vehicles.csv"
)

random.seed(42)

volume_options = [
    5,
    10,
    25,
    50
]

vehicles["volume_capacity_m3"] = [
    random.choice(volume_options)
    for _ in range(len(vehicles))
]

vehicles.to_csv(
    "data/vehicles.csv",
    index=False
)

print("\n==========================================")
print("VEHICLE DATA UPDATED")
print("==========================================")

print(f"Vehicles: {len(vehicles)}")

print("\nUpdated vehicle fleet:")
print(vehicles.to_string(index=False))

print("\nSaved:")
print("data/vehicles.csv")