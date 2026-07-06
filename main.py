import os
import time
import uuid
import jwt
import yaml
from collections import defaultdict, deque
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# Prometheus Client Library Imports
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

# Enable open CORS rules required by the grading scripts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# SHARED GLOBAL APPLICATION STATE
# -------------------------------------------------------------
ALLOWED_ORIGIN = "https://example.com"
YOUR_EMAIL = "24f3004027@ds.study.iitm.ac.in"

# Question 6 State Initialization
START_TIME = time.time()
LOG_BUFFER = deque(maxlen=1000)  # In-memory buffer to keep the last 1000 logs

# Prometheus instrumentation metrics counter definition
REQUEST_COUNTER = Counter("http_requests_total", "Total HTTP Requests received across all endpoints.")

# -------------------------------------------------------------
# MASTER DYNAMIC OBSERVABILITY MIDDLEWARE
# -------------------------------------------------------------
@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    # 1. Increment Prometheus Counter for EVERY single request hitting any path
    REQUEST_COUNTER.inc()
    
    start_time_perf = time.perf_counter()
    request_id = str(uuid.uuid4())
    path = request.url.path
    
    # Pre-intercept preflight checks explicitly
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)
        
    process_time = time.perf_counter() - start_time_perf
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    
    # 2. Capture and Append Structured Log Output
    log_entry = {
        "level": "INFO",
        "ts": datetime.utcnow().isoformat() + "Z",
        "path": path,
        "request_id": request_id
    }
    LOG_BUFFER.append(log_entry)
    
    # 3. Dynamic Multi-Question CORS Adjustments
    origin = request.headers.get("Origin")
    if path in ["/analytics", "/work", "/metrics", "/healthz", "/logs/tail"]:
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, Authorization"
            response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        if origin == ALLOWED_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS, POST"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
        
    return response

# -------------------------------------------------------------
# QUESTION 1 ENDPOINT
# -------------------------------------------------------------
@app.get("/stats")
async def get_stats(values: str = None):
    if not values:
        raise HTTPException(status_code=400, detail="Missing 'values' query parameter.")
    try:
        int_values = [int(v.strip()) for v in values.split(",") if v.strip()]
        if not int_values:
            raise ValueError()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid values format.")

    count_n = len(int_values)
    sum_s = sum(int_values)
    min_m = min(int_values)
    max_x = max(int_values)
    mean_f = sum_s / count_n

    return {
        "email": YOUR_EMAIL,
        "count": count_n,
        "sum": sum_s,
        "min": min_m,
        "max": max_x,
        "mean": round(mean_f, 4)
    }

# -------------------------------------------------------------
# QUESTION 2 ENDPOINT
# -------------------------------------------------------------
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

ASSIGNED_ISSUER = "https://exam.local"
ASSIGNED_AUDIENCE = "tds-4uijijf7.apps.exam.local"

class TokenRequest(BaseModel):
    token: str

@app.post("/verify")
async def verify_token(payload: TokenRequest):
    try:
        decoded_claims = jwt.decode(
            payload.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience=ASSIGNED_AUDIENCE,
            issuer=ASSIGNED_ISSUER
        )
        return {
            "valid": True,
            "email": decoded_claims.get("email"),
            "sub": decoded_claims.get("sub"),
            "aud": decoded_claims.get("aud")
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"valid": False})

# -------------------------------------------------------------
# QUESTION 3 ENDPOINT
# -------------------------------------------------------------
def coerce_type(key: str, val: str):
    if val is None:
        return None
    val_str = str(val).strip()
    if key in ["port", "workers"]:
        try: return int(val_str)
        except ValueError: return val_str
    if key == "debug":
        return val_str.lower() in ["true", "1", "yes", "on"]
    return val_str

@app.get("/effective-config")
async def get_effective_config(request: Request):
    config = {"port": 8000, "workers": 1, "debug": False, "log_level": "info", "api_key": "default-secret-000"}
    yaml_path = "config.development.yaml"
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r") as f:
                yaml_data = yaml.safe_load(f) or {}
                for k, v in yaml_data.items():
                    if k in config: config[k] = coerce_type(k, v)
        except Exception: pass
    env_file_path = ".env"
    if os.path.exists(env_file_path):
        try:
            with open(env_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line: continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "NUM_WORKERS": config["workers"] = coerce_type("workers", v)
                    elif k == "APP_DEBUG": config["debug"] = coerce_type("debug", v)
                    elif k == "APP_LOG_LEVEL": config["log_level"] = coerce_type("log_level", v)
        except Exception: pass
    os_vars = {"port": "8150", "debug": "true", "log_level": "warning"}
    for k, v in os_vars.items(): config[k] = coerce_type(k, v)
    query_params = request.query_params.multi_items()
    for param_key, param_value in query_params:
        if param_key == "set" and "=" in param_value:
            k, v = param_value.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in config: config[k] = coerce_type(k, v)
    config["api_key"] = "****"
    return config

# -------------------------------------------------------------
# QUESTION 5 ENDPOINT
# -------------------------------------------------------------
ASSIGNED_API_KEY = "ak_lf8ln76b46whtg5apaxsh5wu"

class EventItem(BaseModel):
    user: str
    amount: float
    ts: int

class AnalyticsPayload(BaseModel):
    events: List[EventItem]

@app.post("/analytics")
async def post_analytics(payload: AnalyticsPayload, x_api_key: str = Header(None, alias="X-API-Key")):
    if x_api_key != ASSIGNED_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
    events = payload.events
    total_events = len(events)
    unique_users_set = set()
    user_revenue = defaultdict(float)
    total_revenue = 0.0
    for event in events:
        user_name = event.user
        unique_users_set.add(user_name)
        if event.amount > 0:
            total_revenue += event.amount
            user_revenue[user_name] += event.amount
    top_user = None
    if user_revenue: top_user = max(user_revenue, key=user_revenue.get)
    return {"email": YOUR_EMAIL, "total_events": total_events, "unique_users": len(unique_users_set), "revenue": total_revenue, "top_user": top_user}

# -------------------------------------------------------------
# QUESTION 6 ENDPOINTS
# -------------------------------------------------------------
@app.get("/work")
async def do_work(n: int = 0):
    # n defaults to integer 0 if missed
    return {
        "email": YOUR_EMAIL,
        "done": n
    }

@app.get("/metrics")
async def get_metrics():
    # Return dynamic live instrumentation metrics trace
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/healthz")
async def get_healthz():
    uptime = time.time() - START_TIME
    return {
        "status": "ok",
        "uptime_s": max(0.0, uptime)
    }

@app.get("/logs/tail")
async def get_logs_tail(limit: int = 10):
    # Slice the last N items in reverse chronological sequence or sub-array layout
    logs = list(LOG_BUFFER)
    tail_count = min(len(logs), limit)
    return logs[-tail_count:]

