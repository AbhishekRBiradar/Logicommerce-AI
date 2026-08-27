import pandas as pd
from ortools.constraint_solver import (
    pywrapcp,
    routing_enums_pb2
)


# ============================================================
# CONFIGURATION
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
# VEHICLE UTILIZATION
# ============================================================

def calculate_utilization(
    weight,
    volume,
    vehicle
):

    weight_capacity = float(
        vehicle["capacity_kg"]
    )

    volume_capacity = float(
        vehicle["volume_capacity_m3"]
    )

    if weight_capacity <= 0:
        weight_utilization = 0

    else:
        weight_utilization = (
            weight / weight_capacity
        )

    if volume_capacity <= 0:
        volume_utilization = 0

    else:
        volume_utilization = (
            volume / volume_capacity
        )

    overall = (
        weight_utilization
        +
        volume_utilization
    ) / 2

    return (
        weight_utilization,
        volume_utilization,
        overall
    )


# ============================================================
# ROUTE DISTANCE
# ============================================================

def calculate_route_distance(
    route
):

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
# OR-TOOLS STOP ORDER OPTIMIZER
# ============================================================

def optimize_stop_order(
    source,
    destinations
):

    unique_destinations = []

    for destination in destinations:

        if destination not in unique_destinations:

            unique_destinations.append(
                destination
            )

    if not unique_destinations:

        return [source, source]


    nodes = [
        source
    ] + unique_destinations


    number_of_nodes = len(nodes)


    matrix = []

    for from_node in nodes:

        row = []

        for to_node in nodes:

            distance = get_distance(
                from_node,
                to_node
            )

            if distance == float("inf"):

                distance = 999999

            row.append(
                int(round(distance))
            )

        matrix.append(row)


    manager = (
        pywrapcp.RoutingIndexManager(
            number_of_nodes,
            1,
            0
        )
    )


    routing = (
        pywrapcp.RoutingModel(
            manager
        )
    )


    def distance_callback(
        from_index,
        to_index
    ):

        from_node = (
            manager.IndexToNode(
                from_index
            )
        )

        to_node = (
            manager.IndexToNode(
                to_index
            )
        )

        return matrix[
            from_node
        ][
            to_node
        ]


    callback_index = (
        routing.RegisterTransitCallback(
            distance_callback
        )
    )


    routing.SetArcCostEvaluatorOfAllVehicles(
        callback_index
    )


    parameters = (
        pywrapcp.DefaultRoutingSearchParameters()
    )


    parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy
        .PATH_CHEAPEST_ARC
    )


    parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic
        .GUIDED_LOCAL_SEARCH
    )


    parameters.time_limit.seconds = 2


    solution = routing.SolveWithParameters(
        parameters
    )


    if solution is None:

        return None


    index = routing.Start(0)

    route = []


    while not routing.IsEnd(index):

        node = (
            manager.IndexToNode(index)
        )

        route.append(
            nodes[node]
        )

        index = solution.Value(
            routing.NextVar(index)
        )


    route.append(source)


    return route


# ============================================================
# BUILD CANDIDATE ROUTES
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       GLOBAL ROUTE OPTIMIZATION V3"
)

print(
    "=========================================="
)


candidate_routes = []


# ============================================================
# GENERATE CANDIDATES FOR EACH SOURCE
# ============================================================

for source in warehouses:

    source_transfers = transfers[
        transfers[
            "source_warehouse"
        ]
        == source
    ].copy()


    if source_transfers.empty:

        continue


    source_vehicles = vehicles[
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


    if source_vehicles.empty:

        continue


    print()
    print(
        "------------------------------------------"
    )

    print(
        f"Source warehouse: {source}"
    )

    print(
        f"Transfers: "
        f"{len(source_transfers)}"
    )


    # --------------------------------------------------------
    # Generate individual shipment candidates
    # --------------------------------------------------------

    for _, transfer in (
        source_transfers.iterrows()
    ):

        destination = (
            transfer[
                "destination_warehouse"
            ]
        )


        shipment_weight = float(
            transfer[
                "weight_kg"
            ]
        )


        shipment_volume = float(
            transfer[
                "volume_m3"
            ]
        )


        deadline = float(
            transfer[
                "deadline_days"
            ]
        )


        for _, vehicle in (
            source_vehicles.iterrows()
        ):

            vehicle_weight_capacity = float(
                vehicle[
                    "capacity_kg"
                ]
            )


            vehicle_volume_capacity = float(
                vehicle[
                    "volume_capacity_m3"
                ]
            )


            if (
                shipment_weight
                > vehicle_weight_capacity
            ):

                continue


            if (
                shipment_volume
                > vehicle_volume_capacity
            ):

                continue


            route = optimize_stop_order(

                source,

                [destination]

            )


            if route is None:

                continue


            distance = (
                calculate_route_distance(
                    route
                )
            )


            if distance == float("inf"):

                continue


            driving_hours = (
                distance
                / AVERAGE_SPEED_KMPH
            )


            route_hours = (
                driving_hours
                + SERVICE_TIME_HOURS
            )


            if (
                route_hours
                > MAX_ROUTE_HOURS
            ):

                continue


            fuel_efficiency = float(
                vehicle[
                    "fuel_efficiency_kmpl"
                ]
            )


            fuel_litres = (
                distance
                / fuel_efficiency
            )


            fuel_cost = (
                fuel_litres
                * FUEL_PRICE_PER_LITRE
            )


            (
                weight_utilization,
                volume_utilization,
                overall_utilization
            ) = calculate_utilization(

                shipment_weight,

                shipment_volume,

                vehicle

            )


            # ------------------------------------------------
            # Deadline risk
            # ------------------------------------------------

            if route_hours <= deadline * 24:

                deadline_status = (
                    "ON_TIME"
                )

            else:

                deadline_status = (
                    "MISSED_DEADLINE"
                )


            candidate_routes.append({

                "transfer_id":
                    transfer[
                        "transfer_id"
                    ],

                "source":
                    source,

                "destination":
                    destination,

                "route":
                    " → ".join(route),

                "vehicle_id":
                    vehicle[
                        "vehicle_id"
                    ],

                "weight_kg":
                    shipment_weight,

                "volume_m3":
                    shipment_volume,

                "distance_km":
                    distance,

                "route_hours":
                    route_hours,

                "fuel_litres":
                    fuel_litres,

                "fuel_cost":
                    fuel_cost,

                "weight_utilization":
                    weight_utilization,

                "volume_utilization":
                    volume_utilization,

                "overall_utilization":
                    overall_utilization,

                "deadline_days":
                    deadline,

                "deadline_status":
                    deadline_status

            })


# ============================================================
# GLOBAL ASSIGNMENT
# ============================================================

candidate_df = pd.DataFrame(
    candidate_routes
)


print()
print(
    "=========================================="
)

print(
    "       GLOBAL ASSIGNMENT"
)

print(
    "=========================================="
)


selected_routes = []

assigned_transfer_ids = set()


# ============================================================
# PRIORITY ORDER
# ============================================================

priority_order = {

    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2

}


transfer_priority = (
    transfers[
        [
            "transfer_id",
            "priority",
            "deadline_days"
        ]
    ]
    .copy()
)


transfer_priority[
    "priority_rank"
] = transfer_priority[
    "priority"
].map(
    priority_order
).fillna(3)


transfer_priority = (
    transfer_priority
    .sort_values(
        [
            "priority_rank",
            "deadline_days"
        ]
    )
)


# ============================================================
# ASSIGN SHIPMENTS
# ============================================================

for _, transfer in (
    transfer_priority.iterrows()
):

    transfer_id = (
        transfer[
            "transfer_id"
        ]
    )


    if transfer_id in assigned_transfer_ids:

        continue


    candidates = candidate_df[
        candidate_df[
            "transfer_id"
        ]
        == transfer_id
    ].copy()


    if candidates.empty:

        continue


    # --------------------------------------------------------
    # Score candidates
    # --------------------------------------------------------

    candidates[
        "score"
    ] = (

        candidates[
            "fuel_cost"
        ]

        +

        candidates[
            "distance_km"
        ]
        * 0.10

        -

        candidates[
            "overall_utilization"
        ]
        * 300

    )


    # Strong penalty for missed deadline

    candidates.loc[
        candidates[
            "deadline_status"
        ]
        == "MISSED_DEADLINE",
        "score"
    ] += 100000


    candidates = (
        candidates
        .sort_values(
            "score"
        )
    )


    best = (
        candidates.iloc[0]
    )


    selected_routes.append(
        best.to_dict()
    )


    assigned_transfer_ids.add(
        transfer_id
    )


# ============================================================
# UNASSIGNED TRANSFERS
# ============================================================

all_transfer_ids = set(
    transfers[
        "transfer_id"
    ]
)


unassigned = (
    all_transfer_ids
    -
    assigned_transfer_ids
)


# ============================================================
# SAVE RESULTS
# ============================================================

result_df = pd.DataFrame(
    selected_routes
)


output_file = (
    f"{DATA_DIR}/route_optimization_v3.csv"
)


result_df.to_csv(
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
    "       FINAL ROUTE ASSIGNMENT"
)

print(
    "=========================================="
)


if not result_df.empty:

    for _, row in (
        result_df.iterrows()
    ):

        print()
        print(
            "------------------------------------------"
        )

        print(
            f"Transfer: "
            f"{row['transfer_id']}"
        )

        print(
            f"Route: "
            f"{row['route']}"
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
            f"Distance: "
            f"{row['distance_km']:.0f} km"
        )

        print(
            f"Fuel: "
            f"{row['fuel_litres']:.2f} L"
        )

        print(
            f"Fuel cost: "
            f"₹{row['fuel_cost']:.2f}"
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
            f"Deadline: "
            f"{row['deadline_status']}"
        )


# ============================================================
# SUMMARY
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       GLOBAL OPTIMIZATION SUMMARY"
)

print(
    "=========================================="
)


print(
    f"Total transfers: "
    f"{len(all_transfer_ids)}"
)


print(
    f"Assigned transfers: "
    f"{len(assigned_transfer_ids)}"
)


print(
    f"Unassigned transfers: "
    f"{len(unassigned)}"
)


if not result_df.empty:

    print(
        f"Total distance: "
        f"{result_df['distance_km'].sum():.2f} km"
    )

    print(
        f"Total fuel: "
        f"{result_df['fuel_litres'].sum():.2f} L"
    )

    print(
        f"Total fuel cost: "
        f"₹{result_df['fuel_cost'].sum():.2f}"
    )

    print(
        f"Average weight utilization: "
        f"{result_df['weight_utilization'].mean() * 100:.1f}%"
    )

    print(
        f"Average volume utilization: "
        f"{result_df['volume_utilization'].mean() * 100:.1f}%"
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
    "Saved to:"
)

print(
    output_file
)