from pydantic import BaseModel


class DecodedToken(BaseModel):
    aud: str
    email: str
    email_verified: bool
    exp: int
    iat: int
    iss: str
    name: str
    nickname: str
    picture: str
    sub: str
    updated_at: str


class LoginPost(BaseModel):
    username: str
    password: str
