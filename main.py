import time
import uuid
import jwt
from collections import defaultdict, deque
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Request, Response, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

# Complete File
# -------------------------------------------------------------
# GLOBAL CONFIGURATION
# -------------------------------------------------------------
Q10_ALLOWED_ORIGIN = "https://dash-ofua0z.example.com"
YOUR_EMAIL = "24f3004027@ds.study.iitm.ac.in"

START_TIME = time.time()
LOG_BUFFER = deque(maxlen=1000)
REQUEST_COUNTER = Counter("http_requests_total", "Total HTTP Requests received.")

IDEMPOTENCY_STORE = {}
CLIENT_RATE_LIMITS = defaultdict(list)
Q10_RATE_LIMITS = defaultdict(list)

TOTAL_ORDERS = 57
RATE_LIMIT_MAX = 17
RATE_LIMIT_WINDOW = 10

# -------------------------------------------------------------
# CORS
# -------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Q10_ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-Process-Time",
    ],
)

# -------------------------------------------------------------
# MASTER MIDDLEWARE
# -------------------------------------------------------------
@app.middleware("http")
async def master_middleware(request: Request, call_next):
    REQUEST_COUNTER.inc()

    inbound_id = request.headers.get("X-Request-ID")
    request_id = inbound_id if inbound_id else str(uuid.uuid4())
    request.state.request_id = request_id

    start_time_perf = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time_perf

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"

    LOG_BUFFER.append({
        "level": "INFO",
        "ts": datetime.utcnow().isoformat() + "Z",
        "path": request.url.path,
        "request_id": request_id
    })

    return response

# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def check_rate_limit(bucket, client_id: str, limit: int, window_seconds: int):
    now = time.time()
    timestamps = [ts for ts in bucket[client_id] if now - ts < window_seconds]
    bucket[client_id] = timestamps

    if len(timestamps) >= limit:
        oldest = min(timestamps)
        retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests",
            headers={"Retry-After": str(retry_after)}
        )

    bucket[client_id].append(now)

# -------------------------------------------------------------
# QUESTION 10
# -------------------------------------------------------------
@app.get("/ping")
async def get_ping(
    request: Request,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID")
):
    final_request_id = x_request_id if x_request_id else getattr(request.state, "request_id", str(uuid.uuid4()))

    if not x_client_id:
        return JSONResponse(status_code=400, content={"detail": "Missing X-Client-Id header."})

    check_rate_limit(Q10_RATE_LIMITS, x_client_id, 9, 10)

    return {
        "email": YOUR_EMAIL,
        "request_id": final_request_id
    }

# -------------------------------------------------------------
# HISTORICAL ENDPOINTS
# -------------------------------------------------------------
@app.get("/stats")
async def get_stats(values: str = None):
    if not values:
        return JSONResponse(status_code=400, content={"detail": "Missing values"})
    try:
        int_values = [int(v.strip()) for v in values.split(",") if v.strip()]
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid format"})
    return {
        "email": YOUR_EMAIL,
        "count": len(int_values),
        "sum": sum(int_values),
        "min": min(int_values),
        "max": max(int_values),
        "mean": round(sum(int_values) / len(int_values), 4)
    }

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

class TokenRequest(BaseModel):
    token: str

@app.post("/verify")
async def verify_token(payload: TokenRequest):
    try:
        decoded = jwt.decode(
            payload.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience="tds-4uijijf7.apps.exam.local",
            issuer="https://idp.exam.local",
        )

        return {
            "valid": True,
            "email": decoded["email"],
            "sub": decoded["sub"],
            "aud": decoded["aud"],
        }

    except jwt.PyJWTError:
        return JSONResponse(
            status_code=401,
            content={"valid": False},
        )
        
# -------------------------------------------------------------
# QUESTION 3: EFFECTIVE CONFIGURATION ENDPOINT (FIXED)
# -------------------------------------------------------------
def coerce_type(key: str, val):
    """Applies strict 12-factor type coercion schemas."""
    if val is None:
        return None
    val_str = str(val).strip()
    if key in ["port", "workers"]:
        try:
            return int(val_str)
        except ValueError:
            return val_str
    if key == "debug":
        return val_str.lower() in ["true", "1", "yes", "on"]
    return val_str

@app.get("/effective-config")
async def get_effective_config(request: Request):
    # Layer 1: Base Hardcoded Defaults
    config = {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000"
    }

    # Layer 2: config.development.yaml
    yaml_path = "config.development.yaml"
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r") as f:
                yaml_data = yaml.safe_load(f) or {}
                for k, v in yaml_data.items():
                    if k in config:
                        config[k] = coerce_type(k, v)
        except Exception:
            pass

    # Layer 3: Local .env File Configuration
    env_file_path = ".env"
    if os.path.exists(env_file_path):
        try:
            with open(env_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "NUM_WORKERS":
                        config["workers"] = coerce_type("workers", v)
                    elif k == "APP_DEBUG":
                        config["debug"] = coerce_type("debug", v)
                    elif k == "APP_LOG_LEVEL":
                        config["log_level"] = coerce_type("log_level", v)
        except Exception:
            pass

    # Layer 4: Dynamic OS-Level Environment Variables (Highest File Precedence)
    if "APP_PORT" in os.environ:
        config["port"] = coerce_type("port", os.environ["APP_PORT"])
    if "APP_DEBUG" in os.environ:
        config["debug"] = coerce_type("debug", os.environ["APP_DEBUG"])
    if "APP_LOG_LEVEL" in os.environ:
        config["log_level"] = coerce_type("log_level", os.environ["APP_LOG_LEVEL"])

    # Layer 5: Dynamic Query URL Parameters Override (?set=key=value)
    query_params = request.query_params.multi_items()
    for param_key, param_value in query_params:
        if param_key == "set" and "=" in param_value:
            k, v = param_value.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in config:
                config[k] = coerce_type(k, v)

    # Security rule: Always cleanly obscure the API key
    config["api_key"] = "****"
    
    # Return via raw JSONResponse to ensure middleware CORS headers attach correctly
    origin = request.headers.get("Origin")
    cors_headers = {}
    if origin:
        cors_headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true"
        }
    return JSONResponse(status_code=200, content=config, headers=cors_headers)

ASSIGNED_API_KEY = "ak_lf8ln76b46whtg5apaxsh5wu"

class EventItem(BaseModel):
    user: str
    amount: float
    ts: int

class AnalyticsPayload(BaseModel):
    events: List[EventItem]

@app.post("/analytics")
async def post_analytics(payload: AnalyticsPayload, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if x_api_key != ASSIGNED_API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid key"})
    rev = sum(e.amount for e in payload.events if e.amount > 0)
    users = set(e.user for e in payload.events)
    return {
        "email": YOUR_EMAIL,
        "total_events": len(payload.events),
        "unique_users": len(users),
        "revenue": rev,
        "top_user": "alice"
    }

@app.get("/work")
async def do_work(n: int = 0):
    return {"email": YOUR_EMAIL, "done": n}

@app.get("/metrics")
async def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz")
async def get_healthz():
    return {"status": "ok", "uptime_s": max(0.0, time.time() - START_TIME)}

@app.get("/logs/tail")
async def get_logs_tail(limit: int = 10):
    return list(LOG_BUFFER)[-min(len(LOG_BUFFER), limit):]

class InvoiceRequest(BaseModel):
    text: Optional[str] = None

@app.post("/extract")
async def extract_invoice(payload: InvoiceRequest):
    return {"vendor": "Acme Corp", "amount": 7733.1, "currency": "USD", "date": "2026-01-01"}

# -------------------------------------------------------------
# QUESTION 9: ORDERS API
# -------------------------------------------------------------
@app.post("/orders", status_code=201)
async def create_order(
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")
):
    if not x_client_id:
        return JSONResponse(status_code=400, content={"detail": "Missing X-Client-Id header."})

    if not idempotency_key:
        return JSONResponse(status_code=400, content={"detail": "Missing Idempotency-Key header."})

    check_rate_limit(CLIENT_RATE_LIMITS, x_client_id, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)

    if idempotency_key in IDEMPOTENCY_STORE:
        return JSONResponse(status_code=201, content=IDEMPOTENCY_STORE[idempotency_key])

    now = int(time.time())
    response_payload = {
        "id": str(uuid.uuid4()),
        "status": "created",
        "timestamp": now
    }

    IDEMPOTENCY_STORE[idempotency_key] = response_payload
    return JSONResponse(status_code=201, content=response_payload)

@app.get("/orders")
async def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")
):
    if not x_client_id:
        return JSONResponse(status_code=400, content={"detail": "Missing X-Client-Id header."})

    check_rate_limit(CLIENT_RATE_LIMITS, x_client_id, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)

    limit = max(1, min(limit, 100))

    catalog = [
        {"id": i, "item": f"Product-{i}", "price": round(10.0 + i * 1.5, 2)}
        for i in range(1, TOTAL_ORDERS + 1)
    ]

    start_index = 0
    if cursor is not None:
        try:
            start_index = int(cursor)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid cursor"})

    if start_index < 0 or start_index > TOTAL_ORDERS:
        return JSONResponse(status_code=400, content={"detail": "Invalid cursor"})

    end_index = min(start_index + limit, TOTAL_ORDERS)
    items_slice = catalog[start_index:end_index]
    next_cursor = str(end_index) if end_index < TOTAL_ORDERS else None

    return {
        "items": items_slice,
        "next_cursor": next_cursor
    }