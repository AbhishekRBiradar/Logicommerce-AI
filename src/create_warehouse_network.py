import pandas as pd
import numpy as np


# ==========================================
# LOAD WAREHOUSES
# ==========================================

warehouses = pd.read_csv(
    "data/warehouses.csv"
)


# ==========================================
# SAFETY STOCK
# ==========================================

# Keep at least 30% of warehouse capacity
# available as protected stock.

warehouses["safety_stock"] = (
    warehouses["capacity_units"] * 0.30
)


warehouses["usable_surplus"] = (
    warehouses["current_inventory_units"]
    - warehouses["safety_stock"]
)


warehouses["usable_surplus"] = (
    warehouses["usable_surplus"]
    .clip(lower=0)
)


# ==========================================
# APPROXIMATE WAREHOUSE DISTANCES
# ==========================================

# Distances in kilometres.
# These are prototype distances and will later
# be replaced by real routing data.

distance_matrix = {

    "WH01": {
        "WH01": 0,
        "WH02": 35,
        "WH03": 145,
        "WH04": 350,
        "WH05": 575
    },

    "WH02": {
        "WH01": 35,
        "WH02": 0,
        "WH03": 125,
        "WH04": 335,
        "WH05": 560
    },

    "WH03": {
        "WH01": 145,
        "WH02": 125,
        "WH03": 0,
        "WH04": 430,
        "WH05": 700
    },

    "WH04": {
        "WH01": 350,
        "WH02": 335,
        "WH03": 430,
        "WH04": 0,
        "WH05": 630
    },

    "WH05": {
        "WH01": 575,
        "WH02": 560,
        "WH03": 700,
        "WH04": 630,
        "WH05": 0
    }
}


# ==========================================
# CREATE NETWORK TABLE
# ==========================================

network = []


for source in distance_matrix:

    for destination in distance_matrix[source]:

        network.append({

            "source_warehouse":
                source,

            "destination_warehouse":
                destination,

            "distance_km":
                distance_matrix[
                    source
                ][
                    destination
                ]

        })


network_df = pd.DataFrame(
    network
)


# ==========================================
# SAVE
# ==========================================

warehouses.to_csv(
    "data/warehouse_inventory.csv",
    index=False
)


network_df.to_csv(
    "data/warehouse_distances.csv",
    index=False
)


# ==========================================
# DISPLAY
# ==========================================

print(
    "\n=========================================="
)

print(
    "WAREHOUSE NETWORK CREATED"
)

print(
    "=========================================="
)


print(
    "\nWarehouse inventory:"
)

print(
    warehouses[
        [
            "warehouse_id",
            "location",
            "capacity_units",
            "current_inventory_units",
            "safety_stock",
            "usable_surplus"
        ]
    ].to_string(
        index=False
    )
)


print(
    "\nDistance network:"
)

print(
    network_df.head(15).to_string(
        index=False
    )
)


print(
    "\nFiles created:"
)

print(
    "✓ data/warehouse_inventory.csv"
)

print(
    "✓ data/warehouse_distances.csv"
)