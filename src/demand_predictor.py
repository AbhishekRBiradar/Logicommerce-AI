import pandas as pd
import numpy as np
import joblib


# ==========================================
# LOAD MODEL
# ==========================================

print("Loading Demand Intelligence model...")

model = joblib.load(
    "models/demand_xgboost.pkl"
)

print("Model loaded successfully.")


# ==========================================
# LOAD DEMAND HISTORY
# ==========================================

df = pd.read_csv(
    "data/demand_features.csv"
)

df["date"] = pd.to_datetime(
    df["date"]
)


# ==========================================
# PREDICTION FUNCTION
# ==========================================

def predict_demand(product_id, city):

    # Find product + city history

    history = df[
        (df["product_id"] == product_id)
        &
        (df["city"] == city)
    ].copy()


    if history.empty:

        return {
            "error":
            "No demand history found."
        }


    # Latest record

    latest = history.sort_values(
        "date"
    ).iloc[-1]


    # ======================================
    # CREATE INPUT
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


    # ======================================
    # PREDICT
    # ======================================

    prediction = model.predict(
        input_data
    )[0]


    prediction = max(
        0,
        prediction
    )


    # ======================================
    # 7-DAY ESTIMATE
    # ======================================

    seven_day_demand = (
        prediction * 7
    )


    return {

        "product_id":
            product_id,

        "city":
            city,

        "latest_date":
            latest["date"].strftime(
                "%Y-%m-%d"
            ),

        "yesterday_demand":
            float(latest["lag_1"]),

        "seven_day_average":
            round(
                float(
                    latest["rolling_7"]
                ),
                2
            ),

        "fourteen_day_average":
            round(
                float(
                    latest["rolling_14"]
                ),
                2
            ),

        "predicted_daily_demand":
            round(
                float(prediction),
                2
            ),

        "estimated_7_day_demand":
            round(
                float(seven_day_demand),
                2
            )

    }


# ==========================================
# INTERACTIVE MODE
# ==========================================

print("\n==========================================")
print("       DEMAND INTELLIGENCE")
print("==========================================")

product_id = input(
    "\nEnter Product ID: "
).strip()


city = input(
    "Enter City: "
).strip()


result = predict_demand(
    product_id,
    city
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
        "DEMAND FORECAST"
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
        f"Latest data: {result['latest_date']}"
    )

    print(
        "\n------------------------------------------"
    )

    print(
        "HISTORICAL DEMAND"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Yesterday: "
        f"{result['yesterday_demand']:.0f} units"
    )

    print(
        f"7-day average: "
        f"{result['seven_day_average']:.2f} units"
    )

    print(
        f"14-day average: "
        f"{result['fourteen_day_average']:.2f} units"
    )

    print(
        "\n------------------------------------------"
    )

    print(
        "AI FORECAST"
    )

    print(
        "------------------------------------------"
    )

    print(
        f"Predicted daily demand: "
        f"{result['predicted_daily_demand']:.2f} units"
    )

    print(
        f"Estimated 7-day demand: "
        f"{result['estimated_7_day_demand']:.2f} units"
    )

    print(
        "\n=========================================="
    )