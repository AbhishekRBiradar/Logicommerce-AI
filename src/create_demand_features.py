import pandas as pd


# ==========================================
# LOAD DATA
# ==========================================

print("Loading daily demand dataset...")

df = pd.read_csv(
    "data/daily_demand.csv"
)

df["date"] = pd.to_datetime(
    df["date"]
)


# ==========================================
# SORT DATA
# ==========================================

df = df.sort_values(
    [
        "product_id",
        "city",
        "date"
    ]
).reset_index(drop=True)


# ==========================================
# CREATE LAG FEATURES
# ==========================================

grouped = df.groupby(
    [
        "product_id",
        "city"
    ],
    sort=False
)


# Yesterday

df["lag_1"] = grouped["demand"].shift(1)


# Previous available observation
# approximately one week of history

df["lag_7"] = grouped["demand"].shift(7)


# Previous 14 observations

df["lag_14"] = grouped["demand"].shift(14)


# ==========================================
# CREATE ROLLING FEATURES
# ==========================================

df["rolling_7"] = (

    grouped["demand"]

    .transform(
        lambda x:
        x.shift(1)
        .rolling(
            window=7,
            min_periods=1
        )
        .mean()
    )

)


df["rolling_14"] = (

    grouped["demand"]

    .transform(
        lambda x:
        x.shift(1)
        .rolling(
            window=14,
            min_periods=1
        )
        .mean()
    )

)


# ==========================================
# REMOVE ROWS WITHOUT REQUIRED HISTORY
# ==========================================

before = len(df)


df = df.dropna(
    subset=[
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_7",
        "rolling_14"
    ]
).reset_index(drop=True)


after = len(df)


# ==========================================
# SAVE
# ==========================================

df.to_csv(
    "data/demand_features.csv",
    index=False
)


# ==========================================
# SUMMARY
# ==========================================

print("\n==========================================")
print("DEMAND FEATURES CREATED")
print("==========================================")

print(
    "Original rows:",
    before
)

print(
    "Rows after feature creation:",
    after
)

print("\nNew features:")

print("✓ lag_1")
print("✓ lag_7")
print("✓ lag_14")
print("✓ rolling_7")
print("✓ rolling_14")


print(
    "\nSaved to:"
    " data/demand_features.csv"
)


print("\nMissing values in new features:")

print(
    df[
        [
            "lag_1",
            "lag_7",
            "lag_14",
            "rolling_7",
            "rolling_14"
        ]
    ].isnull().sum()
)


print("\nFirst 5 records:")

print(
    df[
        [
            "date",
            "product_id",
            "city",
            "demand",
            "lag_1",
            "lag_7",
            "lag_14",
            "rolling_7",
            "rolling_14"
        ]
    ].head()
)