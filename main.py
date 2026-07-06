import os
import re
import time
import uuid
import jwt
import yaml
from collections import defaultdict, deque
from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()
# ... (Middleware and previous endpoint definitions as before, 
# ensuring they return JSONResponse instead of raising HTTPException)

# -------------------------------------------------------------
# QUESTION 9: ORDERS API (IDEMPOTENCY, PAGINATION, RATE LIMITS)
# -------------------------------------------------------------
TOTAL_ORDERS = 57
RATE_LIMIT_MAX = 17
IDEMPOTENCY_STORE = {}
CLIENT_RATE_LIMITS = defaultdict(list)

@app.post("/orders")
async def create_order(request: Request, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"), x_client_id: Optional[str] = Header(None, alias="X-Client-Id")):
    if not x_client_id:
        return JSONResponse(status_code=400, content={"detail": "Missing X-Client-Id tracking header."})
        
    # Rate Limiting Logic
    now = time.time()
    timestamps = [ts for ts in CLIENT_RATE_LIMITS[x_client_id] if now - ts < 10]
    CLIENT_RATE_LIMITS[x_client_id] = timestamps
    if len(timestamps) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Too Many Requests"}, headers={"Retry-After": "10"})
    CLIENT_RATE_LIMITS[x_client_id].append(now)

    # Idempotency Check
    if not idempotency_key:
        return JSONResponse(status_code=400, content={"detail": "Missing Idempotency-Key header."})
    if idempotency_key in IDEMPOTENCY_STORE:
        return JSONResponse(status_code=200, content=IDEMPOTENCY_STORE[idempotency_key])

    new_order_id = str(uuid.uuid4())
    response_payload = {"id": new_order_id, "status": "created", "timestamp": int(now)}
    IDEMPOTENCY_STORE[idempotency_key] = response_payload
    return JSONResponse(status_code=201, content=response_payload)

@app.get("/orders")
async def list_orders(limit: int = 10, cursor: Optional[str] = None, x_client_id: Optional[str] = Header(None, alias="X-Client-Id")):
    if not x_client_id:
        return JSONResponse(status_code=400, content={"detail": "Missing X-Client-Id"})
    # ... (Add Rate Limiting logic here as well)
    
    # Paginated Scan
    catalog = [{"id": i, "item": f"Product-{i}"} for i in range(1, TOTAL_ORDERS + 1)]
    start_index = int(cursor) if cursor else 0
    items_slice = catalog[start_index:start_index + limit]
    next_cursor = str(start_index + limit) if (start_index + limit) < TOTAL_ORDERS else None

    return {"items": items_slice, "next_cursor": next_cursor}