import os
import math
import pandas as pd


# ============================================================
# LOGICOMMERCE AI V10
# COST + DEADLINE + FLEET OPTIMIZATION
# ============================================================

DATA_DIR = "data"

TRANSFER_FILE = os.path.join(DATA_DIR, "transfer_requests.csv")
VEHICLE_FILE = os.path.join(DATA_DIR, "vehicles.csv")
DISTANCE_FILE = os.path.join(DATA_DIR, "warehouse_distances.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "logistics_optimization_v10.csv")

FUEL_PRICE = 100.0

# Deadline safety margins
URGENT_LIMIT = 1
SOON_LIMIT = 2

# A consolidation is accepted only when savings are meaningful.
MIN_SAVINGS_PERCENT = 1.0


# ============================================================
# LOAD DATA
# ============================================================

print("Loading transfer requests...")
transfers_df = pd.read_csv(TRANSFER_FILE)

print("Loading vehicles...")
vehicles_df = pd.read_csv(VEHICLE_FILE)

print("Loading warehouse distances...")
distances_df = pd.read_csv(DISTANCE_FILE)


# ============================================================
# NORMALIZE COLUMN NAMES
# ============================================================

transfers_df.columns = [
    str(c).strip().lower() for c in transfers_df.columns
]

vehicles_df.columns = [
    str(c).strip().lower() for c in vehicles_df.columns
]

distances_df.columns = [
    str(c).strip().lower() for c in distances_df.columns
]


# ============================================================
# DISTANCE LOOKUP
# ============================================================

def get_distance(source, destination):

    if source == destination:
        return 0.0

    row = distances_df[
        (
            (distances_df["source_warehouse"] == source)
            &
            (distances_df["destination_warehouse"] == destination)
        )
        |
        (
            (distances_df["source_warehouse"] == destination)
            &
            (distances_df["destination_warehouse"] == source)
        )
    ]

    if row.empty:
        return None

    return float(row.iloc[0]["distance_km"])


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

    # Average operational speed.
    # Includes loading/unloading overhead.
    driving_time = distance / 40.0

    number_of_stops = max(0, int(distance > 0))

    handling_time = number_of_stops * 1.0

    return round(
        driving_time + handling_time,
        2
    )


# ============================================================
# URGENCY
# ============================================================

def urgency_level(deadline_days):

    if deadline_days <= URGENT_LIMIT:
        return "URGENT"

    if deadline_days <= SOON_LIMIT:
        return "SOON"

    return "NORMAL"


# ============================================================
# VEHICLE SELECTION
# ============================================================

def find_best_vehicle(
    source,
    weight,
    volume,
    distance
):

    candidates = []

    for _, vehicle in vehicles_df.iterrows():

        # Vehicle must belong to source warehouse.
        if str(vehicle["warehouse_id"]) != str(source):
            continue

        # Vehicle must be available.
        if int(vehicle["available"]) != 1:
            continue

        capacity = float(vehicle["capacity_kg"])
        volume_capacity = float(
            vehicle["volume_capacity_m3"]
        )

        fuel_efficiency = float(
            vehicle["fuel_efficiency_kmpl"]
        )

        # Hard capacity constraints.
        if weight > capacity:
            continue

        if volume > volume_capacity:
            continue

        weight_utilization = (
            weight / capacity
        ) * 100

        volume_utilization = (
            volume / volume_capacity
        ) * 100

        overall_utilization = (
            weight_utilization
            + volume_utilization
        ) / 2

        fuel = (
            distance / fuel_efficiency
        )

        fuel_cost = fuel * FUEL_PRICE

        # Prefer good utilization and fuel efficiency.
        score = (
            fuel_cost
            - overall_utilization * 2
        )

        candidates.append({
            "vehicle_id":
                vehicle["vehicle_id"],

            "capacity_kg":
                capacity,

            "volume_capacity_m3":
                volume_capacity,

            "fuel_efficiency_kmpl":
                fuel_efficiency,

            "weight_utilization":
                weight_utilization,

            "volume_utilization":
                volume_utilization,

            "overall_utilization":
                overall_utilization,

            "fuel":
                fuel,

            "fuel_cost":
                fuel_cost,

            "score":
                score
        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["score"]
    )

    return candidates[0]


# ============================================================
# SEPARATE SHIPMENT COST
# ============================================================

def calculate_separate_cost(group):

    total_cost = 0.0

    for _, shipment in group.iterrows():

        source = shipment["source_warehouse"]
        destination = shipment[
            "destination_warehouse"
        ]

        distance = get_distance(
            source,
            destination
        )

        if distance is None:
            continue

        weight = float(
            shipment["weight_kg"]
        )

        volume = float(
            shipment["volume_m3"]
        )

        vehicle = find_best_vehicle(
            source,
            weight,
            volume,
            distance
        )

        if vehicle is None:

            # Fallback cost using a conservative
            # reference vehicle efficiency.
            fuel = distance / 10.0

        else:

            fuel = vehicle["fuel"]

        total_cost += fuel * FUEL_PRICE

    return total_cost


# ============================================================
# BUILD CONSOLIDATED ROUTE
# ============================================================

def build_route(
    source,
    shipments
):

    destinations = list(
        shipments[
            "destination_warehouse"
        ].unique()
    )

    if not destinations:
        return None

    # Remove source from destinations if present.
    destinations = [
        x for x in destinations
        if x != source
    ]

    if not destinations:
        return {
            "route": [source],
            "distance": 0.0
        }

    # --------------------------------------------------------
    # Greedy nearest-neighbour route.
    # --------------------------------------------------------

    route = [source]
    remaining = destinations.copy()
    current = source

    while remaining:

        nearest = None
        nearest_distance = None

        for destination in remaining:

            distance = get_distance(
                current,
                destination
            )

            if distance is None:
                continue

            if (
                nearest_distance is None
                or distance < nearest_distance
            ):

                nearest = destination
                nearest_distance = distance

        if nearest is None:
            return None

        route.append(nearest)
        remaining.remove(nearest)
        current = nearest

    # Return to source.
    route.append(source)

    total_distance = calculate_route_distance(
        route
    )

    if total_distance is None:
        return None

    return {
        "route": route,
        "distance": total_distance
    }


# ============================================================
# DEADLINE CHECK
# ============================================================

def deadline_status(
    shipments,
    route_time
):

    deadlines = []

    for _, shipment in shipments.iterrows():

        try:
            deadline = float(
                shipment["deadline_days"]
            )

            deadlines.append(deadline)

        except Exception:
            pass

    if not deadlines:
        return "NO_DEADLINE"

    earliest_deadline = min(deadlines)

    if route_time <= earliest_deadline * 24:
        return "ON_TIME"

    if route_time <= earliest_deadline * 24 * 1.10:
        return "AT_RISK"

    return "MISSED_DEADLINE"


# ============================================================
# DECISION ENGINE
# ============================================================

def evaluate_group(
    source,
    destination_group
):

    group = destination_group.copy()

    transfers = group[
        "transfer_id"
    ].tolist()

    weight = group[
        "weight_kg"
    ].sum()

    volume = group[
        "volume_m3"
    ].sum()

    destinations = group[
        "destination_warehouse"
    ].unique()

    # --------------------------------------------------------
    # Separate route
    # --------------------------------------------------------

    separate_cost = calculate_separate_cost(
        group
    )

    # --------------------------------------------------------
    # Consolidated route
    # --------------------------------------------------------

    route_data = build_route(
        source,
        group
    )

    if route_data is None:

        return None

    route = route_data["route"]
    distance = route_data["distance"]

    route_time = calculate_route_time(
        distance
    )

    # --------------------------------------------------------
    # Vehicle
    # --------------------------------------------------------

    vehicle = find_best_vehicle(
        source,
        weight,
        volume,
        distance
    )

    if vehicle is None:

        return None

    optimized_cost = vehicle[
        "fuel_cost"
    ]

    savings = max(
        0.0,
        separate_cost - optimized_cost
    )

    if separate_cost > 0:

        savings_percent = (
            savings / separate_cost
        ) * 100

    else:

        savings_percent = 0.0

    status = deadline_status(
        group,
        route_time
    )

    # --------------------------------------------------------
    # Urgency
    # --------------------------------------------------------

    deadline_values = []

    for _, row in group.iterrows():

        try:
            deadline_values.append(
                float(
                    row["deadline_days"]
                )
            )
        except Exception:
            pass

    earliest_deadline = (
        min(deadline_values)
        if deadline_values
        else None
    )

    urgency = (
        urgency_level(
            earliest_deadline
        )
        if earliest_deadline is not None
        else "NORMAL"
    )

    # --------------------------------------------------------
    # FINAL DECISION
    # --------------------------------------------------------

    # Never consolidate urgent shipments.
    if urgency == "URGENT":

        decision = "URGENT_SEPARATE"

        reason = (
            "Urgent shipment protected "
            "from consolidation delay."
        )

        # For urgent shipment use direct route.
        direct_destination = group.iloc[0][
            "destination_warehouse"
        ]

        direct_distance = get_distance(
            source,
            direct_destination
        )

        if direct_distance is None:
            return None

        direct_vehicle = find_best_vehicle(
            source,
            weight,
            volume,
            direct_distance
        )

        if direct_vehicle is None:
            return None

        route = [
            source,
            direct_destination,
            source
        ]

        distance = (
            direct_distance * 2
        )

        route_time = calculate_route_time(
            distance
        )

        optimized_cost = (
            distance
            / direct_vehicle[
                "fuel_efficiency_kmpl"
            ]
            * FUEL_PRICE
        )

        vehicle = direct_vehicle

        status = deadline_status(
            group,
            route_time
        )

        savings = max(
            0.0,
            separate_cost - optimized_cost
        )

        savings_percent = (
            savings / separate_cost * 100
            if separate_cost > 0
            else 0
        )

    else:

        # Consolidation is allowed only when:
        #
        # 1. Cost is lower.
        # 2. Deadline is not missed.
        # 3. Shipment group fits vehicle.

        if (
            optimized_cost < separate_cost
            and
            savings_percent >= MIN_SAVINGS_PERCENT
            and
            status != "MISSED_DEADLINE"
        ):

            decision = "CONSOLIDATE"

            reason = (
                "Compatible shipments combined "
                "with cost savings while preserving "
                "deadline feasibility."
            )

        else:

            decision = "SEPARATE"

            reason = (
                "Consolidation rejected because "
                "it does not provide sufficient "
                "cost benefit or deadline safety."
            )

            # ------------------------------------------------
            # For single shipment / rejected consolidation,
            # use direct route.
            # ------------------------------------------------

            if len(group) == 1:

                direct_destination = group.iloc[0][
                    "destination_warehouse"
                ]

                direct_distance = get_distance(
                    source,
                    direct_destination
                )

                if direct_distance is None:
                    return None

                direct_vehicle = find_best_vehicle(
                    source,
                    weight,
                    volume,
                    direct_distance
                )

                if direct_vehicle is None:
                    return None

                route = [
                    source,
                    direct_destination,
                    source
                ]

                distance = (
                    direct_distance * 2
                )

                route_time = calculate_route_time(
                    distance
                )

                vehicle = direct_vehicle

                optimized_cost = (
                    distance
                    / vehicle[
                        "fuel_efficiency_kmpl"
                    ]
                    * FUEL_PRICE
                )

                status = deadline_status(
                    group,
                    route_time
                )

                savings = max(
                    0.0,
                    separate_cost - optimized_cost
                )

                savings_percent = (
                    savings
                    / separate_cost
                    * 100
                    if separate_cost > 0
                    else 0
                )

    return {
        "decision":
            decision,

        "source":
            source,

        "route":
            " → ".join(route),

        "transfers":
            ",".join(transfers),

        "vehicle_id":
            vehicle["vehicle_id"],

        "vehicle_capacity_kg":
            vehicle["capacity_kg"],

        "vehicle_volume_m3":
            vehicle["volume_capacity_m3"],

        "weight":
            weight,

        "volume":
            volume,

        "weight_utilization":
            vehicle["weight_utilization"],

        "volume_utilization":
            vehicle["volume_utilization"],

        "overall_utilization":
            vehicle["overall_utilization"],

        "fuel_efficiency":
            vehicle["fuel_efficiency_kmpl"],

        "distance":
            distance,

        "route_time":
            route_time,

        "fuel":
            optimized_cost
            / FUEL_PRICE,

        "fuel_cost":
            optimized_cost,

        "separate_cost":
            separate_cost,

        "savings":
            savings,

        "savings_percent":
            savings_percent,

        "deadline":
            status,

        "urgency":
            urgency,

        "reason":
            reason
    }


# ============================================================
# MAIN OPTIMIZATION
# ============================================================

print()
print("=" * 50)
print("       LOGICOMMERCE AI V10")
print(" COST + DEADLINE + FLEET OPTIMIZATION")
print("=" * 50)


# ------------------------------------------------------------
# Show source warehouse information
# ------------------------------------------------------------

for source in sorted(
    transfers_df[
        "source_warehouse"
    ].unique()
):

    count = len(
        transfers_df[
            transfers_df[
                "source_warehouse"
            ] == source
        ]
    )

    print()
    print("-" * 50)
    print(
        f"SOURCE: {source}"
    )
    print(
        f"Transfers: {count}"
    )


# ============================================================
# PROCESS BY SOURCE
# ============================================================

plans = []
assigned_transfers = set()

sources = sorted(
    transfers_df[
        "source_warehouse"
    ].unique()
)

for source in sources:

    source_df = transfers_df[
        transfers_df[
            "source_warehouse"
        ] == source
    ].copy()

    # --------------------------------------------------------
    # First process urgent transfers individually.
    # --------------------------------------------------------

    urgent_df = source_df[
        source_df[
            "deadline_days"
        ] <= URGENT_LIMIT
    ]

    for _, row in urgent_df.iterrows():

        if row["transfer_id"] in assigned_transfers:
            continue

        group = pd.DataFrame(
            [row]
        )

        plan = evaluate_group(
            source,
            group
        )

        if plan is not None:

            plans.append(plan)

            assigned_transfers.add(
                row["transfer_id"]
            )

    # --------------------------------------------------------
    # Process remaining transfers grouped by destination.
    # --------------------------------------------------------

    remaining = source_df[
        ~source_df[
            "transfer_id"
        ].isin(
            assigned_transfers
        )
    ]

    destination_groups = (
        remaining
        .groupby(
            "destination_warehouse"
        )
    )

    for destination, group in destination_groups:

        transfer_ids = group[
            "transfer_id"
        ].tolist()

        if all(
            x in assigned_transfers
            for x in transfer_ids
        ):
            continue

        plan = evaluate_group(
            source,
            group
        )

        if plan is None:
            continue

        plans.append(plan)

        for transfer_id in transfer_ids:

            assigned_transfers.add(
                transfer_id
            )


# ============================================================
# FALLBACK FOR ANY UNASSIGNED TRANSFERS
# ============================================================

unassigned = transfers_df[
    ~transfers_df[
        "transfer_id"
    ].isin(
        assigned_transfers
    )
]

for _, row in unassigned.iterrows():

    source = row[
        "source_warehouse"
    ]

    group = pd.DataFrame(
        [row]
    )

    plan = evaluate_group(
        source,
        group
    )

    if plan is not None:

        plan["decision"] = (
            "FLEET_FALLBACK"
        )

        plan["reason"] = (
            "Fallback direct dispatch used "
            "to ensure shipment coverage."
        )

        plans.append(plan)

        assigned_transfers.add(
            row["transfer_id"]
        )


# ============================================================
# OUTPUT
# ============================================================

plans_df = pd.DataFrame(
    plans
)


# ============================================================
# DISPLAY RESULTS
# ============================================================

print()
print("=" * 50)
print("       FINAL LOGISTICS PLAN V10")
print("=" * 50)


for _, plan in plans_df.iterrows():

    print()
    print("-" * 50)

    print(
        f"Decision: {plan['decision']}"
    )

    print(
        f"Route: {plan['route']}"
    )

    print(
        f"Transfers: {plan['transfers']}"
    )

    print(
        f"Vehicle: {plan['vehicle_id']}"
    )

    print(
        f"Vehicle capacity: "
        f"{plan['vehicle_capacity_kg']:.0f} kg"
    )

    print(
        f"Vehicle volume: "
        f"{plan['vehicle_volume_m3']:.1f} m³"
    )

    print(
        f"Weight: "
        f"{plan['weight']:.2f} kg"
    )

    print(
        f"Volume: "
        f"{plan['volume']:.3f} m³"
    )

    print(
        f"Weight utilization: "
        f"{plan['weight_utilization']:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{plan['volume_utilization']:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{plan['overall_utilization']:.1f}%"
    )

    print(
        f"Fuel efficiency: "
        f"{plan['fuel_efficiency']:.2f} km/L"
    )

    print(
        f"Distance: "
        f"{plan['distance']:.0f} km"
    )

    print(
        f"Route time: "
        f"{plan['route_time']:.2f} hours"
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
        f"Separate cost: "
        f"₹{plan['separate_cost']:.2f}"
    )

    print(
        f"Savings: "
        f"₹{plan['savings']:.2f}"
    )

    print(
        f"Savings: "
        f"{plan['savings_percent']:.1f}%"
    )

    print(
        f"Deadline: "
        f"{plan['deadline']}"
    )

    print(
        f"Urgency: "
        f"{plan['urgency']}"
    )

    print(
        f"Reason: "
        f"{plan['reason']}"
    )


# ============================================================
# SUMMARY
# ============================================================

total_transfers = len(
    transfers_df
)

assigned_count = len(
    assigned_transfers
)

unassigned_count = (
    total_transfers
    - assigned_count
)

routes_created = len(
    plans_df
)

total_distance = (
    plans_df["distance"].sum()
    if not plans_df.empty
    else 0
)

total_fuel = (
    plans_df["fuel"].sum()
    if not plans_df.empty
    else 0
)

optimized_cost = (
    plans_df["fuel_cost"].sum()
    if not plans_df.empty
    else 0
)

baseline_cost = (
    plans_df["separate_cost"].sum()
    if not plans_df.empty
    else 0
)

total_savings = max(
    0,
    baseline_cost - optimized_cost
)

overall_savings = (
    total_savings
    / baseline_cost
    * 100
    if baseline_cost > 0
    else 0
)

average_weight_utilization = (
    plans_df[
        "weight_utilization"
    ].mean()
    if not plans_df.empty
    else 0
)

average_volume_utilization = (
    plans_df[
        "volume_utilization"
    ].mean()
    if not plans_df.empty
    else 0
)

on_time = len(
    plans_df[
        plans_df[
            "deadline"
        ] == "ON_TIME"
    ]
)

at_risk = len(
    plans_df[
        plans_df[
            "deadline"
        ] == "AT_RISK"
    ]
)

missed = len(
    plans_df[
        plans_df[
            "deadline"
        ] == "MISSED_DEADLINE"
    ]
)

consolidated = len(
    plans_df[
        plans_df[
            "decision"
        ] == "CONSOLIDATE"
    ]
)

separate = len(
    plans_df[
        plans_df[
            "decision"
        ] == "SEPARATE"
    ]
)

urgent_separate = len(
    plans_df[
        plans_df[
            "decision"
        ] == "URGENT_SEPARATE"
    ]
)


print()
print("=" * 50)
print("       V10 OPTIMIZATION SUMMARY")
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
    f"Routes created: {routes_created}"
)

print(
    f"Consolidated routes: {consolidated}"
)

print(
    f"Separate routes: {separate}"
)

print(
    f"Urgent separate: {urgent_separate}"
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
    f"Optimized fuel cost: "
    f"₹{optimized_cost:.2f}"
)

print(
    f"Baseline fuel cost: "
    f"₹{baseline_cost:.2f}"
)

print(
    f"Estimated savings: "
    f"₹{total_savings:.2f}"
)

print(
    f"Overall savings: "
    f"{overall_savings:.1f}%"
)

print(
    f"Average weight utilization: "
    f"{average_weight_utilization:.1f}%"
)

print(
    f"Average volume utilization: "
    f"{average_volume_utilization:.1f}%"
)

print()
print(
    f"ON_TIME routes: {on_time}"
)

print(
    f"AT_RISK routes: {at_risk}"
)

print(
    f"MISSED_DEADLINE routes: {missed}"
)


# ============================================================
# UNASSIGNED TRANSFERS
# ============================================================

if unassigned_count > 0:

    print()
    print(
        "UNASSIGNED TRANSFERS:"
    )

    for transfer_id in transfers_df[
        ~transfers_df[
            "transfer_id"
        ].isin(
            assigned_transfers
        )
    ]["transfer_id"]:

        print(
            f"⚠️ {transfer_id}"
        )

else:

    print()
    print(
        "✅ ALL TRANSFERS ASSIGNED"
    )


# ============================================================
# SAVE
# ============================================================

plans_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print()
print("=" * 50)
print("       LOGICOMMERCE V10 COMPLETE")
print("=" * 50)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)