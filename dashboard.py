import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(
    page_title="Accurator AI Dashboard",
    page_icon="🔬",
    layout="wide"
)

API_URL = "http://127.0.0.1:8000/sensors/batch"

st.title("🔬 Accurator AI")
st.subheader("Self-Calibrating Sensor Monitoring Dashboard")

st.divider()

# Sensor input
st.markdown("### 📡 Live Sensor Readings")

col1, col2, col3 = st.columns(3)

with col1:
    t01 = st.number_input("T01 - Temperature", value=25.4)
    t02 = st.number_input("T02 - Temperature", value=26.1)

with col2:
    h01 = st.number_input("H01 - Humidity", value=62.5)
    h02 = st.number_input("H02 - Humidity", value=64.2)

with col3:
    c01 = st.number_input("C01 - CO₂", value=720.0)
    c02 = st.number_input("C02 - CO₂", value=735.0)

if st.button("🚀 Analyze Sensors", use_container_width=True):

    payload = {
        "sensors": [
            {"id": "T01", "parameter": "temperature", "raw_value": t01},
            {"id": "T02", "parameter": "temperature", "raw_value": t02},
            {"id": "H01", "parameter": "humidity", "raw_value": h01},
            {"id": "H02", "parameter": "humidity", "raw_value": h02},
            {"id": "C01", "parameter": "co2", "raw_value": c01},
            {"id": "C02", "parameter": "co2", "raw_value": c02}
        ]
    }

    try:
        response = requests.post(API_URL, json=payload)

        if response.status_code == 200:

            data = response.json()

            st.success("✅ Sensor analysis completed")

            sensors = data["sensors"]

            # Summary
            healthy = sum(s["status"] == "healthy" for s in sensors)
            warning = sum(s["status"] == "warning" for s in sensors)
            unhealthy = sum(s["status"] == "unhealthy" for s in sensors)

            a, b, c = st.columns(3)

            a.metric("🟢 Healthy", healthy)
            b.metric("🟡 Warning", warning)
            c.metric("🔴 Unhealthy", unhealthy)

            st.divider()

            # Sensor cards
            st.markdown("### 📊 Sensor Health")

            for sensor in sensors:

                status = sensor["status"]

                if status == "healthy":
                    icon = "🟢"
                elif status == "warning":
                    icon = "🟡"
                else:
                    icon = "🔴"

                st.markdown(
                    f"""
                    ### {icon} {sensor['id']} — {sensor['parameter'].upper()}

                    **Status:** `{status.upper()}`  
                    **Raw Value:** `{sensor['raw_value']}`  
                    **Corrected Value:** `{sensor['corrected_value']}`  
                    **Health:** `{sensor['health']}`  
                    **Drift:** `{sensor['drift']}`  
                    **Anomaly Score:** `{sensor['anomaly_score']}`
                    """
                )

                st.progress(
                    max(0, min(100, float(sensor["health"])) / 100)
                )

                st.divider()

            # Table
            st.markdown("### 📋 Sensor Data")

            df = pd.DataFrame(sensors)

            display_columns = [
                "id",
                "parameter",
                "raw_value",
                "corrected_value",
                "drift",
                "health",
                "status",
                "anomaly_score"
            ]

            st.dataframe(
                df[display_columns],
                use_container_width=True
            )

            # Graph
            st.markdown("### 📈 Raw vs Calibrated Values")

            chart_df = df[
                ["id", "raw_value", "corrected_value"]
            ].set_index("id")

            st.bar_chart(chart_df)

        else:
            st.error(f"Backend error: {response.status_code}")

    except Exception as e:
        st.error(f"Could not connect to backend: {e}")