import os
import math
import pandas as pd


# ============================================================
# LOGICOMMERCE AI V11
# FINAL COST + DEADLINE + FLEET OPTIMIZER
# ============================================================

DATA_DIR = "data"

TRANSFER_FILE = os.path.join(DATA_DIR, "transfer_requests.csv")
VEHICLE_FILE = os.path.join(DATA_DIR, "vehicles.csv")
DISTANCE_FILE = os.path.join(DATA_DIR, "warehouse_distances.csv")
OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "logistics_optimization_v11.csv"
)

FUEL_PRICE = 100.0

AVERAGE_SPEED_KMPH = 40.0

SERVICE_TIME_HOURS = 0.25

DEADLINE_BUFFER_HOURS = 2.0


# ============================================================
# HELPERS
# ============================================================

def money(value):
    return round(float(value), 2)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default


def parse_transfer_ids(value):
    if pd.isna(value):
        return []

    return [
        x.strip()
        for x in str(value).split(",")
        if x.strip()
    ]


def get_distance(distance_df, source, destination):

    if source == destination:
        return 0.0

    columns = {str(c).lower(): c for c in distance_df.columns}

    # --------------------------------------------------------
    # Format 1:
    # source_warehouse, destination_warehouse, distance_km
    # --------------------------------------------------------

    source_col = None
    destination_col = None
    distance_col = None

    for name in [
        "source_warehouse",
        "source",
        "from_warehouse",
        "from"
    ]:
        if name in columns:
            source_col = columns[name]
            break

    for name in [
        "destination_warehouse",
        "destination",
        "to_warehouse",
        "to"
    ]:
        if name in columns:
            destination_col = columns[name]
            break

    for name in [
        "distance_km",
        "distance",
        "km"
    ]:
        if name in columns:
            distance_col = columns[name]
            break

    if source_col and destination_col and distance_col:

        rows = distance_df[
            (
                distance_df[source_col].astype(str) == str(source)
            )
            &
            (
                distance_df[destination_col].astype(str)
                == str(destination)
            )
        ]

        if not rows.empty:
            return safe_float(
                rows.iloc[0][distance_col]
            )

        # Try reverse direction
        rows = distance_df[
            (
                distance_df[source_col].astype(str)
                == str(destination)
            )
            &
            (
                distance_df[destination_col].astype(str)
                == str(source)
            )
        ]

        if not rows.empty:
            return safe_float(
                rows.iloc[0][distance_col]
            )

    # --------------------------------------------------------
    # Format 2:
    # source/destination represented as matrix
    # --------------------------------------------------------

    if source in distance_df.columns:

        try:
            value = distance_df.loc[
                distance_df.iloc[:, 0].astype(str)
                == str(destination),
                source
            ]

            if not value.empty:
                return safe_float(
                    value.iloc[0]
                )
        except:
            pass

    return 0.0


def route_distance(route, distance_df):

    total = 0.0

    for i in range(len(route) - 1):

        total += get_distance(
            distance_df,
            route[i],
            route[i + 1]
        )

    return total


def route_time(distance):

    if distance <= 0:
        return 0.0

    driving_time = distance / AVERAGE_SPEED_KMPH

    number_of_stops = max(0, int(distance > 0))

    return (
        driving_time
        + SERVICE_TIME_HOURS
        + number_of_stops * SERVICE_TIME_HOURS
    )


def fuel_required(distance, efficiency):

    if efficiency <= 0:
        return float("inf")

    return distance / efficiency


def fuel_cost(distance, efficiency):

    return money(
        fuel_required(
            distance,
            efficiency
        ) * FUEL_PRICE
    )


def utilization(weight, volume, vehicle):

    weight_capacity = safe_float(
        vehicle["capacity_kg"]
    )

    volume_capacity = safe_float(
        vehicle["volume_capacity_m3"]
    )

    weight_util = (
        weight / weight_capacity * 100
        if weight_capacity > 0
        else 100
    )

    volume_util = (
        volume / volume_capacity * 100
        if volume_capacity > 0
        else 100
    )

    overall = (
        weight_util + volume_util
    ) / 2

    return (
        weight_util,
        volume_util,
        overall
    )


def vehicle_can_carry(
    weight,
    volume,
    vehicle
):

    return (
        weight <= safe_float(
            vehicle["capacity_kg"]
        )
        and
        volume <= safe_float(
            vehicle["volume_capacity_m3"]
        )
    )


def select_vehicle(
    vehicles_df,
    source,
    weight,
    volume,
    distance
):

    candidates = []

    for _, vehicle in vehicles_df.iterrows():

        vehicle_source = str(
            vehicle["warehouse_id"]
        )

        if vehicle_source != str(source):
            continue

        if not vehicle_can_carry(
            weight,
            volume,
            vehicle
        ):
            continue

        efficiency = safe_float(
            vehicle["fuel_efficiency_kmpl"]
        )

        if efficiency <= 0:
            continue

        fuel = fuel_required(
            distance,
            efficiency
        )

        wu, vu, ou = utilization(
            weight,
            volume,
            vehicle
        )

        # Lower fuel + better utilization = better vehicle
        score = (
            fuel * 100
            - ou * 0.5
        )

        candidates.append(
            (
                score,
                vehicle
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0]
    )

    return candidates[0][1]


# ============================================================
# DEADLINE
# ============================================================

def urgency_level(deadline_days):

    deadline_days = safe_float(
        deadline_days
    )

    if deadline_days <= 1:
        return "URGENT"

    if deadline_days <= 2:
        return "SOON"

    return "NORMAL"


def deadline_status(
    route_hours,
    deadline_days
):

    deadline_hours = (
        safe_float(deadline_days)
        * 24
    )

    if route_hours <= (
        deadline_hours
        - DEADLINE_BUFFER_HOURS
    ):
        return "ON_TIME"

    if route_hours <= deadline_hours:
        return "AT_RISK"

    return "MISSED_DEADLINE"


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
# VALIDATE DATA
# ============================================================

required_transfer_columns = [
    "transfer_id",
    "source_warehouse",
    "destination_warehouse",
    "quantity",
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


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 58)
print("       LOGICOMMERCE AI V11")
print(" FINAL COST + DEADLINE + FLEET OPTIMIZATION")
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
# BUILD BASELINE
# ============================================================

print()
print("=" * 58)
print("       BUILDING BASELINE COST")
print("=" * 58)

baseline_records = []

for _, row in transfers_df.iterrows():

    source = row[
        "source_warehouse"
    ]

    destination = row[
        "destination_warehouse"
    ]

    distance_one_way = get_distance(
        distance_df,
        source,
        destination
    )

    round_trip_distance = (
        distance_one_way * 2
    )

    # Baseline uses a standard reference
    # vehicle efficiency of 10 km/L.
    baseline_efficiency = 10.0

    baseline_cost = fuel_cost(
        round_trip_distance,
        baseline_efficiency
    )

    baseline_records.append(
        baseline_cost
    )


transfers_df[
    "_baseline_cost"
] = baseline_records


baseline_total = money(
    transfers_df[
        "_baseline_cost"
    ].sum()
)


# ============================================================
# GROUP TRANSFERS
# ============================================================

groups = []

grouped = transfers_df.groupby(
    [
        "source_warehouse",
        "destination_warehouse"
    ],
    sort=False
)


for (
    source,
    destination
), group in grouped:

    group = group.copy()

    # --------------------------------------------------------
    # Separate urgent transfers
    # --------------------------------------------------------

    urgent = group[
        group[
            "deadline_days"
        ] <= 1
    ]

    normal = group[
        group[
            "deadline_days"
        ] > 1
    ]

    # --------------------------------------------------------
    # Urgent shipments remain separate.
    # --------------------------------------------------------

    for _, row in urgent.iterrows():

        groups.append({

            "source": source,

            "destination": destination,

            "rows": [row],

            "decision": "URGENT_SEPARATE"

        })

    # --------------------------------------------------------
    # Normal shipments may be consolidated.
    # --------------------------------------------------------

    normal_rows = list(
        normal.iterrows()
    )

    if not normal_rows:
        continue

    # Greedy capacity grouping
    current = []

    current_weight = 0.0
    current_volume = 0.0

    for _, row in normal_rows:

        row_weight = safe_float(
            row["weight_kg"]
        )

        row_volume = safe_float(
            row["volume_m3"]
        )

        if (
            current
            and
            (
                current_weight
                + row_weight
                > 5000
                or
                current_volume
                + row_volume
                > 50
            )
        ):

            groups.append({

                "source": source,

                "destination": destination,

                "rows": current.copy(),

                "decision": "CANDIDATE"

            })

            current = []

            current_weight = 0.0
            current_volume = 0.0

        current.append(row)

        current_weight += row_weight
        current_volume += row_volume

    if current:

        groups.append({

            "source": source,

            "destination": destination,

            "rows": current.copy(),

            "decision": "CANDIDATE"

        })


# ============================================================
# OPTIMIZATION
# ============================================================

print()
print("=" * 58)
print("       FINAL LOGISTICS PLAN V11")
print("=" * 58)


results = []

vehicle_next_available = {
    str(row["vehicle_id"]): 0.0
    for _, row in vehicles_df.iterrows()
}


route_number = 0


for group in groups:

    source = group["source"]
    destination = group["destination"]
    rows = group["rows"]

    transfer_ids = [
        str(row["transfer_id"])
        for row in rows
    ]

    weight = sum(
        safe_float(row["weight_kg"])
        for row in rows
    )

    volume = sum(
        safe_float(row["volume_m3"])
        for row in rows
    )

    earliest_deadline = min(
        safe_float(row["deadline_days"])
        for row in rows
    )

    urgency = min(
        (
            urgency_level(
                row["deadline_days"]
            )
            for row in rows
        ),
        key=lambda x: {
            "URGENT": 0,
            "SOON": 1,
            "NORMAL": 2
        }[x]
    )

    one_way_distance = get_distance(
        distance_df,
        source,
        destination
    )

    # --------------------------------------------------------
    # Two-node round trip
    # --------------------------------------------------------

    route = [
        source,
        destination,
        source
    ]

    distance = route_distance(
        route,
        distance_df
    )

    # --------------------------------------------------------
    # Select best vehicle
    # --------------------------------------------------------

    vehicle = select_vehicle(
        vehicles_df,
        source,
        weight,
        volume,
        distance
    )

    if vehicle is None:

        print()
        print("-" * 58)
        print(
            "⚠️ NO SUITABLE VEHICLE"
        )
        print(
            f"Route: {source} → {destination}"
        )
        print(
            "Transfers:",
            ",".join(transfer_ids)
        )

        for row in rows:

            results.append({

                "transfer_ids":
                    row["transfer_id"],

                "source":
                    source,

                "destination":
                    destination,

                "decision":
                    "UNASSIGNED",

                "vehicle_id":
                    "",

                "weight_kg":
                    weight,

                "volume_m3":
                    volume,

                "distance_km":
                    distance,

                "route_time_hours":
                    0,

                "fuel_liters":
                    0,

                "fuel_cost":
                    0,

                "baseline_cost":
                    safe_float(
                        row["_baseline_cost"]
                    ),

                "savings":
                    0,

                "savings_percentage":
                    0,

                "deadline_status":
                    "UNASSIGNED",

                "urgency":
                    urgency,

                "weight_utilization":
                    0,

                "volume_utilization":
                    0,

                "overall_utilization":
                    0,

                "reason":
                    "No feasible vehicle."

            })

        continue


    vehicle_id = str(
        vehicle["vehicle_id"]
    )

    efficiency = safe_float(
        vehicle["fuel_efficiency_kmpl"]
    )


    # --------------------------------------------------------
    # Schedule after vehicle availability
    # --------------------------------------------------------

    departure = max(
        0.0,
        vehicle_next_available[
            vehicle_id
        ]
    )


    distance = route_distance(
        route,
        distance_df
    )

    trip_hours = (
        distance / AVERAGE_SPEED_KMPH
        + SERVICE_TIME_HOURS
    )


    arrival = (
        departure
        + trip_hours
    )


    return_time = (
        arrival
        + trip_hours
    )


    status = deadline_status(
        trip_hours,
        earliest_deadline
    )


    # --------------------------------------------------------
    # Calculate optimized cost
    # --------------------------------------------------------

    optimized_cost = fuel_cost(
        distance,
        efficiency
    )


    # --------------------------------------------------------
    # Baseline for this group
    # --------------------------------------------------------

    separate_cost = money(
        sum(
            safe_float(
                row["_baseline_cost"]
            )
            for row in rows
        )
    )


    # --------------------------------------------------------
    # Urgent shipments
    # --------------------------------------------------------

    if urgency == "URGENT":

        decision = (
            "URGENT_SEPARATE"
        )

        final_cost = optimized_cost

        savings = 0.0

        savings_percentage = 0.0

        reason = (
            "Urgent shipment protected "
            "from consolidation delay."
        )

    else:

        # ----------------------------------------------------
        # Consolidation is allowed only if:
        # 1. Multiple shipments
        # 2. Cost saving exists
        # 3. Deadline remains feasible
        # ----------------------------------------------------

        if len(rows) > 1:

            if (
                optimized_cost
                < separate_cost
                and
                status != "MISSED_DEADLINE"
            ):

                decision = "CONSOLIDATE"

                final_cost = optimized_cost

                savings = money(
                    separate_cost
                    - optimized_cost
                )

                savings_percentage = money(
                    savings
                    / separate_cost
                    * 100
                ) if separate_cost > 0 else 0

                reason = (
                    "Compatible shipments "
                    "combined to reduce cost "
                    "while preserving deadline "
                    "feasibility."
                )

            else:

                decision = "SEPARATE"

                # IMPORTANT:
                # For separate shipment cost,
                # use the actual vehicle cost.
                final_cost = optimized_cost

                savings = 0.0

                savings_percentage = 0.0

                if status == "MISSED_DEADLINE":

                    reason = (
                        "Consolidation rejected "
                        "because deadline feasibility "
                        "was not satisfied."
                    )

                else:

                    reason = (
                        "Consolidation rejected "
                        "because it does not provide "
                        "sufficient cost benefit."
                    )

        else:

            decision = "SEPARATE"

            final_cost = optimized_cost

            savings = 0.0

            savings_percentage = 0.0

            reason = (
                "Single shipment dispatch."
            )


    # --------------------------------------------------------
    # Utilization
    # --------------------------------------------------------

    wu, vu, ou = utilization(
        weight,
        volume,
        vehicle
    )


    fuel = fuel_required(
        distance,
        efficiency
    )


    # --------------------------------------------------------
    # Update vehicle schedule
    # --------------------------------------------------------

    vehicle_next_available[
        vehicle_id
    ] = return_time


    route_number += 1


    # --------------------------------------------------------
    # Print result
    # --------------------------------------------------------

    print()
    print("-" * 58)

    print(
        f"Decision: {decision}"
    )

    print(
        "Route:",
        " → ".join(route)
    )

    print(
        "Transfers:",
        ",".join(transfer_ids)
    )

    print(
        f"Vehicle: {vehicle_id}"
    )

    print(
        f"Vehicle capacity: "
        f"{safe_float(vehicle['capacity_kg']):.0f} kg"
    )

    print(
        f"Vehicle volume: "
        f"{safe_float(vehicle['volume_capacity_m3']):.1f} m³"
    )

    print(
        f"Weight: {weight:.2f} kg"
    )

    print(
        f"Volume: {volume:.3f} m³"
    )

    print(
        f"Weight utilization: "
        f"{wu:.1f}%"
    )

    print(
        f"Volume utilization: "
        f"{vu:.1f}%"
    )

    print(
        f"Overall utilization: "
        f"{ou:.1f}%"
    )

    print(
        f"Fuel efficiency: "
        f"{efficiency:.2f} km/L"
    )

    print(
        f"Distance: "
        f"{distance:.0f} km"
    )

    print(
        f"Route time: "
        f"{trip_hours:.2f} hours"
    )

    print(
        f"Departure: "
        f"{departure:.2f} h"
    )

    print(
        f"Arrival: "
        f"{arrival:.2f} h"
    )

    print(
        f"Fuel: "
        f"{fuel:.2f} L"
    )

    print(
        f"Optimized cost: "
        f"₹{optimized_cost:.2f}"
    )

    print(
        f"Baseline cost: "
        f"₹{separate_cost:.2f}"
    )

    print(
        f"Savings: "
        f"₹{savings:.2f}"
    )

    print(
        f"Savings: "
        f"{savings_percentage:.1f}%"
    )

    print(
        f"Deadline: "
        f"{status}"
    )

    print(
        f"Urgency: "
        f"{urgency}"
    )

    print(
        f"Reason: "
        f"{reason}"
    )


    # --------------------------------------------------------
    # Save one result record
    # --------------------------------------------------------

    results.append({

        "transfer_ids":
            ",".join(transfer_ids),

        "source":
            source,

        "destination":
            destination,

        "route":
            " → ".join(route),

        "decision":
            decision,

        "vehicle_id":
            vehicle_id,

        "vehicle_capacity_kg":
            safe_float(
                vehicle["capacity_kg"]
            ),

        "vehicle_volume_m3":
            safe_float(
                vehicle[
                    "volume_capacity_m3"
                ]
            ),

        "weight_kg":
            round(weight, 2),

        "volume_m3":
            round(volume, 3),

        "weight_utilization":
            round(wu, 2),

        "volume_utilization":
            round(vu, 2),

        "overall_utilization":
            round(ou, 2),

        "fuel_efficiency_kmpl":
            round(efficiency, 2),

        "distance_km":
            round(distance, 2),

        "route_time_hours":
            round(trip_hours, 2),

        "departure_hour":
            round(departure, 2),

        "arrival_hour":
            round(arrival, 2),

        "fuel_liters":
            round(fuel, 2),

        "optimized_cost":
            round(final_cost, 2),

        "baseline_cost":
            round(separate_cost, 2),

        "savings":
            round(savings, 2),

        "savings_percentage":
            round(savings_percentage, 2),

        "deadline_days":
            earliest_deadline,

        "deadline_status":
            status,

        "urgency":
            urgency,

        "reason":
            reason

    })


# ============================================================
# FINAL DATAFRAME
# ============================================================

results_df = pd.DataFrame(
    results
)


# ============================================================
# SUMMARY
# ============================================================

assigned = results_df[
    results_df["decision"]
    != "UNASSIGNED"
]

unassigned = results_df[
    results_df["decision"]
    == "UNASSIGNED"
]


consolidated = results_df[
    results_df["decision"]
    == "CONSOLIDATE"
]


separate = results_df[
    results_df["decision"]
    == "SEPARATE"
]


urgent = results_df[
    results_df["decision"]
    == "URGENT_SEPARATE"
]


total_optimized_cost = money(
    assigned[
        "optimized_cost"
    ].sum()
)


total_baseline_cost = money(
    transfers_df[
        "_baseline_cost"
    ].sum()
)


# ------------------------------------------------------------
# Savings calculation
# ------------------------------------------------------------

total_savings = money(
    max(
        0,
        total_baseline_cost
        - total_optimized_cost
    )
)


overall_savings = (
    total_savings
    / total_baseline_cost
    * 100
    if total_baseline_cost > 0
    else 0
)


total_distance = money(
    assigned[
        "distance_km"
    ].sum()
)


total_fuel = money(
    assigned[
        "fuel_liters"
    ].sum()
)


avg_weight_util = money(
    assigned[
        "weight_utilization"
    ].mean()
    if not assigned.empty
    else 0
)


avg_volume_util = money(
    assigned[
        "volume_utilization"
    ].mean()
    if not assigned.empty
    else 0
)


on_time = len(
    assigned[
        assigned[
            "deadline_status"
        ] == "ON_TIME"
    ]
)


at_risk = len(
    assigned[
        assigned[
            "deadline_status"
        ] == "AT_RISK"
    ]
)


missed = len(
    assigned[
        assigned[
            "deadline_status"
        ] == "MISSED_DEADLINE"
    ]
)


# ============================================================
# SUMMARY OUTPUT
# ============================================================

print()
print("=" * 58)
print("       V11 OPTIMIZATION SUMMARY")
print("=" * 58)

print(
    f"Total transfers: "
    f"{len(transfers_df)}"
)

# ============================================================
# TRANSFER ACCOUNTING
# ============================================================

assigned_transfer_ids = set()
unassigned_transfer_ids = set()

for _, row in assigned.iterrows():

    assigned_transfer_ids.update(
        parse_transfer_ids(
            row["transfer_ids"]
        )
    )


for _, row in unassigned.iterrows():

    unassigned_transfer_ids.update(
        parse_transfer_ids(
            row["transfer_ids"]
        )
    )


print(
    f"Total transfers: "
    f"{len(transfers_df)}"
)

print(
    f"Transfers assigned: "
    f"{len(assigned_transfer_ids)}"
)

print(
    f"Transfers unassigned: "
    f"{len(unassigned_transfer_ids)}"
)

print(
    f"Routes created: "
    f"{len(assigned)}"
)

print(
    f"Consolidated routes: "
    f"{len(consolidated)}"
)

print(
    f"Separate routes: "
    f"{len(separate)}"
)

print(
    f"Urgent separate: "
    f"{len(urgent)}"
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
    f"₹{total_optimized_cost:.2f}"
)

print(
    f"Baseline cost: "
    f"₹{total_baseline_cost:.2f}"
)

print(
    f"Estimated savings: "
    f"₹{total_savings:.2f}"
)

print(
    f"Overall savings: "
    f"{overall_savings:.1f}%"
)

print(
    f"Average weight utilization: "
    f"{avg_weight_util:.1f}%"
)

print(
    f"Average volume utilization: "
    f"{avg_volume_util:.1f}%"
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
# FINAL ACCOUNTING VALIDATION
# ============================================================

expected_transfers = set(
    transfers_df[
        "transfer_id"
    ].astype(str)
)

accounted_transfers = (
    assigned_transfer_ids
    | unassigned_transfer_ids
)

missing_transfers = (
    expected_transfers
    - accounted_transfers
)

duplicate_check = (
    len(assigned_transfer_ids)
    + len(unassigned_transfer_ids)
    == len(accounted_transfers)
)

print()
print("=" * 58)
print("       TRANSFER ACCOUNTING VALIDATION")
print("=" * 58)

print(
    f"Expected transfers: "
    f"{len(expected_transfers)}"
)

print(
    f"Accounted transfers: "
    f"{len(accounted_transfers)}"
)

print(
    f"Missing transfers: "
    f"{len(missing_transfers)}"
)

if not missing_transfers and duplicate_check:

    print(
        "✅ TRANSFER ACCOUNTING PASSED"
    )

else:

    print(
        "⚠️ TRANSFER ACCOUNTING FAILED"
    )

    if missing_transfers:

        print(
            "Missing:",
            ", ".join(
                sorted(missing_transfers)
            )
        )



# ============================================================
# UNASSIGNED
# ============================================================

if not unassigned.empty:

    print()
    print(
        "UNASSIGNED TRANSFERS:"
    )

    for _, row in unassigned.iterrows():

        print(
            f"⚠️ {row['transfer_ids']}"
        )

else:

    print()
    print(
        "✅ ALL TRANSFERS ASSIGNED"
    )


# ============================================================
# SAVE
# ============================================================

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print()
print("=" * 58)
print(
    "       LOGICOMMERCE V11 COMPLETE"
)
print("=" * 58)

print(
    "Saved to:"
)

print(
    OUTPUT_FILE
)