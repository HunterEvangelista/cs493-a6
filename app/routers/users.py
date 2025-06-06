import logging
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, File, Request
from fastapi.responses import JSONResponse, Response

from app.dependencies import get_user_info
from app.models.auth import LoginPost, LoginResponse
from app.models.users import (
    AvatarResponse,
    User,
    UserClient,
    UserCore,
    UserResponse,
    UserRoles,
)
from app.utils.jwt_utils import JWTUtils
from app.utils.storage_utils import StorageHandler

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
async def get_user(
    user_id: int, user: Annotated[User | None, Depends(get_user_info)]
):
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


@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: int, user: Annotated[User | None, Depends(get_user_info)]
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user_id != user.id:
        return JSONResponse(content=error_responses[403], status_code=403)

    user_client = UserClient()

    has_avatar = await user_client.verify_user_has_avatar(user_id)
    if not has_avatar:
        return JSONResponse(content=error_responses[404], status_code=404)

    try:
        file_obj = StorageHandler.get_avatar(user_id)
        file_bytes = file_obj.read()

        logger.info("Returning Response with file bytes")
        return Response(content=file_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Error retrieving avatar for user {user_id}: {e}")
        return JSONResponse(content=error_responses[404], status_code=404)


@router.post("/{user_id}/avatar", response_model=AvatarResponse)
async def upload_user_avatar(
    user_id: int,
    user: Annotated[User | None, Depends(get_user_info)],
    request: Request,
    file: Annotated[bytes, File()],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user_id != user.id:
        return JSONResponse(content=error_responses[403], status_code=403)

    user_client = UserClient()
    scheme, netloc, *_ = request.url.components

    try:
        StorageHandler.upload_avatar(file, f"{user_id}.png")
        await user_client.create_user_avatar_record(user_id)
        return AvatarResponse(
            avatar_url=f"{scheme}://{netloc}/users/{user_id}/avatar"
        )
    except Exception as e:
        logger.error(f"Error uploading avatar for user {user_id}: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)


@router.delete("/{user_id}/avatar", status_code=204)
async def delete_user_avatar(
    user_id: int,
    user: Annotated[User | None, Depends(get_user_info)],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user_id != user.id:
        return JSONResponse(content=error_responses[403], status_code=403)

    user_client = UserClient()

    try:
        user_has_avatar = await user_client.verify_user_has_avatar(user_id)
        if not user_has_avatar:
            return JSONResponse(content=error_responses[404], status_code=404)
        await user_client.delete_user_avatar_record(user_id)
        StorageHandler.delete_avatar(user_id)
    except Exception as e:
        logger.error(f"Error deleting avatar for user {user_id}: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)
