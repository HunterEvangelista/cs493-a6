from fastapi import Request

from app.utils.jwt_utils import JWTUtils


async def authenticate_request(request: Request) -> bool:
    jwt_utils = JWTUtils()
    try:
        # just determine if we can validate
        await jwt_utils.validate_token(request)
    except Exception:
        return False

    return True


# can extend with a get user
