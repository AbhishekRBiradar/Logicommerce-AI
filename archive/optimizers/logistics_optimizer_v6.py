import pandas as pd
from itertools import combinations, permutations


# ============================================================
# LOGICOMMERCE AI V6
# GLOBAL SHIPMENT + VEHICLE UTILIZATION + FUEL OPTIMIZATION
# ============================================================

DATA_DIR = "data"

FUEL_PRICE_PER_LITRE = 100.0
AVERAGE_SPEED_KMPH = 40.0
SERVICE_TIME_HOURS = 0.5
MAX_ROUTE_HOURS = 24.0


# ============================================================
# LOAD DATA
# ============================================================

print("Loading transfer requests...")
transfers = pd.read_csv(
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


# ============================================================
# CLEAN DATA
# ============================================================

numeric_transfer_columns = [
    "quantity",
    "weight_kg",
    "volume_m3",
    "deadline_days"
]

for column in numeric_transfer_columns:
    transfers[column] = pd.to_numeric(
        transfers[column],
        errors="coerce"
    ).fillna(0)


numeric_vehicle_columns = [
    "capacity_kg",
    "volume_capacity_m3",
    "fuel_efficiency_kmpl",
    "available"
]

for column in numeric_vehicle_columns:
    vehicles[column] = pd.to_numeric(
        vehicles[column],
        errors="coerce"
    ).fillna(0)


priority_rank = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2
}

transfers["priority_rank"] = (
    transfers["priority"]
    .map(priority_rank)
    .fillna(3)
)


# ============================================================
# DISTANCE LOOKUP
# ============================================================

distance_lookup = {}

for _, row in distances.iterrows():

    source = row["source_warehouse"]
    destination = row["destination_warehouse"]

    distance_lookup[
        (source, destination)
    ] = float(row["distance_km"])


def get_distance(source, destination):

    if source == destination:
        return 0.0

    return distance_lookup.get(
        (source, destination),
        float("inf")
    )


# ============================================================
# ROUTE DISTANCE
# ============================================================

def route_distance(route):

    total = 0.0

    for i in range(len(route) - 1):

        distance = get_distance(
            route[i],
            route[i + 1]
        )

        if distance == float("inf"):
            return float("inf")

        total += distance

    return total


# ============================================================
# BEST ROUTE
# ============================================================

def find_best_route(source, destinations):

    destinations = list(
        dict.fromkeys(destinations)
    )

    if not destinations:
        return None

    if len(destinations) == 1:

        return [
            source,
            destinations[0]
        ]

    best_route = None
    best_distance = float("inf")

    for ordering in permutations(destinations):

        route = [
            source
        ] + list(ordering)

        distance = route_distance(
            route
        )

        if distance < best_distance:

            best_distance = distance
            best_route = route

    return best_route


# ============================================================
# VEHICLE SELECTION V6
# ============================================================

def select_best_vehicle(
    source,
    weight,
    volume,
    distance
):

    all_source_vehicles = vehicles[
        vehicles["warehouse_id"] == source
    ].copy()

    available_vehicles = all_source_vehicles[
        all_source_vehicles["available"] == 1
    ].copy()


    # --------------------------------------------------------
    # No vehicles at source
    # --------------------------------------------------------

    if available_vehicles.empty:

        return None


    feasible = []

    rejected_capacity = 0
    rejected_volume = 0


    for _, vehicle in available_vehicles.iterrows():

        capacity = float(
            vehicle["capacity_kg"]
        )

        volume_capacity = float(
            vehicle["volume_capacity_m3"]
        )

        efficiency = float(
            vehicle["fuel_efficiency_kmpl"]
        )


        if capacity <= 0:
            continue

        if volume_capacity <= 0:
            continue

        if efficiency <= 0:
            continue


        # ----------------------------------------------------
        # Weight constraint
        # ----------------------------------------------------

        if weight > capacity:

            rejected_capacity += 1
            continue


        # ----------------------------------------------------
        # Volume constraint
        # ----------------------------------------------------

        if volume > volume_capacity:

            rejected_volume += 1
            continue


        # ----------------------------------------------------
        # Utilization
        # ----------------------------------------------------

        weight_utilization = (
            weight / capacity
        )

        volume_utilization = (
            volume / volume_capacity
        )

        overall_utilization = (
            weight_utilization
            +
            volume_utilization
        ) / 2


        # ----------------------------------------------------
        # Fuel
        # ----------------------------------------------------

        fuel_litres = (
            distance / efficiency
        )

        fuel_cost = (
            fuel_litres
            * FUEL_PRICE_PER_LITRE
        )


        # ----------------------------------------------------
        # V6 BEST-FIT SCORE
        #
        # Lower score = better
        # ----------------------------------------------------

        unused_weight = (
            1
            -
            weight_utilization
        )

        unused_volume = (
            1
            -
            volume_utilization
        )


        score = (

            fuel_cost * 0.45

            +

            unused_volume
            * 1000
            * 0.25

            +

            unused_weight
            * 1000
            * 0.15

            +

            (1 / efficiency)
            * 100
            * 0.10

            +

            (capacity / max(weight, 1))
            * 0.05

        )


        feasible.append({

            "vehicle_id":
                vehicle["vehicle_id"],

            "capacity_kg":
                capacity,

            "volume_capacity_m3":
                volume_capacity,

            "fuel_efficiency_kmpl":
                efficiency,

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

        })


    # --------------------------------------------------------
    # No feasible vehicle
    # --------------------------------------------------------

    if not feasible:

        return None


    feasible.sort(
        key=lambda x: x["score"]
    )


    best = feasible[0]


    # --------------------------------------------------------
    # Vehicle selection explanation
    # --------------------------------------------------------

    capacity_ratio = (
        best["capacity_kg"]
        /
        max(weight, 1)
    )

    volume_ratio = (
        best["volume_capacity_m3"]
        /
        max(volume, 0.001)
    )


    # Find whether this is actually a small/best-fit vehicle
    minimum_capacity = min(
        item["capacity_kg"]
        for item in feasible
    )

    minimum_volume = min(
        item["volume_capacity_m3"]
        for item in feasible
    )


    if (
        best["capacity_kg"]
        == minimum_capacity
        and
        best["volume_capacity_m3"]
        == minimum_volume
    ):

        selection_reason = (
            "BEST_FIT_VEHICLE"
        )

    elif (
        best["overall_utilization"]
        >= 0.50
    ):

        selection_reason = (
            "HIGH_UTILIZATION_VEHICLE"
        )

    elif (
        best["fuel_cost"]
        ==
        min(
            item["fuel_cost"]
            for item in feasible
        )
    ):

        selection_reason = (
            "LOWEST_FUEL_COST"
        )

    else:

        selection_reason = (
            "BEST_BALANCED_VEHICLE"
        )


    # --------------------------------------------------------
    # Detect oversized fallback
    # --------------------------------------------------------

    if (
        best["overall_utilization"]
        < 0.15
        and
        len(feasible) > 1
    ):

        selection_reason = (
            "LARGE_VEHICLE_FALLBACK"
        )


    best["selection_reason"] = (
        selection_reason
    )

    best["capacity_ratio"] = (
        capacity_ratio
    )

    best["volume_ratio"] = (
        volume_ratio
    )

    best["feasible_vehicle_count"] = (
        len(feasible)
    )

    best["rejected_weight_count"] = (
        rejected_capacity
    )

    best["rejected_volume_count"] = (
        rejected_volume
    )


    return best


# ============================================================
# DEADLINE
# ============================================================

def check_deadline(
    group,
    route_hours
):

    deadline_days = float(
        group["deadline_days"].min()
    )

    deadline_hours = (
        deadline_days * 24
    )

    if route_hours <= deadline_hours:

        return "ON_TIME"

    return "MISSED_DEADLINE"


# ============================================================
# SEPARATE BASELINE
# ============================================================

def separate_baseline(
    source,
    group
):

    total_cost = 0.0
    total_fuel = 0.0
    total_distance = 0.0


    for _, shipment in group.iterrows():

        destination = (
            shipment[
                "destination_warehouse"
            ]
        )

        distance = get_distance(
            source,
            destination
        )

        if distance == float("inf"):
            continue


        vehicle = select_best_vehicle(

            source,

            float(
                shipment[
                    "weight_kg"
                ]
            ),

            float(
                shipment[
                    "volume_m3"
                ]
            ),

            distance

        )


        if vehicle is None:
            continue


        total_cost += (
            vehicle["fuel_cost"]
        )

        total_fuel += (
            vehicle["fuel_litres"]
        )

        total_distance += (
            distance
        )


    return {

        "cost":
            total_cost,

        "fuel":
            total_fuel,

        "distance":
            total_distance

    }


# ============================================================
# GROUP EVALUATION
# ============================================================

def evaluate_group(
    source,
    group
):

    destinations = (
        group[
            "destination_warehouse"
        ]
        .tolist()
    )


    route = find_best_route(
        source,
        destinations
    )


    if route is None:
        return None


    distance = route_distance(
        route
    )


    if distance == float("inf"):
        return None


    total_weight = float(
        group[
            "weight_kg"
        ].sum()
    )


    total_volume = float(
        group[
            "volume_m3"
        ].sum()
    )


    vehicle = select_best_vehicle(

        source,

        total_weight,

        total_volume,

        distance

    )


    if vehicle is None:
        return None


    driving_hours = (
        distance
        /
        AVERAGE_SPEED_KMPH
    )


    unique_destinations = len(
        set(destinations)
    )


    route_hours = (
        driving_hours
        +
        unique_destinations
        * SERVICE_TIME_HOURS
    )


    if route_hours > MAX_ROUTE_HOURS:
        return None


    deadline = check_deadline(
        group,
        route_hours
    )


    return {

        "route":
            route,

        "distance":
            distance,

        "route_hours":
            route_hours,

        "weight":
            total_weight,

        "volume":
            total_volume,

        "vehicle":
            vehicle,

        "deadline":
            deadline

    }


# ============================================================
# GENERATE GROUPS
# ============================================================

def generate_groups(group):

    indexes = list(
        group.index
    )

    result = []


    # --------------------------------------------------------
    # Same destination groups
    # --------------------------------------------------------

    for destination, destination_group in (
        group.groupby(
            "destination_warehouse"
        )
    ):

        destination_indexes = list(
            destination_group.index
        )


        result.append(
            destination_indexes
        )


        max_size = min(
            len(destination_indexes),
            5
        )


        for size in range(
            2,
            max_size + 1
        ):

            for combo in combinations(
                destination_indexes,
                size
            ):

                result.append(
                    list(combo)
                )


    # --------------------------------------------------------
    # Cross destination groups
    # --------------------------------------------------------

    max_size = min(
        len(indexes),
        4
    )


    for size in range(
        2,
        max_size + 1
    ):

        for combo in combinations(
            indexes,
            size
        ):

            destinations = (
                group.loc[
                    list(combo),
                    "destination_warehouse"
                ]
                .unique()
            )


            if len(destinations) <= 3:

                result.append(
                    list(combo)
                )


    # --------------------------------------------------------
    # Remove duplicate groups
    # --------------------------------------------------------

    unique = set()
    final = []


    for item in result:

        key = tuple(
            sorted(item)
        )


        if key in unique:
            continue


        unique.add(key)

        final.append(
            item
        )


    return final


# ============================================================
# HEADER
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       LOGICOMMERCE AI V6"
)

print(
    " VEHICLE FIT + FUEL + DEADLINE OPTIMIZER"
)

print(
    "=========================================="
)


final_plans = []
assigned = set()


# ============================================================
# PROCESS WAREHOUSES
# ============================================================

for source in sorted(
    transfers[
        "source_warehouse"
    ].unique()
):

    source_data = transfers[
        transfers[
            "source_warehouse"
        ]
        == source
    ].copy()


    source_data = (
        source_data
        .sort_values(
            [
                "priority_rank",
                "deadline_days"
            ]
        )
    )


    print()
    print(
        "------------------------------------------"
    )

    print(
        f"SOURCE: {source}"
    )

    print(
        f"Transfers: "
        f"{len(source_data)}"
    )


    candidate_groups = (
        generate_groups(
            source_data
        )
    )


    while True:

        candidates = []


        for indexes in candidate_groups:

            group = source_data.loc[
                indexes
            ]


            transfer_ids = set(
                group[
                    "transfer_id"
                ]
            )


            if transfer_ids & assigned:
                continue


            plan = evaluate_group(
                source,
                group
            )


            if plan is None:
                continue


            baseline = separate_baseline(
                source,
                group
            )


            optimized_cost = (
                plan[
                    "vehicle"
                ][
                    "fuel_cost"
                ]
            )


            separate_cost = (
                baseline[
                    "cost"
                ]
            )


            savings = (
                separate_cost
                -
                optimized_cost
            )


            savings_percentage = 0.0


            if separate_cost > 0:

                savings_percentage = (
                    savings
                    /
                    separate_cost
                    * 100
                )


            utilization = (
                plan[
                    "vehicle"
                ][
                    "overall_utilization"
                ]
            )


            # ------------------------------------------------
            # V6 decision score
            # ------------------------------------------------

            deadline_penalty = 0

            if (
                plan["deadline"]
                == "MISSED_DEADLINE"
            ):

                deadline_penalty = 100000


            consolidation_bonus = (
                len(transfer_ids)
                * 500
            )


            utilization_bonus = (
                utilization
                * 500
            )


            score = (

                optimized_cost

                +

                deadline_penalty

                -

                savings * 0.60

                -

                utilization_bonus

                -

                consolidation_bonus

            )


            candidates.append({

                "group":
                    group,

                "plan":
                    plan,

                "baseline":
                    baseline,

                "separate_cost":
                    separate_cost,

                "optimized_cost":
                    optimized_cost,

                "savings":
                    savings,

                "savings_percentage":
                    savings_percentage,

                "score":
                    score

            })


        if not candidates:
            break


        candidates.sort(
            key=lambda x:
            x["score"]
        )


        # ----------------------------------------------------
        # Prefer ON-TIME solution
        # ----------------------------------------------------

        on_time = [

            candidate

            for candidate in candidates

            if candidate[
                "plan"
            ][
                "deadline"
            ]
            == "ON_TIME"

        ]


        if on_time:

            on_time.sort(
                key=lambda x:
                x["score"]
            )

            best = on_time[0]

        else:

            best = candidates[0]


        group = best[
            "group"
        ]

        plan = best[
            "plan"
        ]

        vehicle = plan[
            "vehicle"
        ]


        transfer_ids = (
            group[
                "transfer_id"
            ]
            .astype(str)
            .tolist()
        )


        # ----------------------------------------------------
        # Decision
        # ----------------------------------------------------

        if len(
            transfer_ids
        ) > 1:

            decision = (
                "CONSOLIDATE"
            )

            reason = (
                "Compatible shipments "
                "combined using a "
                "capacity-matched vehicle."
            )

        else:

            decision = (
                "SEPARATE"
            )

            reason = (
                "Single shipment dispatch."
            )


        if (
            len(transfer_ids) > 1
            and
            best["savings"] <= 0
        ):

            decision = (
                "SEPARATE"
            )

            reason = (
                "Consolidation does not "
                "reduce fuel cost."
            )


        if (
            plan["deadline"]
            == "MISSED_DEADLINE"
        ):

            decision = (
                "SEPARATE"
            )

            reason = (
                "Deadline protection."
            )


        # ----------------------------------------------------
        # Add V6 vehicle reasoning
        # ----------------------------------------------------

        vehicle_reason = (
            vehicle[
                "selection_reason"
            ]
        )


        if vehicle_reason == (
            "LARGE_VEHICLE_FALLBACK"
        ):

            reason += (
                " Large vehicle selected "
                "because smaller feasible "
                "vehicles were not available."
            )


        elif vehicle_reason == (
            "BEST_FIT_VEHICLE"
        ):

            reason += (
                " Best-fit vehicle selected "
                "to improve utilization."
            )


        elif vehicle_reason == (
            "HIGH_UTILIZATION_VEHICLE"
        ):

            reason += (
                " High-utilization vehicle "
                "selected."
            )


        elif vehicle_reason == (
            "LOWEST_FUEL_COST"
        ):

            reason += (
                " Lowest fuel-cost vehicle "
                "selected."
            )


        # ----------------------------------------------------
        # Save result
        # ----------------------------------------------------

        final_plans.append({

            "source_warehouse":
                source,

            "route":
                " → ".join(
                    plan["route"]
                ),

            "transfer_ids":
                ",".join(
                    transfer_ids
                ),

            "shipment_count":
                len(
                    transfer_ids
                ),

            "vehicle_id":
                vehicle["vehicle_id"],

            "vehicle_selection_reason":
                vehicle_reason,

            "shipment_weight_kg":
                plan["weight"],

            "shipment_volume_m3":
                plan["volume"],

            "vehicle_capacity_kg":
                vehicle["capacity_kg"],

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

            "fuel_efficiency_kmpl":
                vehicle[
                    "fuel_efficiency_kmpl"
                ],

            "distance_km":
                plan["distance"],

            "route_hours":
                plan["route_hours"],

            "fuel_litres":
                vehicle[
                    "fuel_litres"
                ],

            "fuel_cost":
                best[
                    "optimized_cost"
                ],

            "separate_cost":
                best[
                    "separate_cost"
                ],

            "savings":
                best["savings"],

            "savings_percentage":
                best[
                    "savings_percentage"
                ],

            "deadline_status":
                plan["deadline"],

            "decision":
                decision,

            "reason":
                reason

        })


        for transfer_id in transfer_ids:

            assigned.add(
                transfer_id
            )


# ============================================================
# SAVE RESULTS
# ============================================================

result = pd.DataFrame(
    final_plans
)


output_file = (
    f"{DATA_DIR}/logistics_optimization_v6.csv"
)


result.to_csv(
    output_file,
    index=False
)


# ============================================================
# DISPLAY RESULTS
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       FINAL V6 OPTIMIZATION"
)

print(
    "=========================================="
)


for _, row in result.iterrows():

    print()
    print(
        "------------------------------------------"
    )

    print(
        f"Decision: "
        f"{row['decision']}"
    )

    print(
        f"Route: "
        f"{row['route']}"
    )

    print(
        f"Transfers: "
        f"{row['transfer_ids']}"
    )

    print(
        f"Vehicle: "
        f"{row['vehicle_id']}"
    )

    print(
        f"Vehicle selection: "
        f"{row['vehicle_selection_reason']}"
    )

    print(
        f"Weight: "
        f"{row['shipment_weight_kg']:.2f} kg"
    )

    print(
        f"Volume: "
        f"{row['shipment_volume_m3']:.3f} m³"
    )

    print(
        f"Vehicle capacity: "
        f"{row['vehicle_capacity_kg']:.0f} kg"
    )

    print(
        f"Vehicle volume: "
        f"{row['vehicle_volume_capacity_m3']:.1f} m³"
    )

    print(
        f"Weight utilization: "
        f"{row['weight_utilization'] * 100:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{row['volume_utilization'] * 100:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{row['overall_utilization'] * 100:.1f}%"
    )

    print(
        f"Fuel efficiency: "
        f"{row['fuel_efficiency_kmpl']:.2f} km/L"
    )

    print(
        f"Distance: "
        f"{row['distance_km']:.0f} km"
    )

    print(
        f"Fuel: "
        f"{row['fuel_litres']:.2f} L"
    )

    print(
        f"Separate cost: "
        f"₹{row['separate_cost']:.2f}"
    )

    print(
        f"Optimized cost: "
        f"₹{row['fuel_cost']:.2f}"
    )

    print(
        f"Savings: "
        f"₹{row['savings']:.2f}"
    )

    print(
        f"Savings percentage: "
        f"{row['savings_percentage']:.1f}%"
    )

    print(
        f"Deadline: "
        f"{row['deadline_status']}"
    )

    print(
        f"Reason: "
        f"{row['reason']}"
    )


# ============================================================
# SUMMARY
# ============================================================

all_transfers = set(
    transfers[
        "transfer_id"
    ]
)


unassigned = (
    all_transfers
    -
    assigned
)


print()
print(
    "=========================================="
)

print(
    "       V6 OPTIMIZATION SUMMARY"
)

print(
    "=========================================="
)


print(
    f"Total transfers: "
    f"{len(all_transfers)}"
)

print(
    f"Assigned transfers: "
    f"{len(assigned)}"
)

print(
    f"Unassigned transfers: "
    f"{len(unassigned)}"
)

print(
    f"Routes created: "
    f"{len(result)}"
)


if not result.empty:

    total_distance = (
        result[
            "distance_km"
        ].sum()
    )

    total_fuel = (
        result[
            "fuel_litres"
        ].sum()
    )

    optimized_cost = (
        result[
            "fuel_cost"
        ].sum()
    )

    separate_cost = (
        result[
            "separate_cost"
        ].sum()
    )

    savings = (
        result[
            "savings"
        ].sum()
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
        f"Separate baseline: "
        f"₹{separate_cost:.2f}"
    )

    print(
        f"Estimated savings: "
        f"₹{savings:.2f}"
    )


    if separate_cost > 0:

        print(
            f"Overall savings: "
            f"{(savings / separate_cost) * 100:.1f}%"
        )


    print(
        f"Average weight utilization: "
        f"{result['weight_utilization'].mean() * 100:.1f}%"
    )

    print(
        f"Average volume utilization: "
        f"{result['volume_utilization'].mean() * 100:.1f}%"
    )


if unassigned:

    print()
    print(
        "UNASSIGNED TRANSFERS:"
    )

    for transfer_id in sorted(
        unassigned
    ):

        print(
            f"⚠️ {transfer_id}"
        )


print()
print(
    "=========================================="
)

print(
    "V6 OPTIMIZATION COMPLETE"
)

print(
    "Saved to:"
)

print(
    output_file
)