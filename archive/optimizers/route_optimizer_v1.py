import pandas as pd
import math

from ortools.constraint_solver import (
    pywrapcp,
    routing_enums_pb2
)


# ==========================================
# CONFIGURATION
# ==========================================

DATA_DIR = "data"

FUEL_PRICE_PER_LITRE = 100.0

AVERAGE_SPEED_KMPH = 40.0

MAX_ROUTE_HOURS = 24.0


# ==========================================
# LOAD DATA
# ==========================================

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


# ==========================================
# WAREHOUSE LIST
# ==========================================

warehouses = sorted(
    set(
        distances["source_warehouse"]
    )
    |
    set(
        distances["destination_warehouse"]
    )
)

warehouse_index = {
    warehouse: i
    for i, warehouse
    in enumerate(warehouses)
}


# ==========================================
# DISTANCE MATRIX
# ==========================================

num_warehouses = len(
    warehouses
)

distance_matrix = [
    [0] * num_warehouses
    for _ in range(num_warehouses)
]


for _, row in distances.iterrows():

    source = row[
        "source_warehouse"
    ]

    destination = row[
        "destination_warehouse"
    ]

    distance_matrix[
        warehouse_index[source]
    ][
        warehouse_index[destination]
    ] = int(
        round(
            float(
                row["distance_km"]
            )
        )
    )


# ==========================================
# DISPLAY NETWORK
# ==========================================

print()
print(
    "=========================================="
)

print(
    "        WAREHOUSE NETWORK"
)

print(
    "=========================================="
)

print(
    warehouses
)


# ==========================================
# ROUTE SOLVER
# ==========================================

def solve_route(
    source,
    shipment_rows,
    vehicle
):

    # --------------------------------------
    # Source must be first and last
    # --------------------------------------

    destination_nodes = []

    for _, shipment in (
        shipment_rows.iterrows()
    ):

        destination = (
            shipment[
                "destination_warehouse"
            ]
        )

        if destination not in (
            destination_nodes
        ):

            destination_nodes.append(
                destination
            )


    # If there are no destinations
    if not destination_nodes:

        return None


    route_locations = [
        source
    ] + destination_nodes


    # --------------------------------------
    # Create local distance matrix
    # --------------------------------------

    local_matrix = []

    for from_location in (
        route_locations
    ):

        row = []

        for to_location in (
            route_locations
        ):

            distance = (
                distance_matrix[
                    warehouse_index[
                        from_location
                    ]
                ][
                    warehouse_index[
                        to_location
                    ]
                ]
            )

            row.append(
                distance
            )

        local_matrix.append(
            row
        )


    # --------------------------------------
    # OR-Tools manager
    # --------------------------------------

    manager = (
        pywrapcp.RoutingIndexManager(
            len(route_locations),
            1,
            0
        )
    )


    routing = (
        pywrapcp.RoutingModel(
            manager
        )
    )


    # --------------------------------------
    # Distance callback
    # --------------------------------------

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

        return local_matrix[
            from_node
        ][
            to_node
        ]


    transit_callback_index = (
        routing.RegisterTransitCallback(
            distance_callback
        )
    )


    routing.SetArcCostEvaluatorOfAllVehicles(
        transit_callback_index
    )


    # --------------------------------------
    # Search parameters
    # --------------------------------------

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


    search_parameters.time_limit.seconds = 5


    # --------------------------------------
    # Solve
    # --------------------------------------

    solution = routing.SolveWithParameters(
        search_parameters
    )


    if solution is None:

        return None


    # --------------------------------------
    # Extract route
    # --------------------------------------

    index = routing.Start(
        0
    )

    route = []

    total_distance = 0


    while not routing.IsEnd(
        index
    ):

        node = (
            manager.IndexToNode(
                index
            )
        )

        route.append(
            route_locations[node]
        )

        previous_index = index

        index = solution.Value(
            routing.NextVar(
                index
            )
        )

        total_distance += (
            routing.GetArcCostForVehicle(
                previous_index,
                index,
                0
            )
        )


    # Add final warehouse

    route.append(
        route_locations[
            manager.IndexToNode(
                index
            )
        ]
    )


    # --------------------------------------
    # Route time
    # --------------------------------------

    route_hours = (
        total_distance
        / AVERAGE_SPEED_KMPH
    )


    route_hours += 0.5


    # --------------------------------------
    # Fuel
    # --------------------------------------

    fuel_efficiency = float(
        vehicle[
            "fuel_efficiency_kmpl"
        ]
    )


    fuel_required = (
        total_distance
        / fuel_efficiency
    )


    fuel_cost = (
        fuel_required
        * FUEL_PRICE_PER_LITRE
    )


    # --------------------------------------
    # Shipment totals
    # --------------------------------------

    total_weight = (
        shipment_rows[
            "weight_kg"
        ].sum()
    )


    total_volume = (
        shipment_rows[
            "volume_m3"
        ].sum()
    )


    weight_capacity = float(
        vehicle[
            "capacity_kg"
        ]
    )


    volume_capacity = float(
        vehicle[
            "volume_capacity_m3"
        ]
    )


    weight_utilization = (
        total_weight
        / weight_capacity
    )


    volume_utilization = (
        total_volume
        / volume_capacity
    )


    # --------------------------------------
    # Feasibility
    # --------------------------------------

    weight_ok = (
        total_weight
        <= weight_capacity
    )


    volume_ok = (
        total_volume
        <= volume_capacity
    )


    time_ok = (
        route_hours
        <= MAX_ROUTE_HOURS
    )


    feasible = (
        weight_ok
        and volume_ok
        and time_ok
    )


    return {

        "source":
            source,

        "route":
            " → ".join(route),

        "stops":
            len(destination_nodes),

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
            weight_capacity,

        "vehicle_volume_m3":
            volume_capacity,

        "weight_utilization":
            weight_utilization,

        "volume_utilization":
            volume_utilization,

        "fuel_efficiency_kmpl":
            fuel_efficiency,

        "fuel_litres":
            fuel_required,

        "fuel_cost":
            fuel_cost,

        "weight_feasible":
            weight_ok,

        "volume_feasible":
            volume_ok,

        "time_feasible":
            time_ok,

        "feasible":
            feasible

    }


# ==========================================
# OPTIMIZE EACH SOURCE
# ==========================================

print()
print(
    "=========================================="
)

print(
    "        OR-TOOLS ROUTE OPTIMIZER"
)

print(
    "=========================================="
)


route_results = []


for source in warehouses:

    source_shipments = transfers[
        transfers[
            "source_warehouse"
        ]
        == source
    ]


    if source_shipments.empty:

        continue


    print()
    print(
        "------------------------------------------"
    )

    print(
        f"Source warehouse: {source}"
    )


    # --------------------------------------
    # Find available vehicles
    # --------------------------------------

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
    ]


    if source_vehicles.empty:

        print(
            "⚠️ No available vehicles."
        )

        continue


    best_route = None


    # --------------------------------------
    # Try each available vehicle
    # --------------------------------------

    for _, vehicle in (
        source_vehicles.iterrows()
    ):

        route = solve_route(

            source,

            source_shipments,

            vehicle

        )


        if route is None:

            continue


        if not route[
            "feasible"
        ]:

            continue


        # ----------------------------------
        # Choose lowest fuel cost
        # ----------------------------------

        if (
            best_route is None
            or
            route[
                "fuel_cost"
            ]
            < best_route[
                "fuel_cost"
            ]
        ):

            best_route = route


    # --------------------------------------
    # No feasible route
    # --------------------------------------

    if best_route is None:

        print(
            "⚠️ No feasible route found."
        )

        continue


    route_results.append(
        best_route
    )


    # --------------------------------------
    # Display result
    # --------------------------------------

    print()

    print(
        "🏆 OPTIMAL ROUTE"
    )

    print(
        f"Route: "
        f"{best_route['route']}"
    )

    print(
        f"Stops: "
        f"{best_route['stops']}"
    )

    print(
        f"Distance: "
        f"{best_route['distance_km']} km"
    )

    print(
        f"Route time: "
        f"{best_route['route_hours']:.2f} hours"
    )

    print(
        f"Vehicle: "
        f"{best_route['vehicle_id']}"
    )

    print(
        f"Shipment weight: "
        f"{best_route['weight_kg']:.2f} kg"
    )

    print(
        f"Shipment volume: "
        f"{best_route['volume_m3']:.3f} m³"
    )

    print(
        f"Weight utilization: "
        f"{best_route['weight_utilization'] * 100:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{best_route['volume_utilization'] * 100:.1f}%"
    )

    print(
        f"Fuel required: "
        f"{best_route['fuel_litres']:.2f} L"
    )

    print(
        f"Fuel cost: "
        f"₹{best_route['fuel_cost']:.2f}"
    )


# ==========================================
# SAVE RESULTS
# ==========================================

result_df = pd.DataFrame(
    route_results
)


result_df.to_csv(

    f"{DATA_DIR}/route_optimization.csv",

    index=False

)


# ==========================================
# SUMMARY
# ==========================================

print()
print(
    "=========================================="
)

print(
    "        ROUTE OPTIMIZATION SUMMARY"
)

print(
    "=========================================="
)


print(
    f"Optimized routes: "
    f"{len(result_df)}"
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


print()
print(
    "Saved to:"
)

print(
    "data/route_optimization.csv"
)