import pandas as pd


# ==========================================
# LOAD NETWORK DATA
# ==========================================

inventory = pd.read_csv(
    "data/warehouse_inventory.csv"
)

distances = pd.read_csv(
    "data/warehouse_distances.csv"
)


# ==========================================
# FIND BEST TRANSFER PLAN
# ==========================================

def optimize_transfer(
    destination,
    required_quantity
):

    destination_row = inventory[
        inventory["warehouse_id"] == destination
    ]

    if destination_row.empty:

        return {
            "status": "INVALID_DESTINATION"
        }


    # Current destination stock

    destination_stock = float(
        destination_row.iloc[0][
            "current_inventory_units"
        ]
    )


    # Safety stock

    destination_safety = float(
        destination_row.iloc[0][
            "safety_stock"
        ]
    )


    # ======================================
    # CALCULATE SHORTAGE
    # ======================================

    shortage = max(
        0,
        required_quantity - destination_stock
    )


    if shortage <= 0:

        return {

            "status":
                "NO_TRANSFER_REQUIRED",

            "shortage":
                0

        }


    # ======================================
    # GET SOURCE WAREHOUSES
    # ======================================

    candidates = inventory[
        inventory["warehouse_id"]
        != destination
    ].copy()


    # Only warehouses with usable surplus

    candidates = candidates[
        candidates["usable_surplus"] > 0
    ]


    # ======================================
    # ADD DISTANCE
    # ======================================

    candidates = candidates.merge(

        distances[
            distances[
                "destination_warehouse"
            ] == destination
        ][
            [
                "source_warehouse",
                "distance_km"
            ]
        ],

        left_on="warehouse_id",

        right_on="source_warehouse",

        how="left"

    )


    candidates = candidates.dropna(
        subset=["distance_km"]
    )


    # ======================================
    # SORT BY DISTANCE
    # ======================================

    candidates = candidates.sort_values(
        "distance_km"
    )


    # ======================================
    # CREATE TRANSFER PLAN
    # ======================================

    transfer_plan = []

    remaining = shortage


    for _, warehouse in candidates.iterrows():

        if remaining <= 0:
            break


        available = float(
            warehouse["usable_surplus"]
        )


        transfer_quantity = min(
            remaining,
            available
        )


        if transfer_quantity <= 0:
            continue


        transfer_plan.append({

            "source":
                warehouse[
                    "warehouse_id"
                ],

            "destination":
                destination,

            "quantity":
                round(
                    transfer_quantity,
                    2
                ),

            "distance_km":
                warehouse[
                    "distance_km"
                ],

            "available_surplus":
                round(
                    available,
                    2
                )

        })


        remaining -= transfer_quantity


    # ======================================
    # FINAL STATUS
    # ======================================

    if not transfer_plan:

        return {

            "status":
                "NO_SOURCE_AVAILABLE",

            "shortage":
                round(
                    shortage,
                    2
                )

        }


    if remaining > 0:

        status = "PARTIAL_TRANSFER"

    else:

        status = "TRANSFER_PLAN_READY"


    return {

        "status":
            status,

        "original_shortage":
            round(
                shortage,
                2
            ),

        "remaining_shortage":
            round(
                remaining,
                2
            ),

        "transfer_plan":
            transfer_plan

    }


# ==========================================
# INTERACTIVE TEST
# ==========================================

print(
    "\n=========================================="
)

print(
    "       SMART TRANSFER OPTIMIZER"
)

print(
    "=========================================="
)


destination = input(
    "\nDestination Warehouse ID: "
).strip()


required_quantity = float(
    input(
        "Required total stock: "
    )
)


result = optimize_transfer(

    destination,

    required_quantity

)


# ==========================================
# DISPLAY
# ==========================================

print(
    "\n=========================================="
)

print(
    "TRANSFER OPTIMIZATION RESULT"
)

print(
    "=========================================="
)


print(
    f"Status: {result['status']}"
)


if result["status"] == "NO_TRANSFER_REQUIRED":

    print(
        "\nDestination warehouse has sufficient stock."
    )


elif result["status"] == "INVALID_DESTINATION":

    print(
        "\n❌ Invalid warehouse ID."
    )


elif result["status"] == "NO_SOURCE_AVAILABLE":

    print(
        f"\nShortage: "
        f"{result['shortage']:.2f} units"
    )

    print(
        "No warehouse has usable surplus."
    )


else:

    print(
        f"\nOriginal shortage: "
        f"{result['original_shortage']:.2f}"
    )

    print(
        f"Remaining shortage: "
        f"{result['remaining_shortage']:.2f}"
    )


    print(
        "\nTRANSFER PLAN"
    )

    print(
        "------------------------------------------"
    )


    for transfer in result[
        "transfer_plan"
    ]:

        print(

            f"{transfer['source']} → "
            f"{transfer['destination']} | "

            f"Quantity: "
            f"{transfer['quantity']:.2f} | "

            f"Distance: "
            f"{transfer['distance_km']:.0f} km | "

            f"Available surplus: "
            f"{transfer['available_surplus']:.2f}"

        )


print(
    "\n=========================================="
)