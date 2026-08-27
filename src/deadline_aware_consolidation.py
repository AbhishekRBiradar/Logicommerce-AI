import pandas as pd


# ==========================================
# CONFIGURATION
# ==========================================

DATA_DIR = "data"

FUEL_PRICE_PER_LITRE = 100.0

# Maximum time we are willing to wait for
# consolidation.
MAX_CONSOLIDATION_WAIT_DAYS = 2


# ==========================================
# LOAD DATA
# ==========================================

print("Loading transfer requests...")

requests = pd.read_csv(
    f"{DATA_DIR}/transfer_requests.csv"
)

vehicles = pd.read_csv(
    f"{DATA_DIR}/vehicles.csv"
)

distances = pd.read_csv(
    f"{DATA_DIR}/warehouse_distances.csv"
)


# ==========================================
# PRIORITY WEIGHTS
# ==========================================

PRIORITY_WEIGHT = {

    "HIGH": 3,

    "MEDIUM": 2,

    "LOW": 1

}


# ==========================================
# URGENCY SCORE
# ==========================================

def calculate_urgency(
    priority,
    deadline_days
):

    priority_score = (
        PRIORITY_WEIGHT.get(
            priority,
            1
        )
    )

    # Smaller deadline = greater urgency.
    deadline_score = (
        6 - deadline_days
    )

    if deadline_score < 1:
        deadline_score = 1


    urgency = (

        priority_score * 2

        +

        deadline_score

    )


    return urgency


# ==========================================
# CLASSIFY SHIPMENT
# ==========================================

def classify_shipment(
    priority,
    deadline_days
):

    # Immediate dispatch conditions.

    if priority == "HIGH":

        if deadline_days <= 1:

            return "URGENT"


    if deadline_days <= 1:

        return "URGENT"


    # Short deadline.

    if deadline_days == 2:

        return "SOON"


    return "NORMAL"


# ==========================================
# DISTANCE
# ==========================================

def get_distance(
    source,
    destination
):

    result = distances[
        (
            distances[
                "source_warehouse"
            ]
            == source
        )
        &
        (
            distances[
                "destination_warehouse"
            ]
            == destination
        )
    ]


    if result.empty:

        return None


    return float(
        result.iloc[0][
            "distance_km"
        ]
    )


# ==========================================
# FUEL CALCULATION
# ==========================================

def calculate_fuel(
    vehicle,
    distance_km
):

    efficiency = float(
        vehicle[
            "fuel_efficiency_kmpl"
        ]
    )

    fuel = (
        distance_km
        / efficiency
    )

    cost = (
        fuel
        * FUEL_PRICE_PER_LITRE
    )

    return fuel, cost


# ==========================================
# BEST VEHICLE
# ==========================================

def find_vehicle(
    source,
    weight,
    volume,
    distance
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
        &
        (
            vehicles[
                "capacity_kg"
            ]
            >= weight
        )
        &
        (
            vehicles[
                "volume_capacity_m3"
            ]
            >= volume
        )
    ]


    if candidates.empty:

        return None


    best = None

    best_cost = float(
        "inf"
    )


    for _, vehicle in (
        candidates.iterrows()
    ):

        fuel, cost = calculate_fuel(

            vehicle,

            distance

        )


        weight_utilization = (

            weight
            / float(
                vehicle[
                    "capacity_kg"
                ]
            )

        )


        volume_utilization = (

            volume
            / float(
                vehicle[
                    "volume_capacity_m3"
                ]
            )

        )


        utilization = (

            weight_utilization
            +
            volume_utilization

        ) / 2


        # Small penalty for wasting capacity.

        score = (

            cost

            +

            (
                1
                - utilization
            )
            * 100

        )


        if score < best_cost:

            best_cost = score


            best = {

                "vehicle_id":
                    vehicle[
                        "vehicle_id"
                    ],

                "capacity_kg":
                    float(
                        vehicle[
                            "capacity_kg"
                        ]
                    ),

                "volume_capacity_m3":
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
                    ),

                "weight_utilization":
                    weight_utilization,

                "volume_utilization":
                    volume_utilization,

                "overall_utilization":
                    utilization,

                "fuel":
                    fuel,

                "cost":
                    cost

            }


    return best


# ==========================================
# PREPARE REQUEST DATA
# ==========================================

requests[
    "urgency_score"
] = requests.apply(

    lambda row:
        calculate_urgency(

            row["priority"],

            int(
                row["deadline_days"]
            )

        ),

    axis=1

)


requests[
    "urgency_class"
] = requests.apply(

    lambda row:
        classify_shipment(

            row["priority"],

            int(
                row["deadline_days"]
            )

        ),

    axis=1

)


# ==========================================
# ANALYZE GROUP
# ==========================================

def analyze_route_group(
    source,
    destination,
    group
):

    distance = get_distance(

        source,

        destination

    )


    if distance is None:

        return None


    # ======================================
    # SPLIT BY URGENCY
    # ======================================

    urgent = group[
        group[
            "urgency_class"
        ]
        == "URGENT"
    ]


    soon = group[
        group[
            "urgency_class"
        ]
        == "SOON"
    ]


    normal = group[
        group[
            "urgency_class"
        ]
        == "NORMAL"
    ]


    plans = []


    # ======================================
    # URGENT SHIPMENTS
    # ======================================
    #
    # Do not wait for consolidation.
    #

    for _, shipment in (
        urgent.iterrows()
    ):

        weight = float(
            shipment[
                "weight_kg"
            ]
        )

        volume = float(
            shipment[
                "volume_m3"
            ]
        )


        vehicle = find_vehicle(

            source,

            weight,

            volume,

            distance

        )


        plans.append({

            "type":
                "URGENT_DISPATCH",

            "transfer_id":
                shipment[
                    "transfer_id"
                ],

            "source":
                source,

            "destination":
                destination,

            "weight":
                weight,

            "volume":
                volume,

            "priority":
                shipment[
                    "priority"
                ],

            "deadline":
                shipment[
                    "deadline_days"
                ],

            "vehicle":
                vehicle

        })


    # ======================================
    # SOON + NORMAL
    # ======================================

    waiting_group = pd.concat(

        [
            soon,
            normal
        ]

    )


    if not waiting_group.empty:

        total_weight = float(
            waiting_group[
                "weight_kg"
            ].sum()
        )

        total_volume = float(
            waiting_group[
                "volume_m3"
            ].sum()
        )


        vehicle = find_vehicle(

            source,

            total_weight,

            total_volume,

            distance

        )


        if vehicle is not None:

            # --------------------------------
            # Calculate separate cost
            # --------------------------------

            separate_cost = 0.0

            separate_fuel = 0.0

            separate_count = 0


            for _, shipment in (
                waiting_group.iterrows()
            ):

                single_vehicle = (
                    find_vehicle(

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
                )


                if single_vehicle is not None:

                    separate_cost += (
                        single_vehicle[
                            "cost"
                        ]
                    )

                    separate_fuel += (
                        single_vehicle[
                            "fuel"
                        ]
                    )

                    separate_count += 1


            consolidated_cost = (
                vehicle[
                    "cost"
                ]
            )

            consolidated_fuel = (
                vehicle[
                    "fuel"
                ]
            )


            if separate_cost > 0:

                savings = (
                    separate_cost
                    - consolidated_cost
                )

                savings_percentage = (

                    savings
                    / separate_cost
                    * 100

                )

            else:

                savings = 0

                savings_percentage = 0


            # ==================================
            # DECISION
            # ==================================

            if savings_percentage >= 20:

                decision = (
                    "CONSOLIDATE"
                )

            elif (
                vehicle[
                    "overall_utilization"
                ]
                >= 0.20
            ):

                decision = (
                    "CONSOLIDATE"
                )

            else:

                decision = (
                    "SEPARATE_TRIPS"
                )


            plans.append({

                "type":
                    "CONSOLIDATED_DISPATCH",

                "transfer_count":
                    len(
                        waiting_group
                    ),

                "transfer_ids":
                    ",".join(
                        waiting_group[
                            "transfer_id"
                        ].tolist()
                    ),

                "source":
                    source,

                "destination":
                    destination,

                "weight":
                    total_weight,

                "volume":
                    total_volume,

                "vehicle":
                    vehicle,

                "separate_cost":
                    separate_cost,

                "consolidated_cost":
                    consolidated_cost,

                "savings":
                    savings,

                "savings_percentage":
                    savings_percentage,

                "decision":
                    decision

            })


        else:

            # ==================================
            # VEHICLE TOO SMALL
            # ==================================

            for _, shipment in (
                waiting_group.iterrows()
            ):

                weight = float(
                    shipment[
                        "weight_kg"
                    ]
                )

                volume = float(
                    shipment[
                        "volume_m3"
                    ]
                )


                vehicle = find_vehicle(

                    source,

                    weight,

                    volume,

                    distance

                )


                plans.append({

                    "type":
                        "INDIVIDUAL_DISPATCH",

                    "transfer_id":
                        shipment[
                            "transfer_id"
                        ],

                    "source":
                        source,

                    "destination":
                        destination,

                    "weight":
                        weight,

                    "volume":
                        volume,

                    "priority":
                        shipment[
                            "priority"
                        ],

                    "deadline":
                        shipment[
                            "deadline_days"
                        ],

                    "vehicle":
                        vehicle

                })


    return plans


# ==========================================
# MAIN
# ==========================================

print()
print(
    "=========================================="
)

print(
    "   DEADLINE-AWARE CONSOLIDATION ENGINE"
)

print(
    "=========================================="
)


# ==========================================
# DISPLAY URGENCY
# ==========================================

print()
print(
    "SHIPMENT URGENCY ANALYSIS"
)

print(
    "------------------------------------------"
)


for _, shipment in (
    requests.sort_values(
        "urgency_score",
        ascending=False
    ).iterrows()
):

    print(

        f"{shipment['transfer_id']} | "

        f"{shipment['source_warehouse']} → "
        f"{shipment['destination_warehouse']} | "

        f"Priority: "
        f"{shipment['priority']} | "

        f"Deadline: "
        f"{shipment['deadline_days']} day(s) | "

        f"Urgency: "
        f"{shipment['urgency_class']}"

    )


# ==========================================
# ROUTE GROUPS
# ==========================================

groups = requests.groupby(

    [
        "source_warehouse",
        "destination_warehouse"
    ]

)


all_plans = []


for (
    source,
    destination
), group in groups:

    plans = analyze_route_group(

        source,

        destination,

        group

    )


    if plans:

        all_plans.extend(
            plans
        )


# ==========================================
# DISPLAY FINAL PLANS
# ==========================================

print()
print(
    "=========================================="
)

print(
    "        FINAL DISPATCH PLAN"
)

print(
    "=========================================="
)


for plan in all_plans:

    print()
    print(
        "------------------------------------------"
    )


    if plan["type"] == (
        "URGENT_DISPATCH"
    ):

        print(
            "🚨 URGENT DISPATCH"
        )

        print(
            f"Transfer: "
            f"{plan['transfer_id']}"
        )

        print(
            f"Route: "
            f"{plan['source']} → "
            f"{plan['destination']}"
        )

        print(
            f"Priority: "
            f"{plan['priority']}"
        )

        print(
            f"Deadline: "
            f"{plan['deadline']} day(s)"
        )


        if plan["vehicle"]:

            vehicle = plan[
                "vehicle"
            ]

            print(
                f"Vehicle: "
                f"{vehicle['vehicle_id']}"
            )

            print(
                f"Fuel: "
                f"{vehicle['fuel']:.2f} L"
            )

            print(
                f"Fuel cost: "
                f"₹{vehicle['cost']:.2f}"
            )


    elif plan["type"] == (
        "CONSOLIDATED_DISPATCH"
    ):

        print(
            "📦 CONSOLIDATED DISPATCH"
        )

        print(
            f"Transfers: "
            f"{plan['transfer_count']}"
        )

        print(
            f"Transfer IDs: "
            f"{plan['transfer_ids']}"
        )

        print(
            f"Route: "
            f"{plan['source']} → "
            f"{plan['destination']}"
        )

        print(
            f"Total weight: "
            f"{plan['weight']:.2f} kg"
        )

        print(
            f"Total volume: "
            f"{plan['volume']:.3f} m³"
        )


        vehicle = plan[
            "vehicle"
        ]


        print(
            f"Vehicle: "
            f"{vehicle['vehicle_id']}"
        )

        print(
            f"Weight utilization: "
            f"{vehicle['weight_utilization'] * 100:.1f}%"
        )

        print(
            f"Volume utilization: "
            f"{vehicle['volume_utilization'] * 100:.1f}%"
        )

        print(
            f"Overall utilization: "
            f"{vehicle['overall_utilization'] * 100:.1f}%"
        )

        print(
            f"Separate cost: "
            f"₹{plan['separate_cost']:.2f}"
        )

        print(
            f"Consolidated cost: "
            f"₹{plan['consolidated_cost']:.2f}"
        )

        print(
            f"Savings: "
            f"₹{plan['savings']:.2f}"
        )

        print(
            f"Savings: "
            f"{plan['savings_percentage']:.1f}%"
        )


        if plan["decision"] == (
            "CONSOLIDATE"
        ):

            print(
                "✅ DECISION: CONSOLIDATE"
            )

        else:

            print(
                "⚠️ DECISION: SEPARATE"
            )


    else:

        print(
            "📦 INDIVIDUAL DISPATCH"
        )

        print(
            f"Transfer: "
            f"{plan['transfer_id']}"
        )

        print(
            f"Route: "
            f"{plan['source']} → "
            f"{plan['destination']}"
        )


# ==========================================
# SAVE RESULT
# ==========================================

output = []


for plan in all_plans:

    row = {

        "dispatch_type":
            plan["type"],

        "source":
            plan["source"],

        "destination":
            plan["destination"]

    }


    if "transfer_id" in plan:

        row[
            "transfer_id"
        ] = plan[
            "transfer_id"
        ]


    if "transfer_ids" in plan:

        row[
            "transfer_ids"
        ] = plan[
            "transfer_ids"
        ]


    if "transfer_count" in plan:

        row[
            "transfer_count"
        ] = plan[
            "transfer_count"
        ]


    if "priority" in plan:

        row[
            "priority"
        ] = plan[
            "priority"
        ]


    if "deadline" in plan:

        row[
            "deadline_days"
        ] = plan[
            "deadline"
        ]


    row[
        "weight_kg"
    ] = plan.get(
        "weight",
        0
    )


    row[
        "volume_m3"
    ] = plan.get(
        "volume",
        0
    )


    if plan.get(
        "vehicle"
    ):

        vehicle = plan[
            "vehicle"
        ]

        row[
            "vehicle_id"
        ] = vehicle[
            "vehicle_id"
        ]

        row[
            "weight_utilization"
        ] = vehicle[
            "weight_utilization"
        ]

        row[
            "volume_utilization"
        ] = vehicle[
            "volume_utilization"
        ]

        row[
            "overall_utilization"
        ] = vehicle[
            "overall_utilization"
        ]

        row[
            "fuel_litres"
        ] = vehicle[
            "fuel"
        ]

        row[
            "fuel_cost"
        ] = vehicle[
            "cost"
        ]


    row[
        "decision"
    ] = plan.get(
        "decision",
        "DISPATCH"
    )


    output.append(
        row
    )


output_df = pd.DataFrame(
    output
)


output_df.to_csv(

    f"{DATA_DIR}/deadline_aware_plans.csv",

    index=False

)


# ==========================================
# COMPLETE
# ==========================================

print()
print(
    "=========================================="
)

print(
    "DEADLINE-AWARE ANALYSIS COMPLETE"
)

print(
    "=========================================="
)

print(
    "Saved to:"
)

print(
    "data/deadline_aware_plans.csv"
)