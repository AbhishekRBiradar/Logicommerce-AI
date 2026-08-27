import os
import random
import pandas as pd


# ==========================================
# SETTINGS
# ==========================================

random.seed(42)

DATA_DIR = "data"

os.makedirs(DATA_DIR, exist_ok=True)


# ==========================================
# CONFIGURATION
# ==========================================

NUM_REQUESTS = 30

WAREHOUSES = [
    "WH01",
    "WH02",
    "WH03",
    "WH04",
    "WH05"
]


# ==========================================
# LOAD DATA
# ==========================================

print("Loading inventory and product data...")

inventory = pd.read_csv(
    f"{DATA_DIR}/product_inventory.csv"
)

products = pd.read_csv(
    f"{DATA_DIR}/products.csv"
)


# ==========================================
# CREATE TRANSFER REQUESTS
# ==========================================

print("Creating transfer requests...")

requests = []


for i in range(1, NUM_REQUESTS + 1):

    # ------------------------------
    # Select source and destination
    # ------------------------------

    source = random.choice(
        WAREHOUSES
    )

    destination = random.choice(
        [
            w
            for w in WAREHOUSES
            if w != source
        ]
    )


    # ------------------------------
    # Select product
    # ------------------------------

    product = products.sample(
        1
    ).iloc[0]

    product_id = product[
        "product_id"
    ]

    category = product[
        "category"
    ]

    weight_kg = float(
        product[
            "weight_kg"
        ]
    )

    volume_m3 = float(
        product[
            "volume_m3"
        ]
    )


    # ------------------------------
    # Requested quantity
    # ------------------------------

    quantity = random.randint(
        2,
        20
    )


    # ------------------------------
    # Shipment calculations
    # ------------------------------

    total_weight = round(

        quantity
        * weight_kg,

        2
    )

    total_volume = round(

        quantity
        * volume_m3,

        3
    )


    # ------------------------------
    # Priority
    # ------------------------------

    priority = random.choices(

        [
            "LOW",
            "MEDIUM",
            "HIGH"
        ],

        weights=[
            0.30,
            0.50,
            0.20
        ]

    )[0]


    # ------------------------------
    # Deadline
    # ------------------------------

    deadline_days = random.randint(
        1,
        5
    )


    requests.append({

        "transfer_id":
            f"TRF{i:05d}",

        "source_warehouse":
            source,

        "destination_warehouse":
            destination,

        "product_id":
            product_id,

        "category":
            category,

        "quantity":
            quantity,

        "weight_kg":
            total_weight,

        "volume_m3":
            total_volume,

        "priority":
            priority,

        "deadline_days":
            deadline_days

    })


# ==========================================
# DATAFRAME
# ==========================================

requests_df = pd.DataFrame(
    requests
)


# ==========================================
# SAVE
# ==========================================

output_file = (
    f"{DATA_DIR}/transfer_requests.csv"
)

requests_df.to_csv(
    output_file,
    index=False
)


# ==========================================
# SUMMARY
# ==========================================

print(
    "\n=========================================="
)

print(
    "TRANSFER REQUEST DATASET CREATED"
)

print(
    "=========================================="
)

print(
    f"Transfer requests: "
    f"{len(requests_df)}"
)

print(
    f"Unique products: "
    f"{requests_df['product_id'].nunique()}"
)

print(
    f"Total shipment weight: "
    f"{requests_df['weight_kg'].sum():.2f} kg"
)

print(
    f"Total shipment volume: "
    f"{requests_df['volume_m3'].sum():.3f} m³"
)


print(
    "\nTransfer requests:"
)

print(
    requests_df.to_string(
        index=False
    )
)


# ==========================================
# CONSOLIDATION GROUPS
# ==========================================

print(
    "\n=========================================="
)

print(
    "POTENTIAL CONSOLIDATION GROUPS"
)

print(
    "=========================================="
)


groups = (

    requests_df

    .groupby(
        [
            "source_warehouse",
            "destination_warehouse"
        ]
    )

    .agg(

        shipments=(
            "transfer_id",
            "count"
        ),

        total_weight_kg=(
            "weight_kg",
            "sum"
        ),

        total_volume_m3=(
            "volume_m3",
            "sum"
        )

    )

    .reset_index()

)


print(
    groups.to_string(
        index=False
    )
)


print(
    "\nSaved to:"
)

print(
    output_file
)