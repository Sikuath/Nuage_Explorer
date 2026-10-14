
"""Récupération des informations de quota de NUAGE."""

import xml.etree.ElementTree as ET

import httpx


def get_storage_quota(
    url: str,
    username: str,
    password: str,
) -> dict | None:
    """Retourne le quota en octets, ou None si indisponible."""
    url = url.strip()

    if not url.startswith("https://"):
        return None

    if not username.strip() or not password:
        return None

    body = """<?xml version="1.0" encoding="utf-8"?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:quota-used-bytes/>
        <d:quota-available-bytes/>
      </d:prop>
    </d:propfind>
    """

    try:
        with httpx.Client(
            timeout=httpx.Timeout(8.0, connect=5.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.request(
                "PROPFIND",
                url,
                auth=(username, password),
                headers={
                    "Depth": "0",
                    "Content-Type": "application/xml; charset=utf-8",
                },
                content=body,
            )

        if response.status_code != 207:
            return None

        root = ET.fromstring(response.content)

        for propstat in root.iter("{DAV:}propstat"):
            status_element = propstat.find("{DAV:}status")

            # Ignore les propriétés que le serveur refuse.
            if (
                status_element is not None
                and " 200 " not in f" {status_element.text or ''} "
            ):
                continue

            prop = propstat.find("{DAV:}prop")
            if prop is None:
                continue

            used_element = prop.find("{DAV:}quota-used-bytes")
            available_element = prop.find(
                "{DAV:}quota-available-bytes"
            )

            if (
                used_element is None
                or available_element is None
                or not used_element.text
                or not available_element.text
            ):
                continue

            used = int(used_element.text)
            available = int(available_element.text)

            if used < 0 or available < 0:
                return None

            total = used + available

            if total <= 0:
                return None

            return {
                "used": used,
                "available": available,
                "total": total,
            }

    except (
        httpx.HTTPError,
        ET.ParseError,
        ValueError,
        TypeError,
    ):
        return None

    return None
