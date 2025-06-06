import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.dependencies import get_user_info
from app.models.courses import (
    CourseClient,
    CourseException,
    CoursePost,
    CoursePut,
    CourseResponse,
)
from app.models.users import User, UserClient, UserException, UserRoles
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
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role != UserRoles.ADMIN.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    scheme, netloc, *_ = request.url.components
    user_client = UserClient()
    course_client = CourseClient()

    try:
        role = await user_client.get_user_role("id", post.instructor_id)

        if role != UserRoles.INSTRUCTOR.value:
            raise UserException("Instructor not found")
    except UserException as e:
        logger.error(
            f"Error getting user role for instructor {post.instructor_id}: {e}"
        )
        return JSONResponse(content=error_responses[400], status_code=400)

    try:
        course_id = await course_client.create_course(post)
    except Exception as e:
        logger.error(f"Error creating course {post}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)

    return CourseResponse(
        id=course_id,
        title=post.title,
        number=post.number,
        term=post.term,
        instructor_id=post.instructor_id,
        subject=post.subject,
        self=f"{scheme}://{netloc}/courses/{course_id}",
    )


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    request: Request,
):
    scheme, netloc, *_ = request.url.components
    course_client = CourseClient()
    try:
        course = await course_client.get_course(course_id)
    except CourseException as e:
        logger.error(f"Error getting course {course_id}: {e}")
        return JSONResponse(content=error_responses[404], status_code=404)
    except Exception as e:
        logger.error(f"Unexpected error getting course {course_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal Server Error"
        ) from e

    # courses always have an instructor
    try:
        instructor = await course_client.get_instructor(course.id)
    except Exception as e:
        logger.error(
            f"Unexpected error getting instructor {course.instructor_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Internal Server Error"
        ) from e

    return CourseResponse(
        id=course_id,
        number=course.number,
        title=course.title,
        subject=course.subject,
        term=course.term,
        instructor_id=instructor,
        self=f"{scheme}://{netloc}/courses/{course_id}",
    )


@router.get("", response_model=list[CourseResponse])
async def get_courses(
    user: Annotated[User | None, Depends(get_user_info)],
    offset: Annotated[
        int, Query(default=0, ge=0, description="Offset for pagination")
    ],
    limit: Annotated[
        int, Query(default=3, ge=1, description="Limit for pagination")
    ],
    request: Request,
):
    scheme, netloc, *_ = request.url.components
    course_client = CourseClient()

    try:
        courses = await course_client.get_courses(offset=offset, limit=limit)
    except CourseException as e:
        logger.error(f"Error getting courses: {e}")
        return JSONResponse(content=error_responses[404], status_code=404)
    except Exception as e:
        logger.error(f"Unexpected error getting courses: {e}")
        raise HTTPException(
            status_code=500, detail="Internal Server Error"
        ) from e

    course_responses = []
    for course in courses:
        course_responses.append(
            CourseResponse(
                id=course.id,
                number=course.number,
                title=course.title,
                subject=course.subject,
                term=course.term,
                instructor_id=course.instructor_id,
                self=f"{scheme}://{netloc}/courses/{course.id}",
            )
        )

    return course_responses


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course: CoursePut,
    request: Request,
):
    pass
