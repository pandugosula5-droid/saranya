"""
High-Performance Python HTTP Server & REST API for Smart Waste Management System
Built using standard library (ThreadingHTTPServer) - Zero external dependencies!
Features:
- REST API for IoT telemetry (ESP32 / Arduino / Simulator)
- Real-time Server-Sent Events (SSE) push stream for live dashboard updates
- Route optimization (TSP) calculations
- Static file server for modern web dashboard
- SQLite data persistence
"""

import sys
import os
import json
import mimetypes
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
import time
import queue

import database
import route_optimizer

PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# SSE Client Subscribers
sse_clients = []
sse_lock = threading.Lock()

def broadcast_sse(event_type: str, data: dict):
    """Pushes real-time SSE messages to all open browser connections."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n".encode("utf-8")
    with sse_lock:
        stale_clients = []
        for client_queue in sse_clients:
            try:
                client_queue.put_nowait(message)
            except Exception:
                stale_clients.append(client_queue)
        for stale in stale_clients:
            if stale in sse_clients:
                sse_clients.remove(stale)


class SmartWasteAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        # Enable CORS for any client / hardware device
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Real-time SSE Stream
        if path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            client_q = queue.Queue()
            with sse_lock:
                sse_clients.append(client_q)

            # Send initial handshake ping
            initial_ping = f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': time.time()})}\n\n".encode("utf-8")
            self.wfile.write(initial_ping)
            self.wfile.flush()

            try:
                while True:
                    try:
                        msg = client_q.get(timeout=20)
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except queue.Empty:
                        # Send heartbeat ping every 20s
                        heartbeat = f": heartbeat {time.time()}\n\n".encode("utf-8")
                        self.wfile.write(heartbeat)
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                with sse_lock:
                    if client_q in sse_clients:
                        sse_clients.remove(client_q)
            return

        # 2. REST API: Get All Bins
        if path == "/api/bins":
            bins = database.get_all_bins()
            self.send_json({"status": "success", "count": len(bins), "bins": bins})
            return

        # 3. REST API: Get Single Bin
        if path.startswith("/api/bins/"):
            bin_id = path.split("/")[3]
            bin_data = database.get_bin_by_id(bin_id)
            if bin_data:
                self.send_json({"status": "success", "bin": bin_data})
            else:
                self.send_json({"status": "error", "message": "Bin not found"}, 404)
            return

        # 4. REST API: Route Optimization (TSP)
        if path == "/api/routes/optimize":
            threshold = float(query.get("threshold", [80.0])[0])
            all_bins = database.get_all_bins()
            critical_bins = [b for b in all_bins if b["fill_percentage"] >= threshold]
            
            # If no bins meet threshold, allow testing with top 3 fullest bins if forced
            force_preview = query.get("force_preview", ["false"])[0].lower() == "true"
            if not critical_bins and force_preview and all_bins:
                critical_bins = sorted(all_bins, key=lambda x: x["fill_percentage"], reverse=True)[:3]

            route_result = route_optimizer.optimize_collection_route(critical_bins, all_bins)
            self.send_json(route_result)
            return

        # 5. REST API: Get Alerts
        if path == "/api/alerts":
            status_filter = query.get("status", [None])[0]
            alerts = database.get_alerts(status_filter)
            self.send_json({"status": "success", "count": len(alerts), "alerts": alerts})
            return

        # 6. REST API: Analytics Summary
        if path == "/api/analytics":
            summary = database.get_analytics_summary()
            self.send_json({"status": "success", "analytics": summary})
            return

        # Fallback to serving static HTML / JS / CSS
        if path == "/" or path == "":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            body = {}

        # 1. Telemetry Ingestion (ESP32 / Arduino / Simulator)
        if path == "/api/telemetry":
            bin_id = body.get("bin_id")
            distance_cm = body.get("distance_cm")
            
            if not bin_id or distance_cm is None:
                self.send_json({"status": "error", "message": "Missing 'bin_id' or 'distance_cm'"}, 400)
                return

            try:
                result = database.update_bin_telemetry(
                    bin_id=bin_id,
                    distance_cm=float(distance_cm),
                    battery_pct=body.get("battery_pct"),
                    temperature_c=body.get("temperature_c"),
                    gas_ppm=body.get("gas_ppm")
                )
                
                # Broadcast update to web UI in real-time
                broadcast_sse("telemetry", {
                    "bin": result["bin"],
                    "new_alerts": result["new_alerts"]
                })

                self.send_json({
                    "status": "success",
                    "message": f"Telemetry processed for {bin_id}",
                    "bin": result["bin"]
                })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 400)
            return

        # 2. Empty a specific bin (manual or truck collection)
        if path.startswith("/api/bins/") and path.endswith("/empty"):
            bin_id = path.split("/")[3]
            try:
                updated_bin = database.empty_bin(bin_id)
                broadcast_sse("bin_emptied", {"bin": updated_bin})
                self.send_json({"status": "success", "bin": updated_bin})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 400)
            return

        # 3. Execute Complete Optimized Collection Run
        if path == "/api/routes/execute":
            bin_ids = body.get("bin_ids", [])
            truck_id = body.get("truck_id", "TRUCK-ALPHA-01")
            distance_km = float(body.get("distance_km", 12.5))
            fuel_saved_l = float(body.get("fuel_saved_liters", 4.5))
            cost_saved = float(body.get("cost_saved_dollars", 5.85))
            co2_saved_kg = float(body.get("co2_saved_kg", 12.06))

            emptied_bins = []
            for b_id in bin_ids:
                try:
                    emptied = database.empty_bin(b_id)
                    emptied_bins.append(emptied)
                except Exception:
                    pass

            log_id = database.record_collection_trip(
                truck_id=truck_id,
                bin_ids=bin_ids,
                distance_km=distance_km,
                fuel_saved_l=fuel_saved_l,
                cost_saved=cost_saved,
                co2_saved_kg=co2_saved_kg
            )

            broadcast_sse("collection_completed", {
                "truck_id": truck_id,
                "emptied_count": len(emptied_bins),
                "emptied_bins": emptied_bins,
                "log_id": log_id
            })

            self.send_json({
                "status": "success",
                "message": f"Collection completed for {len(emptied_bins)} bins.",
                "log_id": log_id,
                "emptied_bins": emptied_bins
            })
            return

        # 4. Resolve an alert
        if path.startswith("/api/alerts/") and path.endswith("/resolve"):
            try:
                alert_id = int(path.split("/")[3])
                success = database.resolve_alert(alert_id)
                broadcast_sse("alert_resolved", {"alert_id": alert_id})
                self.send_json({"status": "success", "resolved": success})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 400)
            return

        # 5. IoT Simulation Tick (advance urban waste generation)
        if path == "/api/simulate/tick":
            import random
            bins = database.get_all_bins()
            updated_list = []
            for b in bins:
                # Add 4% to 15% fill randomly
                increment = random.uniform(4.0, 14.0)
                new_fill = min(100.0, b["fill_percentage"] + increment)
                new_dist = round(b["depth_cm"] * (1.0 - new_fill / 100.0), 1)
                
                # Small fluctuations in battery, temp, gas
                new_temp = round(b["temperature_c"] + random.uniform(-0.3, 0.5), 1)
                new_gas = round(max(20, b["gas_ppm"] + (25 if new_fill > 80 else random.randint(-5, 10))))
                new_battery = max(10, b["battery_pct"] - (1 if random.random() > 0.8 else 0))

                res = database.update_bin_telemetry(
                    bin_id=b["id"],
                    distance_cm=new_dist,
                    battery_pct=new_battery,
                    temperature_c=new_temp,
                    gas_ppm=new_gas
                )
                updated_list.append(res["bin"])

            broadcast_sse("bulk_telemetry", {"bins": updated_list})
            self.send_json({"status": "success", "updated_count": len(updated_list), "bins": updated_list})
            return

        # 6. Reset Database to Default Seed State
        if path == "/api/simulate/reset":
            if os.path.exists(database.DB_FILE):
                os.remove(database.DB_FILE)
            database.init_db()
            bins = database.get_all_bins()
            broadcast_sse("system_reset", {"bins": bins})
            self.send_json({"status": "success", "message": "System reset to initial realistic state.", "bins": bins})
            return

        self.send_json({"status": "error", "message": f"Endpoint POST {path} not recognized"}, 404)


def run_server(port=PORT):
    database.init_db()
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, SmartWasteAPIHandler)
    print("=" * 70)
    print(f"🚀 Smart Waste Management System Server running at:")
    print(f"   -> Web Dashboard:   http://localhost:{port}/")
    print(f"   -> REST API:        http://localhost:{port}/api/bins")
    print(f"   -> Route Optimizer: http://localhost:{port}/api/routes/optimize")
    print(f"   -> IoT Telemetry:   POST http://localhost:{port}/api/telemetry")
    print(f"   -> SSE Live Stream: http://localhost:{port}/api/stream")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()


if __name__ == "__main__":
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
