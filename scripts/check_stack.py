#!/usr/bin/env python3
"""Check that the local PlantGuard stack and its ksqlDB objects are ready."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from uuid import uuid4

TIMEOUT_SECONDS = 90
EXPECTED_STREAMS = {
    "PLANT_OBSERVATIONS",
    "ENVIRONMENT_READINGS",
    "PLANT_OBSERVATIONS_BY_PLANT",
    "ENVIRONMENT_READINGS_BY_PLANT",
    "OBSERVATION_CONTEXT",
    "ENVIRONMENT_ALERTS",
}
EXPECTED_TABLES = {
    "LATEST_ENVIRONMENT",
    "ENVIRONMENT_SIX_HOUR_SUMMARY",
}
SMOKE_PHOTO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    expected_status: int = 200,
) -> bytes:
    with urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers or {}, method=method), timeout=5
    ) as response:
        if response.status != expected_status:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read()


def wait_for(name: str, check: Callable[[], None]) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            check()
            print(f"[ok] {name}")
            return
        except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(2)
    raise RuntimeError(f"{name} is not ready: {last_error}")


def check_api() -> None:
    payload = json.loads(request("http://localhost:8000/health"))
    if payload.get("status") != "ok":
        raise RuntimeError(f"unexpected API health response: {payload}")


def check_web() -> None:
    page = request("http://localhost:5173/").decode()
    if "<title>PlantGuard</title>" not in page:
        raise RuntimeError("web page does not contain the PlantGuard title")


def check_photo_storage() -> None:
    boundary = f"plantguard-smoke-{uuid4().hex}"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="photo"; filename="smoke.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + SMOKE_PHOTO
        + f"\r\n--{boundary}--\r\n".encode()
    )
    upload = json.loads(
        request(
            "http://localhost:8000/api/v1/photos",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            expected_status=201,
        )
    )

    if request(upload["read_url"]) != SMOKE_PHOTO:
        raise RuntimeError("downloaded photo differs from the uploaded file")
    request(upload["delete_url"], method="DELETE", expected_status=204)
    try:
        request(upload["read_url"])
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise
    raise RuntimeError("deleted photo is still available")


def ksql(command: str) -> list[dict[str, object]]:
    payload = json.dumps({"ksql": command, "streamsProperties": {}}).encode()
    result = json.loads(
        request(
            "http://localhost:8088/ksql",
            data=payload,
            headers={"Content-Type": "application/vnd.ksql.v1+json"},
        )
    )
    if not isinstance(result, list):
        raise RuntimeError(f"unexpected ksqlDB response: {result}")
    return result


def ksql_object_names(command: str, field: str) -> set[str]:
    response = ksql(command)
    objects = response[0].get(field) if response else None
    if not isinstance(objects, list):
        raise RuntimeError(f"unexpected response to {command}: {response}")

    names = {
        item.get("name")
        for item in objects
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if len(names) != len(objects):
        raise RuntimeError(f"invalid {field} list in response to {command}")
    return names


def check_ksqldb() -> None:
    info = json.loads(request("http://localhost:8088/info"))
    status = info.get("KsqlServerInfo", {}).get("serverStatus")
    if status != "RUNNING":
        raise RuntimeError(f"unexpected ksqlDB status: {status}")

    streams = ksql_object_names("SHOW STREAMS;", "streams")
    tables = ksql_object_names("SHOW TABLES;", "tables")
    missing = (EXPECTED_STREAMS - streams) | (EXPECTED_TABLES - tables)
    if missing:
        raise RuntimeError(f"missing ksqlDB objects: {', '.join(sorted(missing))}")


def main() -> None:
    wait_for("API", check_api)
    wait_for("web application", check_web)
    wait_for("photo storage", check_photo_storage)
    wait_for("ksqlDB queries", check_ksqldb)
    print("PlantGuard stack is ready.")


if __name__ == "__main__":
    main()
