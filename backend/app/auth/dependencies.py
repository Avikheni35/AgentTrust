from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer_scheme = HTTPBearer()


@dataclass
class UserContext:
    user_id: str
    tenant_id: str
    email: str
    roles: list[str]
    department: str | None
    region: str | None


async def _get_keycloak_public_key() -> str:
    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()["public_key"]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserContext:
    token = credentials.credentials
    try:
        public_key = await _get_keycloak_public_key()
        pem = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
        payload = jwt.decode(
            token,
            pem,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )

    tenant_id = payload.get("tenant_id") or "default"
    roles = payload.get("realm_access", {}).get("roles", [])

    return UserContext(
        user_id=payload["sub"],
        tenant_id=tenant_id,
        email=payload.get("email", ""),
        roles=roles,
        department=payload.get("department"),
        region=payload.get("region"),
    )


def require_role(*required_roles: str):
    """Dependency factory — raises 403 if user lacks all required roles."""
    async def check(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not any(r in user.roles for r in required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return check
