import pandas as pd
import numpy as np
import joblib

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.ensemble import RandomForestRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

from xgboost import XGBRegressor


# ==========================================
# LOAD DATA
# ==========================================

print("Loading demand features...")

df = pd.read_csv(
    "data/demand_features.csv"
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
    "promotion",

    "lag_1",
    "lag_7",
    "lag_14",

    "rolling_7",
    "rolling_14"

]


target = "demand"


X = df[features]

y = df[target]


# ==========================================
# TIME-BASED SPLIT
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
# PREPROCESSING
# ==========================================

categorical_features = [

    "product_id",
    "category",
    "city"

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
# RANDOM FOREST
# ==========================================

print(
    "\nTraining Random Forest..."
)

rf_model = Pipeline(

    steps=[

        (
            "preprocessor",
            preprocessor
        ),

        (
            "model",

            RandomForestRegressor(

                n_estimators=50,

                max_depth=10,

                min_samples_leaf=2,

                random_state=42,

                n_jobs=-1

            )

        )

    ]

)


rf_model.fit(
    X_train,
    y_train
)


rf_predictions = (
    rf_model.predict(X_test)
)


rf_mae = mean_absolute_error(
    y_test,
    rf_predictions
)


rf_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        rf_predictions
    )
)


print(
    "\nRandom Forest complete."
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

                n_estimators=200,

                max_depth=6,

                learning_rate=0.05,

                subsample=0.8,

                colsample_bytree=0.8,

                min_child_weight=3,

                objective="reg:squarederror",

                eval_metric="mae",

                tree_method="hist",

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

print(
    "\nXGBoost complete."
)

joblib.dump(
    xgb_model,
    "models/demand_xgboost.pkl"
)

print(
    "✓ XGBoost model saved to:"
    " models/demand_xgboost.pkl"
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


print(
    "\nXGBoost complete."
)

joblib.dump(
    xgb_model,
    "models/demand_xgboost.pkl"
)

print(
    "\n✓ XGBoost model saved to:"
    " models/demand_xgboost.pkl"
)


# ==========================================
# RESULTS
# ==========================================

print(
    "\n=========================================="
)

print(
    "IMPROVED DEMAND MODEL RESULTS"
)

print(
    "=========================================="
)


print(
    f"{'Model':<20}"
    f"{'MAE':<12}"
    f"{'RMSE':<12}"
)


print(
    f"{'Random Forest':<20}"
    f"{rf_mae:<12.4f}"
    f"{rf_rmse:<12.4f}"
)


print(
    f"{'XGBoost':<20}"
    f"{xgb_mae:<12.4f}"
    f"{xgb_rmse:<12.4f}"
)


# ==========================================
# COMPARE
# ==========================================

if rf_mae < xgb_mae:

    best_model = "Random Forest"

else:

    best_model = "XGBoost"


print(
    "\n🏆 Best model:",
    best_model
)


# ==========================================
# SAMPLE PREDICTIONS
# ==========================================

results = X_test.copy()

results["actual"] = (
    y_test.values
)

results["rf_prediction"] = (
    np.round(
        rf_predictions,
        2
    )
)

results["xgb_prediction"] = (
    np.round(
        xgb_predictions,
        2
    )
)


print(
    "\n=========================================="
)

print(
    "SAMPLE PREDICTIONS"
)

print(
    "=========================================="
)


print(
    results[
        [
            "product_id",
            "city",
            "lag_1",
            "lag_7",
            "rolling_7",
            "actual",
            "rf_prediction",
            "xgb_prediction"
        ]
    ].head(10)
)