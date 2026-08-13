"""Admin-only endpoints (development verification of RBAC).

Deliberately minimal: exposes a single endpoint used to prove that
admin-only access is enforced server-side.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.core.enums import Role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/test",
    dependencies=[Depends(require_role(Role.ADMIN))],
    summary="Admin-only access check",
)
def admin_test() -> dict:
    """Return 200 only for ADMIN users; 401 unauthenticated / 403 otherwise."""
    return {"status": "admin_access_ok"}
