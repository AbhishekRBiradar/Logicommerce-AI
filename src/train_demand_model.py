import pandas as pd
import numpy as np

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

from sklearn.ensemble import RandomForestRegressor

from xgboost import XGBRegressor


# ==========================================
# LOAD DATA
# ==========================================

print("Loading demand dataset...")

df = pd.read_csv(
    "data/daily_demand.csv"
)

df["date"] = pd.to_datetime(
    df["date"]
)


print(
    "Dataset shape:",
    df.shape
)


# ==========================================
# SORT BY DATE
# ==========================================

df = df.sort_values(
    "date"
).reset_index(drop=True)


# ==========================================
# FEATURES
# ==========================================

features = [

    "product_id",
    "category",
    "city",

    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",

    "promotion"

]


target = "demand"


X = df[features]

y = df[target]


# ==========================================
# TIME-BASED TRAIN / TEST SPLIT
# ==========================================

split_date = pd.Timestamp(
    "2026-07-01"
)


train_mask = (
    df["date"] < split_date
)


test_mask = (
    df["date"] >= split_date
)


X_train = X[train_mask]

X_test = X[test_mask]

y_train = y[train_mask]

y_test = y[test_mask]


print(
    "\nTraining samples:",
    len(X_train)
)

print(
    "Testing samples:",
    len(X_test)
)


# ==========================================
# CATEGORICAL FEATURES
# ==========================================

categorical_features = [

    "product_id",
    "category",
    "city"

]


numeric_features = [

    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "promotion"

]


preprocessor = ColumnTransformer(

    transformers=[

        (
            "categorical",

            OneHotEncoder(
                handle_unknown="ignore"
            ),

            categorical_features

        )

    ],

    remainder="passthrough"

)


# ==========================================
# BASELINE MODEL
# ==========================================

print(
    "\nTraining baseline Random Forest..."
)


baseline_model = Pipeline(

    steps=[

        (
            "preprocessor",
            preprocessor
        ),

        (
            "model",

            RandomForestRegressor(

                n_estimators=100,

                max_depth=10,

                random_state=42,

                n_jobs=-1

            )

        )

    ]

)


baseline_model.fit(
    X_train,
    y_train
)


baseline_predictions = (
    baseline_model.predict(X_test)
)


baseline_mae = mean_absolute_error(
    y_test,
    baseline_predictions
)


baseline_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        baseline_predictions
    )
)


print("\n==========================================")
print("BASELINE RESULTS")
print("==========================================")

print(
    "MAE  :",
    round(baseline_mae, 4)
)

print(
    "RMSE :",
    round(baseline_rmse, 4)
)


# ==========================================
# XGBOOST
# ==========================================

print(
    "\nTraining XGBoost..."
)


xgb_model = Pipeline(

    steps=[

        (
            "preprocessor",

            preprocessor

        ),

        (
            "model",

            XGBRegressor(

                n_estimators=300,

                max_depth=6,

                learning_rate=0.05,

                subsample=0.8,

                colsample_bytree=0.8,

                objective="reg:squarederror",

                random_state=42,

                n_jobs=-1

            )

        )

    ]

)


xgb_model.fit(
    X_train,
    y_train
)


xgb_predictions = (
    xgb_model.predict(X_test)
)


xgb_mae = mean_absolute_error(
    y_test,
    xgb_predictions
)


xgb_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        xgb_predictions
    )
)


print("\n==========================================")
print("XGBOOST RESULTS")
print("==========================================")

print(
    "MAE  :",
    round(xgb_mae, 4)
)

print(
    "RMSE :",
    round(xgb_rmse, 4)
)


# ==========================================
# COMPARISON
# ==========================================

print("\n==========================================")
print("MODEL COMPARISON")
print("==========================================")

print(
    f"{'Model':<20}"
    f"{'MAE':<12}"
    f"{'RMSE':<12}"
)

print(
    f"{'Random Forest':<20}"
    f"{baseline_mae:<12.4f}"
    f"{baseline_rmse:<12.4f}"
)

print(
    f"{'XGBoost':<20}"
    f"{xgb_mae:<12.4f}"
    f"{xgb_rmse:<12.4f}"
)


# ==========================================
# BEST MODEL
# ==========================================

if xgb_mae < baseline_mae:

    print(
        "\n🏆 Best model: XGBoost"
    )

else:

    print(
        "\n🏆 Best model: Random Forest"
    )