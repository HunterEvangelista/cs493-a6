import logging
from enum import Enum
from typing import Optional

from google.cloud import datastore
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserException(Exception):
    pass


class UserRoles(Enum):
    ADMIN = "admin"
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class UserCore(BaseModel):
    id: int
    role: str
    sub: str  # use this to filter for users in datastore


class User(UserCore):
    username: str


class Instructor(UserCore):
    avataor_url: Optional[str]
    courses: list[str]


class UserClient:
    def __init__(self):
        self.client = datastore.Client(database="tarpaulin")
        self.USERS = "Users"

    async def get_user_by_sub(self, sub) -> User:
        query = self.client.query(kind=self.USERS)
        query.add_filter(property_name="sub", operator="=", value=sub)
        try:
            entity = list(query.fetch())
            if len(entity) == 0:
                raise UserException("User not found")
            entity = entity[0]
            entity["id"] = entity.key.id
        except Exception as e:
            logger.error(f"Error fetching user by sub: {e}")
            raise

        if entity:
            return User(**entity)
        return None

    async def get_all_users(self) -> list[UserCore]:
        query = self.client.query(kind=self.USERS)
        entities = list(query.fetch())
        for entity in entities:
            entity["id"] = entity.key.id
        return [UserCore(**entity) for entity in entities]

    async def get_instructur_courses(self, id: int):
        pass

    async def get_student_courses(self, id: int):
        pass
