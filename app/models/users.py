import logging
from enum import Enum
from typing import Literal, Optional, Union

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


class UserResponse(UserCore):
    avataor_url: Optional[str]
    courses: list[str]


class AvatarResponse(BaseModel):
    avatar_url: str


class UserClient:
    def __init__(self):
        self.client = datastore.Client(database="tarpaulin")
        self.USERS = "Users"
        self.USER_AVATAR = "UserAvatar"

    async def get_user_by_sub(self, sub) -> User | None:
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

    async def get_user_by_id(self, id: int) -> User | None:
        user_key = self.client.key(self.USERS, id)
        query = self.client.query(kind=self.USERS)
        query.key_filter(user_key, "=")
        try:
            entity = list(query.fetch())
            if len(entity) == 0:
                raise UserException("User not found")
            entity = entity[0]
            entity[0]["id"] = entity.key.id
        except Exception as e:
            logger.error(f"Error fetching user by sub: {e}")
            raise

        if entity:
            return User(**entity)
        return None

    async def get_user_role(
        self, access: Union[Literal["id"], Literal["sub"]], id
    ) -> str:
        """
        Returns the role of the given user
        """

        if access == "id":
            user = await self.get_user_by_id(id)
        else:
            user = await self.get_user_by_sub(id)

        if user is None:
            logger.error(f"Could not get user via {access} with token {id}")
            raise UserException("User not found")

        return user.role

    async def verify_user_has_avatar(self, id: int) -> bool:
        try:
            user_key = self.client.key(self.USERS, id)
            query = self.client.query(kind=self.USER_AVATAR, ancestor=user_key)
            avatars = list(query.fetch(limit=1))
            return len(avatars) > 0

        except Exception as e:
            logger.error(f"Error checking user avatar for user {id}: {e}")
            return False

    async def create_user_avatar_record(self, user_id: int) -> None:
        try:
            # no need if user already has avatar
            has_avatar = await self.verify_user_has_avatar(user_id)
            if has_avatar:
                logger.info(
                    f"User {user_id} already has an avatar record, skipping creation"
                )
                return

            user_key = self.client.key(self.USERS, user_id)

            avatar_key = self.client.key(self.USER_AVATAR, parent=user_key)
            avatar_entity = datastore.Entity(key=avatar_key)

            avatar_entity["file"] = f"{user_id}.png"

            self.client.put(avatar_entity)

            logger.info(f"Created avatar record for user {user_id}")

        except Exception as e:
            logger.error(
                f"Error creating avatar record for user {user_id}: {e}"
            )
            raise


if __name__ == "__main__":
    import asyncio

    async def main():
        user = UserClient()
        id = 5081054809423871
        valid = await user.verify_user_has_avatar(id)
        if valid:
            print(f"User {id} has avatar")
        else:
            print("No avatar")

    asyncio.run(main())
