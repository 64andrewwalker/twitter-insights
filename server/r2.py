"""Cloudflare R2 archival client for database backups."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_r2_client():
    """Get boto3 S3 client configured for R2. Returns None if not configured."""
    try:
        import boto3
    except ImportError:
        logger.warning("boto3 not installed, R2 archival disabled")
        return None

    endpoint = os.environ.get("R2_ENDPOINT")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all([endpoint, access_key, secret_key]):
        logger.warning("R2 credentials not configured, archival disabled")
        return None

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def archive_db(db_path: Path) -> str | None:
    """Upload DB to R2 as a timestamped backup. Returns version string or None."""
    client = _get_r2_client()
    if not client:
        return None

    bucket = os.environ.get("R2_BUCKET", "ti-db")
    version = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    key = f"backups/{version}.db"

    try:
        client.upload_file(str(db_path), bucket, key)
        logger.info("Archived to R2: %s", key)
        _prune_old_backups(client, bucket)
        return version
    except Exception as e:
        logger.warning("R2 archive failed (non-blocking): %s", e)
        return None


def list_versions(limit: int = 10) -> list[dict]:
    """List available R2 backup versions."""
    client = _get_r2_client()
    if not client:
        return []

    bucket = os.environ.get("R2_BUCKET", "ti-db")

    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        objects = response.get("Contents", [])
        objects.sort(key=lambda o: o["LastModified"], reverse=True)

        versions = []
        for obj in objects[:limit]:
            name = obj["Key"].replace("backups/", "").replace(".db", "")
            versions.append(
                {
                    "version": name,
                    "size_bytes": obj["Size"],
                    "created_at": obj["LastModified"].isoformat(),
                }
            )
        return versions
    except Exception as e:
        logger.warning("Failed to list R2 versions: %s", e)
        return []


def download_version(version: str, dest_path: Path) -> bool:
    """Download a specific backup version from R2."""
    client = _get_r2_client()
    if not client:
        return False

    bucket = os.environ.get("R2_BUCKET", "ti-db")
    key = f"backups/{version}.db"

    try:
        client.download_file(bucket, key, str(dest_path))
        return True
    except Exception as e:
        logger.warning("Failed to download R2 version %s: %s", version, e)
        return False


def _prune_old_backups(client, bucket: str, keep: int = 30) -> None:
    """Keep only the latest N backups."""
    try:
        response = client.list_objects_v2(Bucket=bucket, Prefix="backups/")
        objects = response.get("Contents", [])
        if len(objects) <= keep:
            return

        objects.sort(key=lambda o: o["LastModified"], reverse=True)
        to_delete = objects[keep:]

        for obj in to_delete:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            logger.info("Pruned old backup: %s", obj["Key"])
    except Exception as e:
        logger.warning("Backup pruning failed (non-blocking): %s", e)
