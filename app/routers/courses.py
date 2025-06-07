import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.dependencies import get_user_info
from app.models.courses import (
    CourseClient,
    CourseEnrollmentUpdate,
    CourseException,
    CoursePost,
    CoursePut,
    CourseResponse,
    CoursesResponse,
)
from app.models.users import User, UserClient, UserException, UserRoles
from app.utils.jwt_utils import JWTUtils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

error_responses = {
    400: {"Error": "The request body is invalid"},
    401: {"Error": "Unauthorized"},
    403: {"Error": "You don't have permission on this resource"},
    404: {"Error": "Not found"},
    409: {"Error": "Enrollment data is invalid"},
    500: {"Error": "Internal server error"},
}

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
    responses={**error_responses},
)

jwt_utils = JWTUtils()


@router.post("", response_model=CourseResponse, status_code=201)
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
        instructor = await course_client.get_instructor(course_id)
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


@router.get("", response_model=CoursesResponse)
async def get_courses(
    user: Annotated[User | None, Depends(get_user_info)],
    request: Request,
    offset: Annotated[
        int, Query(ge=0, description="Offset for pagination")
    ] = 0,
    limit: Annotated[int, Query(ge=1, description="Limit for pagination")] = 3,
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

    return CoursesResponse(
        courses=course_responses,
        next=f"{scheme}://{netloc}/courses?offset={offset + limit}&limit={limit}",
    )


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(  # noqa: C901
    course_id: int,
    course: CoursePut,
    request: Request,
    user: Annotated[User | None, Depends(get_user_info)],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role != UserRoles.ADMIN.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    scheme, netloc, *_ = request.url.components
    course_client = CourseClient()
    user_client = UserClient()

    update_data = course.model_dump(exclude_none=True)

    try:
        existing_course = await course_client.get_course(course_id)
        if not existing_course:
            return JSONResponse(content=error_responses[404], status_code=404)
    except CourseException:
        return JSONResponse(content=error_responses[404], status_code=404)
    except Exception as e:
        logger.error(f"Error checking course existence {course_id}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)

    try:
        if not update_data:
            instructor_id = await course_client.get_instructor(course_id)
            return CourseResponse(
                id=course_id,
                number=existing_course.number,
                title=existing_course.title,
                subject=existing_course.subject,
                term=existing_course.term,
                instructor_id=instructor_id,
                self=f"{scheme}://{netloc}/courses/{course_id}",
            )

        if "instructor_id" in update_data:
            instructor_id = update_data.pop("instructor_id")

            try:
                role = await user_client.get_user_role("id", instructor_id)
                if role != UserRoles.INSTRUCTOR.value:
                    return JSONResponse(
                        content=error_responses[400], status_code=400
                    )
            except UserException:
                return JSONResponse(
                    content=error_responses[400], status_code=400
                )

            await course_client.update_instructor(course_id, instructor_id)

        if update_data:
            await course_client.update_course(course_id, update_data)

        updated_course = await course_client.get_course(course_id)
        instructor_id = await course_client.get_instructor(course_id)

        return CourseResponse(
            id=course_id,
            number=updated_course.number,
            title=updated_course.title,
            subject=updated_course.subject,
            term=updated_course.term,
            instructor_id=instructor_id,
            self=f"{scheme}://{netloc}/courses/{course_id}",
        )

    except CourseException as e:
        logger.error(f"CourseException updating course {course_id}: {e}")
        return JSONResponse(content=error_responses[404], status_code=404)
    except UserException as e:
        logger.error(f"UserException updating course {course_id}: {e}")
        return JSONResponse(content=error_responses[400], status_code=400)
    except Exception as e:
        logger.error(f"Error updating course {course_id}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)


@router.delete("/{course_id}", status_code=204, response_model=None)
async def delete_course(
    course_id: int,
    request: Request,
    user: Annotated[User | None, Depends(get_user_info)],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role != UserRoles.ADMIN.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    course_client = CourseClient()
    try:
        await course_client.delete_course(course_id)
    except Exception as e:
        logger.error(f"Error deleting course {course_id}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)

    try:
        await course_client.delete_course_instructor(course_id)
    except Exception as e:
        logger.error(f"Error deleting instructor for course {course_id}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)

    try:
        await course_client.delete_course_enrollment(course_id)
    except Exception as e:
        logger.error(f"Error deleting student for course {course_id}: {e}")
        return JSONResponse(content={"Error": "Server error"}, status_code=500)


@router.patch("/{course_id}/students", response_model=None)
async def update_course_enrollment(  # noqa: C901
    course_id: int,
    request: Request,
    update: CourseEnrollmentUpdate,
    user: Annotated[User | None, Depends(get_user_info)],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role == UserRoles.STUDENT.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    course_client = CourseClient()

    # check if the user is the instructor of the course
    course_instructor_id = await course_client.get_instructor(course_id)

    if (
        user.id != course_instructor_id
        and user.role == UserRoles.INSTRUCTOR.value
    ):
        return JSONResponse(content=error_responses[403], status_code=403)

    try:
        await course_client.get_course(course_id)
    except CourseException:
        logger.error(f"No course found with id: {course_id}")
        return JSONResponse(content=error_responses[403], status_code=403)

    try:
        user_client = UserClient()
        for user_id in update.add:
            user_role = await user_client.get_user_role("id", user_id)
            if user_role != UserRoles.STUDENT.value:
                return JSONResponse(
                    content=error_responses[409], status_code=409
                )
            if user_id in update.remove:
                return JSONResponse(
                    content=error_responses[409], status_code=409
                )

        for user_id in update.remove:
            user_role = await user_client.get_user_role("id", user_id)
            if user_role != UserRoles.STUDENT.value:
                return JSONResponse(
                    content=error_responses[409], status_code=409
                )

    except UserException:
        logger.error("Entered user not found")
        return JSONResponse(content=error_responses[409], status_code=409)
    except Exception as e:
        logger.error(f"Error validating course update: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)

    try:
        await course_client.add_users_to_course(update.add, course_id)
    except Exception as e:
        logger.error(f"Error adding users to course: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)

    try:
        await course_client.remove_users_from_course(update.remove, course_id)
    except Exception as e:
        logger.error(f"Error removing users from course: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)


@router.get("/{course_id}/students", response_model=list[int])
async def get_course_students(
    course_id: int,
    user: Annotated[User | None, Depends(get_user_info)],
):
    if user is None:
        return JSONResponse(content=error_responses[401], status_code=401)

    if user.role == UserRoles.STUDENT.value:
        return JSONResponse(content=error_responses[403], status_code=403)

    course_client = CourseClient()

    # check if the user is the instructor of the course
    course_instructor_id = await course_client.get_instructor(course_id)

    if (
        user.id != course_instructor_id
        and user.role == UserRoles.INSTRUCTOR.value
    ):
        return JSONResponse(content=error_responses[403], status_code=403)

    try:
        await course_client.get_course(course_id)
    except CourseException:
        logger.error(f"No course found with id: {course_id}")
        return JSONResponse(content=error_responses[403], status_code=403)
    course_client = CourseClient()
    try:
        students = await course_client.get_course_students(course_id)
    except Exception as e:
        logger.error(f"Error getting course students: {e}")
        return JSONResponse(content=error_responses[500], status_code=500)
    return students
