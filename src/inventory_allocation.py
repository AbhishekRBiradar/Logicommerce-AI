import pandas as pd


# ==========================================
# LOAD WAREHOUSE DATA
# ==========================================

warehouses = pd.read_csv(
    "data/warehouses.csv"
)


# ==========================================
# INVENTORY ALLOCATION
# ==========================================

def find_stock_transfer(
    destination_warehouse,
    current_stock,
    required_stock
):

    shortage = max(
        0,
        required_stock - current_stock
    )


    if shortage <= 0:

        return {
            "status": "NO_TRANSFER_REQUIRED",
            "shortage": 0
        }


    # ======================================
    # CREATE SIMULATED SURPLUS
    # ======================================

    warehouse_data = warehouses.copy()


    # Estimate usable surplus

    warehouse_data[
        "usable_inventory"
    ] = (

        warehouse_data[
            "current_inventory_units"
        ]

        - warehouse_data[
            "capacity_units"
        ] * 0.30

    )


    warehouse_data[
        "usable_inventory"
    ] = warehouse_data[
        "usable_inventory"
    ].clip(
        lower=0
    )


    # Remove destination warehouse

    candidates = warehouse_data[
        warehouse_data[
            "warehouse_id"
        ]
        != destination_warehouse
    ].copy()


    candidates = candidates[
        candidates[
            "usable_inventory"
        ] > 0
    ]


    if candidates.empty:

        return {

            "status":
                "NO_SURPLUS_WAREHOUSE",

            "shortage":
                round(
                    shortage,
                    2
                )

        }


    # ======================================
    # SELECT BEST SOURCE
    # ======================================

    candidates = candidates.sort_values(

        "usable_inventory",

        ascending=False

    )


    source = candidates.iloc[0]


    transferable = min(

        shortage,

        source[
            "usable_inventory"
        ]

    )


    remaining_shortage = (

        shortage
        - transferable

    )


    # ======================================
    # RESULT
    # ======================================

    return {

        "status":
            "TRANSFER_RECOMMENDED",

        "source_warehouse":
            source[
                "warehouse_id"
            ],

        "destination_warehouse":
            destination_warehouse,

        "transfer_quantity":
            round(
                transferable,
                2
            ),

        "remaining_shortage":
            round(
                remaining_shortage,
                2
            )

    }


# ==========================================
# INTERACTIVE TEST
# ==========================================

print(
    "\n=========================================="
)

print(
    "       INVENTORY ALLOCATION"
)

print(
    "=========================================="
)


destination = input(
    "\nDestination Warehouse ID: "
).strip()


current_stock = float(
    input(
        "Current stock: "
    )
)


required_stock = float(
    input(
        "Required stock: "
    )
)


result = find_stock_transfer(

    destination,

    current_stock,

    required_stock

)


print(
    "\n=========================================="
)

print(
    "ALLOCATION RESULT"
)

print(
    "=========================================="
)


if result["status"] == "NO_TRANSFER_REQUIRED":

    print(
        "Status: Stock is sufficient."
    )


elif result["status"] == "NO_SURPLUS_WAREHOUSE":

    print(
        "Status: No warehouse has enough surplus stock."
    )

    print(
        f"Shortage: "
        f"{result['shortage']:.2f} units"
    )


else:

    print(
        "Status: TRANSFER RECOMMENDED"
    )

    print(
        f"Source: "
        f"{result['source_warehouse']}"
    )

    print(
        f"Destination: "
        f"{result['destination_warehouse']}"
    )

    print(
        f"Transfer quantity: "
        f"{result['transfer_quantity']:.2f} units"
    )

    print(
        f"Remaining shortage: "
        f"{result['remaining_shortage']:.2f} units"
    )


print(
    "\n=========================================="
)