from typing import Annotated

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.dependencies import authenticate_request
from app.exceptions import validation_exception_handler
from app.models.auth import DecodedToken
from app.routers import courses, users
from app.utils.jwt_utils import JWTUtils

app = FastAPI()
oauth = OAuth()
jwt_utils = JWTUtils()
oauth.register(
    "auth0",
    client_id=jwt_utils.get_client_id(),
    client_secret=jwt_utils.get_client_secret(),
    api_base_url="https://" + jwt_utils.get_domain(),
    access_token_url="https://" + jwt_utils.get_domain() + "/oauth/token",
    authorize_url="https://" + jwt_utils.get_domain() + "/authorize",
    client_kwargs={
        "scope": "openid profile email",
    },
)

app.include_router(users.router)
app.include_router(courses.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def handle(request, exc):
    return await validation_exception_handler(request, exc)


# I think I will just use a dependency on each route so I don't have
# weird routing stuff anymore

# @app.middleware("http")
# async def authenticate_user(request: Request, call_next):
#     public = ["/login", "/docs", "/", "/openapi.json"]

#     if request.url.path in public:
#         return await call_next(request)

#     if "/businesses" == request.url.path and request.method == "GET":
#         return await call_next(request)

#     try:
#         JWTUtils.validate_token(request)
#         return await call_next(request)
#     except AuthError as e:
#         return JSONResponse(status_code=e.status_code, content={"error": e.message})


@app.get("/")
async def root(authenticated: Annotated[bool, Depends(authenticate_request)]):
    print("Authenticated dep ran: ", authenticated)
    return JSONResponse(content={"message": "connected"})


@app.get(
    "/decode",
    response_model=DecodedToken,
)
async def decode_token(request: Request):
    token = JWTUtils.extract_token(request)
    return DecodedToken(**JWTUtils.decode_token(token))
