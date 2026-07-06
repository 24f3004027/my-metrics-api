import time
import uuid
from fastapi import FastAPI, Request, Response, HTTPException

app = FastAPI()

# -------------------------------------------------------------
# ASSIGNED CONFIGURATION VALUES
# -------------------------------------------------------------
ALLOWED_ORIGIN = "https://dash-ofua0z.example.com"
YOUR_EMAIL = "24f3004027@ds.study.iitm.ac.in"

# -------------------------------------------------------------
# MIDDLEWARE: Handles X-Request-ID, X-Process-Time, and Strict CORS
# -------------------------------------------------------------
@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())
    
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)
        
    process_time = time.perf_counter() - start_time
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    
    origin = request.headers.get("Origin")
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
        
    return response

# -------------------------------------------------------------
# ENDPOINT: GET /stats
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

