import logging

from google.cloud import datastore
from pydantic import BaseModel, create_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
How do we model courses?
Its going to be so annoying with datastore
"""


def make_optional(model_class):
    return create_model(
        f"{model_class.__name__}Optional",
        **{
            f"{field.name}": (field.type_, None)
            for field in model_class.__fields__.values()
        },
    )


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


CoursePut = make_optional(CoursePost)


class CourseResponse(Course):
    self: str


class CourseWithInstructors(Course):
    instructor_id: int


class CourseClient:
    def __init__(self):
        self.client = datastore.Client()
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

    async def get_course(self, course_id: int) -> Course:
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

        return Course(**entity)

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
        """
        Get instructor ID for a course
        """
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
        """
        Get paginated list of courses sorted by subject
        """
        try:
            course_query = self.client.query(kind=self.COURSES)

            course_query.order = [
                datastore.query.PropertyOrder(
                    "subject", datastore.query.PropertyOrder.ASCENDING
                )
            ]
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
