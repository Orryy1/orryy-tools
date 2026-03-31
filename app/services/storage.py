"""S3-compatible storage service for Cloudflare R2."""

import logging
import asyncio
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from app.config import settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        config=BotoConfig(
            signature_version="s3v4",
            region_name="auto",
        ),
    )


async def upload_file_to_r2(
    file_bytes: bytes,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a file to R2 and return the key.

    Args:
        file_bytes: Raw file bytes.
        key: The S3 object key (path in bucket).
        content_type: MIME type of the file.

    Returns:
        The object key.
    """

    def _upload():
        client = _get_s3_client()
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    result = await asyncio.to_thread(_upload)
    logger.info(f"Uploaded {key} to R2 ({len(file_bytes)} bytes)")
    return result


async def download_file_from_r2(key: str) -> bytes:
    """Download a file from R2.

    Args:
        key: The S3 object key.

    Returns:
        The file bytes.
    """

    def _download():
        client = _get_s3_client()
        response = client.get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
        )
        return response["Body"].read()

    data = await asyncio.to_thread(_download)
    logger.info(f"Downloaded {key} from R2 ({len(data)} bytes)")
    return data


async def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading a file from R2.

    Args:
        key: The S3 object key.
        expires_in: URL expiry time in seconds (default 1 hour).

    Returns:
        Presigned URL string.
    """

    def _presign():
        client = _get_s3_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.R2_BUCKET_NAME,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
        return url

    url = await asyncio.to_thread(_presign)
    return url


async def delete_file_from_r2(key: str) -> None:
    """Delete a file from R2.

    Args:
        key: The S3 object key.
    """

    def _delete():
        client = _get_s3_client()
        client.delete_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
        )

    await asyncio.to_thread(_delete)
    logger.info(f"Deleted {key} from R2")
