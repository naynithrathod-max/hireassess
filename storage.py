"""
Scorecard storage.

The app writes every finished scorecard as a JSON object through this module.
Two backends exist and the app never knows which one is active:

  local  - a directory inside the container. The default.
  azure  - Azure Blob Storage, used when AZURE_STORAGE_CONNECTION_STRING is set.

This is the cloud-storage layer of the project. Flipping one environment
variable moves every scorecard from the container's own disk to managed object
storage, which is the point worth making in the demo: the application code does
not change, only where the bytes live.
"""

import json
import os
from datetime import datetime, timezone

LOCAL_DIR = os.environ.get("SCORECARD_DIR", "/data/scorecards")
CONTAINER_NAME = os.environ.get("AZURE_CONTAINER", "scorecards")


def backend_name():
    if os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip():
        return "azure-blob"
    return "local-disk"


def _azure_client():
    from azure.storage.blob import BlobServiceClient

    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    service = BlobServiceClient.from_connection_string(conn)
    try:
        service.create_container(CONTAINER_NAME)
    except Exception:
        pass  # already exists
    return service


def save_scorecard(attempt_id, payload):
    """Persist one scorecard. Returns a human-readable location string."""
    payload = dict(payload)
    payload["stored_at"] = datetime.now(timezone.utc).isoformat()
    payload["storage_backend"] = backend_name()
    blob_name = f"scorecard-{attempt_id}.json"
    body = json.dumps(payload, indent=2)

    if backend_name() == "azure-blob":
        try:
            service = _azure_client()
            blob = service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            blob.upload_blob(body, overwrite=True)
            return f"azure-blob://{CONTAINER_NAME}/{blob_name}"
        except Exception as exc:
            # Never lose a scorecard because the cloud call failed.
            _save_local(blob_name, body)
            return f"local-disk://{blob_name} (azure failed: {exc})"

    _save_local(blob_name, body)
    return f"local-disk://{blob_name}"


def _save_local(blob_name, body):
    os.makedirs(LOCAL_DIR, exist_ok=True)
    with open(os.path.join(LOCAL_DIR, blob_name), "w") as handle:
        handle.write(body)


def list_scorecards(limit=50):
    """Used by the admin view to prove objects are really being written."""
    if backend_name() == "azure-blob":
        try:
            service = _azure_client()
            container = service.get_container_client(CONTAINER_NAME)
            return [b.name for b in container.list_blobs()][:limit]
        except Exception:
            pass
    if not os.path.isdir(LOCAL_DIR):
        return []
    return sorted(os.listdir(LOCAL_DIR))[:limit]
