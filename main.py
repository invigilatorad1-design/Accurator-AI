from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/status")
def api_status():
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
