import os
import math
import pandas as pd


# ============================================================
# LOGICOMMERCE AI V7
# GLOBAL FLEET + SHIPMENT OPTIMIZATION
# ============================================================

DATA_DIR = "data"

TRANSFER_FILE = os.path.join(DATA_DIR, "transfer_requests.csv")
VEHICLE_FILE = os.path.join(DATA_DIR, "vehicles.csv")
DISTANCE_FILE = os.path.join(DATA_DIR, "warehouse_distances.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "logistics_optimization_v7.csv")

FUEL_PRICE_PER_LITRE = 100.0

# Minimum utilization preference.
# This does NOT reject a vehicle if no better vehicle exists.
TARGET_UTILIZATION = 0.35

# Maximum number of route stops.
MAX_STOPS = 3


# ============================================================
# LOAD DATA
# ============================================================

print("Loading transfer requests...")
transfers = pd.read_csv(TRANSFER_FILE)

print("Loading vehicles...")
vehicles = pd.read_csv(VEHICLE_FILE)

print("Loading warehouse distances...")
distances = pd.read_csv(DISTANCE_FILE)


# ============================================================
# NORMALIZE COLUMNS
# ============================================================

transfers.columns = transfers.columns.str.strip()
vehicles.columns = vehicles.columns.str.strip()
distances.columns = distances.columns.str.strip()


# ============================================================
# DISTANCE LOOKUP
# ============================================================

def get_distance(source, destination):
    """
    Get warehouse-to-warehouse distance.

    Supports common distance dataset column naming.
    """

    possible_source = [
        "source_warehouse",
        "source",
        "from_warehouse",
        "warehouse_from"
    ]

    possible_destination = [
        "destination_warehouse",
        "destination",
        "to_warehouse",
        "warehouse_to"
    ]

    possible_distance = [
        "distance_km",
        "distance",
        "distance_in_km"
    ]

    source_col = next(
        (c for c in possible_source if c in distances.columns),
        None
    )

    destination_col = next(
        (c for c in possible_destination if c in distances.columns),
        None
    )

    distance_col = next(
        (c for c in possible_distance if c in distances.columns),
        None
    )

    if not source_col or not destination_col or not distance_col:
        raise ValueError(
            "warehouse_distances.csv does not contain "
            "recognized source/destination/distance columns."
        )

    match = distances[
        (distances[source_col] == source)
        &
        (distances[destination_col] == destination)
    ]

    if match.empty:

        reverse = distances[
            (distances[source_col] == destination)
            &
            (distances[destination_col] == source)
        ]

        if reverse.empty:
            return None

        return float(reverse.iloc[0][distance_col])

    return float(match.iloc[0][distance_col])


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(route):

    total = 0.0

    for i in range(len(route) - 1):

        distance = get_distance(
            route[i],
            route[i + 1]
        )

        if distance is None:
            return None

        total += distance

    return total


# ============================================================
# ROUTE TIME
# ============================================================

def calculate_route_time(distance):

    # Average operating speed assumption
    average_speed = 40.0

    return distance / average_speed


# ============================================================
# VEHICLE SELECTION
# ============================================================

def select_best_vehicle(
    source,
    weight,
    volume,
    distance,
    reserved_vehicle_ids
):

    candidates = vehicles[
        (vehicles["warehouse_id"] == source)
        &
        (vehicles["available"] == 1)
    ].copy()

    if candidates.empty:
        return None, "NO_AVAILABLE_VEHICLE"

    # Never use a vehicle already allocated to another route.
    candidates = candidates[
        ~candidates["vehicle_id"].isin(
            reserved_vehicle_ids
        )
    ]

    if candidates.empty:
        return None, "FLEET_ALREADY_ASSIGNED"

    # --------------------------------------------------------
    # Hard capacity constraints
    # --------------------------------------------------------

    feasible = candidates[
        (candidates["capacity_kg"] >= weight)
        &
        (candidates["volume_capacity_m3"] >= volume)
    ].copy()

    if feasible.empty:
        return None, "CAPACITY_CONSTRAINT"

    # --------------------------------------------------------
    # Calculate utilization
    # --------------------------------------------------------

    feasible["weight_utilization"] = (
        weight / feasible["capacity_kg"]
    )

    feasible["volume_utilization"] = (
        volume / feasible["volume_capacity_m3"]
    )

    feasible["overall_utilization"] = (
        feasible["weight_utilization"]
        +
        feasible["volume_utilization"]
    ) / 2

    # --------------------------------------------------------
    # Fuel calculation
    # --------------------------------------------------------

    feasible["fuel_litres"] = (
        distance
        /
        feasible["fuel_efficiency_kmpl"]
    )

    feasible["fuel_cost"] = (
        feasible["fuel_litres"]
        *
        FUEL_PRICE_PER_LITRE
    )

    # --------------------------------------------------------
    # Global fleet score
    #
    # Lower is better.
    #
    # Fuel cost is the main objective.
    # Poor utilization adds a penalty.
    # --------------------------------------------------------

    feasible["utilization_penalty"] = (
        (1 - feasible["overall_utilization"])
        * 20
    )

    feasible["score"] = (
        feasible["fuel_cost"]
        +
        feasible["utilization_penalty"]
    )

    feasible = feasible.sort_values(
        by=[
            "score",
            "fuel_cost",
            "vehicle_id"
        ]
    )

    best = feasible.iloc[0]

    utilization = float(
        best["overall_utilization"]
    )

    if utilization >= TARGET_UTILIZATION:
        reason = "BEST_FIT_VEHICLE"

    else:
        reason = "LOW_UTILIZATION_BUT_FEASIBLE"

    return best, reason


# ============================================================
# BUILD DIRECT ROUTE
# ============================================================
def build_direct_route(
    transfer,
    reserved_vehicle_ids
):

    source = transfer["source_warehouse"]
    destination = transfer["destination_warehouse"]

    weight = float(transfer["weight_kg"])
    volume = float(transfer["volume_m3"])

    distance = get_distance(
        source,
        destination
    )

    if distance is None:
        return None

    round_trip_distance = distance * 2

    vehicle, reason = select_best_vehicle(
        source,
        weight,
        volume,
        round_trip_distance,
        reserved_vehicle_ids
    )

    if vehicle is None:
        return None

    fuel = (
        round_trip_distance
        /
        float(vehicle["fuel_efficiency_kmpl"])
    )

    fuel_cost = (
        fuel
        *
        FUEL_PRICE_PER_LITRE
    )

    weight_utilization = (
        weight
        /
        float(vehicle["capacity_kg"])
    )

    volume_utilization = (
        volume
        /
        float(vehicle["volume_capacity_m3"])
    )

    overall_utilization = (
        weight_utilization
        +
        volume_utilization
    ) / 2

    return {
        "route": [
            source,
            destination,
            source
        ],

        "vehicle": vehicle,

        "distance": round_trip_distance,

        "one_way_distance": distance,

        "weight": weight,

        "volume": volume,

        "fuel": fuel,

        "fuel_cost": fuel_cost,

        "weight_utilization":
            weight_utilization,

        "volume_utilization":
            volume_utilization,

        "overall_utilization":
            overall_utilization,

        "reason": reason
    }

# ============================================================
# BUILD CONSOLIDATED ROUTE
# ============================================================

def build_consolidated_route(
    shipment_group,
    reserved_vehicle_ids
):

    if shipment_group.empty:
        return None

    source = shipment_group.iloc[0][
        "source_warehouse"
    ]

    destinations = list(
        dict.fromkeys(
            shipment_group[
                "destination_warehouse"
            ].tolist()
        )
    )

    if not destinations:
        return None

    # Maximum route stops.
    destinations = destinations[
        :MAX_STOPS
    ]

    total_weight = float(
        shipment_group["weight_kg"].sum()
    )

    total_volume = float(
        shipment_group["volume_m3"].sum()
    )

    # --------------------------------------------------------
    # Find best destination order.
    # Simple permutation search works well for our
    # small warehouse network.
    # --------------------------------------------------------

    import itertools

    best_route = None
    best_distance = None

    for permutation in itertools.permutations(
        destinations
    ):

        route = [source] + list(permutation) + [source]

        distance = calculate_route_distance(
            route
        )

        if distance is None:
            continue

        if (
            best_distance is None
            or distance < best_distance
        ):
            best_distance = distance
            best_route = route

    if best_route is None:
        return None

    vehicle, reason = select_best_vehicle(
        source,
        total_weight,
        total_volume,
        best_distance,
        reserved_vehicle_ids
    )

    if vehicle is None:
        return None

    return {
        "route": best_route,
        "vehicle": vehicle,
        "distance": best_distance,
        "reason": reason
    }


# ============================================================
# MAIN GLOBAL OPTIMIZER
# ============================================================

print()
print("=" * 50)
print("       LOGICOMMERCE AI V7")
print(" GLOBAL FLEET + SHIPMENT OPTIMIZATION")
print("=" * 50)


# ------------------------------------------------------------
# Remove invalid rows
# ------------------------------------------------------------

required_transfer_columns = [
    "transfer_id",
    "source_warehouse",
    "destination_warehouse",
    "weight_kg",
    "volume_m3",
    "priority",
    "deadline_days"
]

for column in required_transfer_columns:

    if column not in transfers.columns:
        raise ValueError(
            f"Missing transfer column: {column}"
        )


# ------------------------------------------------------------
# Convert numeric fields
# ------------------------------------------------------------

transfers["weight_kg"] = pd.to_numeric(
    transfers["weight_kg"],
    errors="coerce"
)

transfers["volume_m3"] = pd.to_numeric(
    transfers["volume_m3"],
    errors="coerce"
)

transfers["deadline_days"] = pd.to_numeric(
    transfers["deadline_days"],
    errors="coerce"
)


transfers = transfers.dropna(
    subset=[
        "weight_kg",
        "volume_m3",
        "deadline_days"
    ]
).copy()


# ============================================================
# PRIORITY ORDER
# ============================================================

priority_order = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2
}

transfers["priority_rank"] = (
    transfers["priority"]
    .map(priority_order)
    .fillna(3)
)


# Urgent shipments first.
transfers = transfers.sort_values(
    by=[
        "deadline_days",
        "priority_rank"
    ]
).reset_index(drop=True)


print()

for source in sorted(
    transfers["source_warehouse"].unique()
):

    count = len(
        transfers[
            transfers["source_warehouse"] == source
        ]
    )

    print("-" * 42)
    print(
        f"SOURCE: {source}"
    )
    print(
        f"Pending transfers: {count}"
    )


# ============================================================
# GLOBAL ASSIGNMENT
# ============================================================

print()
print("=" * 50)
print("       GLOBAL FLEET ASSIGNMENT")
print("=" * 50)


assigned = set()
reserved_vehicle_ids = set()

plans = []


# ============================================================
# STEP 1
# URGENT / HIGH PRIORITY SHIPMENTS
# ============================================================

urgent_transfers = transfers[
    (
        transfers["deadline_days"] <= 1
    )
    |
    (
        transfers["priority"] == "HIGH"
    )
].copy()


for _, transfer in urgent_transfers.iterrows():

    transfer_id = transfer["transfer_id"]

    if transfer_id in assigned:
        continue

    result = build_direct_route(
        transfer,
        reserved_vehicle_ids
    )

    if result is None:
        continue

    vehicle = result["vehicle"]

    reserved_vehicle_ids.add(
        vehicle["vehicle_id"]
    )

    assigned.add(
        transfer_id
    )

    plans.append({
    "decision": "URGENT_SEPARATE",

    "transfer_ids": transfer_id,

    "route": result["route"],

    "vehicle": vehicle,

    "distance": result["distance"],

    "weight": result["weight"],

    "volume": result["volume"],

    "fuel": result["fuel"],

    "fuel_cost": result["fuel_cost"],

    "weight_utilization":
        result["weight_utilization"],

    "volume_utilization":
        result["volume_utilization"],

    "overall_utilization":
        result["overall_utilization"],

    "reason":
        "Urgent shipment protected from consolidation delay."
})


# ============================================================
# STEP 2
# GROUP REMAINING SHIPMENTS
# ============================================================

remaining = transfers[
    ~transfers["transfer_id"].isin(
        assigned
    )
].copy()


grouped = remaining.groupby(
    [
        "source_warehouse",
        "destination_warehouse"
    ]
)


for (
    source,
    destination
), group in grouped:

    group = group[
        ~group["transfer_id"].isin(
            assigned
        )
    ]

    if group.empty:
        continue

    # --------------------------------------------------------
    # Try consolidated direct route first.
    # --------------------------------------------------------

    total_weight = float(
        group["weight_kg"].sum()
    )

    total_volume = float(
        group["volume_m3"].sum()
    )

    direct_distance = get_distance(
        source,
        destination
    )

    if direct_distance is None:
        continue

    consolidated_vehicle, reason = select_best_vehicle(
        source,
        total_weight,
        total_volume,
        direct_distance * 2,
        reserved_vehicle_ids
    )

    if consolidated_vehicle is not None:

        route = [
            source,
            destination,
            source
        ]

        fuel = (
            direct_distance * 2
            /
            consolidated_vehicle[
                "fuel_efficiency_kmpl"
            ]
        )

        fuel_cost = (
            fuel
            *
            FUEL_PRICE_PER_LITRE
        )

        weight_utilization = (
            total_weight
            /
            consolidated_vehicle[
                "capacity_kg"
            ]
        )

        volume_utilization = (
            total_volume
            /
            consolidated_vehicle[
                "volume_capacity_m3"
            ]
        )

        overall_utilization = (
            weight_utilization
            +
            volume_utilization
        ) / 2

        vehicle_id = (
            consolidated_vehicle[
                "vehicle_id"
            ]
        )

        reserved_vehicle_ids.add(
            vehicle_id
        )

        transfer_ids = group[
            "transfer_id"
        ].tolist()

        for transfer_id in transfer_ids:
            assigned.add(
                transfer_id
            )

        plans.append({
            "decision": "CONSOLIDATE",
            "transfer_ids": ",".join(
                transfer_ids
            ),
            "route": route,
            "vehicle": consolidated_vehicle,
            "distance": direct_distance * 2,
            "weight": total_weight,
            "volume": total_volume,
            "fuel": fuel,
            "fuel_cost": fuel_cost,
            "weight_utilization": weight_utilization,
            "volume_utilization": volume_utilization,
            "overall_utilization": overall_utilization,
            "reason": reason
        })

        continue

    # --------------------------------------------------------
    # If all shipments cannot fit together,
    # assign individually.
    # --------------------------------------------------------

    for _, transfer in group.iterrows():

        transfer_id = transfer["transfer_id"]

        if transfer_id in assigned:
            continue

        result = build_direct_route(
            transfer,
            reserved_vehicle_ids
        )

        if result is None:
            continue

        vehicle = result["vehicle"]

        distance = result["distance"]

        fuel = (
            distance
            /
            vehicle[
                "fuel_efficiency_kmpl"
            ]
        )

        fuel_cost = (
            fuel
            *
            FUEL_PRICE_PER_LITRE
        )

        weight = float(
            transfer["weight_kg"]
        )

        volume = float(
            transfer["volume_m3"]
        )

        weight_utilization = (
            weight
            /
            vehicle[
                "capacity_kg"
            ]
        )

        volume_utilization = (
            volume
            /
            vehicle[
                "volume_capacity_m3"
            ]
        )

        overall_utilization = (
            weight_utilization
            +
            volume_utilization
        ) / 2

        reserved_vehicle_ids.add(
            vehicle["vehicle_id"]
        )

        assigned.add(
            transfer_id
        )

        plans.append({
            "decision": "SEPARATE",
            "transfer_ids": transfer_id,
            "route": result["route"],
            "vehicle": vehicle,
            "distance": distance,
            "weight": weight,
            "volume": volume,
            "fuel": fuel,
            "fuel_cost": fuel_cost,
            "weight_utilization": weight_utilization,
            "volume_utilization": volume_utilization,
            "overall_utilization": overall_utilization,
            "reason": "Shipment could not be consolidated within available fleet capacity."
        })


# ============================================================
# STEP 3
# TRY MULTI-STOP CONSOLIDATION FOR REMAINING SHIPMENTS
# ============================================================

remaining = transfers[
    ~transfers["transfer_id"].isin(
        assigned
    )
].copy()


for source in remaining[
    "source_warehouse"
].unique():

    source_shipments = remaining[
        remaining["source_warehouse"] == source
    ].copy()

    if source_shipments.empty:
        continue

    destinations = list(
        source_shipments[
            "destination_warehouse"
        ].unique()
    )

    # Try combinations of destinations.
    import itertools

    for stop_count in range(
        min(MAX_STOPS, len(destinations)),
        0,
        -1
    ):

        found = False

        for destination_group in itertools.combinations(
            destinations,
            stop_count
        ):

            candidate = source_shipments[
                source_shipments[
                    "destination_warehouse"
                ].isin(destination_group)
            ]

            candidate = candidate[
                ~candidate[
                    "transfer_id"
                ].isin(assigned)
            ]

            if candidate.empty:
                continue

            result = build_consolidated_route(
                candidate,
                reserved_vehicle_ids
            )

            if result is None:
                continue

            vehicle = result["vehicle"]

            total_weight = float(
                candidate["weight_kg"].sum()
            )

            total_volume = float(
                candidate["volume_m3"].sum()
            )

            distance = result["distance"]

            fuel = (
                distance
                /
                vehicle[
                    "fuel_efficiency_kmpl"
                ]
            )

            fuel_cost = (
                fuel
                *
                FUEL_PRICE_PER_LITRE
            )

            weight_utilization = (
                total_weight
                /
                vehicle[
                    "capacity_kg"
                ]
            )

            volume_utilization = (
                total_volume
                /
                vehicle[
                    "volume_capacity_m3"
                ]
            )

            overall_utilization = (
                weight_utilization
                +
                volume_utilization
            ) / 2

            transfer_ids = candidate[
                "transfer_id"
            ].tolist()

            for transfer_id in transfer_ids:

                assigned.add(
                    transfer_id
                )

            reserved_vehicle_ids.add(
                vehicle["vehicle_id"]
            )

            plans.append({
                "decision": "MULTI_STOP_CONSOLIDATE",
                "transfer_ids": ",".join(
                    transfer_ids
                ),
                "route": result["route"],
                "vehicle": vehicle,
                "distance": distance,
                "weight": total_weight,
                "volume": total_volume,
                "fuel": fuel,
                "fuel_cost": fuel_cost,
                "weight_utilization": weight_utilization,
                "volume_utilization": volume_utilization,
                "overall_utilization": overall_utilization,
                "reason": "Multi-stop consolidation improved fleet utilization."
            })

            found = True
            break

        if found:
            break


# ============================================================
# FINAL INDIVIDUAL FALLBACK
# ============================================================

remaining = transfers[
    ~transfers["transfer_id"].isin(
        assigned
    )
].copy()


for _, transfer in remaining.iterrows():

    transfer_id = transfer["transfer_id"]

    result = build_direct_route(
        transfer,
        reserved_vehicle_ids
    )

    if result is None:
        continue

    vehicle = result["vehicle"]

    distance = result["distance"]

    weight = float(
        transfer["weight_kg"]
    )

    volume = float(
        transfer["volume_m3"]
    )

    fuel = (
        distance
        /
        vehicle[
            "fuel_efficiency_kmpl"
        ]
    )

    fuel_cost = (
        fuel
        *
        FUEL_PRICE_PER_LITRE
    )

    weight_utilization = (
        weight
        /
        vehicle[
            "capacity_kg"
        ]
    )

    volume_utilization = (
        volume
        /
        vehicle[
            "volume_capacity_m3"
        ]
    )

    overall_utilization = (
        weight_utilization
        +
        volume_utilization
    ) / 2

    reserved_vehicle_ids.add(
        vehicle["vehicle_id"]
    )

    assigned.add(
        transfer_id
    )

    plans.append({
        "decision": "FLEET_FALLBACK",
        "transfer_ids": transfer_id,
        "route": result["route"],
        "vehicle": vehicle,
        "distance": distance,
        "weight": weight,
        "volume": volume,
        "fuel": fuel,
        "fuel_cost": fuel_cost,
        "weight_utilization": weight_utilization,
        "volume_utilization": volume_utilization,
        "overall_utilization": overall_utilization,
        "reason": "Final feasible fleet assignment."
    })


# ============================================================
# OUTPUT
# ============================================================

print()
print("=" * 50)
print("       FINAL LOGISTICS PLAN V7")
print("=" * 50)


output_rows = []


for plan in plans:

    vehicle = plan["vehicle"]

    route_text = " → ".join(
        plan["route"]
    )

    print()
    print("-" * 42)

    print(
        f"Decision: {plan['decision']}"
    )

    print(
        f"Route: {route_text}"
    )

    print(
        f"Transfers: {plan['transfer_ids']}"
    )

    print(
        f"Vehicle: {vehicle['vehicle_id']}"
    )

    print(
        f"Vehicle capacity: "
        f"{vehicle['capacity_kg']} kg"
    )

    print(
        f"Vehicle volume: "
        f"{vehicle['volume_capacity_m3']} m³"
    )

    print(
        f"Weight: {plan['weight']:.2f} kg"
    )

    print(
        f"Volume: {plan['volume']:.3f} m³"
    )

    print(
        f"Weight utilization: "
        f"{plan['weight_utilization'] * 100:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{plan['volume_utilization'] * 100:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{plan['overall_utilization'] * 100:.1f}%"
    )

    print(
        f"Distance: "
        f"{plan['distance']:.0f} km"
    )

    print(
        f"Fuel: "
        f"{plan['fuel']:.2f} L"
    )

    print(
        f"Fuel cost: "
        f"₹{plan['fuel_cost']:.2f}"
    )

    print(
        f"Reason: {plan['reason']}"
    )

    output_rows.append({
        "decision": plan["decision"],
        "transfer_ids": plan["transfer_ids"],
        "route": route_text,
        "vehicle_id": vehicle["vehicle_id"],
        "vehicle_capacity_kg": vehicle["capacity_kg"],
        "vehicle_volume_m3": vehicle[
            "volume_capacity_m3"
        ],
        "shipment_weight_kg": plan["weight"],
        "shipment_volume_m3": plan["volume"],
        "weight_utilization_pct":
            plan["weight_utilization"] * 100,
        "volume_utilization_pct":
            plan["volume_utilization"] * 100,
        "overall_utilization_pct":
            plan["overall_utilization"] * 100,
        "distance_km": plan["distance"],
        "fuel_litres": plan["fuel"],
        "fuel_cost": plan["fuel_cost"],
        "reason": plan["reason"]
    })


# ============================================================
# SAVE
# ============================================================

output_df = pd.DataFrame(
    output_rows
)

output_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

assigned_count = len(assigned)

total_transfers = len(
    transfers
)

unassigned_count = (
    total_transfers
    -
    assigned_count
)

total_distance = (
    output_df["distance_km"].sum()
    if not output_df.empty
    else 0
)

total_fuel = (
    output_df["fuel_litres"].sum()
    if not output_df.empty
    else 0
)

total_cost = (
    output_df["fuel_cost"].sum()
    if not output_df.empty
    else 0
)

average_weight_utilization = (
    output_df[
        "weight_utilization_pct"
    ].mean()
    if not output_df.empty
    else 0
)

average_volume_utilization = (
    output_df[
        "volume_utilization_pct"
    ].mean()
    if not output_df.empty
    else 0
)


print()
print("=" * 50)
print("       V7 OPTIMIZATION SUMMARY")
print("=" * 50)

print(
    f"Total transfers: {total_transfers}"
)

print(
    f"Assigned transfers: {assigned_count}"
)

print(
    f"Unassigned transfers: {unassigned_count}"
)

print(
    f"Routes created: {len(output_df)}"
)

print(
    f"Total distance: "
    f"{total_distance:.2f} km"
)

print(
    f"Total fuel: "
    f"{total_fuel:.2f} L"
)

print(
    f"Total fuel cost: "
    f"₹{total_cost:.2f}"
)

print(
    f"Average weight utilization: "
    f"{average_weight_utilization:.1f}%"
)

print(
    f"Average volume utilization: "
    f"{average_volume_utilization:.1f}%"
)


if unassigned_count > 0:

    print()
    print("UNASSIGNED TRANSFERS:")

    for transfer_id in transfers[
        ~transfers[
            "transfer_id"
        ].isin(assigned)
    ]["transfer_id"]:

        print(
            f"⚠️ {transfer_id}"
        )


print()
print("=" * 50)
print("V7 OPTIMIZATION COMPLETE")
print("=" * 50)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)