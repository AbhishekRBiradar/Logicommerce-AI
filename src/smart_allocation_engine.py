import pandas as pd


# ==========================================
# LOAD DATA
# ==========================================

inventory = pd.read_csv(
    "data/product_inventory.csv"
)

products = pd.read_csv(
    "data/products.csv"
)

vehicles = pd.read_csv(
    "data/vehicles.csv"
)

distances = pd.read_csv(
    "data/warehouse_distances.csv"
)


# ==========================================
# CONFIGURATION
# ==========================================

FUEL_PRICE_PER_LITRE = 100.0

SAFETY_STOCK_PERCENT = 0.30


# ==========================================
# PRODUCT INFORMATION
# ==========================================

def get_product(product_id):

    result = products[
        products["product_id"] == product_id
    ]

    if result.empty:
        return None

    return result.iloc[0]


# ==========================================
# DESTINATION STOCK
# ==========================================

def get_destination_stock(
    product_id,
    destination
):

    result = inventory[
        (
            inventory["product_id"]
            == product_id
        )
        &
        (
            inventory["warehouse_id"]
            == destination
        )
    ]

    if result.empty:
        return None

    return float(
        result.iloc[0]["current_stock"]
    )


# ==========================================
# SOURCE WAREHOUSES
# ==========================================

def get_source_warehouses(
    product_id,
    destination
):

    sources = inventory[
        (
            inventory["product_id"]
            == product_id
        )
        &
        (
            inventory["warehouse_id"]
            != destination
        )
    ].copy()

    if sources.empty:
        return pd.DataFrame()


    # --------------------------------------
    # Safety stock
    # --------------------------------------

    sources["safety_stock"] = (
        sources["current_stock"]
        * SAFETY_STOCK_PERCENT
    )


    # --------------------------------------
    # Usable surplus
    # --------------------------------------

    sources["usable_surplus"] = (

        sources["current_stock"]

        - sources["safety_stock"]

    ).clip(
        lower=0
    )


    # --------------------------------------
    # Distance
    # --------------------------------------

    distance_data = distances[
        distances[
            "destination_warehouse"
        ] == destination
    ][
        [
            "source_warehouse",
            "distance_km"
        ]
    ]

    sources = sources.merge(

        distance_data,

        left_on="warehouse_id",

        right_on="source_warehouse",

        how="left"

    )


    sources = sources.dropna(
        subset=["distance_km"]
    )


    sources = sources[
        sources["usable_surplus"] > 0
    ]


    return sources


# ==========================================
# VEHICLE CANDIDATES
# ==========================================

def get_vehicle_candidates(

    source_warehouse,

    shipment_weight,

    shipment_volume

):

    candidates = vehicles[

        (
            vehicles["warehouse_id"]
            == source_warehouse
        )

        &

        (
            vehicles["available"]
            == 1
        )

        &

        (
            vehicles["capacity_kg"]
            >= shipment_weight
        )

        &

        (
            vehicles["volume_capacity_m3"]
            >= shipment_volume
        )

    ].copy()


    return candidates


# ==========================================
# VEHICLE SCORING
# ==========================================

def score_vehicle(

    vehicle,

    shipment_weight,

    shipment_volume,

    distance_km

):

    weight_capacity = float(
        vehicle["capacity_kg"]
    )

    volume_capacity = float(
        vehicle["volume_capacity_m3"]
    )

    fuel_efficiency = float(
        vehicle["fuel_efficiency_kmpl"]
    )


    # --------------------------------------
    # Utilization
    # --------------------------------------

    weight_utilization = (
        shipment_weight
        / weight_capacity
    )

    volume_utilization = (
        shipment_volume
        / volume_capacity
    )


    # --------------------------------------
    # Fuel
    # --------------------------------------

    fuel_litres = (
        distance_km
        / fuel_efficiency
    )


    fuel_cost = (
        fuel_litres
        * FUEL_PRICE_PER_LITRE
    )


    # --------------------------------------
    # Combined utilization
    # --------------------------------------

    utilization = (

        0.5
        * weight_utilization

        +

        0.5
        * volume_utilization

    )


    # --------------------------------------
    # Under-utilization penalty
    #
    # Penalize unnecessarily large vehicles.
    # --------------------------------------

    under_utilization_penalty = (

        1
        - utilization
    ) * 100


    # --------------------------------------
    # Final optimization score
    #
    # Lower is better.
    # --------------------------------------

    score = (

        fuel_cost

        +

        under_utilization_penalty

    )


    return {

        "weight_utilization":
            weight_utilization,

        "volume_utilization":
            volume_utilization,

        "utilization":
            utilization,

        "fuel_litres":
            fuel_litres,

        "fuel_cost":
            fuel_cost,

        "score":
            score

    }


# ==========================================
# SMART ALLOCATION
# ==========================================

def optimize_transfer(

    product_id,

    destination,

    required_stock

):

    # ======================================
    # PRODUCT
    # ======================================

    product = get_product(
        product_id
    )

    if product is None:

        return {
            "status":
                "PRODUCT_NOT_FOUND"
        }


    product_weight = float(
        product["weight_kg"]
    )

    product_volume = float(
        product["volume_m3"]
    )


    # ======================================
    # DESTINATION STOCK
    # ======================================

    current_stock = (
        get_destination_stock(
            product_id,
            destination
        )
    )


    if current_stock is None:

        return {
            "status":
                "DESTINATION_PRODUCT_NOT_FOUND"
        }


    # ======================================
    # SHORTAGE
    # ======================================

    shortage = max(

        0,

        required_stock
        - current_stock

    )


    if shortage <= 0:

        return {

            "status":
                "NO_TRANSFER_REQUIRED",

            "current_stock":
                current_stock,

            "shortage":
                0

        }


    # ======================================
    # SOURCE WAREHOUSES
    # ======================================

    sources = get_source_warehouses(

        product_id,

        destination

    )


    if sources.empty:

        return {

            "status":
                "NO_SOURCE_WAREHOUSE",

            "shortage":
                shortage

        }


    # ======================================
    # BUILD SOURCE OPTIONS
    # ======================================

    source_options = []


    for _, source in sources.iterrows():

        usable_surplus = float(
            source["usable_surplus"]
        )

        quantity = min(

            shortage,

            usable_surplus

        )


        if quantity <= 0:
            continue


        shipment_weight = (

            quantity
            * product_weight

        )

        shipment_volume = (

            quantity
            * product_volume

        )

        distance_km = float(
            source["distance_km"]
        )


        # ----------------------------------
        # Find feasible vehicles
        # ----------------------------------

        vehicle_candidates = (
            get_vehicle_candidates(

                source[
                    "warehouse_id"
                ],

                shipment_weight,

                shipment_volume

            )
        )


        if vehicle_candidates.empty:

            continue


        # ----------------------------------
        # Score every vehicle
        # ----------------------------------

        best_vehicle = None

        best_score = float(
            "inf"
        )

        best_metrics = None


        for _, vehicle in (
            vehicle_candidates.iterrows()
        ):

            metrics = score_vehicle(

                vehicle,

                shipment_weight,

                shipment_volume,

                distance_km

            )


            if metrics["score"] < best_score:

                best_score = (
                    metrics["score"]
                )

                best_vehicle = (
                    vehicle
                )

                best_metrics = (
                    metrics
                )


        if best_vehicle is None:
            continue


        source_options.append({

            "source":
                source[
                    "warehouse_id"
                ],

            "destination":
                destination,

            "quantity":
                quantity,

            "weight_kg":
                shipment_weight,

            "volume_m3":
                shipment_volume,

            "distance_km":
                distance_km,

            "vehicle_id":
                best_vehicle[
                    "vehicle_id"
                ],

            "vehicle_capacity_kg":
                best_vehicle[
                    "capacity_kg"
                ],

            "vehicle_volume_m3":
                best_vehicle[
                    "volume_capacity_m3"
                ],

            "fuel_efficiency_kmpl":
                best_vehicle[
                    "fuel_efficiency_kmpl"
                ],

            "weight_utilization":
                best_metrics[
                    "weight_utilization"
                ],

            "volume_utilization":
                best_metrics[
                    "volume_utilization"
                ],

            "utilization":
                best_metrics[
                    "utilization"
                ],

            "fuel_litres":
                best_metrics[
                    "fuel_litres"
                ],

            "fuel_cost":
                best_metrics[
                    "fuel_cost"
                ],

            "optimization_score":
                best_metrics[
                    "score"
                ]

        })


    # ======================================
    # NO FEASIBLE TRANSFER
    # ======================================

    if not source_options:

        return {

            "status":
                "NO_FEASIBLE_TRANSFER",

            "shortage":
                shortage

        }


    # ======================================
    # SELECT BEST SOURCE
    # ======================================

    source_options.sort(

        key=lambda x:
            x["optimization_score"]

    )


    best = source_options[0]


    # ======================================
    # CHECK REMAINING SHORTAGE
    # ======================================

    remaining_shortage = max(

        0,

        shortage
        - best["quantity"]

    )


    if remaining_shortage > 0:

        status = (
            "PARTIAL_TRANSFER"
        )

    else:

        status = (
            "TRANSFER_PLAN_READY"
        )


    return {

        "status":
            status,

        "product_id":
            product_id,

        "destination":
            destination,

        "required_stock":
            required_stock,

        "current_stock":
            current_stock,

        "shortage":
            shortage,

        "remaining_shortage":
            remaining_shortage,

        "product_weight_kg":
            product_weight,

        "product_volume_m3":
            product_volume,

        "source_options":
            source_options,

        "best_option":
            best

    }


# ==========================================
# INTERACTIVE TEST
# ==========================================

print(
    "\n=========================================="
)

print(
    "     SMART ALLOCATION + VEHICLE OPTIMIZER"
)

print(
    "=========================================="
)


product_id = input(
    "\nProduct ID: "
).strip()


destination = input(
    "Destination Warehouse ID: "
).strip()


required_stock = float(
    input(
        "Required Stock: "
    )
)


result = optimize_transfer(

    product_id,

    destination,

    required_stock

)


# ==========================================
# RESULT
# ==========================================

print(
    "\n=========================================="
)

print(
    "OPTIMIZATION RESULT"
)

print(
    "=========================================="
)

print(
    f"Status: {result['status']}"
)


if result["status"] == (
    "NO_TRANSFER_REQUIRED"
):

    print(
        f"\nCurrent stock: "
        f"{result['current_stock']:.2f}"
    )

    print(
        "Destination has sufficient stock."
    )


elif result["status"] in [

    "TRANSFER_PLAN_READY",

    "PARTIAL_TRANSFER"

]:

    print(
        f"\nProduct: "
        f"{result['product_id']}"
    )

    print(
        f"Destination: "
        f"{result['destination']}"
    )

    print(
        f"Product weight: "
        f"{result['product_weight_kg']:.2f} kg/unit"
    )

    print(
        f"Product volume: "
        f"{result['product_volume_m3']:.3f} m³/unit"
    )

    print(
        f"Current stock: "
        f"{result['current_stock']:.2f}"
    )

    print(
        f"Required stock: "
        f"{result['required_stock']:.2f}"
    )

    print(
        f"Shortage: "
        f"{result['shortage']:.2f}"
    )

    print(
        "\n------------------------------------------"
    )

    print(
        "CANDIDATE SOURCE ANALYSIS"
    )

    print(
        "------------------------------------------"
    )


    for option in result[
        "source_options"
    ]:

        print(
            f"\n{option['source']} → "
            f"{option['destination']}"
        )

        print(
            f"Quantity: "
            f"{option['quantity']:.2f} units"
        )

        print(
            f"Distance: "
            f"{option['distance_km']:.0f} km"
        )

        print(
            f"Vehicle: "
            f"{option['vehicle_id']}"
        )

        print(
            f"Vehicle capacity: "
            f"{option['vehicle_capacity_kg']} kg"
        )

        print(
            f"Vehicle volume: "
            f"{option['vehicle_volume_m3']} m³"
        )

        print(
            f"Weight utilization: "
            f"{option['weight_utilization'] * 100:.1f}%"
        )

        print(
            f"Volume utilization: "
            f"{option['volume_utilization'] * 100:.1f}%"
        )

        print(
            f"Overall utilization: "
            f"{option['utilization'] * 100:.1f}%"
        )

        print(
            f"Fuel: "
            f"{option['fuel_litres']:.2f} L"
        )

        print(
            f"Fuel cost: "
            f"₹{option['fuel_cost']:.2f}"
        )

        print(
            f"Optimization score: "
            f"{option['optimization_score']:.2f}"
        )


    # ==================================
    # BEST OPTION
    # ==================================

    best = result[
        "best_option"
    ]


    print(
        "\n=========================================="
    )

    print(
        "🏆 RECOMMENDED TRANSFER"
    )

    print(
        "=========================================="
    )


    print(
        f"Source: "
        f"{best['source']}"
    )

    print(
        f"Destination: "
        f"{best['destination']}"
    )

    print(
        f"Product: "
        f"{result['product_id']}"
    )

    print(
        f"Quantity: "
        f"{best['quantity']:.2f} units"
    )

    print(
        f"Shipment weight: "
        f"{best['weight_kg']:.2f} kg"
    )

    print(
        f"Shipment volume: "
        f"{best['volume_m3']:.3f} m³"
    )

    print(
        f"Distance: "
        f"{best['distance_km']:.0f} km"
    )

    print(
        f"Vehicle: "
        f"{best['vehicle_id']}"
    )

    print(
        f"Vehicle capacity: "
        f"{best['vehicle_capacity_kg']} kg"
    )

    print(
        f"Vehicle volume: "
        f"{best['vehicle_volume_m3']} m³"
    )

    print(
        f"Weight utilization: "
        f"{best['weight_utilization'] * 100:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{best['volume_utilization'] * 100:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{best['utilization'] * 100:.1f}%"
    )

    print(
        f"Fuel required: "
        f"{best['fuel_litres']:.2f} L"
    )

    print(
        f"Fuel cost: "
        f"₹{best['fuel_cost']:.2f}"
    )


    print(
        "\n=========================================="
    )


else:

    print(
        "\nNo feasible transfer could be found."
    )

    if "shortage" in result:

        print(
            f"Shortage: "
            f"{result['shortage']:.2f} units"
        )


print(
    "=========================================="
)