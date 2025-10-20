# D:\github\1968_SMART_CHAT_BACK\core\config.py
import os
from .endpoints import ENDPOINTS

# SLA / Timeouts
SLA_SEC = float(os.getenv("SLA_SEC", "5"))
DEFAULT_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "6.0"))
RETRY_TOTAL = int(os.getenv("HTTP_RETRY_TOTAL", "2"))

# 快取
INCIDENT_CACHE_TTL_SEC = int(os.getenv("INCIDENT_CACHE_TTL_SEC", "45"))

# URL 由 endpoints.py 統一控管
INCIDENT_ENDPOINTS = ENDPOINTS["incidents"]
ALT_ROUTES_URL = ENDPOINTS["alt_routes"]
SCS_OP_URL = ENDPOINTS["scs"]["op"]
SCS_CFG_URL = ENDPOINTS["scs"]["cfg"]
PARK_URL = ENDPOINTS["parking"]
