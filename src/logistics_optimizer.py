import os
import pandas as pd


# ============================================================
# LOGICOMMERCE AI
# FINAL LOGISTICS OPTIMIZER
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
    "logistics_optimization_v11.csv"
)

FUEL_PRICE_PER_LITRE = 100.0
AVERAGE_SPEED_KMPH = 40.0
SERVICE_TIME_HOURS = 0.25
DEADLINE_BUFFER_HOURS = 2.0


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fuel_required(distance_km, efficiency_kmpl):
    if efficiency_kmpl <= 0:
        return 0.0
    return distance_km / efficiency_kmpl


def fuel_cost(distance_km, efficiency_kmpl):
    return (
        fuel_required(
            distance_km,
            efficiency_kmpl
        )
        * FUEL_PRICE_PER_LITRE
    )


def route_time(distance_km):
    if distance_km <= 0:
        return 0.0

    return (
        distance_km / AVERAGE_SPEED_KMPH
        + SERVICE_TIME_HOURS
    )


def get_urgency(deadline_days):

    deadline_days = safe_float(
        deadline_days
    )

    if deadline_days <= 1:
        return "URGENT"

    if deadline_days <= 2:
        return "SOON"

    return "NORMAL"


def get_deadline_status(
    travel_hours,
    deadline_days
):

    deadline_hours = (
        safe_float(deadline_days)
        * 24
    )

    if travel_hours <= (
        deadline_hours
        - DEADLINE_BUFFER_HOURS
    ):
        return "ON_TIME"

    if travel_hours <= deadline_hours:
        return "AT_RISK"

    return "MISSED_DEADLINE"


# ============================================================
# DISTANCE MAP
# ============================================================

def build_distance_map(distance_df):

    distance_map = {}

    for _, row in distance_df.iterrows():

        source = str(
            row["source_warehouse"]
        ).strip()

        destination = str(
            row["destination_warehouse"]
        ).strip()

        distance = safe_float(
            row["distance_km"]
        )

        distance_map[
            (source, destination)
        ] = distance

        distance_map[
            (destination, source)
        ] = distance

    return distance_map


def get_distance(
    distance_map,
    source,
    destination
):

    if source == destination:
        return 0.0

    return distance_map.get(
        (source, destination),
        0.0
    )


# ============================================================
# UTILIZATION
# ============================================================

def calculate_utilization(
    weight,
    volume,
    vehicle
):

    capacity = safe_float(
        vehicle["capacity_kg"]
    )

    volume_capacity = safe_float(
        vehicle["volume_capacity_m3"]
    )

    weight_utilization = (
        weight / capacity * 100
        if capacity > 0
        else 0.0
    )

    volume_utilization = (
        volume / volume_capacity * 100
        if volume_capacity > 0
        else 0.0
    )

    overall_utilization = (
        weight_utilization
        + volume_utilization
    ) / 2

    return (
        weight_utilization,
        volume_utilization,
        overall_utilization
    )


# ============================================================
# VEHICLE SELECTION
# ============================================================

def find_best_vehicle(
    vehicles_df,
    source,
    weight,
    volume,
    distance
):

    candidates = []

    for _, vehicle in vehicles_df.iterrows():

        # Vehicle must belong to source warehouse.
        if str(
            vehicle["warehouse_id"]
        ) != str(source):

            continue

        # IMPORTANT:
        # vehicle is a Series, so check
        # vehicles_df.columns instead of
        # vehicle.columns.
        if "available" in vehicles_df.columns:

            if safe_float(
                vehicle["available"]
            ) != 1:

                continue

        capacity = safe_float(
            vehicle["capacity_kg"]
        )

        volume_capacity = safe_float(
            vehicle[
                "volume_capacity_m3"
            ]
        )

        efficiency = safe_float(
            vehicle[
                "fuel_efficiency_kmpl"
            ]
        )

        # Hard capacity constraints.
        if weight > capacity:
            continue

        if volume > volume_capacity:
            continue

        if efficiency <= 0:
            continue

        fuel = fuel_required(
            distance,
            efficiency
        )

        fuel_cost_value = (
            fuel
            * FUEL_PRICE_PER_LITRE
        )

        (
            weight_utilization,
            volume_utilization,
            overall_utilization
        ) = calculate_utilization(
            weight,
            volume,
            vehicle
        )

        # Lower cost is primary.
        # Better utilization is a small
        # secondary preference.
        score = (
            fuel_cost_value
            - overall_utilization
        )

        candidates.append({

            "vehicle_id":
                str(
                    vehicle["vehicle_id"]
                ),

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

            "fuel":
                fuel,

            "fuel_cost":
                fuel_cost_value,

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
# DIRECT ROUTE
# ============================================================

def make_direct_route(
    source,
    destination,
    distance_map
):

    one_way_distance = get_distance(
        distance_map,
        source,
        destination
    )

    round_trip_distance = (
        one_way_distance * 2
    )

    route = [
        source,
        destination,
        source
    ]

    return (
        route,
        round_trip_distance
    )


# ============================================================
# CONSOLIDATED GROUP EVALUATION
# ============================================================

def evaluate_group(
    rows,
    source,
    destination,
    vehicles_df,
    distance_map,
    vehicle_next_available
):

    transfer_ids = [
        str(row["transfer_id"])
        for _, row in rows.iterrows()
    ]

    weight = (
        rows["weight_kg"]
        .apply(safe_float)
        .sum()
    )

    volume = (
        rows["volume_m3"]
        .apply(safe_float)
        .sum()
    )

    earliest_deadline = (
        rows["deadline_days"]
        .apply(safe_float)
        .min()
    )

    urgency = get_urgency(
        earliest_deadline
    )

    # --------------------------------------------------------
    # Direct round-trip route.
    # --------------------------------------------------------

    route, distance = make_direct_route(
        source,
        destination,
        distance_map
    )

    # --------------------------------------------------------
    # Best vehicle for the group.
    # --------------------------------------------------------

    vehicle = find_best_vehicle(
        vehicles_df,
        source,
        weight,
        volume,
        distance
    )

    return (
        transfer_ids,
        weight,
        volume,
        earliest_deadline,
        urgency,
        route,
        distance,
        vehicle
    )


# ============================================================
# LOAD DATA
# ============================================================

print("Loading transfer requests...")

transfers_df = pd.read_csv(
    TRANSFER_FILE
)

print("Loading vehicles...")

vehicles_df = pd.read_csv(
    VEHICLE_FILE
)

print("Loading warehouse distances...")

distance_df = pd.read_csv(
    DISTANCE_FILE
)


# ============================================================
# NORMALIZE COLUMNS
# ============================================================

transfers_df.columns = [
    str(c).strip()
    for c in transfers_df.columns
]

vehicles_df.columns = [
    str(c).strip()
    for c in vehicles_df.columns
]

distance_df.columns = [
    str(c).strip()
    for c in distance_df.columns
]


# ============================================================
# VALIDATE COLUMNS
# ============================================================

required_transfer_columns = [
    "transfer_id",
    "source_warehouse",
    "destination_warehouse",
    "weight_kg",
    "volume_m3",
    "priority",
    "deadline_days"
]

required_vehicle_columns = [
    "vehicle_id",
    "warehouse_id",
    "capacity_kg",
    "volume_capacity_m3",
    "fuel_efficiency_kmpl"
]

required_distance_columns = [
    "source_warehouse",
    "destination_warehouse",
    "distance_km"
]


for column in required_transfer_columns:

    if column not in transfers_df.columns:

        raise ValueError(
            f"Missing transfer column: {column}"
        )


for column in required_vehicle_columns:

    if column not in vehicles_df.columns:

        raise ValueError(
            f"Missing vehicle column: {column}"
        )


for column in required_distance_columns:

    if column not in distance_df.columns:

        raise ValueError(
            f"Missing distance column: {column}"
        )


# ============================================================
# DISTANCE MAP
# ============================================================

distance_map = build_distance_map(
    distance_df
)


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 58)
print("       LOGICOMMERCE AI")
print("       FINAL LOGISTICS OPTIMIZER")
print("=" * 58)


# ============================================================
# SOURCE SUMMARY
# ============================================================

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
    print("-" * 58)
    print(
        f"SOURCE: {source}"
    )
    print(
        f"Transfers: {count}"
    )


# ============================================================
# BASELINE COST
#
# Each transfer is treated independently.
# Baseline uses 10 km/L reference efficiency.
# ============================================================

transfers_df[
    "_baseline_cost"
] = 0.0


for index, row in transfers_df.iterrows():

    source = row[
        "source_warehouse"
    ]

    destination = row[
        "destination_warehouse"
    ]

    one_way_distance = get_distance(
        distance_map,
        source,
        destination
    )

    round_trip_distance = (
        one_way_distance * 2
    )

    transfers_df.loc[
        index,
        "_baseline_cost"
    ] = fuel_cost(
        round_trip_distance,
        10.0
    )


# ============================================================
# VEHICLE STATE
# ============================================================

vehicle_next_available = {

    str(row["vehicle_id"]): 0.0

    for _, row in vehicles_df.iterrows()
}


# ============================================================
# RESULT CONTAINERS
# ============================================================

results = []

assigned_transfer_ids = set()


# ============================================================
# FINAL OPTIMIZATION
# ============================================================

for source in sorted(
    transfers_df[
        "source_warehouse"
    ].unique()
):

    source_df = transfers_df[
        transfers_df[
            "source_warehouse"
        ] == source
    ].copy()

    # --------------------------------------------------------
    # Urgent transfers first.
    # --------------------------------------------------------

    source_df = source_df.sort_values(
        by=[
            "deadline_days"
        ]
    )


    # --------------------------------------------------------
    # Group by destination.
    # --------------------------------------------------------

    destination_groups = (
        source_df
        .groupby(
            "destination_warehouse",
            sort=False
        )
    )


    for destination, destination_df in destination_groups:

        urgent_rows = destination_df[
            destination_df[
                "deadline_days"
            ].apply(safe_float)
            <= 1
        ].copy()

        normal_rows = destination_df[
            destination_df[
                "deadline_days"
            ].apply(safe_float)
            > 1
        ].copy()


        # ====================================================
        # URGENT SHIPMENTS
        # ====================================================

        for _, row in urgent_rows.iterrows():

            transfer_id = str(
                row["transfer_id"]
            )

            if transfer_id in assigned_transfer_ids:
                continue

            weight = safe_float(
                row["weight_kg"]
            )

            volume = safe_float(
                row["volume_m3"]
            )

            route, distance = make_direct_route(
                source,
                destination,
                distance_map
            )

            vehicle = find_best_vehicle(
                vehicles_df,
                source,
                weight,
                volume,
                distance
            )

            if vehicle is None:
                continue

            vehicle_id = vehicle[
                "vehicle_id"
            ]

            departure = vehicle_next_available.get(
                vehicle_id,
                0.0
            )

            travel_hours = route_time(
                distance
            )

            arrival = (
                departure
                + travel_hours
            )

            deadline = get_deadline_status(
                travel_hours,
                row["deadline_days"]
            )

            fuel = vehicle["fuel"]

            optimized_cost = (
                vehicle["fuel_cost"]
            )

            baseline = safe_float(
                row["_baseline_cost"]
            )

            weight_utilization = vehicle[
                "weight_utilization"
            ]

            volume_utilization = vehicle[
                "volume_utilization"
            ]

            overall_utilization = vehicle[
                "overall_utilization"
            ]

            results.append({

                "transfer_ids":
                    transfer_id,

                "source":
                    source,

                "destination":
                    destination,

                "route":
                    " → ".join(route),

                "decision":
                    "URGENT_SEPARATE",

                "vehicle_id":
                    vehicle_id,

                "vehicle_capacity_kg":
                    vehicle[
                        "capacity_kg"
                    ],

                "vehicle_volume_m3":
                    vehicle[
                        "volume_capacity_m3"
                    ],

                "weight_kg":
                    weight,

                "volume_m3":
                    volume,

                "weight_utilization":
                    weight_utilization,

                "volume_utilization":
                    volume_utilization,

                "overall_utilization":
                    overall_utilization,

                "fuel_efficiency_kmpl":
                    vehicle[
                        "fuel_efficiency_kmpl"
                    ],

                "distance_km":
                    distance,

                "route_time_hours":
                    travel_hours,

                "departure_hour":
                    departure,

                "arrival_hour":
                    arrival,

                "fuel_liters":
                    fuel,

                "optimized_cost":
                    optimized_cost,

                "baseline_cost":
                    baseline,

                "savings":
                    0.0,

                "savings_percentage":
                    0.0,

                "deadline_days":
                    safe_float(
                        row["deadline_days"]
                    ),

                "deadline_status":
                    deadline,

                "urgency":
                    "URGENT",

                "reason":
                    "Urgent shipment protected "
                    "from consolidation delay."

            })

            assigned_transfer_ids.add(
                transfer_id
            )

            vehicle_next_available[
                vehicle_id
            ] = (
                arrival
                + travel_hours
            )


        # ====================================================
        # NORMAL SHIPMENTS
        # ====================================================

        if normal_rows.empty:
            continue


        transfer_ids = [
            str(x)
            for x in normal_rows[
                "transfer_id"
            ]
        ]

        weight = (
            normal_rows[
                "weight_kg"
            ]
            .apply(safe_float)
            .sum()
        )

        volume = (
            normal_rows[
                "volume_m3"
            ]
            .apply(safe_float)
            .sum()
        )

        earliest_deadline = (
            normal_rows[
                "deadline_days"
            ]
            .apply(safe_float)
            .min()
        )

        urgency = get_urgency(
            earliest_deadline
        )


        # ----------------------------------------------------
        # Try complete consolidation.
        # ----------------------------------------------------

        route, consolidated_distance = (
            make_direct_route(
                source,
                destination,
                distance_map
            )
        )

        vehicle = find_best_vehicle(
            vehicles_df,
            source,
            weight,
            volume,
            consolidated_distance
        )


        # ----------------------------------------------------
        # If group fits, compare costs.
        # ----------------------------------------------------

        if vehicle is not None:

            vehicle_id = vehicle[
                "vehicle_id"
            ]

            departure = vehicle_next_available.get(
                vehicle_id,
                0.0
            )

            consolidated_time = route_time(
                consolidated_distance
            )

            arrival = (
                departure
                + consolidated_time
            )

            deadline = get_deadline_status(
                consolidated_time,
                earliest_deadline
            )

            consolidated_cost = (
                vehicle["fuel_cost"]
            )

            separate_baseline = (
                normal_rows[
                    "_baseline_cost"
                ].sum()
            )


            # ------------------------------------------------
            # Consolidate only when cost is lower
            # and deadline is safe.
            # ------------------------------------------------

            if (
                len(normal_rows) > 1
                and
                consolidated_cost
                < separate_baseline
                and
                deadline
                != "MISSED_DEADLINE"
            ):

                decision = "CONSOLIDATE"

                final_cost = consolidated_cost

                savings = (
                    separate_baseline
                    - consolidated_cost
                )

                savings_percentage = (
                    savings
                    / separate_baseline
                    * 100
                    if separate_baseline > 0
                    else 0.0
                )

                reason = (
                    "Compatible shipments combined "
                    "to reduce cost while preserving "
                    "deadline feasibility."
                )

            else:

                # ------------------------------------------------
                # Process each normal shipment separately.
                # ------------------------------------------------

                for _, row in normal_rows.iterrows():

                    transfer_id = str(
                        row["transfer_id"]
                    )

                    if transfer_id in assigned_transfer_ids:
                        continue

                    single_weight = safe_float(
                        row["weight_kg"]
                    )

                    single_volume = safe_float(
                        row["volume_m3"]
                    )

                    single_route, single_distance = (
                        make_direct_route(
                            source,
                            destination,
                            distance_map
                        )
                    )

                    single_vehicle = find_best_vehicle(
                        vehicles_df,
                        source,
                        single_weight,
                        single_volume,
                        single_distance
                    )

                    if single_vehicle is None:
                        continue

                    single_vehicle_id = (
                        single_vehicle[
                            "vehicle_id"
                        ]
                    )

                    single_departure = (
                        vehicle_next_available.get(
                            single_vehicle_id,
                            0.0
                        )
                    )

                    single_time = route_time(
                        single_distance
                    )

                    single_arrival = (
                        single_departure
                        + single_time
                    )

                    single_deadline = (
                        get_deadline_status(
                            single_time,
                            row["deadline_days"]
                        )
                    )

                    single_cost = (
                        single_vehicle[
                            "fuel_cost"
                        ]
                    )

                    single_baseline = safe_float(
                        row["_baseline_cost"]
                    )

                    results.append({

                        "transfer_ids":
                            transfer_id,

                        "source":
                            source,

                        "destination":
                            destination,

                        "route":
                            " → ".join(
                                single_route
                            ),

                        "decision":
                            "SEPARATE",

                        "vehicle_id":
                            single_vehicle_id,

                        "vehicle_capacity_kg":
                            single_vehicle[
                                "capacity_kg"
                            ],

                        "vehicle_volume_m3":
                            single_vehicle[
                                "volume_capacity_m3"
                            ],

                        "weight_kg":
                            single_weight,

                        "volume_m3":
                            single_volume,

                        "weight_utilization":
                            single_vehicle[
                                "weight_utilization"
                            ],

                        "volume_utilization":
                            single_vehicle[
                                "volume_utilization"
                            ],

                        "overall_utilization":
                            single_vehicle[
                                "overall_utilization"
                            ],

                        "fuel_efficiency_kmpl":
                            single_vehicle[
                                "fuel_efficiency_kmpl"
                            ],

                        "distance_km":
                            single_distance,

                        "route_time_hours":
                            single_time,

                        "departure_hour":
                            single_departure,

                        "arrival_hour":
                            single_arrival,

                        "fuel_liters":
                            single_vehicle[
                                "fuel"
                            ],

                        "optimized_cost":
                            single_cost,

                        "baseline_cost":
                            single_baseline,

                        "savings":
                            0.0,

                        "savings_percentage":
                            0.0,

                        "deadline_days":
                            safe_float(
                                row[
                                    "deadline_days"
                                ]
                            ),

                        "deadline_status":
                            single_deadline,

                        "urgency":
                            get_urgency(
                                row[
                                    "deadline_days"
                                ]
                            ),

                        "reason":
                            (
                                "Single shipment dispatch."
                                if len(normal_rows) == 1
                                else
                                "Consolidation rejected "
                                "because it does not "
                                "provide sufficient cost "
                                "benefit or deadline safety."
                            )

                    })

                    assigned_transfer_ids.add(
                        transfer_id
                    )

                    vehicle_next_available[
                        single_vehicle_id
                    ] = (
                        single_arrival
                        + single_time
                    )

                continue


            # ------------------------------------------------
            # Save consolidated group.
            # ------------------------------------------------

            if decision == "CONSOLIDATE":

                results.append({

                    "transfer_ids":
                        ",".join(
                            transfer_ids
                        ),

                    "source":
                        source,

                    "destination":
                        destination,

                    "route":
                        " → ".join(
                            route
                        ),

                    "decision":
                        "CONSOLIDATE",

                    "vehicle_id":
                        vehicle_id,

                    "vehicle_capacity_kg":
                        vehicle[
                            "capacity_kg"
                        ],

                    "vehicle_volume_m3":
                        vehicle[
                            "volume_capacity_m3"
                        ],

                    "weight_kg":
                        weight,

                    "volume_m3":
                        volume,

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
                        consolidated_distance,

                    "route_time_hours":
                        consolidated_time,

                    "departure_hour":
                        departure,

                    "arrival_hour":
                        arrival,

                    "fuel_liters":
                        vehicle[
                            "fuel"
                        ],

                    "optimized_cost":
                        consolidated_cost,

                    "baseline_cost":
                        separate_baseline,

                    "savings":
                        savings,

                    "savings_percentage":
                        savings_percentage,

                    "deadline_days":
                        earliest_deadline,

                    "deadline_status":
                        deadline,

                    "urgency":
                        urgency,

                    "reason":
                        reason

                })

                for transfer_id in transfer_ids:

                    assigned_transfer_ids.add(
                        transfer_id
                    )

                vehicle_next_available[
                    vehicle_id
                ] = (
                    arrival
                    + consolidated_time
                )


# ============================================================
# RESULT DATAFRAME
# ============================================================

results_df = pd.DataFrame(
    results
)


# ============================================================
# ACCOUNTING VALIDATION
# ============================================================

expected_ids = set(
    transfers_df[
        "transfer_id"
    ]
    .astype(str)
)

accounted_ids = set()


if not results_df.empty:

    for value in results_df[
        "transfer_ids"
    ].dropna():

        for transfer_id in str(
            value
        ).split(","):

            transfer_id = (
                transfer_id.strip()
            )

            if transfer_id:

                accounted_ids.add(
                    transfer_id
                )


missing_ids = (
    expected_ids
    - accounted_ids
)


# ============================================================
# FINAL PLAN OUTPUT
# ============================================================

print()
print("=" * 58)
print("       FINAL LOGISTICS PLAN")
print("=" * 58)


for _, plan in results_df.iterrows():

    print()
    print("-" * 58)

    print(
        f"Decision: "
        f"{plan['decision']}"
    )

    print(
        f"Route: "
        f"{plan['route']}"
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
        f"Optimized cost: "
        f"₹{plan['optimized_cost']:.2f}"
    )

    print(
        f"Baseline cost: "
        f"₹{plan['baseline_cost']:.2f}"
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
    expected_ids
)

assigned_transfers = len(
    accounted_ids
)

unassigned_transfers = len(
    missing_ids
)

routes_created = len(
    results_df
)


if not results_df.empty:

    total_distance = results_df[
        "distance_km"
    ].sum()

    total_fuel = results_df[
        "fuel_liters"
    ].sum()

    optimized_cost_total = results_df[
        "optimized_cost"
    ].sum()

    baseline_cost_total = results_df[
        "baseline_cost"
    ].sum()

    average_weight_utilization = (
        results_df[
            "weight_utilization"
        ].mean()
    )

    average_volume_utilization = (
        results_df[
            "volume_utilization"
        ].mean()
    )

else:

    total_distance = 0.0
    total_fuel = 0.0
    optimized_cost_total = 0.0
    baseline_cost_total = 0.0
    average_weight_utilization = 0.0
    average_volume_utilization = 0.0


estimated_savings = max(
    0.0,
    baseline_cost_total
    - optimized_cost_total
)


overall_savings = (
    estimated_savings
    / baseline_cost_total
    * 100
    if baseline_cost_total > 0
    else 0.0
)


consolidated_routes = len(
    results_df[
        results_df[
            "decision"
        ] == "CONSOLIDATE"
    ]
)


separate_routes = len(
    results_df[
        results_df[
            "decision"
        ] == "SEPARATE"
    ]
)


urgent_routes = len(
    results_df[
        results_df[
            "decision"
        ] == "URGENT_SEPARATE"
    ]
)


on_time = len(
    results_df[
        results_df[
            "deadline_status"
        ] == "ON_TIME"
    ]
)


at_risk = len(
    results_df[
        results_df[
            "deadline_status"
        ] == "AT_RISK"
    ]
)


missed = len(
    results_df[
        results_df[
            "deadline_status"
        ] == "MISSED_DEADLINE"
    ]
)


print()
print("=" * 58)
print("       FINAL OPTIMIZATION SUMMARY")
print("=" * 58)

print(
    f"Total transfers: "
    f"{total_transfers}"
)

print(
    f"Transfers assigned: "
    f"{assigned_transfers}"
)

print(
    f"Transfers unassigned: "
    f"{unassigned_transfers}"
)

print(
    f"Routes created: "
    f"{routes_created}"
)

print(
    f"Consolidated routes: "
    f"{consolidated_routes}"
)

print(
    f"Separate routes: "
    f"{separate_routes}"
)

print(
    f"Urgent separate: "
    f"{urgent_routes}"
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
    f"Optimized cost: "
    f"₹{optimized_cost_total:.2f}"
)

print(
    f"Baseline cost: "
    f"₹{baseline_cost_total:.2f}"
)

print(
    f"Estimated savings: "
    f"₹{estimated_savings:.2f}"
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
    f"ON_TIME routes: "
    f"{on_time}"
)

print(
    f"AT_RISK routes: "
    f"{at_risk}"
)

print(
    f"MISSED_DEADLINE routes: "
    f"{missed}"
)


# ============================================================
# ACCOUNTING VALIDATION
# ============================================================

print()
print("=" * 58)
print("       TRANSFER ACCOUNTING VALIDATION")
print("=" * 58)

print(
    f"Expected transfers: "
    f"{len(expected_ids)}"
)

print(
    f"Accounted transfers: "
    f"{len(accounted_ids)}"
)

print(
    f"Missing transfers: "
    f"{len(missing_ids)}"
)


if not missing_ids:

    print(
        "✅ TRANSFER ACCOUNTING PASSED"
    )

    print()
    print(
        "✅ ALL TRANSFERS ASSIGNED"
    )

else:

    print(
        "⚠️ TRANSFER ACCOUNTING FAILED"
    )

    print()

    for transfer_id in sorted(
        missing_ids
    ):

        print(
            f"⚠️ {transfer_id}"
        )


# ============================================================
# SAVE OUTPUT
# ============================================================

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 58)
print("       LOGICOMMERCE AI COMPLETE")
print("=" * 58)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)