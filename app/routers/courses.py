import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_user_info
from app.models.courses import CoursePost, CourseResponse
from app.models.users import User
from app.utils.jwt_utils import JWTUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

error_responses = {
    400: {"Error": "The request body is invalid"},
    401: {"Error": "Unauthorized"},
    403: {"Error": "You don't have permission on this resource"},
    404: {"Error": "Not Found"},
}

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
    responses={**error_responses},
)

jwt_utils = JWTUtils()


@router.post("", response_model=CourseResponse)
async def add_new_course(
    user: Annotated[User | None, Depends(get_user_info)],
    post: CoursePost,
    request: Request,
):
    """
    Need to validate instructor id

    Only users with an admin role
    invalid token => 401
    Not an admin => 403

    400 error should happen only when
    This should not be an issue
    FastAPI checks dependencies before validation
    """
    pass
