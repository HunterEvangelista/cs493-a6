import logging
from typing import Annotated, Any, Dict

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import get_user_info
from app.models.auth import LoginPost, LoginResponse
from app.models.users import User, UserClient, UserCore, UserRoles, UserResponse
from app.utils.jwt_utils import JWTUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
POST login

GET users
- admin only

GET users/:id
- admin or JWT matches user
- must have avatar and courses (for instructors and students)

POST users/:id/avatar
- user with matching JWT
- file must be in google cloud storage

GET /users/:id/avatar
- User with matching JWT
- read and return file from google cloud storage

DELETE /users/:id/avatar
- User with matching JWT
- delete file from google cloud storage
"""

error_responses = {
    400: {"Error": "The request body is invalid"},
    401: {"Error": "Unauthorized"},
    403: {"Error": "You don't have permission on this resource"},
    404: {"Error": "Not Found"},
}

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={**error_responses},
)

jwt_utils = JWTUtils()


@router.post("/login", response_model=LoginResponse)
async def login(login: LoginPost):
    body = {
        "grant_type": "password",
        "username": login.username,
        "password": login.password,
        "client_id": jwt_utils.get_client_id(),
        "client_secret": jwt_utils.get_client_secret(),
    }
    headers = {"content-type": "application/json"}
    url = "https://" + jwt_utils.get_domain() + "/oauth/token"

    try:
        resp = requests.post(url, json=body, headers=headers)
    except Exception as e:
        logger.error(f"Exception raised: {str(e)}")
        raise
    content = resp.json()
    if "error" in content:
        logger.error(f"Error response from auth0: {content}")
        return JSONResponse(content=error_responses[401], status_code=401)
    return LoginResponse(token=content["id_token"])


# get all users
# must have all 9 pre-created users from datastore


@router.get("", response_model=list[UserCore])
async def get_users(user: Annotated[User | None, Depends(get_user_info)]):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role != UserRoles.ADMIN.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    user_client = UserClient()

    return await user_client.get_all_users()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, user: Annotated[User | None, Depends(get_user_info)]):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role != UserRoles.ADMIN.value and user_id != user.id:
        return JSONResponse(content=error_responses[403], status_code=403)

    user_client = UserClient()

    try:
        retrieved_user = await user_client.get_user_by_id(user_id)
        if retrieved_user is None:
            raise Exception
    except Exception:
        return JSONResponse(content=error_responses[403], status_code=403)

    # if user is instructor, get courses they are teaching
    #
    # if user is a student, get the courses they are enrolled in
