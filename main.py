import time
import uuid
from fastapi import FastAPI, Request, Response, HTTPException, status
import jwt
from pydantic import BaseModel

# QUESTION 1
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

# QUESTION 2
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

ASSIGNED_ISSUER = "https://idp.exam.local"
ASSIGNED_AUDIENCE = "tds-4uijijf7.apps.exam.local"

class TokenRequest(BaseModel):
    token: str

@app.post("/verify")
async def verify_token(payload: TokenRequest):
    try:
        # PyJWT handles signature checking, expiration verification (exp), 
        # issuer verification (iss), and audience verification (aud) all at once.
        decoded_claims = jwt.decode(
            payload.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience=ASSIGNED_AUDIENCE,
            issuer=ASSIGNED_ISSUER
        )
        
        # If decoding succeeds, token is valid. Return structural 200 payload.
        return {
            "valid": True,
            "email": decoded_claims.get("email"),
            "sub": decoded_claims.get("sub"),
            "aud": decoded_claims.get("aud")
        }
        
    except jwt.PyJWTError:
        # Any failure (signature mismatch, expired token, wrong issuer, bad audience)
        # falls into here. Return an explicit 401 error with valid: false.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"valid": False}
        )
 
