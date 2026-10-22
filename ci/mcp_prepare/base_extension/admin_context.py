"""Identity bound only AFTER the existing endpoint validates OAuth/native auth."""
from contextvars import ContextVar
verified_identity=ContextVar('ems_admin_verified_identity',default=None)

async def require_admin(hass):
    claims=verified_identity.get()
    if not isinstance(claims,dict) or not isinstance(claims.get('sub'),str):
        raise PermissionError('ADMIN_IDENTITY_REQUIRED')
    user=await hass.auth.async_get_user(claims['sub'])
    if user is None or not user.is_active or not user.is_admin:
        raise PermissionError('ACTIVE_HA_ADMIN_REQUIRED')
    return user.id
