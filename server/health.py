"""
~/nexora/server/health.py — Telemetria de hardware e saúde do host do NEXORA.
"""

import os
import shutil
import time


def register(route, ApiError):
    @route("GET", "/api/health")
    def handle_health(req, query, body):
        total, used, free = shutil.disk_usage("/")
        load_1, load_5, load_15 = os.getloadavg()
        
        mem_info = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem_info[parts[0].strip()] = parts[1].strip()
        except Exception:
            pass

        return {
            "ok": True,
            "system": {
                "load": {"1m": load_1, "5m": load_5, "15m": load_15},
                "disk": {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "used_pct": round((used / total) * 100, 1)
                },
                "memory": {
                    "total": mem_info.get("MemTotal", "N/A"),
                    "free": mem_info.get("MemAvailable", mem_info.get("MemFree", "N/A"))
                },
                "timestamp": time.time()
            }
        }
