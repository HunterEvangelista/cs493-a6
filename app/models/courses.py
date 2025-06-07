import logging
from typing import Optional

from google.cloud import datastore
from pydantic import BaseModel

from app.models.users import UserClient, UserRoles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
How do we model courses?
Its going to be so annoying with datastore
"""


class CourseException(Exception):
    pass


class CourseCore(BaseModel):
    number: int
    subject: str
    title: str
    term: str


class Course(CourseCore):
    """
    Represents the course entity in datastore
    """

    id: int
    instructor_id: int


class CourseInstructors(BaseModel):
    course_id: int
    instructor_id: int


class CourseEnrolment(BaseModel):
    course_id: int
    student_id: int


class CoursePost(CourseCore):
    instructor_id: int


class CoursePut(BaseModel):
    number: Optional[int] = None
    subject: Optional[str] = None
    title: Optional[str] = None
    term: Optional[str] = None
    instructor_id: Optional[int] = None


class CourseResponse(Course):
    self: str


class CoursesResponse(BaseModel):
    courses: list[CourseResponse]
    next: str


class CourseWithInstructors(Course):
    instructor_id: int


class CourseEnrollmentUpdate(BaseModel):
    add: list[int]
    remove: list[int]


class CourseClient:
    def __init__(self):
        self.client = datastore.Client(database="tarpaulin")
        self.COURSES = "Courses"
        self.COURSE_INSTRUCTORS = "CourseInstructor"
        self.COURSE_ENROLMENT = "CourseEnrolment"

    async def create_course(self, course: CoursePost) -> int:
        try:
            new_course_key = self.client.key(self.COURSES)
            new_course = datastore.Entity(key=new_course_key)
            new_course.update(
                {
                    "number": course.number,
                    "subject": course.subject,
                    "title": course.title,
                    "term": course.term,
                }
            )
            self.client.put(new_course)

            new_course["id"] = new_course.key.id
        except Exception as e:
            logger.error(f"Error creating course: {e}")
            raise

        try:
            new_course_instructor_key = self.client.key(self.COURSE_INSTRUCTORS)
            new_course_instructor = datastore.Entity(
                key=new_course_instructor_key
            )
            new_course_instructor.update(
                {
                    "course_id": new_course.key.id,
                    "instructor_id": course.instructor_id,
                }
            )
            self.client.put(new_course_instructor)
        except Exception as e:
            logger.error(f"Error creating course instructor: {e}")
            raise

        return new_course["id"]

    async def get_course(self, course_id: int) -> CourseCore:
        course_key = self.client.key(self.COURSES, course_id)
        query = self.client.query(kind=self.COURSES)
        query.key_filter(course_key, "=")
        try:
            entity = list(query.fetch())
            if len(entity) == 0:
                raise CourseException("Course not found")
            entity = entity[0]
            entity["id"] = entity.key.id

        except Exception as e:
            logger.error(f"Error fetching course: {e}")
            raise

        return CourseCore(
            subject=entity["subject"],
            title=entity["title"],
            number=entity["number"],
            id=entity["id"],
            term=entity["term"],
        )

    async def get_course_instructor(self, course_id: int) -> int:
        course_instructor_key = self.client.key(
            self.COURSE_INSTRUCTORS, course_id
        )
        query = self.client.query(kind=self.COURSE_INSTRUCTORS)
        query.key_filter(course_instructor_key, "=")
        try:
            entity = list(query.fetch())
            if len(entity) == 0:
                raise CourseException("Course instructor not found")
            entity = entity[0]
            entity["id"] = entity.key.id

        except Exception as e:
            logger.error(f"Error fetching course instructor: {e}")
            raise

        return entity["instructor_id"]

    async def get_instructor(self, course_id: int) -> int:
        query = self.client.query(kind=self.COURSE_INSTRUCTORS)
        query.add_filter(
            property_name="course_id", operator="=", value=course_id
        )

        try:
            entities = list(query.fetch(limit=1))
            if len(entities) == 0:
                raise CourseException("Course instructor not found")
            return entities[0]["instructor_id"]
        except Exception as e:
            logger.error(
                f"Error fetching instructor for course {course_id}: {e}"
            )
            raise

    async def get_courses(
        self, offset: int = 0, limit: int = 3
    ) -> list[Course]:
        try:
            course_query = self.client.query(kind=self.COURSES)
            course_query.order = ["subject"]
            course_entities = list(
                course_query.fetch(offset=offset, limit=limit)
            )

            if not course_entities:
                return []

            for entity in course_entities:
                entity["id"] = entity.key.id

            courses_with_instructors = []
            for course_entity in course_entities:
                try:
                    instructor_id = await self.get_instructor(
                        course_entity["id"]
                    )
                    course_entity["instructor_id"] = instructor_id
                    courses_with_instructors.append(Course(**course_entity))
                except CourseException as e:
                    logger.warning(
                        f"Course {course_entity['id']} has no instructor: {e}"
                    )
                    continue

            return courses_with_instructors

        except Exception as e:
            logger.error(f"Error fetching courses: {e}")
            raise

    async def get_course_students(self, course_id: int) -> list[int]:
        try:
            query = self.client.query(kind=self.COURSE_ENROLMENT)
            query.add_filter(
                property_name="course_id", operator="=", value=course_id
            )
            entities = list(query.fetch())
            student_ids = [entity["student_id"] for entity in entities]

        except Exception as e:
            logger.error(f"Error fetching course students: {e}")
            raise

        return student_ids

    async def get_user_courses(self, user_id: int) -> list[int]:
        user_client = UserClient()
        try:
            user_role = await user_client.get_user_role("id", user_id)
            if user_role == UserRoles.ADMIN.value:
                raise Exception("Admins cannot be enrolled in courses")
        except Exception as e:
            logger.error(f"Error getting user role: {str(e)}")
            raise

        course_ids = []

        try:
            if user_role == UserRoles.STUDENT.value:
                query = self.client.query(kind=self.COURSE_ENROLMENT)
                query.add_filter(
                    property_name="student_id", operator="=", value=user_id
                )
                entities = list(query.fetch())
                course_ids = [entity["course_id"] for entity in entities]

            elif user_role == UserRoles.INSTRUCTOR.value:
                query = self.client.query(kind=self.COURSE_INSTRUCTORS)
                query.add_filter(
                    property_name="instructor_id", operator="=", value=user_id
                )
                entities = list(query.fetch())
                course_ids = [entity["course_id"] for entity in entities]

        except Exception as e:
            logger.error(f"Error getting user courses: {str(e)}")
            raise

        return course_ids

    async def update_course(self, course_id: int, updates: dict) -> None:
        try:
            course_key = self.client.key(self.COURSES, course_id)
            course_entity = self.client.get(course_key)

            if not course_entity:
                raise CourseException(f"Course with ID {course_id} not found")

            valid_properties = {"number", "subject", "title", "term"}
            for property, value in updates.items():
                if property in valid_properties:
                    course_entity[property] = value
                else:
                    raise CourseException(
                        f"Invalid course property: {property}"
                    )

            self.client.put(course_entity)
            logger.info(f"Successfully updated course {course_id}")

        except Exception as e:
            logger.error(f"Error updating course {course_id}: {str(e)}")
            raise

    async def update_instructor(
        self, course_id: int, new_instructor_id: int
    ) -> None:
        """
        Update the instructor for a course
        """
        try:
            course_key = self.client.key(self.COURSES, course_id)
            course_entity = self.client.get(course_key)

            if not course_entity:
                raise CourseException(f"Course with ID {course_id} not found")

            query = self.client.query(kind=self.COURSE_INSTRUCTORS)
            query.add_filter(
                property_name="course_id", operator="=", value=course_id
            )

            instructor_entities = list(query.fetch())

            if instructor_entities:
                instructor_entity = instructor_entities[0]
                instructor_entity["instructor_id"] = new_instructor_id
                self.client.put(instructor_entity)
            else:
                new_instructor_key = self.client.key(self.COURSE_INSTRUCTORS)
                new_instructor_entity = datastore.Entity(key=new_instructor_key)
                new_instructor_entity.update(
                    {
                        "course_id": course_id,
                        "instructor_id": new_instructor_id,
                    }
                )
                self.client.put(new_instructor_entity)

            logger.info(
                f"Successfully updated instructor for course {course_id} to {new_instructor_id}"
            )

        except Exception as e:
            logger.error(
                f"Error updating instructor for course {course_id}: {str(e)}"
            )
            raise

    async def delete_course(self, course_id: int) -> None:
        try:
            course_key = self.client.key(self.COURSES, course_id)
            course_entity = self.client.get(course_key)

            if not course_entity:
                raise CourseException(f"Course with ID {course_id} not found")

            self.client.delete(course_key)

            logger.info(f"Successfully deleted course {course_id}")

        except Exception as e:
            logger.error(f"Error deleting course {course_id}: {str(e)}")
            raise

    async def delete_course_instructor(self, course_id: int) -> None:
        """Dangerous, must be used with the delete course method"""
        try:
            course_instructor_query = self.client.query(
                kind=self.COURSE_INSTRUCTORS
            )
            course_instructor_query.add_filter(
                property_name="course_id", operator="=", value=course_id
            )
            instructor_entities = list(course_instructor_query.fetch())

            if instructor_entities:
                instructor_entity = instructor_entities[0]
                self.client.delete(instructor_entity.key)

            logger.info(
                f"Successfully deleted instructor for course {course_id}"
            )

        except Exception as e:
            logger.error(
                f"Error deleting instructor for course {course_id}: {str(e)}"
            )
            raise

    async def delete_course_enrollment(self, course_id: int) -> None:
        try:
            course_enrollment_query = self.client.query(
                kind=self.COURSE_ENROLMENT
            )
            course_enrollment_query.add_filter(
                property_name="course_id", operator="=", value=course_id
            )
            enrollment_entities = list(course_enrollment_query.fetch())

            if enrollment_entities:
                for enrollment_entity in enrollment_entities:
                    self.client.delete(enrollment_entity.key)

            logger.info(
                f"Successfully deleted enrollments for course {course_id}"
            )

        except Exception as e:
            logger.error(
                f"Error deleting enrollments for course {course_id}: {str(e)}"
            )
            raise

    async def check_if_enrolled(self, user_id: int, course_id: int) -> bool:
        try:
            query = self.client.query(kind=self.COURSE_ENROLMENT)
            query.add_filter("course_id", "=", course_id)
            query.add_filter("student_id", "=", user_id)
            results = list(query.fetch(limit=1))
            return bool(len(results))
        except Exception as e:
            logger.error(
                f"Error checking enrollment for user {user_id} in course {course_id}: {str(e)}"
            )
            raise

    async def add_users_to_course(self, user_ids: list[int], course_id: int):
        if len(user_ids) == 0:
            return
        try:
            for user_id in user_ids:
                enrolled = await self.check_if_enrolled(user_id, course_id)
                if enrolled:
                    continue
                new_enrollment_key = self.client.key(self.COURSE_ENROLMENT)
                new_course_enrollment = datastore.Entity(key=new_enrollment_key)
                new_course_enrollment.update(
                    {"course_id": course_id, "student_id": user_id}
                )
                self.client.put(new_course_enrollment)

        except Exception as e:
            logger.error(f"Error adding users to course {course_id}: {str(e)}")
            raise

    async def remove_users_from_course(
        self, user_ids: list[int], course_id: int
    ):
        if len(user_ids) == 0:
            return
        try:
            for user_id in user_ids:
                enrolled = await self.check_if_enrolled(user_id, course_id)
                if not enrolled:
                    continue
                enrollment_query = self.client.query(kind=self.COURSE_ENROLMENT)
                enrollment_query.add_filter(
                    property_name="course_id", operator="=", value=course_id
                )
                enrollment_query.add_filter(
                    property_name="student_id", operator="=", value=user_id
                )
                enrollment_entities = list(enrollment_query.fetch())

                if enrollment_entities:
                    for enrollment_entity in enrollment_entities:
                        self.client.delete(enrollment_entity.key)

        except Exception as e:
            logger.error(
                f"Error removing users from course {course_id}: {str(e)}"
            )
            raise
