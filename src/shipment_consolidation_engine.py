import pandas as pd


# ==========================================
# CONFIGURATION
# ==========================================

DATA_DIR = "data"

FUEL_PRICE_PER_LITRE = 100.0


# ==========================================
# LOAD DATA
# ==========================================

print("Loading transfer requests...")
requests = pd.read_csv(
    f"{DATA_DIR}/transfer_requests.csv"
)

print("Loading vehicles...")
vehicles = pd.read_csv(
    f"{DATA_DIR}/vehicles.csv"
)

print("Loading warehouse distances...")
distances = pd.read_csv(
    f"{DATA_DIR}/warehouse_distances.csv"
)


# ==========================================
# FIND DISTANCE
# ==========================================

def get_distance(source, destination):

    result = distances[
        (
            distances["source_warehouse"]
            == source
        )
        &
        (
            distances["destination_warehouse"]
            == destination
        )
    ]

    if result.empty:
        return None

    return float(
        result.iloc[0]["distance_km"]
    )


# ==========================================
# CALCULATE FUEL
# ==========================================

def calculate_fuel(
    vehicle,
    distance_km
):

    fuel_efficiency = float(
        vehicle["fuel_efficiency_kmpl"]
    )

    fuel_litres = (
        distance_km
        / fuel_efficiency
    )

    fuel_cost = (
        fuel_litres
        * FUEL_PRICE_PER_LITRE
    )

    return fuel_litres, fuel_cost


# ==========================================
# FIND BEST VEHICLE
# ==========================================

def find_best_vehicle(
    source,
    total_weight,
    total_volume,
    distance_km
):

    candidates = vehicles[
        (
            vehicles["warehouse_id"]
            == source
        )
        &
        (
            vehicles["available"]
            == 1
        )
        &
        (
            vehicles["capacity_kg"]
            >= total_weight
        )
        &
        (
            vehicles["volume_capacity_m3"]
            >= total_volume
        )
    ].copy()

    if candidates.empty:
        return None


    best_vehicle = None
    best_score = float("inf")


    for _, vehicle in candidates.iterrows():

        capacity_kg = float(
            vehicle["capacity_kg"]
        )

        volume_capacity = float(
            vehicle[
                "volume_capacity_m3"
            ]
        )


        # ------------------------------
        # UTILIZATION
        # ------------------------------

        weight_utilization = (
            total_weight
            / capacity_kg
        )

        volume_utilization = (
            total_volume
            / volume_capacity
        )

        overall_utilization = (
            weight_utilization
            + volume_utilization
        ) / 2


        # ------------------------------
        # FUEL
        # ------------------------------

        fuel_litres, fuel_cost = (
            calculate_fuel(
                vehicle,
                distance_km
            )
        )


        # ------------------------------
        # OPTIMIZATION SCORE
        # ------------------------------
        #
        # Lower score is better.
        #
        # Fuel cost is the main factor.
        # Under-utilization receives a
        # small penalty.
        #

        utilization_penalty = (
            1
            - overall_utilization
        ) * 100


        score = (
            fuel_cost
            + utilization_penalty
        )


        if score < best_score:

            best_score = score

            best_vehicle = {

                "vehicle_id":
                    vehicle["vehicle_id"],

                "capacity_kg":
                    capacity_kg,

                "volume_capacity_m3":
                    volume_capacity,

                "fuel_efficiency_kmpl":
                    float(
                        vehicle[
                            "fuel_efficiency_kmpl"
                        ]
                    ),

                "weight_utilization":
                    weight_utilization,

                "volume_utilization":
                    volume_utilization,

                "overall_utilization":
                    overall_utilization,

                "fuel_litres":
                    fuel_litres,

                "fuel_cost":
                    fuel_cost,

                "score":
                    score

            }


    return best_vehicle


# ==========================================
# ANALYZE ONE CONSOLIDATION GROUP
# ==========================================

def analyze_group(
    source,
    destination,
    group
):

    # ======================================
    # TOTAL SHIPMENT
    # ======================================

    shipment_count = len(group)

    total_weight = float(
        group["weight_kg"].sum()
    )

    total_volume = float(
        group["volume_m3"].sum()
    )


    # ======================================
    # DISTANCE
    # ======================================

    distance_km = get_distance(
        source,
        destination
    )


    if distance_km is None:

        return None


    # ======================================
    # FIND VEHICLE FOR CONSOLIDATED LOAD
    # ======================================

    consolidated_vehicle = (
        find_best_vehicle(

            source,

            total_weight,

            total_volume,

            distance_km

        )
    )


    # ======================================
    # CANNOT CONSOLIDATE
    # ======================================

    if consolidated_vehicle is None:

        return {

            "status":
                "CANNOT_CONSOLIDATE",

            "source":
                source,

            "destination":
                destination,

            "shipment_count":
                shipment_count,

            "total_weight":
                total_weight,

            "total_volume":
                total_volume,

            "distance":
                distance_km

        }


    # ======================================
    # CALCULATE SEPARATE TRIPS
    # ======================================

    separate_cost = 0.0
    separate_fuel = 0.0
    separate_trips = 0

    separate_possible = True


    for _, shipment in group.iterrows():

        shipment_weight = float(
            shipment["weight_kg"]
        )

        shipment_volume = float(
            shipment["volume_m3"]
        )


        vehicle = find_best_vehicle(

            source,

            shipment_weight,

            shipment_volume,

            distance_km

        )


        if vehicle is None:

            separate_possible = False

            break


        separate_cost += float(
            vehicle["fuel_cost"]
        )

        separate_fuel += float(
            vehicle["fuel_litres"]
        )

        separate_trips += 1


    # ======================================
    # IF SEPARATE TRIPS ARE NOT POSSIBLE
    # ======================================

    if not separate_possible:

        separate_cost = 0.0
        separate_fuel = 0.0
        separate_trips = 0


    # ======================================
    # CONSOLIDATED COST
    # ======================================

    consolidated_cost = float(
        consolidated_vehicle[
            "fuel_cost"
        ]
    )

    consolidated_fuel = float(
        consolidated_vehicle[
            "fuel_litres"
        ]
    )


    # ======================================
    # SAVINGS
    # ======================================

    if separate_cost > 0:

        savings = (
            separate_cost
            - consolidated_cost
        )

        savings_percentage = (
            savings
            / separate_cost
            * 100
        )

    else:

        savings = 0.0
        savings_percentage = 0.0


    # ======================================
    # SMART DECISION
    # ======================================
    #
    # Consolidate if:
    #
    # 1. There is actual cost saving
    #    of at least 20%
    #
    # OR
    #
    # 2. Vehicle utilization is at
    #    least 20%.
    #
    # This prevents the previous bug
    # where 75% savings was rejected
    # simply because utilization was low.
    #

    utilization = float(
        consolidated_vehicle[
            "overall_utilization"
        ]
    )


    if (

        savings_percentage >= 20

    ):

        decision = "CONSOLIDATE"


    elif (

        savings > 0

        and

        utilization >= 0.20

    ):

        decision = "CONSOLIDATE"


    else:

        decision = "SEPARATE_TRIPS"


    # ======================================
    # RETURN RESULT
    # ======================================

    return {

        "status":
            "CONSOLIDATION_ANALYZED",

        "source":
            source,

        "destination":
            destination,

        "shipment_count":
            shipment_count,

        "total_weight":
            total_weight,

        "total_volume":
            total_volume,

        "distance":
            distance_km,

        "vehicle":
            consolidated_vehicle,

        "separate_trips":
            separate_trips,

        "separate_fuel":
            separate_fuel,

        "separate_cost":
            separate_cost,

        "consolidated_fuel":
            consolidated_fuel,

        "consolidated_cost":
            consolidated_cost,

        "savings":
            savings,

        "savings_percentage":
            savings_percentage,

        "decision":
            decision

    }


# ==========================================
# MAIN PROGRAM
# ==========================================

print()
print("==========================================")
print("     SHIPMENT CONSOLIDATION ENGINE")
print("==========================================")


# ==========================================
# GROUP REQUESTS
# ==========================================

groups = requests.groupby(

    [
        "source_warehouse",
        "destination_warehouse"
    ]

)


results = []


# ==========================================
# ANALYZE EVERY GROUP
# ==========================================

for (
    source,
    destination
), group in groups:

    result = analyze_group(

        source,
        destination,
        group

    )


    if result is not None:

        results.append(
            result
        )


# ==========================================
# DISPLAY RESULTS
# ==========================================

for result in results:

    print()
    print("==========================================")

    print(
        f"{result['source']} → "
        f"{result['destination']}"
    )

    print(
        "=========================================="
    )

    print(
        f"Shipments: "
        f"{result['shipment_count']}"
    )

    print(
        f"Total weight: "
        f"{result['total_weight']:.2f} kg"
    )

    print(
        f"Total volume: "
        f"{result['total_volume']:.3f} m³"
    )

    print(
        f"Distance: "
        f"{result['distance']:.0f} km"
    )


    # ======================================
    # CANNOT CONSOLIDATE
    # ======================================

    if result["status"] == (
        "CANNOT_CONSOLIDATE"
    ):

        print()
        print(
            "❌ CANNOT CONSOLIDATE"
        )

        print(
            "No available vehicle can carry "
            "the combined shipment."
        )

        continue


    # ======================================
    # VEHICLE
    # ======================================

    vehicle = result[
        "vehicle"
    ]


    print()
    print(
        "------------------------------------------"
    )

    print(
        "CONSOLIDATED VEHICLE"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Vehicle: "
        f"{vehicle['vehicle_id']}"
    )

    print(
        f"Weight capacity: "
        f"{vehicle['capacity_kg']:.0f} kg"
    )

    print(
        f"Volume capacity: "
        f"{vehicle['volume_capacity_m3']:.2f} m³"
    )

    print(
        f"Weight utilization: "
        f"{vehicle['weight_utilization'] * 100:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{vehicle['volume_utilization'] * 100:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{vehicle['overall_utilization'] * 100:.1f}%"
    )


    # ======================================
    # COST COMPARISON
    # ======================================

    print()
    print(
        "------------------------------------------"
    )

    print(
        "COST COMPARISON"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Separate trips: "
        f"{result['separate_trips']}"
    )

    print(
        f"Separate fuel: "
        f"{result['separate_fuel']:.2f} L"
    )

    print(
        f"Separate cost: "
        f"₹{result['separate_cost']:.2f}"
    )

    print()

    print(
        f"Consolidated fuel: "
        f"{result['consolidated_fuel']:.2f} L"
    )

    print(
        f"Consolidated cost: "
        f"₹{result['consolidated_cost']:.2f}"
    )

    print(
        f"Fuel/cost savings: "
        f"₹{result['savings']:.2f}"
    )

    print(
        f"Savings percentage: "
        f"{result['savings_percentage']:.1f}%"
    )


    # ======================================
    # DECISION
    # ======================================

    print()
    print(
        "------------------------------------------"
    )


    if result["decision"] == (
        "CONSOLIDATE"
    ):

        print(
            "✅ AI DECISION: CONSOLIDATE"
        )

        print(
            "Multiple shipments should "
            "share this vehicle."
        )

    else:

        print(
            "⚠️ AI DECISION: SEPARATE TRIPS"
        )

        print(
            "Separate trips are currently "
            "more appropriate."
        )


# ==========================================
# SAVE RESULTS
# ==========================================

summary = []


for result in results:

    row = {

        "source_warehouse":
            result["source"],

        "destination_warehouse":
            result["destination"],

        "shipment_count":
            result["shipment_count"],

        "total_weight_kg":
            result["total_weight"],

        "total_volume_m3":
            result["total_volume"],

        "distance_km":
            result["distance"],

        "decision":
            result["decision"]

    }


    if result["status"] == (
        "CONSOLIDATION_ANALYZED"
    ):

        vehicle = result[
            "vehicle"
        ]


        row.update({

            "vehicle_id":
                vehicle[
                    "vehicle_id"
                ],

            "vehicle_capacity_kg":
                vehicle[
                    "capacity_kg"
                ],

            "vehicle_volume_capacity_m3":
                vehicle[
                    "volume_capacity_m3"
                ],

            "weight_utilization":
                vehicle[
                    "weight_utilization"
                ],

            "volume_utilization":
                vehicle[
                    "volume_utilization"
                ],

            "overall_utilization":
                vehicle[
                    "overall_utilization"
                ],

            "separate_cost":
                result[
                    "separate_cost"
                ],

            "consolidated_cost":
                result[
                    "consolidated_cost"
                ],

            "savings":
                result[
                    "savings"
                ],

            "savings_percentage":
                result[
                    "savings_percentage"
                ]

        })


    summary.append(
        row
    )


summary_df = pd.DataFrame(
    summary
)


summary_df.to_csv(

    f"{DATA_DIR}/consolidation_results.csv",

    index=False

)


# ==========================================
# COMPLETE
# ==========================================

print()
print("==========================================")
print("CONSOLIDATION ANALYSIS COMPLETE")
print("==========================================")

print(
    "Saved to:"
)

print(
    "data/consolidation_results.csv"
)