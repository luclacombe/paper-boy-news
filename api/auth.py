"""JWT verification middleware for Supabase auth."""

import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if not JWT_SECRET and ENVIRONMENT == "production":
    raise RuntimeError(
        "SUPABASE_JWT_SECRET must be set in production. "
        "Set the environment variable before starting the server."
    )


async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Decode Supabase JWT and return the user ID.

    In dev mode (no JWT secret configured), allows unauthenticated requests
    and returns a placeholder user ID.
    """
    # Dev mode: skip verification if no secret is configured
    if not JWT_SECRET:
        logger.warning(
            "SUPABASE_JWT_SECRET not set — running in insecure dev mode. "
            "Never deploy without this variable."
        )
        if credentials and credentials.credentials:
            try:
                payload = jwt.decode(
                    credentials.credentials,
                    options={"verify_signature": False},
                )
                return payload.get("sub", "dev-user")
            except jwt.DecodeError:
                pass
        return "dev-user"

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
