import asyncio

from google.cloud import datastore
from pydantic import BaseModel


class UserCore(BaseModel):
    id: int
    role: str
    sub: str  # use this to filter for users in datastore


class User(UserCore):
    username: str


class UserClient:
    def __init__(self):
        self.client = datastore.Client(database="tarpaulin")
        self.USERS = "Users"

    async def get_user_by_sub(self, sub) -> User:
        query = self.client.query(kind=self.USERS)
        query.add_filter(property_name="sub", operator="=", value=sub)
        entity = list(query.fetch())[0]
        entity["id"] = entity.key.id
        if entity:
            print(entity)
            return User(**entity)
        return None


if __name__ == "__main__":
    user_client = UserClient()
    user = asyncio.run(
        user_client.get_user_by_sub("auth0|683937ac2b6ad634b969de2e")
    )
    print(user)
