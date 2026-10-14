# ☀️ Climate Intelligence: Heatwave Monitoring & Early Warning System

An end-to-end real-time climate intelligence and environmental risk monitoring platform engineered for detecting, analyzing, and alerting on extreme heatwave events across geographic regions.

![Dashboard Preview](https://img.shields.io/badge/Status-Active-success)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)
![Leaflet](https://img.shields.io/badge/Map-Leaflet.js-199900?logo=leaflet&logoColor=white)
![Streamlit](https://img.shields.io/badge/Analytics-Streamlit-FF4B4B?logo=streamlit&logoColor=white)

---

## 🌟 Key Features

- **Geospatial Real-Time Heat Map**: Interactive Leaflet-powered heat map displaying real-time weather stations, heat index values, and localized risk zones.
- **Automated Alert Generation**: Real-time detection of temperature spikes, severe heat index thresholds, and automated alert dispatching.
- **FastAPI Backend & SSE**: High-performance RESTful APIs and Server-Sent Events (SSE) for live streaming of sensor updates.
- **PostgreSQL Database Engine**: Optimized relational schemas with partitioned readings, stored procedures, triggers, materialized views, and analytical queries.
- **Sensor Telemetry Simulator**: Background simulator that mimics continuous IoT sensor telemetry across multiple regional weather stations with stochastic heatwave spikes.
- **Streamlit Analytics Dashboard**: Comprehensive data science and historical analytics exploration interface with Plotly charts.
- **Offline / Standalone Fallback**: Built-in mock data engine ensuring frontend UI and API endpoints can run independently even if PostgreSQL is offline.

---

## 🏗️ Architecture

```
                                  +---------------------------+
                                  |   Sensor Simulator (IoT)  |
                                  |      (simulator.py)       |
                                  +-------------+-------------+
                                                |
                                                v
+-----------------------+         +-------------+-------------+
|    Web Dashboard      | <====== |      FastAPI Server       |
| (HTML5 / CSS / JS)    |   SSE   |         (api.py)          |
+-----------------------+  & REST +-------------+-------------+
                                                |
                                                v
+-----------------------+         +-------------+-------------+
|  Streamlit Analytics  | <====== |    PostgreSQL Database    |
|    (dashboard.py)     |         |   (schema & procedures)   |
+-----------------------+         +---------------------------+
```

---

## 📂 Project Structure

```
├── api.py                  # FastAPI application with REST & SSE endpoints
├── app.js                  # Frontend client application logic & Leaflet map integration
├── dashboard.py            # Streamlit interactive exploratory analytics dashboard
├── simulator.py            # Real-time weather station sensor simulator
├── mock_data.py            # Fallback mock data provider for zero-dependency demos
├── check_db.py             # Database connectivity & health checker
├── index.html              # Modern dark-mode web monitoring dashboard
├── style.css               # Glassmorphic, modern UI design styles
├── schema.sql              # Core database schema (tables, foreign keys, indexes)
├── advanced_objects.sql    # Functions, triggers, views & stored procedures
├── dml.sql                 # Seed and reference data inserts
├── queries.sql             # Analytical reporting queries
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables configuration template
└── .gitignore              # Ignored files (secrets, cache, virtualenvs)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- PostgreSQL 14+ (optional for mock mode, required for full persistence)

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Vedantranecodes/Heatwave-monitoring-.git
cd Heatwave-monitoring-
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Configure your PostgreSQL credentials and simulation parameters in `.env`:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=heatwave_db
DB_USER=postgres
DB_PASSWORD=your_password_here
SIMULATION_INTERVAL_SEC=5
SPIKE_PROBABILITY=0.10
```

### 4. Database Setup (Optional if using Mock Mode)

Execute SQL scripts in order:

```bash
psql -U postgres -d heatwave_db -f schema.sql
psql -U postgres -d heatwave_db -f advanced_objects.sql
psql -U postgres -d heatwave_db -f dml.sql
```

Verify connection:
```bash
python check_db.py
```

---

## 🖥️ Running the Application

### Option A: Run the FastAPI Backend & Web Dashboard

Start the API server:
```bash
uvicorn api:app --reload --port 8000
```
Open `index.html` directly in your browser or serve via any static file server (e.g. `python -m http.server 3000`).

### Option B: Run the IoT Telemetry Simulator

To continuously stream sensor data to PostgreSQL:
```bash
python simulator.py
```

### Option C: Run the Streamlit Analytics Dashboard

```bash
streamlit run dashboard.py
```

---

## 🛡️ License

This project is licensed under the MIT License.
