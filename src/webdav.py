import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urljoin
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