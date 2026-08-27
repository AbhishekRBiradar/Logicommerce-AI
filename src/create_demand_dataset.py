import pandas as pd
import numpy as np


np.random.seed(42)


# ==========================================
# LOAD DATA
# ==========================================

print("Loading orders...")

orders = pd.read_csv("data/orders.csv")
products = pd.read_csv("data/products.csv")

orders["order_date"] = pd.to_datetime(
    orders["order_date"]
)


# ==========================================
# PRODUCT INFORMATION
# ==========================================

product_info = products[
    [
        "product_id",
        "category"
    ]
].drop_duplicates()


# ==========================================
# PRODUCT-CITY COMBINATIONS
# ==========================================

product_city = orders[
    [
        "product_id",
        "destination"
    ]
].drop_duplicates()


product_city = product_city.merge(
    product_info,
    on="product_id",
    how="left"
)


product_city.rename(
    columns={
        "destination": "city"
    },
    inplace=True
)


print(
    "Product-city combinations:",
    len(product_city)
)


# ==========================================
# DATE RANGE
# ==========================================

dates = pd.date_range(
    "2026-01-01",
    "2026-08-26",
    freq="D"
)


date_df = pd.DataFrame({
    "date": dates
})


# ==========================================
# CREATE COMPLETE GRID
# ==========================================

date_df["_key"] = 1
product_city["_key"] = 1


daily = date_df.merge(
    product_city,
    on="_key"
).drop(
    columns="_key"
)


# ==========================================
# ACTUAL HISTORICAL SALES
# ==========================================

sales = (
    orders
    .groupby(
        [
            "order_date",
            "product_id",
            "destination"
        ]
    )["quantity"]
    .sum()
    .reset_index()
)


sales.rename(
    columns={
        "order_date": "date",
        "destination": "city",
        "quantity": "actual_sales"
    },
    inplace=True
)


daily = daily.merge(
    sales,
    on=[
        "date",
        "product_id",
        "city"
    ],
    how="left"
)


daily["actual_sales"] = (
    daily["actual_sales"]
    .fillna(0)
)


# ==========================================
# CALENDAR FEATURES
# ==========================================

daily["day_of_week"] = (
    daily["date"].dt.dayofweek
)

daily["day_of_month"] = (
    daily["date"].dt.day
)

daily["month"] = (
    daily["date"].dt.month
)

daily["is_weekend"] = (
    daily["day_of_week"] >= 5
).astype(int)


# ==========================================
# PRODUCT POPULARITY
# ==========================================

product_sales = (
    orders
    .groupby("product_id")["quantity"]
    .sum()
)


product_sales = (
    product_sales
    / product_sales.mean()
)


daily["product_popularity"] = (
    daily["product_id"]
    .map(product_sales)
    .fillna(1.0)
)


# Limit extreme popularity

daily["product_popularity"] = (
    daily["product_popularity"]
    .clip(0.3, 3.0)
)


# ==========================================
# CITY DEMAND FACTOR
# ==========================================

city_factor = {

    "Bangalore": 1.40,

    "Mumbai": 1.30,

    "Delhi": 1.25,

    "Chennai": 1.15,

    "Hyderabad": 1.10,

    "Pune": 1.00,

    "Mysore": 0.80,

    "Tumkur": 0.70

}


daily["city_factor"] = (
    daily["city"]
    .map(city_factor)
)


# ==========================================
# CATEGORY FACTOR
# ==========================================

category_factor = {

    "Mobile": 1.30,

    "Laptop": 1.15,

    "Electronics": 1.20,

    "Fashion": 1.10,

    "Grocery": 1.25,

    "Beauty": 0.90,

    "Home": 0.95,

    "Accessories": 1.00

}


daily["category_factor"] = (
    daily["category"]
    .map(category_factor)
)


# ==========================================
# PROMOTIONS
# ==========================================

daily["promotion"] = np.random.choice(

    [0, 1],

    size=len(daily),

    p=[0.80, 0.20]

)


# ==========================================
# SEASONAL FACTORS
# ==========================================

daily["season_factor"] = 1.0


# Weekend

daily.loc[
    daily["is_weekend"] == 1,
    "season_factor"
] *= 1.20


# Month-end

daily.loc[
    daily["day_of_month"] >= 25,
    "season_factor"
] *= 1.10


# Promotion

daily.loc[
    daily["promotion"] == 1,
    "season_factor"
] *= 1.35


# ==========================================
# BASE DEMAND
# ==========================================

base_demand = (

    1.5

    * daily["product_popularity"]

    * daily["city_factor"]

    * daily["category_factor"]

    * daily["season_factor"]

)


# ==========================================
# HISTORICAL SALES SIGNAL
# ==========================================

historical_signal = (

    0.35
    * daily["actual_sales"]

)


# ==========================================
# RANDOM DEMAND
# ==========================================

noise = np.random.normal(

    1.0,

    0.20,

    len(daily)

)


noise = np.clip(
    noise,
    0.60,
    1.50
)


# ==========================================
# FINAL DEMAND
# ==========================================

daily["demand"] = np.maximum(

    0,

    np.round(

        (
            base_demand
            + historical_signal
        )
        * noise

    )

).astype(int)


# ==========================================
# REMOVE TEMPORARY COLUMNS
# ==========================================

daily = daily[
    [
        "date",
        "product_id",
        "category",
        "city",
        "day_of_week",
        "day_of_month",
        "month",
        "is_weekend",
        "promotion",
        "demand"
    ]
]


# ==========================================
# SAVE
# ==========================================

daily.to_csv(
    "data/daily_demand.csv",
    index=False
)


# ==========================================
# SUMMARY
# ==========================================

zero_rows = (
    daily["demand"] == 0
).sum()


total_rows = len(daily)


zero_percentage = (
    zero_rows / total_rows * 100
)


print("\n==========================================")
print("REALISTIC DEMAND DATASET")
print("==========================================")

print(
    "Rows:",
    total_rows
)

print(
    "Products:",
    daily["product_id"].nunique()
)

print(
    "Cities:",
    daily["city"].nunique()
)

print(
    "Average demand:",
    round(
        daily["demand"].mean(),
        2
    )
)

print(
    "Zero-demand rows:",
    zero_rows
)

print(
    "Zero-demand percentage:",
    round(
        zero_percentage,
        2
    ),
    "%"
)

print(
    "\nDemand statistics:"
)

print(
    daily["demand"].describe()
)

print(
    "\nSaved to:"
    " data/daily_demand.csv"
)