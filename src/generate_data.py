import os
import random
import numpy as np
import pandas as pd


# ==========================================
# SETTINGS
# ==========================================

random.seed(42)
np.random.seed(42)

DATA_DIR = "data"

os.makedirs(DATA_DIR, exist_ok=True)


# ==========================================
# BASIC CONFIGURATION
# ==========================================

NUM_CUSTOMERS = 10000
NUM_PRODUCTS = 1000
NUM_ORDERS = 20000
NUM_VEHICLES = 40


CITIES = [
    "Bangalore",
    "Mysore",
    "Tumkur",
    "Chennai",
    "Hyderabad",
    "Mumbai",
    "Pune",
    "Delhi"
]


CATEGORIES = [
    "Electronics",
    "Mobile",
    "Laptop",
    "Home",
    "Fashion",
    "Beauty",
    "Grocery",
    "Accessories"
]


WAREHOUSE_LOCATIONS = [
    "Bangalore",
    "Hoskote",
    "Mysore",
    "Chennai",
    "Hyderabad"
]


# ==========================================
# 1. CUSTOMERS
# ==========================================

print("Creating customers...")

customers = []

for i in range(1, NUM_CUSTOMERS + 1):

    city = random.choice(CITIES)

    previous_orders = np.random.poisson(8)

    average_order_value = round(
        np.random.lognormal(
            mean=7.5,
            sigma=0.5
        ),
        2
    )

    customers.append({

        "customer_id":
            f"CUS{i:06d}",

        "city":
            city,

        "previous_orders":
            previous_orders,

        "average_order_value":
            average_order_value

    })


customers_df = pd.DataFrame(customers)


# ==========================================
# 2. PRODUCTS
# ==========================================

print("Creating products...")

products = []

for i in range(1, NUM_PRODUCTS + 1):

    category = random.choice(CATEGORIES)

    price = round(
        np.random.lognormal(
            mean=7,
            sigma=0.8
        ),
        2
    )

    weight_kg = round(
        np.random.uniform(
            0.1,
            25
        ),
        2
    )

    volume_m3 = round(
        np.random.uniform(
            0.01,
            0.5
        ),
        3
    )

    products.append({

        "product_id":
            f"PRD{i:05d}",

        "category":
            category,

        "price":
            price,

        "weight_kg":
            weight_kg,

        "volume_m3":
            volume_m3

    })


products_df = pd.DataFrame(products)


# ==========================================
# 3. WAREHOUSES
# ==========================================

print("Creating warehouses...")

warehouses = []

for i, location in enumerate(
    WAREHOUSE_LOCATIONS,
    start=1
):

    capacity_units = random.randint(
        5000,
        15000
    )

    current_inventory_units = random.randint(
        3000,
        min(10000, capacity_units)
    )

    warehouses.append({

        "warehouse_id":
            f"WH{i:02d}",

        "location":
            location,

        "capacity_units":
            capacity_units,

        "current_inventory_units":
            current_inventory_units

    })


warehouses_df = pd.DataFrame(
    warehouses
)


# ==========================================
# 4. VEHICLES
# ==========================================

print("Creating vehicles...")

vehicles = []

for i in range(1, NUM_VEHICLES + 1):

    warehouse_id = random.choice(
        warehouses_df[
            "warehouse_id"
        ].tolist()
    )

    capacity_kg = random.choice([
        500,
        1000,
        2000,
        5000
    ])

    # Volume is related to vehicle size.
    # These are synthetic simulation values.

    volume_by_capacity = {

        500: 5,

        1000: 10,

        2000: 25,

        5000: 50

    }

    volume_capacity_m3 = (
        volume_by_capacity[
            capacity_kg
        ]
    )

    fuel_efficiency_kmpl = round(
        random.uniform(
            6,
            18
        ),
        2
    )

    available = random.choice([
        0,
        1
    ])

    vehicles.append({

        "vehicle_id":
            f"VEH{i:03d}",

        "warehouse_id":
            warehouse_id,

        "capacity_kg":
            capacity_kg,

        "volume_capacity_m3":
            volume_capacity_m3,

        "fuel_efficiency_kmpl":
            fuel_efficiency_kmpl,

        "available":
            available

    })


vehicles_df = pd.DataFrame(
    vehicles
)


# ==========================================
# 5. ORDERS
# ==========================================

print("Creating orders...")

orders = []

for i in range(1, NUM_ORDERS + 1):

    customer = customers_df.sample(
        1
    ).iloc[0]

    product = products_df.sample(
        1
    ).iloc[0]

    warehouse = warehouses_df.sample(
        1
    ).iloc[0]

    quantity = random.randint(
        1,
        5
    )

    order_value = round(
        product["price"] * quantity,
        2
    )

    order_date = (
        pd.Timestamp("2026-01-01")
        + pd.Timedelta(
            days=random.randint(
                0,
                237
            )
        )
    )

    delivery_deadline = (
        order_date
        + pd.Timedelta(
            days=random.randint(
                1,
                7
            )
        )
    )

    payment_status = random.choices(

        [
            "PAID",
            "PENDING",
            "REFUNDED"
        ],

        weights=[
            0.85,
            0.10,
            0.05
        ]

    )[0]

    orders.append({

        "order_id":
            f"ORD{i:07d}",

        "customer_id":
            customer["customer_id"],

        "product_id":
            product["product_id"],

        "warehouse_id":
            warehouse["warehouse_id"],

        "order_date":
            order_date.strftime(
                "%Y-%m-%d"
            ),

        "quantity":
            quantity,

        "order_value":
            order_value,

        "destination":
            customer["city"],

        "delivery_deadline":
            delivery_deadline.strftime(
                "%Y-%m-%d"
            ),

        "payment_status":
            payment_status

    })


orders_df = pd.DataFrame(
    orders
)


# ==========================================
# 6. DELIVERIES
# ==========================================

print("Creating deliveries...")

deliveries = []

for _, order in orders_df.iterrows():

    distance = round(
        np.random.gamma(
            shape=3,
            scale=20
        ),
        2
    )

    traffic = random.choices(

        [
            "LOW",
            "MEDIUM",
            "HIGH",
            "SEVERE"
        ],

        weights=[
            0.25,
            0.40,
            0.25,
            0.10
        ]

    )[0]

    traffic_multiplier = {

        "LOW": 1.0,

        "MEDIUM": 1.25,

        "HIGH": 1.6,

        "SEVERE": 2.2

    }[traffic]

    estimated_time = round(
        distance / 35 * 60,
        2
    )

    actual_time = round(

        estimated_time
        * traffic_multiplier
        * np.random.uniform(
            0.85,
            1.20
        ),

        2

    )

    if actual_time <= estimated_time * 1.15:

        delivery_status = "ON_TIME"

    elif actual_time <= estimated_time * 1.50:

        delivery_status = "DELAYED"

    else:

        delivery_status = "SEVERELY_DELAYED"

    deliveries.append({

        "delivery_id":
            f"DEL{len(deliveries) + 1:07d}",

        "order_id":
            order["order_id"],

        "distance_km":
            distance,

        "traffic_level":
            traffic,

        "estimated_time_min":
            estimated_time,

        "actual_time_min":
            actual_time,

        "delivery_status":
            delivery_status

    })


deliveries_df = pd.DataFrame(
    deliveries
)


# ==========================================
# 7. SAVE DATA
# ==========================================

print("\nSaving datasets...")


customers_df.to_csv(
    f"{DATA_DIR}/customers.csv",
    index=False
)


products_df.to_csv(
    f"{DATA_DIR}/products.csv",
    index=False
)


warehouses_df.to_csv(
    f"{DATA_DIR}/warehouses.csv",
    index=False
)


vehicles_df.to_csv(
    f"{DATA_DIR}/vehicles.csv",
    index=False
)


orders_df.to_csv(
    f"{DATA_DIR}/orders.csv",
    index=False
)


deliveries_df.to_csv(
    f"{DATA_DIR}/deliveries.csv",
    index=False
)


# ==========================================
# 8. VALIDATION
# ==========================================

print("\n==========================================")
print("DATA VALIDATION")
print("==========================================")


print(
    f"Customers : {len(customers_df)}"
)

print(
    f"Products  : {len(products_df)}"
)

print(
    f"Warehouses: {len(warehouses_df)}"
)

print(
    f"Vehicles  : {len(vehicles_df)}"
)

print(
    f"Orders    : {len(orders_df)}"
)

print(
    f"Deliveries: {len(deliveries_df)}"
)


print("\nVehicle columns:")

print(
    vehicles_df.columns.tolist()
)


print("\nVehicle sample:")

print(
    vehicles_df.head(10).to_string(
        index=False
    )
)


print("\nProduct columns:")

print(
    products_df.columns.tolist()
)


print("\nProduct sample:")

print(
    products_df.head(5).to_string(
        index=False
    )
)


# ==========================================
# 9. FINAL SUMMARY
# ==========================================

print("\n==========================================")
print("LOGICOMMERCE DATASET CREATED")
print("==========================================")

print("Files created:")

print("  ✓ customers.csv")
print("  ✓ products.csv")
print("  ✓ warehouses.csv")
print("  ✓ vehicles.csv")
print("  ✓ orders.csv")
print("  ✓ deliveries.csv")

print("\nDataset generation completed successfully!")