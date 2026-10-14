import os
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

import httpx


class WebDAVError(Exception):
    """Erreur liée à l'accès WebDAV."""


def list_directory(
    url: str,
    username: str,
    password: str,
) -> list[dict]:
    """Liste les fichiers et dossiers d'un répertoire WebDAV."""
    url = url.strip()

    if not url.startswith("https://"):
        raise WebDAVError("L'accès WebDAV exige une adresse HTTPS.")

    if not username.strip() or not password:
        raise WebDAVError("Identifiant ou mot de passe manquant.")

    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.request(
                "PROPFIND",
                url,
                auth=(username, password),
                headers={"Depth": "1"},
            )

        if response.status_code == 401:
            raise WebDAVError("Authentification refusée (401).")
        if response.status_code == 403:
            raise WebDAVError("Accès interdit (403).")
        if response.status_code == 404:
            raise WebDAVError("Répertoire introuvable (404).")
        if response.status_code != 207:
            raise WebDAVError(
                f"Réponse WebDAV inattendue : HTTP {response.status_code}."
            )

        root = ET.fromstring(response.content)
        entries = []

        for item in root:
            href_element = item.find("{DAV:}href")
            if href_element is None or not href_element.text:
                continue

            href = href_element.text
            item_url = urljoin(str(response.url), href)

            propstat = item.find("{DAV:}propstat")
            if propstat is None:
                continue

            prop = propstat.find("{DAV:}prop")
            if prop is None:
                continue

            resource_type = prop.find("{DAV:}resourcetype")
            is_directory = (
                resource_type is not None
                and resource_type.find("{DAV:}collection") is not None
            )

            name = unquote(href.rstrip("/").split("/")[-1])
            current_path = url.rstrip("/")

            # Le serveur renvoie aussi le répertoire lui-même :
            # on l'ignore pour ne garder que son contenu.
            if item_url.rstrip("/") == current_path:
                continue

            size_element = prop.find("{DAV:}getcontentlength")
            size = (
                int(size_element.text)
                if size_element is not None
                and size_element.text
                else 0
            )

            modified_element = prop.find("{DAV:}getlastmodified")
            modified = (
                modified_element.text
                if modified_element is not None
                else ""
            )

            entries.append(
                {
                    "name": name,
                    "href": href,
                    "is_directory": is_directory,
                    "size": size,
                    "modified": modified,                  
                }
            )

        return sorted(
            entries,
            key=lambda entry: (
                not entry["is_directory"],
                entry["name"].casefold(),
            ),
        )

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le délai de connexion à NUAGE est dépassé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(f"Erreur réseau : {exc}") from exc
    except ET.ParseError as exc:
        raise WebDAVError(
            "La réponse du serveur WebDAV est illisible."
        ) from exc
    except (ValueError, TypeError) as exc:
        raise WebDAVError(
            f"Impossible de lire la réponse WebDAV : {exc}"
        ) from exc


def download_file(
    url: str,
    username: str,
    password: str,
    destination: str | Path,
    progress_callback=None,
) -> Path:
    """Télécharge un fichier WebDAV vers un chemin local."""
    url = url.strip()
    destination = Path(destination)

    if not url.startswith("https://"):
        raise WebDAVError("Le téléchargement exige une adresse HTTPS.")

    if not username.strip() or not password:
        raise WebDAVError("Identifiant ou mot de passe manquant.")

    temporary_path = None

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(
            timeout=httpx.Timeout(60.0, connect=25.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            with client.stream(
                "GET",
                url,
                auth=(username, password),
            ) as response:
                if response.status_code == 401:
                    raise WebDAVError("Authentification refusée (401).")
                if response.status_code == 403:
                    raise WebDAVError("Accès interdit (403).")
                if response.status_code == 404:
                    raise WebDAVError("Fichier introuvable (404).")
                if response.status_code != 200:
                    raise WebDAVError(
                        f"Réponse inattendue : HTTP {response.status_code}."
                    )

                total = int(
                    response.headers.get("content-length", 0) or 0
                )
                downloaded = 0
                last_percent = -1

                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=f".{destination.name}.",
                    suffix=".part",
                    dir=destination.parent,
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)

                    for chunk in response.iter_bytes(
                        chunk_size=256 * 1024
                    ):
                        if not chunk:
                            continue

                        temporary.write(chunk)
                        downloaded += len(chunk)

                        if total > 0 and progress_callback:
                            percent = min(
                                100, downloaded * 100 // total
                            )
                            if percent != last_percent:
                                progress_callback(percent)
                                last_percent = percent

                # Le fichier final n'est remplacé qu'une fois
                # le téléchargement terminé.
                os.replace(temporary_path, destination)
                temporary_path = None

        if progress_callback:
            progress_callback(100)

        return destination

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le téléchargement a dépassé le délai autorisé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(f"Erreur réseau : {exc}") from exc
    except OSError as exc:
        raise WebDAVError(
            f"Erreur d'écriture sur le PC : {exc}"
        ) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

def upload_file(
    source: str | Path,
    destination_url: str,
    username: str,
    password: str,
    progress_callback=None,
    overwrite: bool = False,
) -> str:
    """Envoie un fichier local dans un dossier WebDAV."""
    from urllib.parse import quote, urljoin

    source = Path(source)
    destination_url = destination_url.strip()

    if not source.is_file():
        raise WebDAVError(
            f"Fichier local introuvable : {source}"
        )

    if not destination_url.startswith("https://"):
        raise WebDAVError(
            "L'envoi exige une adresse HTTPS."
        )

    if not username.strip() or not password:
        raise WebDAVError(
            "Identifiant ou mot de passe manquant."
        )

    target_url = urljoin(
        destination_url.rstrip("/") + "/",
        quote(source.name, safe=""),
    )

    headers = {
        "Content-Length": str(source.stat().st_size),
        "Content-Type": "application/octet-stream",
    }

    # Empêche d'écraser un fichier existant sans confirmation.
    if not overwrite:
        headers["If-None-Match"] = "*"

    total = source.stat().st_size
    uploaded = 0
    last_percent = -1

    def file_chunks():
        nonlocal uploaded, last_percent

        with source.open("rb") as file:
            while True:
                chunk = file.read(256 * 1024)
                if not chunk:
                    break

                uploaded += len(chunk)

                if progress_callback and total > 0:
                    percent = min(100, uploaded * 100 // total)
                    if percent != last_percent:
                        progress_callback(percent)
                        last_percent = percent

                yield chunk

    try:
        with httpx.Client(
            timeout=httpx.Timeout(60.0, connect=25.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.put(
                target_url,
                auth=(username, password),
                headers=headers,
                content=file_chunks(),
            )

        if response.status_code == 401:
            raise WebDAVError("Authentification refusée (401).")
        if response.status_code == 403:
            raise WebDAVError("Envoi interdit (403).")
        if response.status_code == 404:
            raise WebDAVError("Dossier de destination introuvable (404).")
        if response.status_code == 412:
            raise WebDAVError(
                "Un fichier de ce nom existe déjà. "
                "Confirme son remplacement avant de recommencer."
            )
        if response.status_code == 507:
            raise WebDAVError(
                "Espace de stockage NUAGE insuffisant (507)."
            )
        if response.status_code not in (200, 201, 204):
            raise WebDAVError(
                f"Échec de l'envoi : HTTP {response.status_code}."
            )

        if progress_callback:
            progress_callback(100)

        return target_url

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le délai d'envoi est dépassé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(
            f"Erreur réseau pendant l'envoi : {exc}"
        ) from exc
    except OSError as exc:
        raise WebDAVError(
            f"Impossible de lire le fichier local : {exc}"
        ) from exc

def delete_file(
    url: str,
    username: str,
    password: str,
) -> str:
    """Supprime un fichier distant via WebDAV."""
    url = url.strip()

    if not url.startswith("https://"):
        raise WebDAVError(
            "La suppression exige une adresse HTTPS."
        )

    if not username.strip() or not password:
        raise WebDAVError(
            "Identifiant ou mot de passe manquant."
        )

    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.delete(
                url,
                auth=(username, password),
            )

        if response.status_code == 401:
            raise WebDAVError("Authentification refusée (401).")
        if response.status_code == 403:
            raise WebDAVError("Suppression interdite (403).")
        if response.status_code == 404:
            raise WebDAVError("Fichier introuvable (404).")
        if response.status_code == 423:
            raise WebDAVError("Le fichier est verrouillé (423).")
        if response.status_code not in (200, 202, 204):
            raise WebDAVError(
                f"Échec de la suppression : "
                f"HTTP {response.status_code}."
            )

        return url

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le délai de suppression est dépassé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(
            f"Erreur réseau pendant la suppression : {exc}"
        ) from exc

def create_directory(
    parent_url: str,
    name: str,
    username: str,
    password: str,
) -> str:
    """Crée un nouveau dossier dans un répertoire WebDAV."""
    from urllib.parse import quote, urljoin

    parent_url = parent_url.strip()
    name = name.strip()

    if not parent_url.startswith("https://"):
        raise WebDAVError(
            "La création exige une adresse HTTPS."
        )

    if not username.strip() or not password:
        raise WebDAVError(
            "Identifiant ou mot de passe manquant."
        )

    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or any(ord(char) < 32 for char in name)
    ):
        raise WebDAVError(
            "Nom de dossier invalide. "
            "Choisis un nom sans barre oblique."
        )

    target_url = urljoin(
        parent_url.rstrip("/") + "/",
        quote(name, safe=""),
    )

    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.request(
                "MKCOL",
                target_url,
                auth=(username, password),
            )

        if response.status_code == 201:
            return target_url

        if response.status_code == 401:
            raise WebDAVError(
                "Authentification refusée (401)."
            )
        if response.status_code == 403:
            raise WebDAVError(
                "Création de dossier interdite (403)."
            )
        if response.status_code == 405:
            raise WebDAVError(
                "Un fichier ou un dossier porte déjà ce nom."
            )
        if response.status_code == 409:
            raise WebDAVError(
                "Le dossier parent n'existe pas ou ne permet "
                "pas cette création (409)."
            )
        if response.status_code == 507:
            raise WebDAVError(
                "Espace de stockage NUAGE insuffisant (507)."
            )

        raise WebDAVError(
            f"Échec de création : HTTP {response.status_code}."
        )

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le délai de création du dossier est dépassé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(
            f"Erreur réseau pendant la création : {exc}"
        ) from exc

def _transfer_resource(
    method: str,
    source_url: str,
    destination_url: str,
    username: str,
    password: str,
    overwrite: bool = False,
    is_directory: bool = False,
) -> str:
    """Copie ou déplace une ressource directement sur le serveur WebDAV."""

    source_url = source_url.strip()
    destination_url = destination_url.strip()

    if not source_url.startswith("https://"):
        raise WebDAVError("La source doit utiliser HTTPS.")

    if not destination_url.startswith("https://"):
        raise WebDAVError("La destination doit utiliser HTTPS.")

    if not username.strip() or not password:
        raise WebDAVError("Identifiant ou mot de passe manquant.")

    source = urlsplit(source_url)
    destination = urlsplit(destination_url)

    if source.netloc.lower() != destination.netloc.lower():
        raise WebDAVError(
            "La source et la destination doivent appartenir "
            "au même serveur."
        )

    if source_url.rstrip("/") == destination_url.rstrip("/"):
        raise WebDAVError(
            "La source et la destination sont identiques."
        )

    headers = {
        "Destination": destination_url,
        "Overwrite": "T" if overwrite else "F",
    }

    # Une collection doit être copiée avec son contenu.
    if method == "COPY" and is_directory:
        headers["Depth"] = "infinity"

    try:
        with httpx.Client(
            timeout=httpx.Timeout(60.0, connect=25.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.request(
                method,
                source_url,
                auth=(username, password),
                headers=headers,
            )

        if response.status_code == 401:
            raise WebDAVError("Authentification refusée (401).")

        if response.status_code == 403:
            raise WebDAVError(
                "Opération interdite par le serveur (403)."
            )

        if response.status_code == 404:
            raise WebDAVError(
                "La source ou la destination est introuvable (404)."
            )

        if response.status_code == 405:
            raise WebDAVError(
                "Cette opération n'est pas autorisée sur cette ressource (405)."
            )

        if response.status_code == 409:
            raise WebDAVError(
                "Destination invalide : le dossier parent n'existe pas "
                "ou l'opération est incompatible avec l'arborescence (409)."
            )

        if response.status_code == 412:
            raise WebDAVError(
                "Un élément portant déjà ce nom existe dans la destination."
            )

        if response.status_code == 423:
            raise WebDAVError("La ressource est verrouillée (423).")

        if response.status_code == 507:
            raise WebDAVError(
                "Espace de stockage NUAGE insuffisant (507)."
            )

        if response.status_code not in (200, 201, 202, 204):
            raise WebDAVError(
                f"Échec de l'opération WebDAV : "
                f"HTTP {response.status_code}."
            )

        return destination_url

    except WebDAVError:
        raise
    except httpx.TimeoutException as exc:
        raise WebDAVError(
            "Le délai de l'opération WebDAV est dépassé."
        ) from exc
    except httpx.RequestError as exc:
        raise WebDAVError(
            f"Erreur réseau pendant l'opération WebDAV : {exc}"
        ) from exc


def copy_resource(
    source_url: str,
    destination_url: str,
    username: str,
    password: str,
    overwrite: bool = False,
    is_directory: bool = False,
) -> str:
    """Copie un fichier ou un dossier sur NUAGE."""
    return _transfer_resource(
        "COPY",
        source_url,
        destination_url,
        username,
        password,
        overwrite=overwrite,
        is_directory=is_directory,
    )


def move_resource(
    source_url: str,
    destination_url: str,
    username: str,
    password: str,
    overwrite: bool = False,
    is_directory: bool = False,
) -> str:
    """Déplace un fichier ou un dossier sur NUAGE."""
    return _transfer_resource(
        "MOVE",
        source_url,
        destination_url,
        username,
        password,
        overwrite=overwrite,
        is_directory=is_directory,
    )


def rename_resource(
    source_url: str,
    new_name: str,
    username: str,
    password: str,
    is_directory: bool = False,
) -> str:
    """Renomme un fichier ou un dossier sans le télécharger."""

    new_name = new_name.strip()

    if (
        not new_name
        or new_name in (".", "..")
        or "/" in new_name
        or "\\" in new_name
        or any(ord(char) < 32 for char in new_name)
    ):
        raise WebDAVError("Nom de fichier ou de dossier invalide.")

    source = urlsplit(source_url)
    source_path = source.path.rstrip("/")

    if not source_path or "/" not in source_path:
        raise WebDAVError("Impossible de déterminer le dossier parent.")

    parent_path = source_path.rsplit("/", 1)[0] + "/"
    destination_path = parent_path + quote(new_name, safe="")

    if is_directory:
        destination_path += "/"

    destination_url = source._replace(
        path=destination_path,
        query="",
        fragment="",
    ).geturl()

    return move_resource(
        source_url,
        destination_url,
        username,
        password,
        overwrite=False,
        is_directory=is_directory,
    )