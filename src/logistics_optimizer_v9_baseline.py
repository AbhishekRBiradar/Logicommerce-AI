import os
import math
import pandas as pd


# ============================================================
# LOGICOMMERCE AI V9
# GLOBAL FLEET + CONSOLIDATION + DEADLINE OPTIMIZATION
# ============================================================

DATA_DIR = "data"

TRANSFER_FILE = os.path.join(
    DATA_DIR,
    "transfer_requests.csv"
)

VEHICLE_FILE = os.path.join(
    DATA_DIR,
    "vehicles.csv"
)

DISTANCE_FILE = os.path.join(
    DATA_DIR,
    "warehouse_distances.csv"
)

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "logistics_optimization_v9.csv"
)

FUEL_PRICE = 100.0

# Minimum utilization preference.
# This is a preference, NOT a hard constraint.
TARGET_UTILIZATION = 0.30

# Deadline safety buffer.
DEADLINE_BUFFER_HOURS = 2.0

# Maximum number of stops in a consolidated route.
MAX_STOPS = 3


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
    str(c).strip()
    for c in transfers_df.columns
]

vehicles_df.columns = [
    str(c).strip()
    for c in vehicles_df.columns
]

distances_df.columns = [
    str(c).strip()
    for c in distances_df.columns
]


# ============================================================
# DISTANCE LOOKUP
# ============================================================

distance_map = {}


for _, row in distances_df.iterrows():

    source = str(
        row["source_warehouse"]
    ).strip()

    destination = str(
        row["destination_warehouse"]
    ).strip()

    distance = float(
        row["distance_km"]
    )

    distance_map[
        (source, destination)
    ] = distance

    distance_map[
        (destination, source)
    ] = distance


def get_distance(source, destination):

    if source == destination:
        return 0.0

    return float(
        distance_map.get(
            (source, destination),
            999999.0
        )
    )


# ============================================================
# PREPARE TRANSFER DATA
# ============================================================

transfers = []


for _, row in transfers_df.iterrows():

    transfers.append({

        "transfer_id":
            str(row["transfer_id"]),

        "source":
            str(row["source_warehouse"]),

        "destination":
            str(row["destination_warehouse"]),

        "weight":
            float(row["weight_kg"]),

        "volume":
            float(row["volume_m3"]),

        "priority":
            str(row["priority"]).upper(),

        "deadline_days":
            float(row["deadline_days"])

    })


# ============================================================
# VEHICLE DATA
# ============================================================

vehicles = []


for _, row in vehicles_df.iterrows():

    available = int(
        row["available"]
    )

    if available != 1:
        continue

    vehicles.append({

        "vehicle_id":
            str(row["vehicle_id"]),

        "warehouse_id":
            str(row["warehouse_id"]),

        "capacity":
            float(row["capacity_kg"]),

        "volume_capacity":
            float(row["volume_capacity_m3"]),

        "fuel_efficiency":
            float(row["fuel_efficiency_kmpl"])

    })


# ============================================================
# VEHICLE STATE
# ============================================================

vehicle_state = {}

for vehicle in vehicles:

    vehicle_state[
        vehicle["vehicle_id"]
    ] = {

        "available_from": 0.0,

        "current_location":
            vehicle["warehouse_id"],

        "trips": 0,

        "distance": 0.0,

        "fuel": 0.0

    }


# ============================================================
# PRIORITY WEIGHTS
# ============================================================

priority_weight = {

    "HIGH": 3,

    "MEDIUM": 2,

    "LOW": 1

}


def urgency_score(transfer):

    deadline = transfer[
        "deadline_days"
    ]

    priority = transfer[
        "priority"
    ]

    score = (
        priority_weight.get(
            priority,
            1
        ) * 10
    )

    score += max(
        0,
        10 - deadline
    )

    return score


# ============================================================
# SORT TRANSFERS
# ============================================================

transfers.sort(
    key=lambda x: (
        -urgency_score(x),
        x["deadline_days"]
    )
)


# ============================================================
# ROUTE TIME
# ============================================================

def route_time(distance):

    # Approximate average operating speed.
    return (
        distance / 40.0
        + 0.25
    )


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(
    source,
    destinations
):

    current = source

    total = 0.0

    for destination in destinations:

        total += get_distance(
            current,
            destination
        )

        current = destination

    # Return vehicle to source.
    total += get_distance(
        current,
        source
    )

    return total


# ============================================================
# VEHICLE SELECTION
# ============================================================

def choose_vehicle(
    source,
    weight,
    volume,
    distance,
    earliest_deadline_hours
):

    candidates = []

    for vehicle in vehicles:

        if (
            vehicle["capacity"]
            < weight
        ):
            continue

        if (
            vehicle["volume_capacity"]
            < volume
        ):
            continue

        state = vehicle_state[
            vehicle["vehicle_id"]
        ]

        # Vehicle must be able to reach source.
        reposition_distance = get_distance(
            state["current_location"],
            source
        )

        reposition_time = route_time(
            reposition_distance
        )

        departure = max(
            state["available_from"],
            reposition_time
        )

        trip_time = route_time(
            distance
        )

        arrival = (
            departure
            + trip_time
        )

        deadline_hours = (
            earliest_deadline_hours
        )

        if (
            arrival
            > deadline_hours
            + DEADLINE_BUFFER_HOURS
        ):
            continue

        weight_util = (
            weight
            / vehicle["capacity"]
        )

        volume_util = (
            volume
            / vehicle["volume_capacity"]
        )

        overall_util = (
            weight_util
            + volume_util
        ) / 2

        fuel = (
            distance
            / vehicle["fuel_efficiency"]
        )

        fuel_cost = (
            fuel
            * FUEL_PRICE
        )

        # Prefer:
        # 1. lower fuel cost
        # 2. better utilization
        # 3. less repositioning
        score = (
            fuel_cost
            + (
                max(
                    0,
                    TARGET_UTILIZATION
                    - overall_util
                )
                * 500
            )
            + (
                reposition_distance
                * 0.5
            )
        )

        candidates.append({

            "vehicle":
                vehicle,

            "score":
                score,

            "departure":
                departure,

            "arrival":
                arrival,

            "fuel":
                fuel,

            "fuel_cost":
                fuel_cost,

            "weight_util":
                weight_util,

            "volume_util":
                volume_util,

            "overall_util":
                overall_util

        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["score"]
    )

    return candidates[0]


# ============================================================
# BUILD CONSOLIDATION GROUPS
# ============================================================

def build_groups(
    source_transfers
):

    groups = []

    remaining = list(
        source_transfers
    )

    while remaining:

        first = remaining.pop(0)

        group = [first]

        current_weight = (
            first["weight"]
        )

        current_volume = (
            first["volume"]
        )

        current_destinations = [
            first["destination"]
        ]

        # Try adding compatible shipments.
        candidates = []

        for transfer in remaining:

            new_weight = (
                current_weight
                + transfer["weight"]
            )

            new_volume = (
                current_volume
                + transfer["volume"]
            )

            if (
                new_weight > 5000
                or new_volume > 50
            ):
                continue

            destinations = (
                current_destinations
                + [transfer["destination"]]
            )

            # Avoid excessive route complexity.
            unique_destinations = list(
                dict.fromkeys(
                    destinations
                )
            )

            if len(
                unique_destinations
            ) > MAX_STOPS:
                continue

            # Consolidation is useful when
            # destinations are compatible.
            extra_distance = (
                calculate_route_distance(
                    first["source"],
                    unique_destinations
                )
            )

            candidates.append(
                (
                    transfer,
                    extra_distance
                )
            )

        # Prefer same destination first.
        candidates.sort(
            key=lambda x: (
                x[0]["destination"]
                != first["destination"],
                x[1]
            )
        )

        for transfer, _ in candidates:

            if len(group) >= 5:
                break

            new_weight = (
                current_weight
                + transfer["weight"]
            )

            new_volume = (
                current_volume
                + transfer["volume"]
            )

            if (
                new_weight <= 5000
                and new_volume <= 50
            ):

                # Never combine urgent
                # shipments with normal shipments.
                if (
                    first["deadline_days"]
                    <= 1
                    and transfer["deadline_days"]
                    > 1
                ):
                    continue

                group.append(
                    transfer
                )

                current_weight = (
                    new_weight
                )

                current_volume = (
                    new_volume
                )

                current_destinations.append(
                    transfer["destination"]
                )

        for transfer in group[1:]:

            if transfer in remaining:
                remaining.remove(
                    transfer
                )

        groups.append(group)

    return groups


# ============================================================
# BASELINE COST
# ============================================================

baseline_cost = 0.0


for transfer in transfers:

    source = transfer["source"]

    destination = transfer[
        "destination"
    ]

    distance = (
        get_distance(
            source,
            destination
        )
        * 2
    )

    # Use the best compatible vehicle
    # purely for baseline calculation.
    compatible = [
        v
        for v in vehicles
        if (
            v["capacity"]
            >= transfer["weight"]
            and
            v["volume_capacity"]
            >= transfer["volume"]
        )
    ]

    if compatible:

        vehicle = min(
            compatible,
            key=lambda v:
                distance
                / v["fuel_efficiency"]
        )

        baseline_cost += (
            distance
            / vehicle[
                "fuel_efficiency"
            ]
            * FUEL_PRICE
        )


# ============================================================
# MAIN OPTIMIZATION
# ============================================================

print()
print("=" * 50)
print("       LOGICOMMERCE AI V9")
print(" GLOBAL FLEET + CONSOLIDATION OPTIMIZATION")
print("=" * 50)


# ============================================================
# SOURCE SUMMARY
# ============================================================

sources = sorted(
    set(
        t["source"]
        for t in transfers
    )
)

for source in sources:

    count = sum(
        1
        for t in transfers
        if t["source"] == source
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
# CREATE GROUPS BY SOURCE
# ============================================================

all_groups = []

for source in sources:

    source_transfers = [
        t
        for t in transfers
        if t["source"] == source
    ]

    groups = build_groups(
        source_transfers
    )

    all_groups.extend(
        groups
    )


# ============================================================
# FINAL PLANS
# ============================================================

plans = []

assigned_ids = set()


for group in all_groups:

    source = group[0]["source"]

    weight = sum(
        t["weight"]
        for t in group
    )

    volume = sum(
        t["volume"]
        for t in group
    )

    destinations = []

    for transfer in group:

        destination = (
            transfer["destination"]
        )

        if destination not in destinations:
            destinations.append(
                destination
            )

    # --------------------------------------------------------
    # Destination ordering
    # --------------------------------------------------------

    if len(destinations) > 1:

        remaining_destinations = (
            destinations.copy()
        )

        ordered = []

        current = source

        while remaining_destinations:

            next_destination = min(
                remaining_destinations,
                key=lambda d:
                    get_distance(
                        current,
                        d
                    )
            )

            ordered.append(
                next_destination
            )

            remaining_destinations.remove(
                next_destination
            )

            current = next_destination

        destinations = ordered

    route_distance = (
        calculate_route_distance(
            source,
            destinations
        )
    )

    route_hours = route_time(
        route_distance
    )

    earliest_deadline = min(
        t["deadline_days"]
        for t in group
    )

    deadline_hours = (
        earliest_deadline
        * 24
    )

    vehicle_choice = choose_vehicle(
        source,
        weight,
        volume,
        route_distance,
        deadline_hours
    )

    # --------------------------------------------------------
    # If deadline-compatible vehicle
    # doesn't exist, use best feasible
    # available vehicle.
    # --------------------------------------------------------

    fallback = False

    if vehicle_choice is None:

        fallback = True

        candidates = []

        for vehicle in vehicles:

            if (
                vehicle["capacity"]
                < weight
            ):
                continue

            if (
                vehicle["volume_capacity"]
                < volume
            ):
                continue

            state = vehicle_state[
                vehicle["vehicle_id"]
            ]

            reposition_distance = (
                get_distance(
                    state["current_location"],
                    source
                )
            )

            reposition_time = route_time(
                reposition_distance
            )

            departure = max(
                state["available_from"],
                reposition_time
            )

            arrival = (
                departure
                + route_hours
            )

            fuel = (
                route_distance
                / vehicle[
                    "fuel_efficiency"
                ]
            )

            fuel_cost = (
                fuel
                * FUEL_PRICE
            )

            candidates.append(
                (
                    fuel_cost,
                    vehicle,
                    departure,
                    arrival,
                    fuel
                )
            )

        if candidates:

            candidates.sort(
                key=lambda x: x[0]
            )

            (
                fuel_cost,
                vehicle,
                departure,
                arrival,
                fuel
            ) = candidates[0]

            vehicle_choice = {

                "vehicle":
                    vehicle,

                "departure":
                    departure,

                "arrival":
                    arrival,

                "fuel":
                    fuel,

                "fuel_cost":
                    fuel_cost,

                "weight_util":
                    weight
                    / vehicle[
                        "capacity"
                    ],

                "volume_util":
                    volume
                    / vehicle[
                        "volume_capacity"
                    ],

                "overall_util":
                    (
                        (
                            weight
                            / vehicle[
                                "capacity"
                            ]
                        )
                        +
                        (
                            volume
                            / vehicle[
                                "volume_capacity"
                            ]
                        )
                    ) / 2

            }

    if vehicle_choice is None:

        # This should rarely happen.
        continue

    vehicle = vehicle_choice[
        "vehicle"
    ]

    departure = vehicle_choice[
        "departure"
    ]

    arrival = vehicle_choice[
        "arrival"
    ]

    fuel = vehicle_choice[
        "fuel"
    ]

    fuel_cost = vehicle_choice[
        "fuel_cost"
    ]

    weight_util = vehicle_choice[
        "weight_util"
    ]

    volume_util = vehicle_choice[
        "volume_util"
    ]

    overall_util = vehicle_choice[
        "overall_util"
    ]

    # --------------------------------------------------------
    # Deadline status
    # --------------------------------------------------------

    if arrival <= deadline_hours:

        deadline_status = (
            "ON_TIME"
        )

    elif arrival <= (
        deadline_hours
        + DEADLINE_BUFFER_HOURS
    ):

        deadline_status = (
            "AT_RISK"
        )

    else:

        deadline_status = (
            "MISSED_DEADLINE"
        )

    # --------------------------------------------------------
    # Decision
    # --------------------------------------------------------

    if fallback:

        decision = (
            "FLEET_FALLBACK"
        )

        reason = (
            "Best feasible fleet vehicle "
            "selected after deadline-aware "
            "vehicle constraints could not "
            "be satisfied."
        )

    elif len(group) > 1:

        decision = (
            "CONSOLIDATE"
        )

        reason = (
            "Compatible shipments combined "
            "to reduce fuel consumption "
            "and dispatch cost."
        )

    else:

        decision = (
            "SEPARATE"
        )

        reason = (
            "Single shipment or consolidation "
            "would not provide additional benefit."
        )

    # --------------------------------------------------------
    # Cost comparison
    # --------------------------------------------------------

    separate_cost = 0.0

    for transfer in group:

        individual_distance = (
            get_distance(
                transfer["source"],
                transfer["destination"]
            )
            * 2
        )

        compatible = [
            v
            for v in vehicles
            if (
                v["capacity"]
                >= transfer["weight"]
                and
                v["volume_capacity"]
                >= transfer["volume"]
            )
        ]

        if compatible:

            best_vehicle = min(
                compatible,
                key=lambda v:
                    individual_distance
                    / v[
                        "fuel_efficiency"
                    ]
            )

            separate_cost += (
                individual_distance
                / best_vehicle[
                    "fuel_efficiency"
                ]
                * FUEL_PRICE
            )

    savings = (
        separate_cost
        - fuel_cost
    )

    if separate_cost > 0:

        savings_percentage = (
            savings
            / separate_cost
            * 100
        )

    else:

        savings_percentage = 0.0

    # Never claim negative savings
    # as a positive optimization.
    if savings < 0:

        savings_percentage = 0.0

    transfer_ids = ",".join(
        t["transfer_id"]
        for t in group
    )

    assigned_ids.update(
        t["transfer_id"]
        for t in group
    )

    route_text = (
        " → ".join(
            [source]
            + destinations
            + [source]
        )
    )

    plans.append({

        "decision":
            decision,

        "source":
            source,

        "destination":
            destinations[-1],

        "route":
            route_text,

        "transfer_ids":
            transfer_ids,

        "transfer_count":
            len(group),

        "vehicle_id":
            vehicle["vehicle_id"],

        "vehicle_capacity_kg":
            vehicle["capacity"],

        "vehicle_volume_m3":
            vehicle[
                "volume_capacity"
            ],

        "weight_kg":
            weight,

        "volume_m3":
            volume,

        "weight_utilization_pct":
            weight_util * 100,

        "volume_utilization_pct":
            volume_util * 100,

        "overall_utilization_pct":
            overall_util * 100,

        "fuel_efficiency_kmpl":
            vehicle[
                "fuel_efficiency"
            ],

        "distance_km":
            route_distance,

        "route_time_hours":
            route_hours,

        "departure_hour":
            departure,

        "arrival_hour":
            arrival,

        "fuel_liters":
            fuel,

        "fuel_cost":
            fuel_cost,

        "separate_cost":
            separate_cost,

        "savings":
            max(
                0.0,
                savings
            ),

        "savings_percentage":
            max(
                0.0,
                savings_percentage
            ),

        "deadline_days":
            earliest_deadline,

        "deadline_status":
            deadline_status,

        "reason":
            reason

    })

    # --------------------------------------------------------
    # Update fleet state
    # --------------------------------------------------------

    state = vehicle_state[
        vehicle["vehicle_id"]
    ]

    state[
        "available_from"
    ] = (
        departure
        + route_hours
    )

    state[
        "current_location"
    ] = source

    state[
        "trips"
    ] += 1

    state[
        "distance"
    ] += route_distance

    state[
        "fuel"
    ] += fuel


# ============================================================
# SAVE OUTPUT
# ============================================================

result_df = pd.DataFrame(
    plans
)

if not result_df.empty:

    result_df.to_csv(
        OUTPUT_FILE,
        index=False
    )


# ============================================================
# PRINT FINAL PLAN
# ============================================================

print()
print("=" * 50)
print("       FINAL LOGISTICS PLAN V9")
print("=" * 50)


for _, plan in result_df.iterrows():

    print()
    print("-" * 50)

    print(
        f"Decision: {plan['decision']}"
    )

    print(
        f"Route: {plan['route']}"
    )

    print(
        f"Transfers: "
        f"{plan['transfer_ids']}"
    )

    print(
        f"Vehicle: "
        f"{plan['vehicle_id']}"
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
        f"{plan['weight_kg']:.2f} kg"
    )

    print(
        f"Volume: "
        f"{plan['volume_m3']:.3f} m³"
    )

    print(
        f"Weight utilization: "
        f"{plan['weight_utilization_pct']:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{plan['volume_utilization_pct']:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{plan['overall_utilization_pct']:.1f}%"
    )

    print(
        f"Fuel efficiency: "
        f"{plan['fuel_efficiency_kmpl']:.2f} km/L"
    )

    print(
        f"Distance: "
        f"{plan['distance_km']:.0f} km"
    )

    print(
        f"Route time: "
        f"{plan['route_time_hours']:.2f} hours"
    )

    print(
        f"Departure: "
        f"{plan['departure_hour']:.2f} h"
    )

    print(
        f"Arrival: "
        f"{plan['arrival_hour']:.2f} h"
    )

    print(
        f"Fuel: "
        f"{plan['fuel_liters']:.2f} L"
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
        f"{plan['savings_percentage']:.1f}%"
    )

    print(
        f"Deadline: "
        f"{plan['deadline_status']}"
    )

    print(
        f"Reason: "
        f"{plan['reason']}"
    )


# ============================================================
# SUMMARY
# ============================================================

total_transfers = len(
    transfers
)

assigned_transfers = len(
    assigned_ids
)

unassigned_transfers = (
    total_transfers
    - assigned_transfers
)

routes_created = len(
    result_df
)

total_distance = (
    result_df[
        "distance_km"
    ].sum()
    if not result_df.empty
    else 0
)

total_fuel = (
    result_df[
        "fuel_liters"
    ].sum()
    if not result_df.empty
    else 0
)

optimized_cost = (
    result_df[
        "fuel_cost"
    ].sum()
    if not result_df.empty
    else 0
)

estimated_savings = max(
    0.0,
    baseline_cost
    - optimized_cost
)

if baseline_cost > 0:

    savings_percentage = (
        estimated_savings
        / baseline_cost
        * 100
    )

else:

    savings_percentage = 0.0


average_weight_util = (
    result_df[
        "weight_utilization_pct"
    ].mean()
    if not result_df.empty
    else 0
)

average_volume_util = (
    result_df[
        "volume_utilization_pct"
    ].mean()
    if not result_df.empty
    else 0
)


print()
print("=" * 50)
print("       V9 OPTIMIZATION SUMMARY")
print("=" * 50)

print(
    f"Total transfers: "
    f"{total_transfers}"
)

print(
    f"Assigned transfers: "
    f"{assigned_transfers}"
)

print(
    f"Unassigned transfers: "
    f"{unassigned_transfers}"
)

print(
    f"Routes created: "
    f"{routes_created}"
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
    f"₹{estimated_savings:.2f}"
)

print(
    f"Overall savings: "
    f"{savings_percentage:.1f}%"
)

print(
    f"Average weight utilization: "
    f"{average_weight_util:.1f}%"
)

print(
    f"Average volume utilization: "
    f"{average_volume_util:.1f}%"
)


# ============================================================
# DEADLINE SUMMARY
# ============================================================

if not result_df.empty:

    on_time = sum(
        result_df[
            "deadline_status"
        ] == "ON_TIME"
    )

    at_risk = sum(
        result_df[
            "deadline_status"
        ] == "AT_RISK"
    )

    missed = sum(
        result_df[
            "deadline_status"
        ] == "MISSED_DEADLINE"
    )

else:

    on_time = 0
    at_risk = 0
    missed = 0


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
# FLEET SUMMARY
# ============================================================

print()
print("=" * 50)
print("       VEHICLE FLEET SUMMARY")
print("=" * 50)


if not result_df.empty:

    fleet_summary = (
        result_df
        .groupby(
            "vehicle_id"
        )
        .agg(
            trips=(
                "transfer_count",
                "sum"
            ),
            distance_km=(
                "distance_km",
                "sum"
            ),
            fuel_liters=(
                "fuel_liters",
                "sum"
            )
        )
        .reset_index()
    )

    for _, row in fleet_summary.iterrows():

        print(
            f"{row['vehicle_id']} | "
            f"Transfers: "
            f"{int(row['trips'])} | "
            f"Distance: "
            f"{row['distance_km']:.0f} km | "
            f"Fuel: "
            f"{row['fuel_liters']:.2f} L"
        )


# ============================================================
# UNASSIGNED
# ============================================================

if unassigned_transfers > 0:

    print()
    print(
        "UNASSIGNED TRANSFERS:"
    )

    for transfer in transfers:

        if (
            transfer["transfer_id"]
            not in assigned_ids
        ):

            print(
                f"⚠️ "
                f"{transfer['transfer_id']}"
            )


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 50)
print("       V9 OPTIMIZATION COMPLETE")
print("=" * 50)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)