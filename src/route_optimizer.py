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

transfers["weight_kg"] = pd.to_numeric(
    transfers["weight_kg"],
    errors="coerce"
).fillna(0)

transfers["volume_m3"] = pd.to_numeric(
    transfers["volume_m3"],
    errors="coerce"
).fillna(0)

transfers["quantity"] = pd.to_numeric(
    transfers["quantity"],
    errors="coerce"
).fillna(0)

vehicles["capacity_kg"] = pd.to_numeric(
    vehicles["capacity_kg"],
    errors="coerce"
).fillna(0)

vehicles["volume_capacity_m3"] = pd.to_numeric(
    vehicles["volume_capacity_m3"],
    errors="coerce"
).fillna(0)

vehicles["fuel_efficiency_kmpl"] = pd.to_numeric(
    vehicles["fuel_efficiency_kmpl"],
    errors="coerce"
).fillna(1)


# ============================================================
# WAREHOUSE NETWORK
# ============================================================

warehouse_names = sorted(
    set(
        distances["source_warehouse"]
    )
    |
    set(
        distances["destination_warehouse"]
    )
)


warehouse_index = {
    name: index
    for index, name in enumerate(
        warehouse_names
    )
}


# ============================================================
# DISTANCE LOOKUP
# ============================================================

distance_lookup = {}

for _, row in distances.iterrows():

    source = row[
        "source_warehouse"
    ]

    destination = row[
        "destination_warehouse"
    ]

    distance_lookup[
        (source, destination)
    ] = float(
        row["distance_km"]
    )


def get_distance(
    source,
    destination
):

    return distance_lookup.get(
        (source, destination),
        float("inf")
    )


# ============================================================
# VEHICLE ROUTE SOLVER
# ============================================================

def solve_vehicle_route(
    source,
    shipments,
    vehicle
):

    # --------------------------------------------------------
    # Find destinations
    # --------------------------------------------------------

    destinations = []

    for _, shipment in (
        shipments.iterrows()
    ):

        destination = (
            shipment[
                "destination_warehouse"
            ]
        )

        if destination not in destinations:

            destinations.append(
                destination
            )


    if not destinations:

        return None


    # --------------------------------------------------------
    # Source is depot
    # --------------------------------------------------------

    nodes = [
        source
    ] + destinations


    number_of_nodes = len(nodes)


    # --------------------------------------------------------
    # Build distance matrix
    # --------------------------------------------------------

    matrix = []

    for from_node in nodes:

        row = []

        for to_node in nodes:

            if from_node == to_node:

                distance = 0

            else:

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


    # --------------------------------------------------------
    # OR-Tools routing model
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Distance callback
    # --------------------------------------------------------

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


    distance_callback_index = (
        routing.RegisterTransitCallback(
            distance_callback
        )
    )


    routing.SetArcCostEvaluatorOfAllVehicles(
        distance_callback_index
    )


    # --------------------------------------------------------
    # Search configuration
    # --------------------------------------------------------

    search_parameters = (
        pywrapcp.DefaultRoutingSearchParameters()
    )


    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy
        .PATH_CHEAPEST_ARC
    )


    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic
        .GUIDED_LOCAL_SEARCH
    )


    search_parameters.time_limit.seconds = 3


    # --------------------------------------------------------
    # Solve
    # --------------------------------------------------------

    solution = routing.SolveWithParameters(
        search_parameters
    )


    if solution is None:

        return None


    # --------------------------------------------------------
    # Extract route
    # --------------------------------------------------------

    index = routing.Start(0)

    route = []

    total_distance = 0


    while not routing.IsEnd(index):

        node = (
            manager.IndexToNode(
                index
            )
        )

        route.append(
            nodes[node]
        )

        previous_index = index

        index = solution.Value(
            routing.NextVar(index)
        )

        total_distance += (
            routing.GetArcCostForVehicle(
                previous_index,
                index,
                0
            )
        )


    # Return to source

    route.append(source)


    # --------------------------------------------------------
    # Shipment totals
    # --------------------------------------------------------

    total_weight = float(
        shipments[
            "weight_kg"
        ].sum()
    )


    total_volume = float(
        shipments[
            "volume_m3"
        ].sum()
    )


    vehicle_capacity = float(
        vehicle[
            "capacity_kg"
        ]
    )


    vehicle_volume = float(
        vehicle[
            "volume_capacity_m3"
        ]
    )


    # --------------------------------------------------------
    # Capacity checks
    # --------------------------------------------------------

    weight_feasible = (
        total_weight
        <= vehicle_capacity
    )


    volume_feasible = (
        total_volume
        <= vehicle_volume
    )


    # --------------------------------------------------------
    # Route time
    # --------------------------------------------------------

    driving_hours = (
        total_distance
        / AVERAGE_SPEED_KMPH
    )


    number_of_stops = len(
        destinations
    )


    service_hours = (
        number_of_stops
        * SERVICE_TIME_HOURS
    )


    route_hours = (
        driving_hours
        + service_hours
    )


    time_feasible = (
        route_hours
        <= MAX_ROUTE_HOURS
    )


    # --------------------------------------------------------
    # Fuel
    # --------------------------------------------------------

    fuel_efficiency = float(
        vehicle[
            "fuel_efficiency_kmpl"
        ]
    )


    fuel_litres = (
        total_distance
        / fuel_efficiency
    )


    fuel_cost = (
        fuel_litres
        * FUEL_PRICE_PER_LITRE
    )


    # --------------------------------------------------------
    # Utilization
    # --------------------------------------------------------

    weight_utilization = (
        total_weight
        / vehicle_capacity
    )


    volume_utilization = (
        total_volume
        / vehicle_volume
    )


    overall_utilization = (
        weight_utilization
        + volume_utilization
    ) / 2


    # --------------------------------------------------------
    # Feasibility
    # --------------------------------------------------------

    feasible = (
        weight_feasible
        and volume_feasible
        and time_feasible
    )


    return {

        "source":
            source,

        "route":
            " → ".join(route),

        "stops":
            number_of_stops,

        "distance_km":
            total_distance,

        "route_hours":
            route_hours,

        "weight_kg":
            total_weight,

        "volume_m3":
            total_volume,

        "vehicle_id":
            vehicle[
                "vehicle_id"
            ],

        "vehicle_capacity_kg":
            vehicle_capacity,

        "vehicle_volume_m3":
            vehicle_volume,

        "weight_utilization":
            weight_utilization,

        "volume_utilization":
            volume_utilization,

        "overall_utilization":
            overall_utilization,

        "fuel_efficiency_kmpl":
            fuel_efficiency,

        "fuel_litres":
            fuel_litres,

        "fuel_cost":
            fuel_cost,

        "weight_feasible":
            weight_feasible,

        "volume_feasible":
            volume_feasible,

        "time_feasible":
            time_feasible,

        "feasible":
            feasible

    }


# ============================================================
# BUILD MULTI-VEHICLE CANDIDATES
# ============================================================

print()
print(
    "=========================================="
)

print(
    "      MULTI-VEHICLE ROUTE OPTIMIZER"
)

print(
    "=========================================="
)


route_results = []


# ============================================================
# PROCESS EACH SOURCE
# ============================================================

for source in warehouse_names:

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
        f"Source: {source}"
    )

    print(
        f"Shipments: "
        f"{len(source_shipments)}"
    )


    # --------------------------------------------------------
    # Available vehicles
    # --------------------------------------------------------

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

        print(
            "⚠️ No available vehicles."
        )

        continue


    # --------------------------------------------------------
    # Track remaining shipments
    # --------------------------------------------------------

    remaining = source_shipments.copy()

    route_number = 1


    # ========================================================
    # BUILD MULTIPLE ROUTES
    # ========================================================

    while not remaining.empty:

        best_candidate = None

        best_score = float("inf")


        # ----------------------------------------------------
        # Try every vehicle
        # ----------------------------------------------------

        for _, vehicle in (
            source_vehicles.iterrows()
        ):

            # ----------------------------------------------
            # Sort shipments by volume/weight importance
            # ----------------------------------------------

            candidate_rows = []

            current_weight = 0.0
            current_volume = 0.0


            for index, shipment in (
                remaining.iterrows()
            ):

                shipment_weight = float(
                    shipment[
                        "weight_kg"
                    ]
                )

                shipment_volume = float(
                    shipment[
                        "volume_m3"
                    ]
                )


                if (
                    current_weight
                    + shipment_weight
                    <= float(
                        vehicle[
                            "capacity_kg"
                        ]
                    )
                    and
                    current_volume
                    + shipment_volume
                    <= float(
                        vehicle[
                            "volume_capacity_m3"
                        ]
                    )
                ):

                    candidate_rows.append(
                        index
                    )

                    current_weight += (
                        shipment_weight
                    )

                    current_volume += (
                        shipment_volume
                    )


            if not candidate_rows:

                continue


            candidate_shipments = (
                remaining.loc[
                    candidate_rows
                ].copy()
            )


            route = solve_vehicle_route(

                source,

                candidate_shipments,

                vehicle

            )


            if route is None:

                continue


            if not route[
                "feasible"
            ]:

                continue


            # ------------------------------------------------
            # Optimization score
            # ------------------------------------------------

            # Lower fuel is better.

            fuel_score = (
                route[
                    "fuel_cost"
                ]
            )


            # Higher utilization is better.

            utilization_bonus = (
                route[
                    "overall_utilization"
                ]
                * 500
            )


            score = (
                fuel_score
                - utilization_bonus
            )


            if score < best_score:

                best_score = score

                best_candidate = {

                    "route":
                        route,

                    "shipment_indexes":
                        candidate_rows

                }


        # ----------------------------------------------------
        # No route possible
        # ----------------------------------------------------

        if best_candidate is None:

            print(
                "⚠️ Remaining shipments "
                "cannot currently be routed."
            )

            break


        # ----------------------------------------------------
        # Save route
        # ----------------------------------------------------

        route = (
            best_candidate[
                "route"
            ]
        )


        shipment_indexes = (
            best_candidate[
                "shipment_indexes"
            ]
        )


        selected_shipments = (
            remaining.loc[
                shipment_indexes
            ]
        )


        transfer_ids = ",".join(
            selected_shipments[
                "transfer_id"
            ].astype(str)
        )


        route_results.append({

            **route,

            "route_number":
                route_number,

            "transfer_ids":
                transfer_ids,

            "shipment_count":
                len(
                    selected_shipments
                )

        })


        print()

        print(
            f"🏆 ROUTE {route_number}"
        )

        print(
            f"Route: "
            f"{route['route']}"
        )

        print(
            f"Transfers: "
            f"{transfer_ids}"
        )

        print(
            f"Vehicle: "
            f"{route['vehicle_id']}"
        )

        print(
            f"Distance: "
            f"{route['distance_km']} km"
        )

        print(
            f"Route time: "
            f"{route['route_hours']:.2f} hours"
        )

        print(
            f"Weight: "
            f"{route['weight_kg']:.2f} kg"
        )

        print(
            f"Volume: "
            f"{route['volume_m3']:.3f} m³"
        )

        print(
            f"Weight utilization: "
            f"{route['weight_utilization'] * 100:.1f}%"
        )

        print(
            f"Volume utilization: "
            f"{route['volume_utilization'] * 100:.1f}%"
        )

        print(
            f"Fuel: "
            f"{route['fuel_litres']:.2f} L"
        )

        print(
            f"Fuel cost: "
            f"₹{route['fuel_cost']:.2f}"
        )


        # ----------------------------------------------------
        # Remove assigned shipments
        # ----------------------------------------------------

        remaining = remaining.drop(
            shipment_indexes
        )


        route_number += 1


# ============================================================
# SAVE
# ============================================================

result_df = pd.DataFrame(
    route_results
)


output_file = (
    f"{DATA_DIR}/route_optimization.csv"
)


result_df.to_csv(
    output_file,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print()
print(
    "=========================================="
)

print(
    "       ROUTE OPTIMIZATION SUMMARY"
)

print(
    "=========================================="
)


print(
    f"Routes created: "
    f"{len(result_df)}"
)


if not result_df.empty:

    print(
        f"Transfers covered: "
        f"{result_df['shipment_count'].sum()}"
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


print()
print(
    "Saved to:"
)

print(
    output_file
)