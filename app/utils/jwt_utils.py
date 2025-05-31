import logging

import jwt
from fastapi import Request
from google.cloud import secretmanager
from jwt import PyJWKClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code


class JWTUtils:
    """Configuration for JWT token generation and validation."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._secret_client = secretmanager.SecretManagerServiceClient()
        self.CLIENT_ID = None
        self.CLIENT_SECRET = None
        self.DOMAIN = None
        self.ALGORITHM = ["RS256"]
        self._initialized = True

        self._load_config()

    def _get_secret(self, secret_id):
        try:
            name = f"projects/evangelh493a3/secrets/{secret_id}/versions/latest"
            resp = self._secret_client.access_secret_version(
                request={"name": name}
            )
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_id}: {e}")
            raise
        return resp.payload.data.decode("UTF-8")

    def _load_config(self):
        if self.CLIENT_ID is None:
            self.CLIENT_ID = self._get_secret("client_id")
            self.CLIENT_SECRET = self._get_secret("client_secret")
            self.DOMAIN = self._get_secret("oauth_domain")

    def get_client_id(self) -> str:
        if self.CLIENT_ID is None:
            self._load_config()

        if self.CLIENT_ID is None:
            logger.error("Error setting JWT config")
            raise ValueError("JWT configuration is not loaded")
        return self.CLIENT_ID

    def get_client_secret(self) -> str:
        if self.CLIENT_SECRET is None:
            self._load_config()

        if self.CLIENT_SECRET is None:
            logger.error("Error setting JWT config")
            raise ValueError("JWT configuration is not loaded")
        return self.CLIENT_SECRET

    def get_domain(self) -> str:
        if self.DOMAIN is None:
            self._load_config()

        if self.DOMAIN is None:
            logger.error("Error setting JWT config")
            raise ValueError("JWT configuration is not loaded")
        return self.DOMAIN

    async def generate_token(self, payload: dict) -> str:
        """Generate a JWT token using the provided payload."""
        if not self.CLIENT_ID or not self.CLIENT_SECRET or not self.DOMAIN:
            raise ValueError("JWT configuration is not loaded")

        return jwt.encode(
            payload, self.CLIENT_SECRET, algorithm=self.ALGORITHM[0]
        )

    def extract_token(self, request: Request) -> str:
        """Extracts the JWT from the header"""
        if "Authorization" not in request.headers:
            logger.error("Authorization header is missing")
            raise AuthError("Authorization header is missing", status_code=401)

        token = request.headers["Authorization"].split(" ")[1]
        if not token:
            logger.error("Token is missing")
            raise AuthError("Token is missing", status_code=401)

        return token

    async def validate_token(self, request: Request) -> dict:
        """Validate a JWT token and return the payload if valid."""
        token = self.extract_token(request)
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as e:
            logger.error(f"Invalid header: {e}")
            raise

        if unverified_header["alg"] not in self.ALGORITHM:
            logger.error(f"Invalid algorithm: {unverified_header['alg']}")
            raise AuthError("Invalid algorithm", status_code=401)

        return await self.decode_token(token)

    async def decode_token(self, token: str) -> dict:
        if self.DOMAIN is None:
            logger.error("JWT domain not configured")
            raise AuthError("JWT domain not configured", status_code=500)

        optional_custom_headers = {"User-agent": "custom-user-agent"}
        url = "https://" + self.DOMAIN + "/.well-known/jwks.json"
        jwks_client = PyJWKClient(url, headers=optional_custom_headers)
        rsa_key = jwks_client.get_signing_key_from_jwt(token)

        if rsa_key:
            try:
                payload = jwt.decode(
                    jwt=token,
                    key=rsa_key,
                    algorithms=self.ALGORITHM[0],
                    audience=self.CLIENT_ID,
                    issuer="https://" + self.DOMAIN + "/",
                )
            except jwt.ExpiredSignatureError:
                logger.error("Token has expired")
                raise
            except jwt.MissingRequiredClaimError:
                logger.error("Invalid claims")
                raise
            except Exception:
                logger.error("Invalid token")
                raise

            return payload

        logger.error("No RSA key found")
        raise AuthError("no_rsa_key", status_code=401)
