import logging
from typing import Annotated

from fastapi import Depends, Request

from app.models.users import User, UserClient
from app.utils.jwt_utils import JWTUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def authenticate_request(request: Request) -> bool:
    jwt_utils = JWTUtils()
    try:
        # just determine if we can validate
        await jwt_utils.validate_token(request)
    except Exception:
        return False

    return True


async def get_user_info(
    request: Request,
    authenticated: Annotated[bool, Depends(authenticate_request)],
) -> User | None:
    if not authenticated:
        return None

    jwt_utils = JWTUtils()
    user_client = UserClient()

    token = jwt_utils.extract_token(request)
    user_info = await jwt_utils.decode_token(token)
    try:
        user = await user_client.get_user_by_sub(user_info["sub"])
    except Exception as e:
        logger.error(f"Error fetching user: {str(e)}")
        return None

    return user
