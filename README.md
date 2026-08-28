# 🚚 Logicommerce AI

## AI-Powered Logistics Optimization Platform

Logicommerce AI is an intelligent logistics optimization system designed to improve warehouse-to-warehouse shipment planning by combining shipment consolidation, vehicle selection, route optimization, fleet utilization, fuel-cost analysis, and deadline-aware dispatch decisions.

The system analyzes shipment weight, shipment volume, vehicle capacity, vehicle volume capacity, fuel efficiency, warehouse distance, shipment priority, and delivery deadlines to generate optimized logistics plans.

---

## 📌 Problem Statement

Logistics operations commonly face problems such as:

- Under-utilized vehicles
- Excess fuel consumption
- Unnecessary separate trips
- Poor shipment consolidation
- Vehicle capacity mismatch
- Delayed shipments
- Inefficient warehouse-to-warehouse routing
- Increasing transportation costs

For example, sending a small shipment using a large 5,000 kg / 50 m³ vehicle may result in very low vehicle utilization.

Logicommerce AI addresses these problems by selecting suitable vehicles and consolidating compatible shipments when doing so provides operational and cost benefits.

---

## 🎯 Objectives

The main objectives of Logicommerce AI are:

1. Reduce transportation and fuel costs.
2. Improve vehicle weight and volume utilization.
3. Consolidate compatible shipments.
4. Protect urgent shipments from unnecessary consolidation delays.
5. Select vehicles according to shipment requirements.
6. Optimize warehouse-to-warehouse routes.
7. Monitor shipment deadline performance.
8. Provide explainable logistics decisions.
9. Generate an operational dispatch plan.
10. Provide a visual logistics dashboard.

---

## 🧠 Key Features

### 📦 Shipment Consolidation

Groups compatible shipments from the same source and destination when consolidation can reduce transportation cost while satisfying capacity and deadline requirements.

### 🚛 Vehicle Selection

Vehicle selection considers:

- Weight capacity
- Volume capacity
- Fuel efficiency
- Shipment weight
- Shipment volume

This helps avoid unnecessary use of oversized vehicles.

### 🛣️ Route Optimization

The system evaluates warehouse-to-warehouse routes using the warehouse distance network and supports optimized logistics movement across multiple warehouses.

### ⏱️ Deadline Awareness

Transfers are evaluated using:

- `ON_TIME`
- `AT_RISK`
- `MISSED_DEADLINE`

Urgent shipments can be kept separate to reduce the risk of consolidation-related delays.

### ⛽ Fuel Optimization

Fuel consumption is estimated using:

`Fuel = Distance / Vehicle Fuel Efficiency`

## System Architecture

<img src="https://raw.githubusercontent.com/AbhishekRBiradar/Logicommerce-AI/main/docs/architecture.png" alt="Logicommerce AI Architecture" width="100%">

The overall workflow is:

Input Data → Shipment Intelligence → Shipment Consolidation → Vehicle Selection → Route Optimization → Fuel & Cost Optimization → Deadline Validation → Final Logistics Plan → Streamlit Dashboard

## 📊 Dashboard

The Streamlit dashboard provides:

- Operations overview
- Cost comparison
- Deadline monitoring
- Dispatch strategy
- Fleet utilization
- AI decision explanations
- Final logistics plan
- CSV export

## 📈 Demonstration Results

The current validated demonstration run produced:

- Total transfers: 30
- Transfers assigned: 30
- Transfers unassigned: 0
- Routes created: 20
- Consolidated routes: 6
- Separate routes: 7
- Urgent separate routes: 7
- Total distance: 14,910 km
- Total fuel: 1,023.76 L
- Optimized cost: ₹102,374.89
- Baseline cost: ₹219,400.00
- Estimated savings: ₹117,025.11
- Overall savings: 53.3%
- Average weight utilization: 14.4%
- Average volume utilization: 33.0%
- ON_TIME routes: 17
- AT_RISK routes: 0
- MISSED_DEADLINE routes: 3

These values correspond to the current demonstration dataset and may change when the transfer-request dataset is regenerated.

## 🧪 Validation

The final pipeline verifies that every transfer is accounted for.

Current validation:

- Expected transfers: 30
- Accounted transfers: 30
- Missing transfers: 0
- Transfer accounting validation: PASSED

## 🔬 Optimization Methodology

Logicommerce AI uses a layered decision process:

1. Shipment Intelligence
2. Shipment Consolidation
3. Vehicle Matching
4. Route Planning
5. Fuel Optimization
6. Cost Optimization
7. Deadline Validation
8. Explainable Decision Generation

## 📦 Example Decision

**Decision:** CONSOLIDATE

**Route:** WH01 → WH02 → WH01

**Transfers:** TRF00001, TRF00007, TRF00024, TRF00030

**Vehicle:** VEH025

The system combines compatible shipments when capacity constraints are satisfied and the combined dispatch provides a cost benefit without compromising deadline feasibility.

## 🎯 Business Impact

Logicommerce AI is designed to help logistics operations:

- Reduce fuel consumption
- Reduce unnecessary trips
- Improve fleet utilization
- Reduce transportation cost
- Improve shipment consolidation
- Protect urgent shipments
- Improve deadline visibility
- Support data-driven dispatch decisions

## 🚀 Future Improvements

Potential future extensions include:

- Real-time GPS tracking
- Live traffic integration
- Dynamic fuel-price integration
- Real-time vehicle availability
- Predictive ETA models
- Machine-learning-based delay prediction
- PostgreSQL or cloud database integration
- REST API integration
- Real-time event processing
- Advanced fleet optimization
- Cloud deployment
- Authentication and role-based access
- Reinforcement learning for dynamic routing

## 🎓 Skills Demonstrated

Python · Pandas · NumPy · Operations Research · Constraint Optimization · Google OR-Tools · Route Optimization · Fleet Optimization · Shipment Consolidation · Fuel Optimization · Cost Optimization · Deadline-Aware Planning · Streamlit · Git · GitHub · System Design


## 🔗 Repository

https://github.com/AbhishekRBiradar/Logicommerce-AI

## 👨‍💻 Author

**Abhishek Rajkumar Biradar**

AI & Machine Learning Student

## ⭐ Project Status

Core optimization engine ✅

Shipment consolidation ✅

Vehicle optimization ✅

Route optimization ✅

Fuel optimization ✅

Deadline analysis ✅

Transfer validation ✅

Streamlit dashboard ✅

GitHub repository ✅

README documentation ✅

## 📄 License

This project is intended for educational, portfolio and demonstration purposes.
