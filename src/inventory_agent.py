import pandas as pd
import joblib


# ==========================================
# LOAD DATA
# ==========================================

print("Loading inventory intelligence...")

model = joblib.load(
    "models/demand_xgboost.pkl"
)

demand_df = pd.read_csv(
    "data/demand_features.csv"
)

demand_df["date"] = pd.to_datetime(
    demand_df["date"]
)


# ==========================================
# INVENTORY DATA
# ==========================================

inventory = pd.read_csv(
    "data/warehouses.csv"
)


# ==========================================
# INVENTORY ANALYSIS
# ==========================================

def analyze_inventory(
    product_id,
    city,
    current_stock
):

    # Find product history

    history = demand_df[
        (demand_df["product_id"] == product_id)
        &
        (demand_df["city"] == city)
    ].copy()


    if history.empty:

        return {
            "error":
            "No demand history found."
        }


    # Latest demand information

    latest = history.sort_values(
        "date"
    ).iloc[-1]


    # ======================================
    # PREDICT DAILY DEMAND
    # ======================================

    input_data = pd.DataFrame([{

        "product_id":
            latest["product_id"],

        "category":
            latest["category"],

        "city":
            latest["city"],

        "day_of_week":
            latest["day_of_week"],

        "day_of_month":
            latest["day_of_month"],

        "month":
            latest["month"],

        "is_weekend":
            latest["is_weekend"],

        "promotion":
            latest["promotion"],

        "lag_1":
            latest["lag_1"],

        "lag_7":
            latest["lag_7"],

        "lag_14":
            latest["lag_14"],

        "rolling_7":
            latest["rolling_7"],

        "rolling_14":
            latest["rolling_14"]

    }])


    predicted_daily = model.predict(
        input_data
    )[0]


    predicted_daily = max(
        0,
        predicted_daily
    )


    # ======================================
    # 7-DAY DEMAND
    # ======================================

    predicted_7_day = (
        predicted_daily * 7
    )


    # ======================================
    # SAFETY STOCK
    # ======================================

    safety_stock = max(
        2,
        predicted_7_day * 0.20
    )


    required_stock = (
        predicted_7_day
        + safety_stock
    )


    stock_difference = (
        current_stock
        - required_stock
    )


    # ======================================
    # INVENTORY STATUS
    # ======================================

    if current_stock < predicted_7_day:

        status = "CRITICAL"

        action = (
            "Immediate replenishment or "
            "stock transfer required."
        )


    elif current_stock < required_stock:

        status = "LOW"

        action = (
            "Increase stock or transfer "
            "additional units."
        )


    else:

        status = "HEALTHY"

        action = (
            "Current stock is sufficient."
        )


    # ======================================
    # RETURN RESULT
    # ======================================

    return {

        "product_id":
            product_id,

        "city":
            city,

        "current_stock":
            round(
                current_stock,
                2
            ),

        "predicted_daily_demand":
            round(
                predicted_daily,
                2
            ),

        "predicted_7_day_demand":
            round(
                predicted_7_day,
                2
            ),

        "safety_stock":
            round(
                safety_stock,
                2
            ),

        "required_stock":
            round(
                required_stock,
                2
            ),

        "stock_difference":
            round(
                stock_difference,
                2
            ),

        "status":
            status,

        "action":
            action

    }


# ==========================================
# INTERACTIVE MODE
# ==========================================

print("\n==========================================")
print("       INVENTORY INTELLIGENCE")
print("==========================================")


product_id = input(
    "\nEnter Product ID: "
).strip()


city = input(
    "Enter City: "
).strip()


stock_input = input(
    "Enter Current Stock: "
).strip()


try:

    current_stock = float(
        stock_input
    )

except ValueError:

    print(
        "\n❌ Invalid stock value."
    )

    raise SystemExit


result = analyze_inventory(
    product_id,
    city,
    current_stock
)


# ==========================================
# DISPLAY
# ==========================================

if "error" in result:

    print(
        "\n❌",
        result["error"]
    )

else:

    print(
        "\n=========================================="
    )

    print(
        "INVENTORY ANALYSIS"
    )

    print(
        "=========================================="
    )

    print(
        f"Product: {result['product_id']}"
    )

    print(
        f"City: {result['city']}"
    )


    print(
        "\n------------------------------------------"
    )

    print(
        "DEMAND FORECAST"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Predicted daily demand: "
        f"{result['predicted_daily_demand']:.2f}"
    )

    print(
        f"Predicted 7-day demand: "
        f"{result['predicted_7_day_demand']:.2f}"
    )


    print(
        "\n------------------------------------------"
    )

    print(
        "INVENTORY"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Current stock: "
        f"{result['current_stock']:.2f}"
    )

    print(
        f"Safety stock: "
        f"{result['safety_stock']:.2f}"
    )

    print(
        f"Required stock: "
        f"{result['required_stock']:.2f}"
    )


    print(
        "\n------------------------------------------"
    )

    print(
        "AI DECISION"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Status: {result['status']}"
    )

    print(
        f"Stock difference: "
        f"{result['stock_difference']:.2f}"
    )

    print(
        f"Action: {result['action']}"
    )


    print(
        "\n=========================================="
    )