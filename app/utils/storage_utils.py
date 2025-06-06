import io
import logging

from google.cloud import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StorageHandler:
    BUCKET_NAME = "a6_avatar_bucket"

    @staticmethod
    def upload_avatar(file: bytes, filename: str) -> str:
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(StorageHandler.BUCKET_NAME)
            blob = bucket.blob(filename)
            blob.upload_from_string(file, content_type="image/png")

            if not blob.exists():
                logger.error("Error uploading avatar")
                raise Exception("Avatar upload failed")
            return blob.public_url
        except Exception as e:
            logger.error(f"Error uploading avatar: {e}")
            raise

    @staticmethod
    def get_avatar(user_id: int) -> str:
        storage_client = storage.Client()
        bucket = storage_client.bucket(StorageHandler.BUCKET_NAME)
        blob = bucket.blob(f"{user_id}.png")
        if not blob.exists():
            logger.error(f"Avatar not found for user {user_id}")
            raise Exception("Avatar not found")

        file_obj = io.BytesIO()
        blob.download_to_file(file_obj)
        file_obj.seek(0)
        return file_obj

    def delete_avatar(user_id: int) -> None:
        storage_client = storage.Client()
        bucket = storage_client.bucket(StorageHandler.BUCKET_NAME)
        blob = bucket.blob(f"{user_id}.png")
        if blob.exists():
            blob.delete()
            logger.info(f"Avatar deleted for user {user_id}")
        else:
            logger.error(f"Avatar not found for user {user_id}")
            raise Exception("Avatar not found")
