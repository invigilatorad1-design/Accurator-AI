from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase_client import supabase
from schemas import SensorData
from calibration import (
    CALIBRATION_MODELS,
    EXPECTED_SENSORS,
    calibrate,
    health_from_raw,
)

app = FastAPI(title="Accurator AI Backend")


class BatchSensorData(BaseModel):
    sensors: list[SensorData]


def process_sensor(sensor: SensorData):
    """Automatically calibrate and assess one sensor."""

    if sensor.id not in EXPECTED_SENSORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sensor ID: {sensor.id}. "
                   f"Expected: {sorted(EXPECTED_SENSORS)}",
        )

    expected_parameter = EXPECTED_SENSORS[sensor.id]

    if sensor.parameter.lower() != expected_parameter.lower():
        raise HTTPException(
            status_code=400,
            detail=(
                f"{sensor.id} must use parameter '{expected_parameter}', "
                f"received '{sensor.parameter}'"
            ),
        )

    raw = float(sensor.raw_value)

    # Automatic calibration:
    # corrected_value = gain * raw_value + offset
    corrected, gain, offset = calibrate(sensor.id, raw)

    # Automatic health/status — no manual status required.
    health, status, anomaly_score = health_from_raw(sensor.id, raw)

    # Calibration correction magnitude.
    drift = abs(raw - corrected)

    # Sensor confidence follows health.
    weight = health / 100.0

    return {
        "id": sensor.id,
        "parameter": sensor.parameter,
        "raw_value": raw,
        "corrected_value": round(corrected, 4),
        "drift": round(drift, 4),
        "health": health,
        "weight": round(weight, 4),
        "status": status,
        "calibration_gain": gain,
        "calibration_offset": offset,
        "anomaly_score": anomaly_score,
    }


@app.get("/")
def root():
    return {
        "project": "Accurator AI",
        "status": "Backend running successfully",
        "calibration": "automatic",
        "sensors": sorted(EXPECTED_SENSORS),
    }


@app.get("/test-supabase")
def test_supabase():
    response = supabase.table("sensors").select("*").limit(5).execute()

    return {
        "status": "Supabase connected successfully",
        "records": response.data,
    }


@app.get("/calibration")
def get_calibration_models():
    """Show the learned gain/offset used by the backend."""
    return {
        "formula": "calibrated_value = gain * raw_value + offset",
        "models": CALIBRATION_MODELS,
    }


@app.post("/sensors")
def create_sensor(sensor: SensorData):
    try:
        processed = process_sensor(sensor)

        # Only columns that already exist in Supabase are written.
        db_data = {
            "id": processed["id"],
            "parameter": processed["parameter"],
            "raw_value": processed["raw_value"],
            "corrected_value": processed["corrected_value"],
            "drift": processed["drift"],
            "health": processed["health"],
            "weight": processed["weight"],
            "status": processed["status"],
        }

        response = (
            supabase
            .table("sensors")
            .upsert(db_data)
            .execute()
        )

        return {
            "status": "success",
            "message": "Sensor calibrated and saved successfully",
            "sensor": processed,
            "database": response.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sensors/batch")
def create_sensors_batch(batch: BatchSensorData):
    """Process and save all six sensors automatically."""

    try:
        expected_ids = set(EXPECTED_SENSORS)

        if len(batch.sensors) != 6:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Expected exactly 6 sensors "
                    "(T01, T02, H01, H02, C01, C02), "
                    f"received {len(batch.sensors)}"
                ),
            )

        received_ids = {sensor.id for sensor in batch.sensors}

        if received_ids != expected_ids:
            missing = sorted(expected_ids - received_ids)
            extra = sorted(received_ids - expected_ids)

            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Batch must contain T01, T02, H01, H02, C01 and C02"
                    ),
                    "missing": missing,
                    "unexpected": extra,
                },
            )

        # Automatic calibration + health analysis for all six.
        processed = [
            process_sensor(sensor)
            for sensor in batch.sensors
        ]

        db_data = [
            {
                "id": s["id"],
                "parameter": s["parameter"],
                "raw_value": s["raw_value"],
                "corrected_value": s["corrected_value"],
                "drift": s["drift"],
                "health": s["health"],
                "weight": s["weight"],
                "status": s["status"],
            }
            for s in processed
        ]

        response = (
            supabase
            .table("sensors")
            .upsert(db_data)
            .execute()
        )

        return {
            "status": "success",
            "message": "All 6 sensors calibrated and saved successfully",
            "count": len(processed),
            "sensors": processed,
            "database": response.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
