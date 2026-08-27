import pandas as pd
from itertools import combinations


# ============================================================
# LOGICOMMERCE AI
# V4 LOGISTICS OPTIMIZATION ENGINE
# ============================================================

DATA_DIR = "data"

FUEL_PRICE_PER_LITRE = 100.0
AVERAGE_SPEED_KMPH = 40.0
SERVICE_TIME_HOURS = 0.5

# Maximum travel time allowed for a single dispatch.
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


# ============================================================
# PRIORITY RANKING
# ============================================================

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
    ] = float(
        row["distance_km"]
    )


def get_distance(
    source,
    destination
):

    if source == destination:
        return 0.0

    return distance_lookup.get(
        (source, destination),
        float("inf")
    )


# ============================================================
# WAREHOUSES
# ============================================================

warehouses = sorted(
    set(
        distances["source_warehouse"]
    )
    |
    set(
        distances["destination_warehouse"]
    )
)


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(route):

    total_distance = 0.0

    for i in range(
        len(route) - 1
    ):

        distance = get_distance(
            route[i],
            route[i + 1]
        )

        if distance == float("inf"):

            return float("inf")

        total_distance += distance

    return total_distance


# ============================================================
# FIND BEST MULTI-STOP ROUTE
# ============================================================

def find_best_route(
    source,
    destinations
):

    destinations = list(
        dict.fromkeys(
            destinations
        )
    )

    if not destinations:

        return None


    # --------------------------------------------------------
    # Direct route
    # --------------------------------------------------------

    if len(destinations) == 1:

        destination = destinations[0]

        distance = get_distance(
            source,
            destination
        )

        if distance == float("inf"):

            return None

        return [
            source,
            destination
        ]


    # --------------------------------------------------------
    # For small number of stops, test permutations.
    #
    # Our dataset has only a few warehouses, so this is
    # practical and gives us a genuinely shortest route.
    # --------------------------------------------------------

    best_route = None
    best_distance = float("inf")


    from itertools import permutations


    for ordering in permutations(
        destinations
    ):

        route = [
            source
        ] + list(ordering)


        distance = (
            calculate_route_distance(
                route
            )
        )


        if distance < best_distance:

            best_distance = distance

            best_route = route


    return best_route


# ============================================================
# SHIPMENT TOTALS
# ============================================================

def shipment_totals(
    shipment_group
):

    total_weight = float(
        shipment_group[
            "weight_kg"
        ].sum()
    )

    total_volume = float(
        shipment_group[
            "volume_m3"
        ].sum()
    )

    return (
        total_weight,
        total_volume
    )


# ============================================================
# VEHICLE SELECTION
# ============================================================

def select_vehicle(
    source,
    total_weight,
    total_volume,
    route_distance
):

    candidates = vehicles[
        (
            vehicles[
                "warehouse_id"
            ]
            == source
        )
        &
        (
            vehicles[
                "available"
            ]
            == 1
        )
    ].copy()


    if candidates.empty:

        return None


    feasible = []


    for _, vehicle in (
        candidates.iterrows()
    ):

        capacity = float(
            vehicle[
                "capacity_kg"
            ]
        )

        volume_capacity = float(
            vehicle[
                "volume_capacity_m3"
            ]
        )

        fuel_efficiency = float(
            vehicle[
                "fuel_efficiency_kmpl"
            ]
        )


        if capacity <= 0:
            continue

        if volume_capacity <= 0:
            continue

        if fuel_efficiency <= 0:
            continue


        # ------------------------------------
        # Capacity checks
        # ------------------------------------

        if total_weight > capacity:

            continue


        if total_volume > volume_capacity:

            continue


        # ------------------------------------
        # Utilization
        # ------------------------------------

        weight_utilization = (
            total_weight
            / capacity
        )

        volume_utilization = (
            total_volume
            / volume_capacity
        )

        overall_utilization = (
            weight_utilization
            +
            volume_utilization
        ) / 2


        # ------------------------------------
        # Fuel
        # ------------------------------------

        fuel_litres = (
            route_distance
            / fuel_efficiency
        )


        fuel_cost = (
            fuel_litres
            * FUEL_PRICE_PER_LITRE
        )


        # ------------------------------------
        # Vehicle-size penalty
        #
        # Prefer a vehicle that is reasonably
        # matched to the shipment.
        # ------------------------------------

        unused_capacity = (
            1
            -
            overall_utilization
        )


        score = (
            fuel_cost
            +
            unused_capacity
            * 100
        )


        feasible.append({

            "vehicle_id":
                vehicle[
                    "vehicle_id"
                ],

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

            "fuel_litres":
                fuel_litres,

            "fuel_cost":
                fuel_cost,

            "score":
                score

        })


    if not feasible:

        return None


    feasible.sort(
        key=lambda x: x["score"]
    )


    return feasible[0]


# ============================================================
# DEADLINE CHECK
# ============================================================

def check_deadline(
    shipment_group,
    route_hours
):

    minimum_deadline = float(
        shipment_group[
            "deadline_days"
        ].min()
    )


    deadline_hours = (
        minimum_deadline
        * 24
    )


    if route_hours <= deadline_hours:

        return "ON_TIME"

    return "MISSED_DEADLINE"


# ============================================================
# SEPARATE COST CALCULATION
# ============================================================

def calculate_separate_cost(
    source,
    shipment_group
):

    total_cost = 0.0
    total_fuel = 0.0
    total_distance = 0.0


    for _, shipment in (
        shipment_group.iterrows()
    ):

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


        vehicle = select_vehicle(

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
            vehicle[
                "fuel_cost"
            ]
        )


        total_fuel += (
            vehicle[
                "fuel_litres"
            ]
        )


        total_distance += distance


    return {
        "cost": total_cost,
        "fuel": total_fuel,
        "distance": total_distance
    }


# ============================================================
# CONSOLIDATED PLAN
# ============================================================

def evaluate_group(
    source,
    shipment_group
):

    destinations = (
        shipment_group[
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


    distance = (
        calculate_route_distance(
            route
        )
    )


    if distance == float("inf"):

        return None


    total_weight, total_volume = (
        shipment_totals(
            shipment_group
        )
    )


    vehicle = select_vehicle(

        source,

        total_weight,

        total_volume,

        distance

    )


    if vehicle is None:

        return None


    # --------------------------------------------------------
    # Route time
    # --------------------------------------------------------

    driving_hours = (
        distance
        / AVERAGE_SPEED_KMPH
    )


    stop_count = len(
        set(destinations)
    )


    route_hours = (
        driving_hours
        +
        stop_count
        * SERVICE_TIME_HOURS
    )


    if route_hours > MAX_ROUTE_HOURS:

        return None


    deadline_status = check_deadline(

        shipment_group,

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

        "deadline_status":
            deadline_status

    }


# ============================================================
# CONSOLIDATION GROUP GENERATION
# ============================================================

def generate_groups(
    source_shipments
):

    groups = []


    # --------------------------------------------------------
    # 1. Same destination groups
    # --------------------------------------------------------

    destination_groups = (
        source_shipments
        .groupby(
            "destination_warehouse"
        )
    )


    for destination, group in (
        destination_groups
    ):

        indexes = list(
            group.index
        )


        # Full same-destination group

        groups.append(
            indexes
        )


        # ----------------------------------------------------
        # Also generate smaller combinations.
        # This helps when the complete group doesn't fit.
        # ----------------------------------------------------

        if len(indexes) > 1:

            max_size = min(
                len(indexes),
                5
            )


            for size in range(
                2,
                max_size + 1
            ):

                for combo in combinations(
                    indexes,
                    size
                ):

                    groups.append(
                        list(combo)
                    )


    # --------------------------------------------------------
    # 2. Cross-destination consolidation
    # --------------------------------------------------------

    indexes = list(
        source_shipments.index
    )


    max_group_size = min(
        len(indexes),
        4
    )


    for size in range(
        2,
        max_group_size + 1
    ):

        for combo in combinations(
            indexes,
            size
        ):

            destinations = (
                source_shipments
                .loc[
                    list(combo),
                    "destination_warehouse"
                ]
                .unique()
                .tolist()
            )


            # Don't generate extremely complex
            # multi-destination groups.

            if len(destinations) <= 3:

                groups.append(
                    list(combo)
                )


    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_groups = set()


    final_groups = []


    for group in groups:

        key = tuple(
            sorted(group)
        )


        if key in unique_groups:

            continue


        unique_groups.add(
            key
        )


        final_groups.append(
            group
        )


    return final_groups


# ============================================================
# MAIN OPTIMIZATION
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       LOGICOMMERCE AI V4"
)

print(
    " GLOBAL SHIPMENT + FUEL OPTIMIZATION"
)

print(
    "=========================================="
)


final_plans = []

assigned_ids = set()

unassigned_records = []


# ============================================================
# PROCESS EACH SOURCE WAREHOUSE
# ============================================================

for source in warehouses:

    source_shipments = transfers[
        transfers[
            "source_warehouse"
        ]
        == source
    ].copy()


    if source_shipments.empty:

        continue


    print()
    print(
        "------------------------------------------"
    )

    print(
        f"SOURCE: {source}"
    )

    print(
        f"Pending transfers: "
        f"{len(source_shipments)}"
    )


    # --------------------------------------------------------
    # Process urgent shipments first
    # --------------------------------------------------------

    source_shipments = (
        source_shipments
        .sort_values(
            [
                "priority_rank",
                "deadline_days"
            ]
        )
    )


    # --------------------------------------------------------
    # Generate candidate groups
    # --------------------------------------------------------

    groups = generate_groups(
        source_shipments
    )


    candidate_plans = []


    for group_indexes in groups:

        group = source_shipments.loc[
            group_indexes
        ]


        # Skip already assigned shipments

        if any(
            transfer_id in assigned_ids
            for transfer_id in group[
                "transfer_id"
            ]
        ):

            continue


        consolidated = evaluate_group(

            source,

            group

        )


        if consolidated is None:

            continue


        # ----------------------------------------------------
        # Separate baseline
        # ----------------------------------------------------

        separate = (
            calculate_separate_cost(
                source,
                group
            )
        )


        separate_cost = (
            separate[
                "cost"
            ]
        )


        consolidated_cost = (
            consolidated[
                "vehicle"
            ][
                "fuel_cost"
            ]
        )


        savings = (
            separate_cost
            -
            consolidated_cost
        )


        savings_percentage = 0.0


        if separate_cost > 0:

            savings_percentage = (
                savings
                /
                separate_cost
                * 100
            )


        # ----------------------------------------------------
        # Deadline protection
        # ----------------------------------------------------

        deadline_status = (
            consolidated[
                "deadline_status"
            ]
        )


        # A missed deadline is heavily penalized.

        deadline_penalty = 0


        if (
            deadline_status
            == "MISSED_DEADLINE"
        ):

            deadline_penalty = 100000


        # ----------------------------------------------------
        # Optimization score
        # ----------------------------------------------------

        utilization = (
            consolidated[
                "vehicle"
            ][
                "overall_utilization"
            ]
        )


        score = (

            consolidated_cost

            + deadline_penalty

            - savings * 0.50

            - utilization * 300

        )


        candidate_plans.append({

            "group":
                group,

            "consolidated":
                consolidated,

            "separate":
                separate,

            "separate_cost":
                separate_cost,

            "consolidated_cost":
                consolidated_cost,

            "savings":
                savings,

            "savings_percentage":
                savings_percentage,

            "score":
                score

        })


    # --------------------------------------------------------
    # Choose plans repeatedly
    # --------------------------------------------------------

    while True:

        available_candidates = []


        for candidate in candidate_plans:

            group = candidate[
                "group"
            ]


            ids = set(
                group[
                    "transfer_id"
                ]
            )


            if ids & assigned_ids:

                continue


            available_candidates.append(
                candidate
            )


        if not available_candidates:

            break


        available_candidates.sort(
            key=lambda x: (
                x["score"],
                -x[
                    "consolidated"
                ][
                    "vehicle"
                ][
                    "overall_utilization"
                ]
            )
        )


        best = (
            available_candidates[0]
        )


        group = best[
            "group"
        ]


        # ----------------------------------------------------
        # Don't select a consolidation that causes a deadline
        # miss when an alternative feasible option exists.
        # ----------------------------------------------------

        if (
            best[
                "consolidated"
            ][
                "deadline_status"
            ]
            == "MISSED_DEADLINE"
        ):

            # Look for an on-time alternative.

            on_time = [

                candidate

                for candidate
                in available_candidates

                if candidate[
                    "consolidated"
                ][
                    "deadline_status"
                ]
                == "ON_TIME"

            ]


            if on_time:

                on_time.sort(
                    key=lambda x:
                    x["score"]
                )

                best = on_time[0]

                group = best[
                    "group"
                ]


        # ----------------------------------------------------
        # Create final plan
        # ----------------------------------------------------

        consolidated = best[
            "consolidated"
        ]


        vehicle = consolidated[
            "vehicle"
        ]


        transfer_ids = (
            group[
                "transfer_id"
            ]
            .astype(str)
            .tolist()
        )


        if len(transfer_ids) > 1:

            decision = (
                "CONSOLIDATE"
            )

            reason = (
                "Compatible shipments "
                "combined to reduce "
                "fuel and dispatch cost."
            )

        else:

            decision = (
                "SEPARATE"
            )

            reason = (
                "Single shipment dispatch."
            )


        # If consolidation produces no savings

        if (
            len(transfer_ids) > 1
            and
            best[
                "savings"
            ] <= 0
        ):

            decision = (
                "SEPARATE"
            )

            reason = (
                "Consolidation does not "
                "reduce estimated fuel cost."
            )


        # Deadline protection

        if (
            consolidated[
                "deadline_status"
            ]
            == "MISSED_DEADLINE"
        ):

            decision = (
                "SEPARATE"
            )

            reason = (
                "Consolidation would "
                "miss the shipment deadline."
            )


        final_plans.append({

            "source_warehouse":
                source,

            "destination_route":
                " → ".join(
                    consolidated[
                        "route"
                    ]
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
                vehicle[
                    "vehicle_id"
                ],

            "weight_kg":
                consolidated[
                    "weight"
                ],

            "volume_m3":
                consolidated[
                    "volume"
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

            "distance_km":
                consolidated[
                    "distance"
                ],

            "route_hours":
                consolidated[
                    "route_hours"
                ],

            "fuel_litres":
                vehicle[
                    "fuel_litres"
                ],

            "fuel_cost":
                best[
                    "consolidated_cost"
                ],

            "separate_cost":
                best[
                    "separate_cost"
                ],

            "savings":
                best[
                    "savings"
                ],

            "savings_percentage":
                best[
                    "savings_percentage"
                ],

            "deadline_status":
                consolidated[
                    "deadline_status"
                ],

            "decision":
                decision,

            "reason":
                reason

        })


        for transfer_id in (
            transfer_ids
        ):

            assigned_ids.add(
                transfer_id
            )


# ============================================================
# IDENTIFY UNASSIGNED
# ============================================================

all_ids = set(
    transfers[
        "transfer_id"
    ]
)


unassigned_ids = (
    all_ids
    -
    assigned_ids
)


# ============================================================
# SAVE RESULTS
# ============================================================

result_df = pd.DataFrame(
    final_plans
)


output_file = (
    f"{DATA_DIR}/logistics_optimization_v4.csv"
)


result_df.to_csv(
    output_file,
    index=False
)


# ============================================================
# DISPLAY FINAL PLAN
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       FINAL LOGISTICS PLAN V4"
)

print(
    "=========================================="
)


if result_df.empty:

    print(
        "No feasible logistics plans found."
    )

else:

    for _, row in (
        result_df.iterrows()
    ):

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
            f"{row['destination_route']}"
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
            f"Weight: "
            f"{row['weight_kg']:.2f} kg"
        )

        print(
            f"Volume: "
            f"{row['volume_m3']:.3f} m³"
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
            f"Distance: "
            f"{row['distance_km']:.0f} km"
        )

        print(
            f"Route time: "
            f"{row['route_hours']:.2f} hours"
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

print()
print(
    "=========================================="
)

print(
    "       V4 OPTIMIZATION SUMMARY"
)

print(
    "=========================================="
)


print(
    f"Total transfers: "
    f"{len(all_ids)}"
)


print(
    f"Assigned transfers: "
    f"{len(assigned_ids)}"
)


print(
    f"Unassigned transfers: "
    f"{len(unassigned_ids)}"
)


if not result_df.empty:

    print(
        f"Routes created: "
        f"{len(result_df)}"
    )

    print(
        f"Total distance: "
        f"{result_df['distance_km'].sum():.2f} km"
    )

    print(
        f"Total fuel: "
        f"{result_df['fuel_litres'].sum():.2f} L"
    )

    print(
        f"Optimized fuel cost: "
        f"₹{result_df['fuel_cost'].sum():.2f}"
    )

    print(
        f"Separate baseline cost: "
        f"₹{result_df['separate_cost'].sum():.2f}"
    )

    print(
        f"Estimated savings: "
        f"₹{result_df['savings'].sum():.2f}"
    )

    baseline = (
        result_df[
            "separate_cost"
        ].sum()
    )

    savings = (
        result_df[
            "savings"
        ].sum()
    )


    if baseline > 0:

        print(
            f"Overall savings: "
            f"{(savings / baseline) * 100:.1f}%"
        )


    print(
        f"Average weight utilization: "
        f"{result_df['weight_utilization'].mean() * 100:.1f}%"
    )

    print(
        f"Average volume utilization: "
        f"{result_df['volume_utilization'].mean() * 100:.1f}%"
    )


# ============================================================
# UNASSIGNED REASONS
# ============================================================

if unassigned_ids:

    print()
    print(
        "=========================================="
    )

    print(
        "       UNASSIGNED TRANSFERS"
    )

    print(
        "=========================================="
    )


    for transfer_id in sorted(
        unassigned_ids
    ):

        transfer = transfers[
            transfers[
                "transfer_id"
            ]
            == transfer_id
        ]


        if transfer.empty:

            continue


        row = transfer.iloc[0]


        source = row[
            "source_warehouse"
        ]

        destination = row[
            "destination_warehouse"
        ]

        weight = row[
            "weight_kg"
        ]

        volume = row[
            "volume_m3"
        ]


        available_vehicles = vehicles[
            (
                vehicles[
                    "warehouse_id"
                ]
                == source
            )
            &
            (
                vehicles[
                    "available"
                ]
                == 1
            )
        ]


        if available_vehicles.empty:

            reason = (
                "No available vehicle "
                "at source warehouse."
            )

        elif not any(
            (
                available_vehicles[
                    "capacity_kg"
                ]
                >= weight
            )
            &
            (
                available_vehicles[
                    "volume_capacity_m3"
                ]
                >= volume
            )
        ):

            reason = (
                "No available vehicle "
                "has sufficient capacity "
                "or volume."
            )

        else:

            reason = (
                "No feasible route/group "
                "was selected by the "
                "optimization engine."
            )


        print(
            f"{transfer_id}: {source} → "
            f"{destination} | {reason}"
        )


print()
print(
    "=========================================="
)

print(
    "V4 OPTIMIZATION COMPLETE"
)

print(
    "Saved to:"
)

print(
    output_file
)