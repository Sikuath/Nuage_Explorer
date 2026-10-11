import xml.etree.ElementTree as ET

import httpx


DAV_NS = "{DAV:}"


class WebDAVError(Exception):
    """Erreur de connexion ou de protocole WebDAV."""


def list_directory(url: str, username: str, password: str) -> list[dict]:
    """Teste la connexion et retourne le contenu du dossier WebDAV."""
    url = url.strip()

    if not url.startswith("https://"):
        raise WebDAVError("L'adresse WebDAV doit utiliser HTTPS.")

    if not username.strip() or not password:
        raise WebDAVError("Identifiant ou mot de passe manquant.")

    body = """<?xml version="1.0" encoding="utf-8"?>
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:displayname/>
        <d:resourcetype/>
        <d:getcontentlength/>
        <d:getlastmodified/>
      </d:prop>
    </d:propfind>"""

    try:
        with httpx.Client(
            timeout=25.0,
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.request(
                "PROPFIND",
                url,
                auth=(username, password),
                headers={
                    "Depth": "1",
                    "Content-Type": "application/xml; charset=utf-8",
                },
                content=body.encode("utf-8"),
            )

    except httpx.TimeoutException as exc:
        raise WebDAVError("Délai de connexion dépassé.") from exc
    except httpx.RequestError as exc:
        raise WebDAVError(
            f"Impossible de joindre le serveur : {exc}"
        ) from exc

    if response.status_code == 401:
        raise WebDAVError(
            "Authentification refusée. Vérifie l'identifiant "
            "et le mot de passe d'application."
        )

    if response.status_code == 403:
        raise WebDAVError(
            "Accès interdit par le serveur (403)."
        )

    if response.status_code == 404:
        raise WebDAVError(
            "Chemin WebDAV introuvable (404). Vérifie l'adresse."
        )

    if response.status_code != 207:
        raise WebDAVError(
            f"Réponse WebDAV inattendue : HTTP {response.status_code}."
        )

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise WebDAVError(
            "La réponse du serveur n'est pas un XML WebDAV valide."
        ) from exc

    entries = []

    for item in root.findall(f"{DAV_NS}response"):
        href = item.findtext(f"{DAV_NS}href", default="")
        prop = item.find(
            f"{DAV_NS}propstat/{DAV_NS}prop"
        )

        if prop is None:
            continue

        display_name = prop.findtext(
            f"{DAV_NS}displayname", default=""
        )

        resource_type = prop.find(f"{DAV_NS}resourcetype")
        is_directory = (
            resource_type is not None
            and resource_type.find(f"{DAV_NS}collection") is not None
        )

        size_text = prop.findtext(
            f"{DAV_NS}getcontentlength", default=""
        )
        modified = prop.findtext(
            f"{DAV_NS}getlastmodified", default=""
        )

        try:
            size = int(size_text) if size_text else None
        except ValueError:
            size = None

        entries.append({
            "name": display_name or href.rstrip("/").split("/")[-1],
            "href": href,
            "is_directory": is_directory,
            "size": size,
            "modified": modified,
        })

    return entries
