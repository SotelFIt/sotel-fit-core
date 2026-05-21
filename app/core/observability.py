import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy.orm import Session

class ObservabilityManager:
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.requests_by_endpoint = {}
        self.response_times = []
        self.status_codes = {}
        self.errors = []
        self.module_status = {}

    def record_request(self, endpoint: str, method: str, status_code: int, response_time: float):
        self.request_count += 1
        key = f"{method} {endpoint}"
        self.requests_by_endpoint[key] = self.requests_by_endpoint.get(key, 0) + 1
        self.response_times.append(response_time)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

    def record_error(self, endpoint: str, error: str, severity: str = "medium"):
        self.errors.append({
            "endpoint": endpoint,
            "error": error,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_uptime(self) -> str:
        elapsed = time.time() - self.start_time
        days = int(elapsed // 86400)
        hours = int((elapsed % 86400) // 3600)
        minutes = int((elapsed % 3600) // 60)
        return f"{days}d {hours}h {minutes}m"

    def get_memory_usage(self) -> Dict[str, Any]:
        process = psutil.Process()
        mem = process.memory_info()
        return {
            "rss_mb": round(mem.rss / 1024 / 1024, 2),
            "vms_mb": round(mem.vms / 1024 / 1024, 2)
        }

    def get_average_response_time(self) -> float:
        if not self.response_times:
            return 0
        return round(sum(self.response_times) / len(self.response_times) * 1000, 2)

    def get_health_detailed(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "uptime": self.get_uptime(),
            "requests": self.request_count
        }

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "requests": {
                "total": self.request_count,
                "by_endpoint": self.requests_by_endpoint,
                "status_200": self.status_codes.get(200, 0),
                "status_401": self.status_codes.get(401, 0),
                "status_404": self.status_codes.get(404, 0),
                "status_500": self.status_codes.get(500, 0),
                "success_rate": round((self.status_codes.get(200, 0) / self.request_count * 100) if self.request_count > 0 else 0, 1)
            },
            "performance": {
                "avg_response_time_ms": self.get_average_response_time(),
                "uptime": self.get_uptime()
            },
            "errors": {
                "total": len(self.errors),
                "by_severity": {
                    "critical": len([e for e in self.errors if e.get("severity") == "critical"]),
                    "high": len([e for e in self.errors if e.get("severity") == "high"]),
                    "medium": len([e for e in self.errors if e.get("severity") == "medium"]),
                    "low": len([e for e in self.errors if e.get("severity") == "low"])
                },
                "recent_errors": self.errors[-5:]
            },
            "top_metrics": {
                "most_accessed_endpoint": max(self.requests_by_endpoint, key=self.requests_by_endpoint.get) if self.requests_by_endpoint else None,
                "most_accessed_count": max(self.requests_by_endpoint.values()) if self.requests_by_endpoint else 0,
                "endpoint_with_most_errors": "N/A",
                "error_count": len(self.errors)
            }
        }

observability = ObservabilityManager()
