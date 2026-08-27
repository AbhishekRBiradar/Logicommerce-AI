import os
import itertools
import pandas as pd


# ============================================================
# LOGICOMMERCE AI V8
# FLEET-AWARE GLOBAL LOGISTICS OPTIMIZER
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
    "logistics_optimization_v8.csv"
)

FUEL_PRICE_PER_LITRE = 100.0

AVERAGE_SPEED_KMPH = 40.0

MAX_STOPS = 3

START_TIME = 0.0


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
# NORMALIZE
# ============================================================

transfers.columns = transfers.columns.str.strip()
vehicles.columns = vehicles.columns.str.strip()
distances.columns = distances.columns.str.strip()


# ============================================================
# VALIDATE VEHICLE DATA
# ============================================================

required_vehicle_columns = [
    "vehicle_id",
    "warehouse_id",
    "capacity_kg",
    "volume_capacity_m3",
    "fuel_efficiency_kmpl",
    "available"
]

for column in required_vehicle_columns:

    if column not in vehicles.columns:

        raise ValueError(
            f"Missing vehicle column: {column}"
        )


# ============================================================
# VALIDATE TRANSFER DATA
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

for column in required_transfer_columns:

    if column not in transfers.columns:

        raise ValueError(
            f"Missing transfer column: {column}"
        )


# ============================================================
# DISTANCE COLUMN DETECTION
# ============================================================

source_columns = [
    "source_warehouse",
    "source",
    "from_warehouse"
]

destination_columns = [
    "destination_warehouse",
    "destination",
    "to_warehouse"
]

distance_columns = [
    "distance_km",
    "distance"
]


distance_source_column = next(
    (
        column
        for column in source_columns
        if column in distances.columns
    ),
    None
)

distance_destination_column = next(
    (
        column
        for column in destination_columns
        if column in distances.columns
    ),
    None
)

distance_value_column = next(
    (
        column
        for column in distance_columns
        if column in distances.columns
    ),
    None
)


if (
    distance_source_column is None
    or
    distance_destination_column is None
    or
    distance_value_column is None
):

    raise ValueError(
        "Could not identify warehouse distance columns."
    )


# ============================================================
# DISTANCE LOOKUP
# ============================================================

def get_distance(
    source,
    destination
):

    match = distances[
        (
            distances[
                distance_source_column
            ] == source
        )
        &
        (
            distances[
                distance_destination_column
            ] == destination
        )
    ]

    if not match.empty:

        return float(
            match.iloc[0][
                distance_value_column
            ]
        )

    reverse = distances[
        (
            distances[
                distance_source_column
            ] == destination
        )
        &
        (
            distances[
                distance_destination_column
            ] == source
        )
    ]

    if not reverse.empty:

        return float(
            reverse.iloc[0][
                distance_value_column
            ]
        )

    return None


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(route):

    total_distance = 0.0

    for index in range(
        len(route) - 1
    ):

        distance = get_distance(
            route[index],
            route[index + 1]
        )

        if distance is None:

            return None

        total_distance += distance

    return total_distance


# ============================================================
# ROUTE TIME
# ============================================================

def calculate_route_time(
    distance
):

    return (
        distance
        /
        AVERAGE_SPEED_KMPH
    )


# ============================================================
# PRIORITY
# ============================================================

priority_rank = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2
}


transfers["priority_rank"] = (
    transfers[
        "priority"
    ]
    .map(priority_rank)
    .fillna(3)
)


# ============================================================
# NUMERIC CONVERSION
# ============================================================

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
# VEHICLE STATE
#
# IMPORTANT:
# Vehicles are NOT permanently reserved.
#
# Each vehicle gets a next_available_hour.
# ============================================================

vehicle_state = {}


for _, vehicle in vehicles.iterrows():

    vehicle_state[
        vehicle["vehicle_id"]
    ] = {

        "next_available_hour":
            START_TIME,

        "trips":
            0,

        "total_distance":
            0.0,

        "total_fuel":
            0.0
    }


# ============================================================
# VEHICLE CANDIDATES
# ============================================================

def get_vehicle_candidates(
    source,
    weight,
    volume,
    current_time
):

    candidates = []

    source_vehicles = vehicles[
        (
            vehicles[
                "warehouse_id"
            ] == source
        )
        &
        (
            vehicles[
                "available"
            ] == 1
        )
    ]

    for _, vehicle in source_vehicles.iterrows():

        vehicle_id = vehicle[
            "vehicle_id"
        ]

        state = vehicle_state[
            vehicle_id
        ]

        # ----------------------------------------------------
        # Vehicle must be available by current time.
        # ----------------------------------------------------

        if (
            state[
                "next_available_hour"
            ]
            >
            current_time
        ):

            continue

        # ----------------------------------------------------
        # Hard weight constraint
        # ----------------------------------------------------

        if (
            float(vehicle["capacity_kg"])
            <
            weight
        ):

            continue

        # ----------------------------------------------------
        # Hard volume constraint
        # ----------------------------------------------------

        if (
            float(
                vehicle[
                    "volume_capacity_m3"
                ]
            )
            <
            volume
        ):

            continue

        weight_utilization = (
            weight
            /
            float(
                vehicle[
                    "capacity_kg"
                ]
            )
        )

        volume_utilization = (
            volume
            /
            float(
                vehicle[
                    "volume_capacity_m3"
                ]
            )
        )

        overall_utilization = (
            weight_utilization
            +
            volume_utilization
        ) / 2

        candidates.append({

            "vehicle": vehicle,

            "weight_utilization":
                weight_utilization,

            "volume_utilization":
                volume_utilization,

            "overall_utilization":
                overall_utilization,

            "next_available_hour":
                state[
                    "next_available_hour"
                ]
        })

    return candidates


# ============================================================
# VEHICLE SELECTION
# ============================================================

def select_vehicle(
    source,
    weight,
    volume,
    distance,
    current_time
):

    candidates = get_vehicle_candidates(
        source,
        weight,
        volume,
        current_time
    )

    if not candidates:

        return None

    for candidate in candidates:

        vehicle = candidate[
            "vehicle"
        ]

        fuel = (
            distance
            /
            float(
                vehicle[
                    "fuel_efficiency_kmpl"
                ]
            )
        )

        fuel_cost = (
            fuel
            *
            FUEL_PRICE_PER_LITRE
        )

        utilization = candidate[
            "overall_utilization"
        ]

        capacity_waste = (
            1.0
            -
            utilization
        )

        # ----------------------------------------------------
        # V8 vehicle score
        #
        # Fuel cost is important.
        # But extremely oversized vehicles receive a penalty.
        # ----------------------------------------------------

        score = (
            fuel_cost
            +
            (
                capacity_waste
                *
                250
            )
        )

        candidate[
            "fuel"
        ] = fuel

        candidate[
            "fuel_cost"
        ] = fuel_cost

        candidate[
            "score"
        ] = score

    candidates.sort(
        key=lambda item: (
            item["score"],
            -item[
                "overall_utilization"
            ],
            item[
                "fuel_cost"
            ]
        )
    )

    return candidates[0]


# ============================================================
# ROUTE ORDER
# ============================================================

def best_multi_stop_route(
    source,
    destinations
):

    unique_destinations = list(
        dict.fromkeys(
            destinations
        )
    )

    if not unique_destinations:

        return None

    unique_destinations = (
        unique_destinations[
            :MAX_STOPS
        ]
    )

    best_route = None
    best_distance = None

    for permutation in itertools.permutations(
        unique_destinations
    ):

        route = (
            [source]
            +
            list(permutation)
            +
            [source]
        )

        distance = calculate_route_distance(
            route
        )

        if distance is None:

            continue

        if (
            best_distance is None
            or
            distance < best_distance
        ):

            best_distance = distance
            best_route = route

    if best_route is None:

        return None

    return {
        "route":
            best_route,

        "distance":
            best_distance
    }


# ============================================================
# CHECK DEADLINE
# ============================================================

def deadline_status(
    arrival_time,
    deadline_days
):

    deadline_hours = (
        deadline_days
        *
        24
    )

    if arrival_time <= deadline_hours:

        return "ON_TIME"

    if arrival_time <= (
        deadline_hours
        +
        6
    ):

        return "AT_RISK"

    return "MISSED_DEADLINE"


# ============================================================
# CREATE PLAN
# ============================================================

def create_plan(
    shipment_group,
    current_time,
    decision
):

    if shipment_group.empty:

        return None

    source = shipment_group.iloc[0][
        "source_warehouse"
    ]

    destinations = shipment_group[
        "destination_warehouse"
    ].tolist()

    route_info = best_multi_stop_route(
        source,
        destinations
    )

    if route_info is None:

        return None

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

    distance = float(
        route_info[
            "distance"
        ]
    )

    route_time = calculate_route_time(
        distance
    )

    vehicle_choice = select_vehicle(
        source,
        total_weight,
        total_volume,
        distance,
        current_time
    )

    if vehicle_choice is None:

        return None

    vehicle = vehicle_choice[
        "vehicle"
    ]

    vehicle_id = vehicle[
        "vehicle_id"
    ]

    arrival_time = (
        current_time
        +
        route_time
    )

    return_time = (
        current_time
        +
        route_time
        +
        route_time
    )

    deadline_days = float(
        shipment_group[
            "deadline_days"
        ].min()
    )

    deadline = deadline_status(
        arrival_time,
        deadline_days
    )

    transfer_ids = shipment_group[
        "transfer_id"
    ].tolist()

    return {

        "decision":
            decision,

        "transfer_ids":
            ",".join(
                transfer_ids
            ),

        "route":
            route_info["route"],

        "vehicle":
            vehicle,

        "vehicle_id":
            vehicle_id,

        "departure_hour":
            current_time,

        "arrival_hour":
            arrival_time,

        "return_hour":
            return_time,

        "route_time":
            route_time,

        "distance":
            distance,

        "weight":
            total_weight,

        "volume":
            total_volume,

        "fuel":
            vehicle_choice["fuel"],

        "fuel_cost":
            vehicle_choice["fuel_cost"],

        "weight_utilization":
            vehicle_choice[
                "weight_utilization"
            ],

        "volume_utilization":
            vehicle_choice[
                "volume_utilization"
            ],

        "overall_utilization":
            vehicle_choice[
                "overall_utilization"
            ],

        "deadline_days":
            deadline_days,

        "deadline_status":
            deadline,

        "vehicle_capacity":
            float(
                vehicle[
                    "capacity_kg"
                ]
            ),

        "vehicle_volume":
            float(
                vehicle[
                    "volume_capacity_m3"
                ]
            ),

        "fuel_efficiency":
            float(
                vehicle[
                    "fuel_efficiency_kmpl"
                ]
            )
    }


# ============================================================
# UPDATE VEHICLE STATE
# ============================================================

def commit_vehicle_trip(
    plan
):

    vehicle_id = plan[
        "vehicle_id"
    ]

    state = vehicle_state[
        vehicle_id
    ]

    state[
        "next_available_hour"
    ] = plan[
        "return_hour"
    ]

    state[
        "trips"
    ] += 1

    state[
        "total_distance"
    ] += plan[
        "distance"
    ]

    state[
        "total_fuel"
    ] += plan[
        "fuel"
    ]


# ============================================================
# DISPLAY HEADER
# ============================================================

print()
print("=" * 50)
print("       LOGICOMMERCE AI V8")
print(" FLEET-AWARE GLOBAL OPTIMIZATION")
print("=" * 50)


# ============================================================
# SHOW SOURCES
# ============================================================

print()

for source in sorted(
    transfers[
        "source_warehouse"
    ].unique()
):

    count = len(
        transfers[
            transfers[
                "source_warehouse"
            ] == source
        ]
    )

    print("-" * 42)

    print(
        f"SOURCE: {source}"
    )

    print(
        f"Transfers: {count}"
    )


# ============================================================
# SORT TRANSFERS
#
# Urgent first.
# Then HIGH priority.
# Then deadline.
# ============================================================

transfers = transfers.sort_values(
    by=[
        "deadline_days",
        "priority_rank"
    ]
).reset_index(
    drop=True
)


assigned_ids = set()

plans = []


# ============================================================
# PASS 1
# URGENT / HIGH PRIORITY
#
# These are deliberately protected from consolidation.
# ============================================================

urgent = transfers[
    (
        transfers[
            "deadline_days"
        ] <= 1
    )
    |
    (
        transfers[
            "priority"
        ] == "HIGH"
    )
].copy()


for _, transfer in urgent.iterrows():

    transfer_id = transfer[
        "transfer_id"
    ]

    if transfer_id in assigned_ids:

        continue

    group = pd.DataFrame(
        [transfer]
    )

    # Find earliest available vehicle.
    # We try current time first.
    current_time = 0.0

    plan = create_plan(
        group,
        current_time,
        "URGENT_SEPARATE"
    )

    if plan is None:

        # Try later times by checking the fleet.
        possible_times = []

        source = transfer[
            "source_warehouse"
        ]

        weight = float(
            transfer["weight_kg"]
        )

        volume = float(
            transfer["volume_m3"]
        )

        for _, vehicle in vehicles.iterrows():

            if vehicle[
                "warehouse_id"
            ] != source:

                continue

            if vehicle[
                "available"
            ] != 1:

                continue

            if (
                float(
                    vehicle[
                        "capacity_kg"
                    ]
                )
                < weight
            ):

                continue

            if (
                float(
                    vehicle[
                        "volume_capacity_m3"
                    ]
                )
                < volume
            ):

                continue

            possible_times.append(
                vehicle_state[
                    vehicle[
                        "vehicle_id"
                    ]
                ][
                    "next_available_hour"
                ]
            )

        if possible_times:

            current_time = min(
                possible_times
            )

            plan = create_plan(
                group,
                current_time,
                "URGENT_SEPARATE"
            )

    if plan is None:

        continue

    plans.append(
        plan
    )

    assigned_ids.add(
        transfer_id
    )

    commit_vehicle_trip(
        plan
    )


# ============================================================
# PASS 2
# SAME ROUTE CONSOLIDATION
# ============================================================

remaining = transfers[
    ~transfers[
        "transfer_id"
    ].isin(
        assigned_ids
    )
].copy()


route_groups = remaining.groupby(
    [
        "source_warehouse",
        "destination_warehouse"
    ]
)


for (
    source,
    destination
), group in route_groups:

    group = group[
        ~group[
            "transfer_id"
        ].isin(
            assigned_ids
        )
    ].copy()

    if group.empty:

        continue

    # --------------------------------------------------------
    # Find earliest available vehicle at source.
    # --------------------------------------------------------

    possible_times = []

    for _, vehicle in vehicles.iterrows():

        if vehicle[
            "warehouse_id"
        ] != source:

            continue

        if vehicle[
            "available"
        ] != 1:

            continue

        possible_times.append(
            vehicle_state[
                vehicle[
                    "vehicle_id"
                ]
            ][
                "next_available_hour"
            ]
        )

    if not possible_times:

        continue

    current_time = min(
        possible_times
    )

    plan = create_plan(
        group,
        current_time,
        "CONSOLIDATE"
    )

    if plan is None:

        # ----------------------------------------------------
        # If complete group doesn't fit,
        # schedule individual shipments.
        # ----------------------------------------------------

        for _, transfer in group.iterrows():

            transfer_id = transfer[
                "transfer_id"
            ]

            if transfer_id in assigned_ids:

                continue

            single_group = pd.DataFrame(
                [transfer]
            )

            possible_times = []

            for _, vehicle in vehicles.iterrows():

                if vehicle[
                    "warehouse_id"
                ] != source:

                    continue

                if vehicle[
                    "available"
                ] != 1:

                    continue

                possible_times.append(
                    vehicle_state[
                        vehicle[
                            "vehicle_id"
                        ]
                    ][
                        "next_available_hour"
                    ]
                )

            if not possible_times:

                continue

            current_time = min(
                possible_times
            )

            single_plan = create_plan(
                single_group,
                current_time,
                "SEPARATE"
            )

            if single_plan is None:

                continue

            plans.append(
                single_plan
            )

            assigned_ids.add(
                transfer_id
            )

            commit_vehicle_trip(
                single_plan
            )

        continue

    # --------------------------------------------------------
    # Deadline safety.
    # If consolidation misses the earliest deadline,
    # try individual shipment.
    # --------------------------------------------------------

    if plan[
        "deadline_status"
    ] == "MISSED_DEADLINE":

        for _, transfer in group.iterrows():

            transfer_id = transfer[
                "transfer_id"
            ]

            if transfer_id in assigned_ids:

                continue

            single_group = pd.DataFrame(
                [transfer]
            )

            current_time = min(
                possible_times
            )

            single_plan = create_plan(
                single_group,
                current_time,
                "SEPARATE"
            )

            if single_plan is None:

                continue

            plans.append(
                single_plan
            )

            assigned_ids.add(
                transfer_id
            )

            commit_vehicle_trip(
                single_plan
            )

        continue

    plans.append(
        plan
    )

    for transfer_id in group[
        "transfer_id"
    ]:

        assigned_ids.add(
            transfer_id
        )

    commit_vehicle_trip(
        plan
    )


# ============================================================
# PASS 3
# MULTI-STOP CONSOLIDATION
# ============================================================

remaining = transfers[
    ~transfers[
        "transfer_id"
    ].isin(
        assigned_ids
    )
].copy()


for source in remaining[
    "source_warehouse"
].unique():

    source_group = remaining[
        remaining[
            "source_warehouse"
        ] == source
    ].copy()

    if source_group.empty:

        continue

    destinations = list(
        source_group[
            "destination_warehouse"
        ].unique()
    )

    # --------------------------------------------------------
    # Try combinations of destinations.
    # --------------------------------------------------------

    found = False

    for stop_count in range(
        min(
            MAX_STOPS,
            len(destinations)
        ),
        1,
        -1
    ):

        combinations = itertools.combinations(
            destinations,
            stop_count
        )

        for destination_group in combinations:

            candidate = source_group[
                source_group[
                    "destination_warehouse"
                ].isin(
                    destination_group
                )
            ].copy()

            candidate = candidate[
                ~candidate[
                    "transfer_id"
                ].isin(
                    assigned_ids
                )
            ]

            if candidate.empty:

                continue

            possible_times = []

            for _, vehicle in vehicles.iterrows():

                if vehicle[
                    "warehouse_id"
                ] != source:

                    continue

                if vehicle[
                    "available"
                ] != 1:

                    continue

                possible_times.append(
                    vehicle_state[
                        vehicle[
                            "vehicle_id"
                        ]
                    ][
                        "next_available_hour"
                    ]
                )

            if not possible_times:

                continue

            current_time = min(
                possible_times
            )

            plan = create_plan(
                candidate,
                current_time,
                "MULTI_STOP_CONSOLIDATE"
            )

            if plan is None:

                continue

            if plan[
                "deadline_status"
            ] == "MISSED_DEADLINE":

                continue

            plans.append(
                plan
            )

            for transfer_id in candidate[
                "transfer_id"
            ]:

                assigned_ids.add(
                    transfer_id
                )

            commit_vehicle_trip(
                plan
            )

            found = True

            break

        if found:

            break


# ============================================================
# PASS 4
# FINAL FALLBACK
# ============================================================

remaining = transfers[
    ~transfers[
        "transfer_id"
    ].isin(
        assigned_ids
    )
].copy()


for _, transfer in remaining.iterrows():

    transfer_id = transfer[
        "transfer_id"
    ]

    if transfer_id in assigned_ids:

        continue

    source = transfer[
        "source_warehouse"
    ]

    possible_times = []

    for _, vehicle in vehicles.iterrows():

        if vehicle[
            "warehouse_id"
        ] != source:

            continue

        if vehicle[
            "available"
        ] != 1:

            continue

        possible_times.append(
            vehicle_state[
                vehicle[
                    "vehicle_id"
                ]
            ][
                "next_available_hour"
            ]
        )

    if not possible_times:

        continue

    current_time = min(
        possible_times
    )

    single_group = pd.DataFrame(
        [transfer]
    )

    plan = create_plan(
        single_group,
        current_time,
        "FLEET_FALLBACK"
    )

    if plan is None:

        continue

    plans.append(
        plan
    )

    assigned_ids.add(
        transfer_id
    )

    commit_vehicle_trip(
        plan
    )


# ============================================================
# DISPLAY FINAL PLAN
# ============================================================

print()
print("=" * 50)
print("       FINAL LOGISTICS PLAN V8")
print("=" * 50)


output_rows = []


for plan in plans:

    vehicle = plan[
        "vehicle"
    ]

    route_text = " → ".join(
        plan[
            "route"
        ]
    )

    print()
    print("-" * 42)

    print(
        f"Decision: "
        f"{plan['decision']}"
    )

    print(
        f"Route: "
        f"{route_text}"
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
        f"{plan['vehicle_capacity']:.0f} kg"
    )

    print(
        f"Vehicle volume: "
        f"{plan['vehicle_volume']:.1f} m³"
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
        f"Fuel efficiency: "
        f"{plan['fuel_efficiency']:.2f} km/L"
    )

    print(
        f"Distance: "
        f"{plan['distance']:.0f} km"
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
        f"Vehicle return: "
        f"{plan['return_hour']:.2f} h"
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
        f"Deadline: "
        f"{plan['deadline_status']}"
    )


    output_rows.append({

        "decision":
            plan["decision"],

        "transfer_ids":
            plan["transfer_ids"],

        "route":
            route_text,

        "vehicle_id":
            plan["vehicle_id"],

        "vehicle_capacity_kg":
            plan["vehicle_capacity"],

        "vehicle_volume_m3":
            plan["vehicle_volume"],

        "shipment_weight_kg":
            plan["weight"],

        "shipment_volume_m3":
            plan["volume"],

        "weight_utilization_pct":
            plan[
                "weight_utilization"
            ]
            *
            100,

        "volume_utilization_pct":
            plan[
                "volume_utilization"
            ]
            *
            100,

        "overall_utilization_pct":
            plan[
                "overall_utilization"
            ]
            *
            100,

        "fuel_efficiency_kmpl":
            plan[
                "fuel_efficiency"
            ],

        "distance_km":
            plan["distance"],

        "route_time_hours":
            plan["route_time"],

        "departure_hour":
            plan[
                "departure_hour"
            ],

        "arrival_hour":
            plan[
                "arrival_hour"
            ],

        "return_hour":
            plan[
                "return_hour"
            ],

        "fuel_litres":
            plan["fuel"],

        "fuel_cost":
            plan["fuel_cost"],

        "deadline_days":
            plan[
                "deadline_days"
            ],

        "deadline_status":
            plan[
                "deadline_status"
            ]
    })


# ============================================================
# DATAFRAME
# ============================================================

output_df = pd.DataFrame(
    output_rows
)


# ============================================================
# BASELINE CALCULATION
#
# Baseline = each transfer independently.
# Uses the cheapest currently feasible vehicle.
# ============================================================

baseline_cost = 0.0

baseline_distance = 0.0

baseline_fuel = 0.0


for _, transfer in transfers.iterrows():

    source = transfer[
        "source_warehouse"
    ]

    destination = transfer[
        "destination_warehouse"
    ]

    weight = float(
        transfer["weight_kg"]
    )

    volume = float(
        transfer["volume_m3"]
    )

    one_way_distance = get_distance(
        source,
        destination
    )

    if one_way_distance is None:

        continue

    round_trip_distance = (
        one_way_distance
        *
        2
    )

    candidates = vehicles[
        (
            vehicles[
                "warehouse_id"
            ] == source
        )
        &
        (
            vehicles[
                "available"
            ] == 1
        )
    ]

    feasible = candidates[
        (
            candidates[
                "capacity_kg"
            ]
            >= weight
        )
        &
        (
            candidates[
                "volume_capacity_m3"
            ]
            >= volume
        )
    ]

    if feasible.empty:

        continue

    fuel_values = (
        round_trip_distance
        /
        feasible[
            "fuel_efficiency_kmpl"
        ]
    )

    cheapest_fuel = float(
        fuel_values.min()
    )

    baseline_fuel += (
        cheapest_fuel
    )

    baseline_distance += (
        round_trip_distance
    )

    baseline_cost += (
        cheapest_fuel
        *
        FUEL_PRICE_PER_LITRE
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
    -
    assigned_transfers
)

routes_created = len(
    output_df
)


if not output_df.empty:

    total_distance = float(
        output_df[
            "distance_km"
        ].sum()
    )

    total_fuel = float(
        output_df[
            "fuel_litres"
        ].sum()
    )

    optimized_cost = float(
        output_df[
            "fuel_cost"
        ].sum()
    )

    average_weight_utilization = float(
        output_df[
            "weight_utilization_pct"
        ].mean()
    )

    average_volume_utilization = float(
        output_df[
            "volume_utilization_pct"
        ].mean()
    )

else:

    total_distance = 0.0

    total_fuel = 0.0

    optimized_cost = 0.0

    average_weight_utilization = 0.0

    average_volume_utilization = 0.0


estimated_savings = (
    baseline_cost
    -
    optimized_cost
)


if baseline_cost > 0:

    savings_percentage = (
        estimated_savings
        /
        baseline_cost
    ) * 100

else:

    savings_percentage = 0.0


on_time_count = 0
at_risk_count = 0
missed_count = 0


if not output_df.empty:

    on_time_count = len(
        output_df[
            output_df[
                "deadline_status"
            ] == "ON_TIME"
        ]
    )

    at_risk_count = len(
        output_df[
            output_df[
                "deadline_status"
            ] == "AT_RISK"
        ]
    )

    missed_count = len(
        output_df[
            output_df[
                "deadline_status"
            ] == "MISSED_DEADLINE"
        ]
    )


# ============================================================
# PRINT SUMMARY
# ============================================================

print()
print("=" * 50)
print("       V8 OPTIMIZATION SUMMARY")
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
    f"Savings percentage: "
    f"{savings_percentage:.1f}%"
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
    f"ON_TIME routes: {on_time_count}"
)

print(
    f"AT_RISK routes: {at_risk_count}"
)

print(
    f"MISSED_DEADLINE routes: {missed_count}"
)


# ============================================================
# UNASSIGNED
# ============================================================

if unassigned_transfers > 0:

    print()
    print(
        "UNASSIGNED TRANSFERS:"
    )

    unassigned = transfers[
        ~transfers[
            "transfer_id"
        ].isin(
            assigned_ids
        )
    ]

    for transfer_id in unassigned[
        "transfer_id"
    ]:

        print(
            f"⚠️ {transfer_id}"
        )


# ============================================================
# VEHICLE UTILIZATION SUMMARY
# ============================================================

print()
print("=" * 50)
print("       VEHICLE FLEET SUMMARY")
print("=" * 50)

for vehicle_id, state in sorted(
    vehicle_state.items()
):

    if state["trips"] == 0:

        continue

    print(
        f"{vehicle_id} | "
        f"Trips: {state['trips']} | "
        f"Distance: "
        f"{state['total_distance']:.0f} km | "
        f"Fuel: "
        f"{state['total_fuel']:.2f} L"
    )


# ============================================================
# SAVE
# ============================================================

output_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print()
print("=" * 50)
print("V8 OPTIMIZATION COMPLETE")
print("=" * 50)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)