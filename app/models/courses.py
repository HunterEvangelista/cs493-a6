from pydantic import BaseModel

"""
How do we model courses?
Its going to be so annoying with datastore
"""


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


class CourseInstructors(BaseModel):
    course_id: int
    instructor_id: int


class CourseEnrolment(BaseModel):
    course_id: int
    student_id: int


class CoursePost(CourseCore):
    insrtuctor_id: int


class CourseResponse(Course):
    self: str
