import pandas as pd
import numpy as np


# ==========================================
# LOAD PRODUCTS AND WAREHOUSES
# ==========================================

products = pd.read_csv(
    "data/products.csv"
)

warehouses = pd.read_csv(
    "data/warehouses.csv"
)


np.random.seed(42)


# ==========================================
# CREATE PRODUCT × WAREHOUSE INVENTORY
# ==========================================

records = []


for _, warehouse in warehouses.iterrows():

    warehouse_id = warehouse["warehouse_id"]

    capacity = warehouse["capacity_units"]

    # Number of products stored in this warehouse
    num_products = len(products)

    # Base allocation per product
    base_stock = max(
        1,
        int(
            capacity /
            num_products *
            np.random.uniform(
                0.5,
                2.0
            )
        )
    )

    for _, product in products.iterrows():

        product_id = product["product_id"]

        # Random product-level inventory
        stock = max(
            0,
            int(
                base_stock *
                np.random.uniform(
                    0.5,
                    2.5
                )
            )
        )

        records.append({

            "warehouse_id":
                warehouse_id,

            "location":
                warehouse["location"],

            "product_id":
                product_id,

            "category":
                product["category"],

            "current_stock":
                stock

        })


inventory = pd.DataFrame(
    records
)


# ==========================================
# SAVE
# ==========================================

inventory.to_csv(
    "data/product_inventory.csv",
    index=False
)


# ==========================================
# SUMMARY
# ==========================================

print(
    "\n=========================================="
)

print(
    "PRODUCT INVENTORY CREATED"
)

print(
    "=========================================="
)

print(
    f"Products: {inventory['product_id'].nunique()}"
)

print(
    f"Warehouses: {inventory['warehouse_id'].nunique()}"
)

print(
    f"Inventory records: {len(inventory)}"
)

print(
    f"Total units: "
    f"{inventory['current_stock'].sum():,}"
)


print(
    "\nPRD00031 inventory:"
)

print(
    inventory[
        inventory["product_id"] == "PRD00031"
    ].to_string(
        index=False
    )
)


print(
    "\nSaved to:"
)

print(
    "data/product_inventory.csv"
)