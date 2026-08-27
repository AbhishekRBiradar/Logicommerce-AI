import pandas as pd


# ==========================================
# CONFIGURATION
# ==========================================

DATA_DIR = "data"

AVERAGE_SPEED_KMPH = 40.0
LOADING_TIME_HOURS = 0.5


# ==========================================
# LOAD DATA
# ==========================================

print("Loading dispatch plans...")
plans = pd.read_csv(
    f"{DATA_DIR}/deadline_aware_plans.csv"
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
# DISTANCE
# ==========================================

def get_distance(source, destination):

    result = distances[
        (
            distances["source_warehouse"]
            == source
        )
        &
        (
            distances["destination_warehouse"]
            == destination
        )
    ]

    if result.empty:
        return None

    return float(
        result.iloc[0]["distance_km"]
    )


# ==========================================
# TRIP TIME
# ==========================================

def trip_time(distance_km):

    travel_time = (
        distance_km
        / AVERAGE_SPEED_KMPH
    )

    return (
        travel_time
        + LOADING_TIME_HOURS
    )


# ==========================================
# VEHICLE SCHEDULER
# ==========================================

class VehicleScheduler:

    def __init__(self):

        self.available_at = {}

        for _, vehicle in vehicles.iterrows():

            self.available_at[
                vehicle["vehicle_id"]
            ] = 0.0


    # ======================================
    # FIND VEHICLE
    # ======================================

    def find_vehicle(
        self,
        source,
        weight,
        volume,
        distance,
        current_time,
        deadline_days
    ):

        candidates = vehicles[
            (
                vehicles["warehouse_id"]
                == source
            )
            &
            (
                vehicles["available"]
                == 1
            )
            &
            (
                vehicles["capacity_kg"]
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


        best = None

        best_score = float("inf")


        for _, vehicle in (
            candidates.iterrows()
        ):

            vehicle_id = (
                vehicle["vehicle_id"]
            )


            # When this vehicle becomes free.

            vehicle_free_time = (
                self.available_at[
                    vehicle_id
                ]
            )


            # Vehicle can depart when it
            # is both requested and available.

            departure_time = max(

                current_time,

                vehicle_free_time

            )


            duration = trip_time(
                distance
            )


            arrival_time = (
                departure_time
                + duration
            )


            # ==================================
            # DEADLINE
            # ==================================

            deadline_hours = None

            if pd.notna(
                deadline_days
            ):

                deadline_hours = (
                    float(deadline_days)
                    * 24
                )


            if deadline_hours is None:

                deadline_status = (
                    "NO_DEADLINE"
                )

            elif arrival_time <= (
                deadline_hours
            ):

                deadline_status = (
                    "ON_TIME"
                )

            elif arrival_time <= (
                deadline_hours * 1.20
            ):

                deadline_status = (
                    "AT_RISK"
                )

            else:

                deadline_status = (
                    "MISSED_DEADLINE"
                )


            # ==================================
            # SCORE
            # ==================================

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


            fuel_efficiency = float(
                vehicle[
                    "fuel_efficiency_kmpl"
                ]
            )


            fuel = (
                distance
                / fuel_efficiency
            )


            # Deadline is heavily prioritized.

            if deadline_status == (
                "ON_TIME"
            ):

                deadline_penalty = 0

            elif deadline_status == (
                "AT_RISK"
            ):

                deadline_penalty = 5000

            else:

                deadline_penalty = 100000


            # Earlier departure is better.

            waiting_penalty = (
                departure_time
                * 50
            )


            # Better utilization is preferred.

            utilization_penalty = (
                1
                - utilization
            ) * 100


            score = (

                deadline_penalty

                +

                waiting_penalty

                +

                fuel * 100

                +

                utilization_penalty

            )


            if score < best_score:

                best_score = score

                best = {

                    "vehicle_id":
                        vehicle_id,

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
                        fuel_efficiency,

                    "departure_time":
                        departure_time,

                    "arrival_time":
                        arrival_time,

                    "return_time":
                        departure_time
                        + (
                            duration * 2
                        ),

                    "trip_hours":
                        duration,

                    "fuel":
                        fuel,

                    "fuel_cost":
                        fuel * 100,

                    "weight_utilization":
                        weight_utilization,

                    "volume_utilization":
                        volume_utilization,

                    "overall_utilization":
                        utilization,

                    "deadline_status":
                        deadline_status,

                    "score":
                        score

                }


        return best


    # ======================================
    # RESERVE VEHICLE
    # ======================================

    def reserve(
        self,
        vehicle_id,
        return_time
    ):

        self.available_at[
            vehicle_id
        ] = return_time


# ==========================================
# PLAN PRIORITY
# ==========================================

priority_order = {

    "URGENT_DISPATCH": 1,

    "CONSOLIDATED_DISPATCH": 2,

    "INDIVIDUAL_DISPATCH": 3

}


plans["sort_order"] = (
    plans["dispatch_type"]
    .map(priority_order)
    .fillna(99)
)


# More urgent deadlines first.

plans["deadline_sort"] = (
    pd.to_numeric(
        plans.get(
            "deadline_days",
            pd.Series(
                [999] * len(plans)
            )
        ),
        errors="coerce"
    )
    .fillna(999)
)


plans = plans.sort_values(
    [
        "sort_order",
        "deadline_sort"
    ]
)


# ==========================================
# START
# ==========================================

print()
print("==========================================")
print("       TIME-AWARE VEHICLE SCHEDULER")
print("==========================================")


scheduler = VehicleScheduler()

results = []


# ==========================================
# PROCESS PLANS
# ==========================================

for _, plan in plans.iterrows():

    source = plan[
        "source"
    ]

    destination = plan[
        "destination"
    ]

    weight = float(
        plan[
            "weight_kg"
        ]
    )

    volume = float(
        plan[
            "volume_m3"
        ]
    )


    distance = get_distance(
        source,
        destination
    )


    if distance is None:
        continue


    deadline_days = plan.get(
        "deadline_days",
        None
    )


    # ======================================
    # FIND BEST VEHICLE
    # ======================================

    vehicle = scheduler.find_vehicle(

        source,

        weight,

        volume,

        distance,

        0.0,

        deadline_days

    )


    # ======================================
    # VEHICLE UNAVAILABLE
    # ======================================

    if vehicle is None:

        results.append({

            "source":
                source,

            "destination":
                destination,

            "dispatch_type":
                plan[
                    "dispatch_type"
                ],

            "transfer_id":
                plan.get(
                    "transfer_id",
                    ""
                ),

            "transfer_ids":
                plan.get(
                    "transfer_ids",
                    ""
                ),

            "status":
                "NO_COMPATIBLE_VEHICLE",

            "vehicle_id":
                "",

            "distance_km":
                distance,

            "weight_kg":
                weight,

            "volume_m3":
                volume

        })

        continue


    # ======================================
    # RESERVE VEHICLE
    # ======================================

    scheduler.reserve(

        vehicle[
            "vehicle_id"
        ],

        vehicle[
            "return_time"
        ]

    )


    # ======================================
    # SAVE RESULT
    # ======================================

    results.append({

        "source":
            source,

        "destination":
            destination,

        "dispatch_type":
            plan[
                "dispatch_type"
            ],

        "transfer_id":
            plan.get(
                "transfer_id",
                ""
            ),

        "transfer_ids":
            plan.get(
                "transfer_ids",
                ""
            ),

        "status":
            "SCHEDULED",

        "vehicle_id":
            vehicle[
                "vehicle_id"
            ],

        "vehicle_capacity_kg":
            vehicle[
                "capacity_kg"
            ],

        "vehicle_volume_m3":
            vehicle[
                "volume_capacity_m3"
            ],

        "distance_km":
            distance,

        "trip_hours":
            vehicle[
                "trip_hours"
            ],

        "departure_hour":
            vehicle[
                "departure_time"
            ],

        "arrival_hour":
            vehicle[
                "arrival_time"
            ],

        "return_hour":
            vehicle[
                "return_time"
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

        "fuel_litres":
            vehicle[
                "fuel"
            ],

        "fuel_cost":
            vehicle[
                "fuel_cost"
            ],

        "deadline_days":
            deadline_days,

        "deadline_status":
            vehicle[
                "deadline_status"
            ]

    })


# ==========================================
# RESULTS
# ==========================================

result_df = pd.DataFrame(
    results
)


print()
print("==========================================")
print("       FINAL VEHICLE SCHEDULE")
print("==========================================")


for _, row in (
    result_df.iterrows()
):

    print()
    print("------------------------------------------")

    print(
        f"{row['source']} → "
        f"{row['destination']}"
    )

    print(
        f"Type: "
        f"{row['dispatch_type']}"
    )


    transfer_id = row.get(
        "transfer_id",
        ""
    )

    transfer_ids = row.get(
        "transfer_ids",
        ""
    )


    if pd.notna(
        transfer_id
    ) and str(
        transfer_id
    ) != "":

        print(
            f"Transfer: "
            f"{transfer_id}"
        )


    if pd.notna(
        transfer_ids
    ) and str(
        transfer_ids
    ) != "":

        print(
            f"Transfers: "
            f"{transfer_ids}"
        )


    print(
        f"Status: "
        f"{row['status']}"
    )


    if row["status"] == (
        "SCHEDULED"
    ):

        print(
            f"Vehicle: "
            f"{row['vehicle_id']}"
        )

        print(
            f"Distance: "
            f"{row['distance_km']:.0f} km"
        )

        print(
            f"Departure: "
            f"{row['departure_hour']:.2f} h"
        )

        print(
            f"Arrival: "
            f"{row['arrival_hour']:.2f} h"
        )

        print(
            f"Vehicle return: "
            f"{row['return_hour']:.2f} h"
        )

        print(
            f"Trip time: "
            f"{row['trip_hours']:.2f} h"
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
            f"Fuel: "
            f"{row['fuel_litres']:.2f} L"
        )

        print(
            f"Fuel cost: "
            f"₹{row['fuel_cost']:.2f}"
        )

        print(
            f"Deadline status: "
            f"{row['deadline_status']}"
        )

    else:

        print(
            "⚠️ No compatible vehicle."
        )


# ==========================================
# SAVE
# ==========================================

result_df.to_csv(

    f"{DATA_DIR}/vehicle_schedule.csv",

    index=False

)


# ==========================================
# SUMMARY
# ==========================================

scheduled = result_df[
    result_df["status"]
    == "SCHEDULED"
]

failed = result_df[
    result_df["status"]
    != "SCHEDULED"
]


print()
print("==========================================")
print("          SCHEDULING SUMMARY")
print("==========================================")

print(
    f"Total plans: "
    f"{len(result_df)}"
)

print(
    f"Scheduled: "
    f"{len(scheduled)}"
)

print(
    f"Unscheduled: "
    f"{len(failed)}"
)


if len(scheduled) > 0:

    print(
        f"On time: "
        f"{len(scheduled[scheduled['deadline_status'] == 'ON_TIME'])}"
    )

    print(
        f"At risk: "
        f"{len(scheduled[scheduled['deadline_status'] == 'AT_RISK'])}"
    )

    print(
        f"Missed deadline: "
        f"{len(scheduled[scheduled['deadline_status'] == 'MISSED_DEADLINE'])}"
    )


print()
print(
    "Saved to:"
)

print(
    "data/vehicle_schedule.csv"
)