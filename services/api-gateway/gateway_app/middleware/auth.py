from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
try:
    from ..config import settings
except ImportError:
    from config import settings

security = HTTPBearer(auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(seconds=settings.token_expiry_seconds))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def auth_middleware(request: Request, call_next):
    # Public endpoints bypass
    path = request.url.path
    if (
        path in ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/api/v1/auth/token"]
        or path.startswith("/static")
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # In development mode, allow dev-token bypass if not supplied
        if settings.environment == "dev":
            request.state.user = {"sub": "dev_user", "roles": ["admin"]}
            return await call_next(request)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Bearer authorization token",
        )

    token = auth_header.split(" ")[1]
    payload = verify_access_token(token)
    request.state.user = payload
    return await call_next(request)
