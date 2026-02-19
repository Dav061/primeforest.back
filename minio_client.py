from minio import Minio
from django.conf import settings

def get_minio_client():
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

def upload_file(file_path, object_name):
    client = get_minio_client()
    client.fput_object(settings.MINIO_BUCKET_NAME, object_name, file_path)
    return f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{object_name}"