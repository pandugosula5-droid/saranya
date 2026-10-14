"""
Database module for Smart Waste Management System
Manages SQLite storage for:
- Smart Bins registry & live status
- Telemetry history (ultrasonic readings, battery, temperature, gas)
- Automated alerts (fill thresholds, fire/odor hazards)
- Collection run logs & environmental savings
"""

import sqlite3
import datetime
import os
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "smart_waste.db")

# Initial Realistic Seed Bins
SEED_BINS = [
    {
        "id": "BIN-101",
        "name": "Central Metro Station - East Gate",
        "zone": "Transit Hub",
        "waste_type": "Recyclable",
        "lat": 12.9756,
        "lng": 77.6066,
        "depth_cm": 100.0,
        "current_distance_cm": 12.0,  # 88% full -> CRITICAL
        "battery_pct": 92,
        "temperature_c": 28.4,
        "gas_ppm": 145,
    },
    {
        "id": "BIN-102",
        "name": "Tech Corridor Food Court",
        "zone": "Commercial Area",
        "waste_type": "Organic",
        "lat": 12.9820,
        "lng": 77.5990,
        "depth_cm": 100.0,
        "current_distance_cm": 16.0,  # 84% full -> CRITICAL
        "battery_pct": 88,
        "temperature_c": 31.2,
        "gas_ppm": 290,
    },
    {
        "id": "BIN-103",
        "name": "City General Hospital - South Wing",
        "zone": "Healthcare Zone",
        "waste_type": "Hazardous/Medical",
        "lat": 12.9640,
        "lng": 77.5880,
        "depth_cm": 100.0,
        "current_distance_cm": 38.0,  # 62% full -> WARNING
        "battery_pct": 95,
        "temperature_c": 24.1,
        "gas_ppm": 80,
    },
    {
        "id": "BIN-104",
        "name": "Greenwood Residential Park",
        "zone": "Public Park",
        "waste_type": "General",
        "lat": 12.9580,
        "lng": 77.6150,
        "depth_cm": 100.0,
        "current_distance_cm": 70.0,  # 30% full -> SAFE
        "battery_pct": 98,
        "temperature_c": 23.5,
        "gas_ppm": 45,
    },
    {
        "id": "BIN-105",
        "name": "Grand Boulevard Shopping Mall",
        "zone": "Retail District",
        "waste_type": "Recyclable",
        "lat": 12.9710,
        "lng": 77.6200,
        "depth_cm": 100.0,
        "current_distance_cm": 9.0,   # 91% full -> CRITICAL / OVERFLOWING
        "battery_pct": 81,
        "temperature_c": 29.8,
        "gas_ppm": 210,
    },
    {
        "id": "BIN-106",
        "name": "Apex University Campus - Library",
        "zone": "Educational Campus",
        "waste_type": "Recyclable",
        "lat": 12.9850,
        "lng": 77.6120,
        "depth_cm": 100.0,
        "current_distance_cm": 55.0,  # 45% full -> SAFE
        "battery_pct": 90,
        "temperature_c": 25.0,
        "gas_ppm": 60,
    },
    {
        "id": "BIN-107",
        "name": "Old Market Fish & Vegetable Yard",
        "zone": "Wholesale Market",
        "waste_type": "Organic",
        "lat": 12.9670,
        "lng": 77.5790,
        "depth_cm": 100.0,
        "current_distance_cm": 14.0,  # 86% full -> CRITICAL
        "battery_pct": 76,
        "temperature_c": 33.5,
        "gas_ppm": 420,  # High odor/methane alert
    },
    {
        "id": "BIN-108",
        "name": "Riverside Promenade - Pier 3",
        "zone": "Waterfront Area",
        "waste_type": "General",
        "lat": 12.9910,
        "lng": 77.5920,
        "depth_cm": 100.0,
        "current_distance_cm": 65.0,  # 35% full -> SAFE
        "battery_pct": 89,
        "temperature_c": 24.8,
        "gas_ppm": 55,
    }
]

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_status(fill_pct: float, temp_c: float, gas_ppm: float) -> str:
    if fill_pct >= 95.0 or temp_c >= 55.0:
        return "Overflowing"
    elif fill_pct >= 80.0 or gas_ppm >= 400.0:
        return "Critical"
    elif fill_pct >= 60.0:
        return "Warning"
    else:
        return "Safe"

def init_db():
    """Initializes tables and seeds initial smart bins if database is empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Bins Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bins (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        zone TEXT NOT NULL,
        waste_type TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        depth_cm REAL NOT NULL DEFAULT 100.0,
        current_distance_cm REAL NOT NULL DEFAULT 80.0,
        fill_percentage REAL NOT NULL DEFAULT 20.0,
        battery_pct INTEGER NOT NULL DEFAULT 100,
        temperature_c REAL NOT NULL DEFAULT 25.0,
        gas_ppm REAL NOT NULL DEFAULT 50.0,
        status TEXT NOT NULL DEFAULT 'Safe',
        last_updated TEXT NOT NULL,
        last_collected TEXT NOT NULL
    );
    """)

    # Telemetry History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bin_id TEXT NOT NULL,
        distance_cm REAL NOT NULL,
        fill_percentage REAL NOT NULL,
        battery_pct INTEGER,
        temperature_c REAL,
        gas_ppm REAL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (bin_id) REFERENCES bins (id)
    );
    """)

    # Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bin_id TEXT NOT NULL,
        bin_name TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        FOREIGN KEY (bin_id) REFERENCES bins (id)
    );
    """)

    # Collection Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS collection_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id TEXT NOT NULL,
        bins_emptied TEXT NOT NULL,
        bins_count INTEGER NOT NULL,
        distance_km REAL NOT NULL,
        fuel_saved_liters REAL NOT NULL,
        cost_saved_dollars REAL NOT NULL,
        co2_saved_kg REAL NOT NULL,
        completed_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # Check if seed bins are present
    cursor.execute("SELECT COUNT(*) FROM bins")
    count = cursor.fetchone()[0]
    
    now = datetime.datetime.now().isoformat()
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()

    if count == 0:
        for b in SEED_BINS:
            depth = b["depth_cm"]
            dist = b["current_distance_cm"]
            fill_pct = round(max(0.0, min(100.0, (depth - dist) / depth * 100.0)), 1)
            status = calculate_status(fill_pct, b["temperature_c"], b["gas_ppm"])

            cursor.execute("""
            INSERT INTO bins (
                id, name, zone, waste_type, lat, lng,
                depth_cm, current_distance_cm, fill_percentage,
                battery_pct, temperature_c, gas_ppm, status,
                last_updated, last_collected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                b["id"], b["name"], b["zone"], b["waste_type"], b["lat"], b["lng"],
                depth, dist, fill_pct,
                b["battery_pct"], b["temperature_c"], b["gas_ppm"], status,
                now, yesterday
            ))

            # Initial telemetry record
            cursor.execute("""
            INSERT INTO telemetry_history (
                bin_id, distance_cm, fill_percentage, battery_pct, temperature_c, gas_ppm, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                b["id"], dist, fill_pct, b["battery_pct"], b["temperature_c"], b["gas_ppm"], now
            ))

            # Trigger alert if critical
            if fill_pct >= 80.0:
                cursor.execute("""
                INSERT INTO alerts (bin_id, bin_name, alert_type, severity, message, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    b["id"], b["name"], "HIGH_FILL", "critical",
                    f"Waste level reached {fill_pct}%. Immediate collection required to prevent overflow.",
                    now, "active"
                ))
            
            if b["gas_ppm"] >= 400.0:
                cursor.execute("""
                INSERT INTO alerts (bin_id, bin_name, alert_type, severity, message, timestamp, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    b["id"], b["name"], "ODOR_METHANE", "warning",
                    f"Elevated methane/VOC levels ({b['gas_ppm']} ppm) detected. Sanitation check advised.",
                    now, "active"
                ))

        # Seed historical collection log for rich analytics
        cursor.execute("""
        INSERT INTO collection_logs (
            truck_id, bins_emptied, bins_count, distance_km, fuel_saved_liters, cost_saved_dollars, co2_saved_kg, completed_at
        ) VALUES
        ('TRUCK-01', 'BIN-101, BIN-105, BIN-107', 3, 14.2, 5.8, 7.54, 15.54, ?),
        ('TRUCK-02', 'BIN-102, BIN-103', 2, 11.5, 4.2, 5.46, 11.25, ?)
        """, (
            (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(),
            (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        ))

        conn.commit()
    conn.close()


def get_all_bins() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bins ORDER BY fill_percentage DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_bin_by_id(bin_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bins WHERE id = ?", (bin_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def update_bin_telemetry(
    bin_id: str,
    distance_cm: float,
    battery_pct: Optional[int] = None,
    temperature_c: Optional[float] = None,
    gas_ppm: Optional[float] = None
) -> Dict[str, Any]:
    """
    Called by ESP32 or IoT simulator to update bin readings.
    Automatically computes fill level, updates status, and logs alerts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bins WHERE id = ?", (bin_id,))
    bin_data = cursor.fetchone()
    if not bin_data:
        conn.close()
        raise ValueError(f"Bin ID {bin_id} not found in database.")

    depth = bin_data["depth_cm"]
    dist = max(2.0, min(depth, distance_cm))
    fill_pct = round(max(0.0, min(100.0, (depth - dist) / depth * 100.0)), 1)
    
    bat = battery_pct if battery_pct is not None else bin_data["battery_pct"]
    temp = temperature_c if temperature_c is not None else bin_data["temperature_c"]
    gas = gas_ppm if gas_ppm is not None else bin_data["gas_ppm"]
    
    status = calculate_status(fill_pct, temp, gas)
    now = datetime.datetime.now().isoformat()

    cursor.execute("""
    UPDATE bins
    SET current_distance_cm = ?,
        fill_percentage = ?,
        battery_pct = ?,
        temperature_c = ?,
        gas_ppm = ?,
        status = ?,
        last_updated = ?
    WHERE id = ?
    """, (dist, fill_pct, bat, temp, gas, status, now, bin_id))

    # Append to history
    cursor.execute("""
    INSERT INTO telemetry_history (bin_id, distance_cm, fill_percentage, battery_pct, temperature_c, gas_ppm, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (bin_id, dist, fill_pct, bat, temp, gas, now))

    # Auto-generate Alert if threshold exceeded and no active alert exists for this condition
    new_alerts = []
    if fill_pct >= 80.0:
        cursor.execute("""
        SELECT COUNT(*) FROM alerts WHERE bin_id = ? AND alert_type = 'HIGH_FILL' AND status = 'active'
        """, (bin_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO alerts (bin_id, bin_name, alert_type, severity, message, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (
                bin_id, bin_data["name"], "HIGH_FILL",
                "critical" if fill_pct >= 90 else "warning",
                f"Fill level surged to {fill_pct}%. Immediate collection scheduled.",
                now
            ))
            new_alerts.append(f"Fill level critical: {fill_pct}%")

    if temp >= 50.0:
        cursor.execute("""
        SELECT COUNT(*) FROM alerts WHERE bin_id = ? AND alert_type = 'FIRE_HAZARD' AND status = 'active'
        """, (bin_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO alerts (bin_id, bin_name, alert_type, severity, message, timestamp, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (
                bin_id, bin_data["name"], "FIRE_HAZARD", "critical",
                f"Hazardous thermal spike detected: {temp}°C! Possible smoldering waste.",
                now
            ))
            new_alerts.append(f"Temperature hazard: {temp}°C")

    conn.commit()

    # Fetch updated bin
    cursor.execute("SELECT * FROM bins WHERE id = ?", (bin_id,))
    updated_bin = dict(cursor.fetchone())
    conn.close()

    return {
        "bin": updated_bin,
        "new_alerts": new_alerts
    }


def empty_bin(bin_id: str) -> Dict[str, Any]:
    """Simulates truck emptying a bin: resets fill to 0% (distance = depth_cm)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT depth_cm FROM bins WHERE id = ?", (bin_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Bin {bin_id} not found.")

    depth = row["depth_cm"]
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
    UPDATE bins
    SET current_distance_cm = ?,
        fill_percentage = 0.0,
        status = 'Safe',
        last_updated = ?,
        last_collected = ?
    WHERE id = ?
    """, (depth - 5.0, now, now, bin_id))

    # Resolve active fill alerts
    cursor.execute("""
    UPDATE alerts SET status = 'resolved' WHERE bin_id = ? AND alert_type = 'HIGH_FILL'
    """, (bin_id,))

    conn.commit()
    cursor.execute("SELECT * FROM bins WHERE id = ?", (bin_id,))
    updated = dict(cursor.fetchone())
    conn.close()
    return updated


def record_collection_trip(truck_id: str, bin_ids: List[str], distance_km: float, fuel_saved_l: float, cost_saved: float, co2_saved_kg: float) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO collection_logs (
        truck_id, bins_emptied, bins_count, distance_km, fuel_saved_liters, cost_saved_dollars, co2_saved_kg, completed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (truck_id, ", ".join(bin_ids), len(bin_ids), distance_km, fuel_saved_l, cost_saved, co2_saved_kg, now))
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_alerts(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM alerts WHERE status = ? ORDER BY id DESC LIMIT 50", (status_filter,))
    else:
        cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_alert(alert_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET status = 'resolved' WHERE id = ?", (alert_id,))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_analytics_summary() -> Dict[str, Any]:
    """Generates comprehensive aggregated metrics for data analytics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Bins status breakdown
    cursor.execute("SELECT status, COUNT(*) as count FROM bins GROUP BY status")
    status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    # Average fill level
    cursor.execute("SELECT AVG(fill_percentage), MAX(fill_percentage), MIN(fill_percentage) FROM bins")
    avg_fill, max_fill, min_fill = cursor.fetchone()

    # Waste composition
    cursor.execute("SELECT waste_type, COUNT(*) as count FROM bins GROUP BY waste_type")
    composition = {r["waste_type"]: r["count"] for r in cursor.fetchall()}

    # Total savings from collection logs
    cursor.execute("""
    SELECT 
        SUM(bins_count) as total_bins_collected,
        SUM(distance_km) as total_distance_km,
        SUM(fuel_saved_liters) as total_fuel_saved,
        SUM(cost_saved_dollars) as total_cost_saved,
        SUM(co2_saved_kg) as total_co2_saved
    FROM collection_logs
    """)
    totals = cursor.fetchone()

    # Active alerts count
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'active'")
    active_alerts = cursor.fetchone()[0]

    conn.close()

    return {
        "total_bins": sum(status_counts.values()),
        "status_breakdown": {
            "Safe": status_counts.get("Safe", 0),
            "Warning": status_counts.get("Warning", 0),
            "Critical": status_counts.get("Critical", 0),
            "Overflowing": status_counts.get("Overflowing", 0)
        },
        "average_fill_pct": round(avg_fill or 0.0, 1),
        "max_fill_pct": round(max_fill or 0.0, 1),
        "min_fill_pct": round(min_fill or 0.0, 1),
        "waste_composition": composition,
        "active_alerts_count": active_alerts,
        "lifetime_savings": {
            "bins_collected": totals["total_bins_collected"] or 0,
            "fuel_saved_liters": round(totals["total_fuel_saved"] or 0.0, 1),
            "cost_saved_dollars": round(totals["total_cost_saved"] or 0.0, 2),
            "co2_saved_kg": round(totals["total_co2_saved"] or 0.0, 1)
        }
    }
