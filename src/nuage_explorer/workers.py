"""Workers Qt : transferts, prévisualisation et édition de documents."""
from .common import *

class DownloadWorker(QThread):
    progress = Signal(int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, url, username, password, destination, parent=None):
        super().__init__(parent)
        self.url = url
        self.username = username
        self.password = password
        self.destination = destination

    def run(self):
        try:
            result = download_file(
                self.url,
                self.username,
                self.password,
                self.destination,
                self.progress.emit,
            )
            self.succeeded.emit(str(result))
        except Exception as exc:
            self.failed.emit(str(exc))


class MultiDownloadWorker(QThread):
    progress = Signal(int)
    current_file = Signal(str)
    completed = Signal(object)

    def __init__(self, files, destination, username, password, parent=None):
        super().__init__(parent)
        self.files = files
        self.destination = Path(destination)
        self.username = username
        self.password = password

    def run(self):
        results = {"success": [], "failed": []}
        total = len(self.files)

        for index, item in enumerate(self.files):
            name = item["name"]
            self.current_file.emit(name)

            destination = self.destination / Path(name).name

            def report_progress(percent, index=index):
                overall = int((index * 100 + percent) / total)
                self.progress.emit(min(100, overall))

            try:
                result = download_file(
                    item["url"],
                    self.username,
                    self.password,
                    destination,
                    report_progress,
                )
                results["success"].append(str(result))

            except Exception as exc:
                results["failed"].append((name, str(exc)))

        self.progress.emit(100)
        self.completed.emit(results)


class UploadWorker(QThread):
    progress = Signal(int)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        source,
        destination_url,
        username,
        password,
        overwrite=False,
        parent=None,
    ):
        super().__init__(parent)
        self.source = source
        self.destination_url = destination_url
        self.username = username
        self.password = password
        self.overwrite = overwrite

    def run(self):
        try:
            result = upload_file(
                self.source,
                self.destination_url,
                self.username,
                self.password,
                self.progress.emit,
                overwrite=self.overwrite,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MultiUploadWorker(QThread):
    progress = Signal(int)
    current_file = Signal(str)
    completed = Signal(dict)

    def __init__(
        self,
        files,
        destination_url,
        username,
        password,
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.destination_url = destination_url
        self.username = username
        self.password = password

    def run(self):
        results = {
            "success": [],
            "failed": [],
        }

        total = len(self.files)

        for index, file in enumerate(self.files):
            name = file["name"]
            self.current_file.emit(name)

            def update_progress(percent, index=index):
                overall = int((index + percent / 100) / total * 100)
                self.progress.emit(overall)

            try:
                upload_file(
                    file["source"],
                    self.destination_url,
                    self.username,
                    self.password,
                    update_progress,
                    overwrite=file["overwrite"],
                )
                results["success"].append(name)

            except Exception as exc:
                results["failed"].append((name, str(exc)))

            self.progress.emit(int((index + 1) / total * 100))

        self.completed.emit(results)


class DeleteWorker(QThread):
    completed = Signal(dict)

    def __init__(
        self,
        items,
        username,
        password,
        parent=None,
    ):
        super().__init__(parent)
        self.items = items
        self.username = username
        self.password = password

    def run(self):
        results = {
            "success": [],
            "failed": [],
        }

        for item in self.items:
            name = item["name"]

            try:
                delete_file(
                    item["url"],
                    self.username,
                    self.password,
                )
                results["success"].append(name)

            except Exception as exc:
                results["failed"].append((name, str(exc)))

        self.completed.emit(results)


class PreviewWorker(QThread):
    """Récupère temporairement un fichier et prépare son aperçu."""

    progress = Signal(int, str)
    succeeded = Signal(str, str)
    failed = Signal(str)

    def __init__(self, item, profile, parent=None):
        super().__init__(parent)
        self.item = item
        self.profile = profile

    def run(self):
        temp_root = application_root() / "temp"

        try:
            temp_root.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix="nuage-preview-",
                    dir=temp_root,
                )
            )
        except OSError as exc:
            self.failed.emit(
                "Impossible de créer le dossier temporaire :\n"
                f"{temp_root}\n\n{exc}"
            )
            return

        try:
            suffix = Path(self.item["name"]).suffix.lower()
            source_path = temp_dir / f"source{suffix}"

            self.progress.emit(0, "Récupération temporaire du fichier…")

            download_file(
                self.item["url"],
                self.profile["username"],
                self.profile["password"],
                source_path,
                lambda percent: self.progress.emit(
                    percent, "Récupération temporaire du fichier…"
                ),
            )

            if suffix in IMAGE_EXTENSIONS or suffix == ".pdf":
                preview_path = source_path

            elif suffix in OFFICE_EXTENSIONS:
                soffice = find_libreoffice()

                if soffice is None:
                    raise RuntimeError(
                        "LibreOffice n'a pas été trouvé sur ce PC. "
                        "Il est nécessaire pour prévisualiser les documents "
                        "bureautiques."
                    )

                self.progress.emit(100, "Conversion temporaire en PDF…")

                profile_dir = temp_dir / "lo-profile"
                profile_dir.mkdir()

                command = [
                    str(soffice),
                    "--headless",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temp_dir),
                    str(source_path),
                ]

                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError(
                        "La conversion en PDF a dépassé 120 secondes."
                    ) from exc

                preview_path = temp_dir / "source.pdf"

                if result.returncode != 0 or not preview_path.is_file():
                    details = (result.stderr or result.stdout or "").strip()
                    if details:
                        details = "\n\n" + details[-1200:]

                    raise RuntimeError(
                        "LibreOffice n'a pas réussi à convertir ce document."
                        + details
                    )

            else:
                raise RuntimeError(
                    f"Le format {suffix or 'inconnu'} "
                    "ne peut pas être prévisualisé."
                )

            self.progress.emit(100, "Aperçu prêt.")
            self.succeeded.emit(str(preview_path), str(temp_dir))

        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.failed.emit(str(exc))


class NewOfficeDocumentWorker(QThread):
    progress = Signal(str)
    result_ready = Signal(bool, str)

    def __init__(
        self,
        document_type,
        filename,
        folder_url,
        username,
        password,
        parent=None,
    ):
        super().__init__(parent)
        self.document_type = document_type
        self.filename = filename
        self.folder_url = folder_url
        self.username = username
        self.password = password

    def run(self):
        temp_dir = None

        try:
            office = find_libreoffice()
            if not office:
                raise RuntimeError(
                    "LibreOffice est introuvable sur cet ordinateur."
                )

            editions_dir = Path(application_root()) / "editions"
            editions_dir.mkdir(parents=True, exist_ok=True)

            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix="nuage-nouveau-",
                    dir=str(editions_dir),
                )
            )

            local_path = temp_dir / self.filename

            self.progress.emit("Création du document…")

            if self.document_type == "writer":
                document = OpenDocumentText()
                document.text.addElement(P(text=""))
                document.save(str(local_path))

            elif self.document_type == "calc":
                document = OpenDocumentSpreadsheet()
                table = Table(name="Feuille1")
                document.spreadsheet.addElement(table)
                row = TableRow()
                table.addElement(row)
                row.addElement(TableCell())
                document.save(str(local_path))

            elif self.document_type == "impress":
                document = OpenDocumentPresentation()
                page = Page(
                    name="Diapo 1",
                    masterpagename="Default",
                )
                document.presentation.addElement(page)
                document.save(str(local_path))

            else:
                raise ValueError("Type de document inconnu.")

            # Profil dédié : évite de réutiliser une instance
            # LibreOffice déjà ouverte.
            profile_dir = temp_dir / "profil-libreoffice"
            profile_dir.mkdir()

            profile_url = profile_dir.resolve().as_uri()

            self.progress.emit(
                "LibreOffice est ouvert. Enregistre puis ferme "
                "le document pour l'envoyer sur Nextcloud."
            )

            process = subprocess.Popen(
                [
                    office,
                    f"-env:UserInstallation={profile_url}",
                    str(local_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.wait()

            if not local_path.exists():
                raise RuntimeError(
                    "Le fichier local est introuvable après fermeture."
                )

            self.progress.emit("Envoi du document sur Nextcloud…")

            # upload_file attend l'URL du DOSSIER de destination :
            # il y ajoute lui-même le nom du fichier.
            upload_file(
                str(local_path),
                self.folder_url,
                self.username,
                self.password,
                lambda *args: None,
                overwrite=False,
            )

            self.result_ready.emit(
                True,
                f"Document envoyé sur Nextcloud : {self.filename}",
            )

        except Exception as exc:
            self.result_ready.emit(
                False,
                f"Échec de la création ou de l'envoi : {exc}"
                + (
                    f"\n\nLe fichier local est conservé dans :\n{temp_dir}"
                    if temp_dir and temp_dir.exists()
                    else ""
                ),
            )


class OfficeEditWorker(QThread):
    """Ouvre un document dans LibreOffice puis synchronise les modifications."""

    progress = Signal(int, str)
    editor_started = Signal(str)
    sync_started = Signal(str)
    completed = Signal(dict)

    def __init__(self, item, profile, parent=None):
        super().__init__(parent)
        self.item = dict(item)
        self.profile = {
            "username": profile["username"],
            "password": profile["password"],
        }

    def run(self):
        name = self.item["name"]
        edition_dir = None
        local_path = None
        original_hash = None
        keep_copy = False

        result = {
            "ok": False,
            "name": name,
            "changed": False,
            "error": "",
        }

        try:
            soffice = find_libreoffice()

            if soffice is None:
                raise RuntimeError(
                    "LibreOffice est introuvable sur ce poste. "
                    "Vérifie qu'il est installé et accessible."
                )

            editions_root = application_root() / "editions"
            editions_root.mkdir(parents=True, exist_ok=True)

            edition_dir = Path(
                tempfile.mkdtemp(
                    prefix="nuage-edition-",
                    dir=editions_root,
                )
            )

            local_name = Path(name).name
            local_path = edition_dir / local_name

            self.progress.emit(0, f"Téléchargement de {name}…")

            download_file(
                self.item["url"],
                self.profile["username"],
                self.profile["password"],
                local_path,
                lambda percent: self.progress.emit(
                    percent, f"Téléchargement de {name}…"
                ),
            )

            original_hash = file_sha256(local_path)

            # Métadonnées permettant de comparer cette copie locale au serveur
            # lors du prochain démarrage, sans deviner son emplacement distant.
            metadata_path = edition_dir / "edition.json"
            metadata_path.write_text(
                json.dumps(
                    {"url": self.item["url"], "filename": local_name},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            # Profil séparé : évite de confier ce document à une session
            # LibreOffice déjà ouverte, dont le processus pourrait se terminer
            # avant la fermeture réelle du document.
            profile_dir = edition_dir / "lo-profile"
            profile_dir.mkdir()

            command = [
                str(soffice),
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--nologo",
                "--nodefault",
                "--norestore",
                "--nofirststartwizard",
                str(local_path),
            ]

            creationflags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if soffice.suffix.lower() == ".com"
                else 0
            )

            process = subprocess.Popen(
                command,
                cwd=str(edition_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )

            self.editor_started.emit(name)

            # Le thread attend pendant que l'utilisateur travaille.
            # L'interface Nextcloud Explorer reste réactive.
            process.wait()

            if not local_path.is_file():
                raise RuntimeError(
                    "Le fichier local n'existe plus après la fermeture "
                    "de LibreOffice."
                )

            current_hash = file_sha256(local_path)
            changed = current_hash != original_hash
            result["changed"] = changed

            if changed:
                self.sync_started.emit(name)
                self.progress.emit(
                    0,
                    f"Envoi des modifications de {name} vers NUAGE…",
                )

                remote = urlsplit(self.item["url"])
                parent_path = remote.path.rsplit("/", 1)[0] + "/"
                parent_url = remote._replace(
                    path=parent_path,
                    query="",
                    fragment="",
                ).geturl()

                upload_file(
                    local_path,
                    parent_url,
                    self.profile["username"],
                    self.profile["password"],
                    progress_callback=lambda percent: self.progress.emit(
                        percent,
                        f"Envoi des modifications de {name} vers NUAGE…",
                    ),
                    overwrite=True,
                )

            result["ok"] = True

        except Exception as exc:
            # En cas d'échec de synchronisation, ne jamais supprimer
            # une copie locale contenant des changements.
            changed = False

            if (
                local_path is not None
                and local_path.is_file()
                and original_hash is not None
            ):
                try:
                    changed = file_sha256(local_path) != original_hash
                except OSError:
                    changed = True

            result["changed"] = changed
            result["error"] = str(exc)

            if changed:
                keep_copy = True
                result["error"] += (
                    "\n\nLa copie modifiée a été conservée sur la clé USB :\n"
                    f"{local_path}\n\n"
                    "Ne la supprime pas avant d'avoir récupéré "
                    "tes modifications."
                )

        finally:
            if edition_dir is not None and not keep_copy:
                shutil.rmtree(edition_dir, ignore_errors=True)

            self.completed.emit(result)


class ResourceOperationWorker(QThread):
    """Exécute les copies, déplacements et renommages sans bloquer l'interface."""

    progress = Signal(int, str)
    completed = Signal(dict)

    def __init__(self, operations, username, password, parent=None):
        super().__init__(parent)
        self.operations = operations
        self.username = username
        self.password = password

    def run(self):
        results = {
            "success": [],
            "failed": [],
        }

        total = len(self.operations)

        for index, operation in enumerate(self.operations):
            name = operation["name"]
            self.progress.emit(
                int(index * 100 / total),
                name,
            )

            try:
                if operation["operation"] == "rename":
                    rename_resource(
                        operation["url"],
                        operation["new_name"],
                        self.username,
                        self.password,
                        is_directory=operation["is_directory"],
                    )
                else:
                    transfer_function = (
                        copy_resource
                        if operation["operation"] == "copy"
                        else move_resource
                    )

                    transfer_function(
                        operation["url"],
                        operation["destination_url"],
                        self.username,
                        self.password,
                        overwrite=False,
                        is_directory=operation["is_directory"],
                    )

                results["success"].append(name)

            except Exception as exc:
                results["failed"].append((name, str(exc)))

            self.progress.emit(
                int((index + 1) * 100 / total),
                name,
            )

        self.completed.emit(results)


class EditionCleanupWorker(QThread):
    """Analyse les copies locales d'édition et ne supprime que les copies identiques au serveur."""

    completed = Signal(dict)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = {
            "username": profile["username"],
            "password": profile["password"],
        }

    def run(self):
        editions_root = Path(application_root()) / "editions"
        result = {
            "removed": 0,
            "kept": 0,
            "checked": 0,
            "missing_on_server": [],
            "modified": [],
            "untracked": [],
            "errors": [],
        }

        if not editions_root.is_dir():
            self.completed.emit(result)
            return

        # Signale aussi les fichiers directement placés dans editions :
        # sans edition.json, leur URL distante ne peut pas être déterminée.
        for path in editions_root.iterdir():
            if path.is_file() and not path.is_symlink():
                result["untracked"].append(str(path))

        for edition_dir in editions_root.iterdir():
            if not edition_dir.is_dir() or edition_dir.is_symlink():
                continue

            metadata_path = edition_dir / "edition.json"
            if not metadata_path.is_file():
                # Anciennes copies sans URL : conserver et signaler, jamais supprimer.
                local_files = [
                    p for p in edition_dir.iterdir()
                    if p.is_file() and p.name != "edition.json"
                ]
                if local_files:
                    result["untracked"].extend(str(p) for p in local_files)
                    result["kept"] += len(local_files)
                continue

            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                remote_url = metadata["url"]
                filename = metadata["filename"]
                local_path = edition_dir / filename
                if not local_path.is_file():
                    result["errors"].append(
                        f"{edition_dir}: le fichier local attendu « {filename} » est introuvable."
                    )
                    result["kept"] += 1
                    continue

                result["checked"] += 1

                remote = urlsplit(remote_url)
                parent_path = remote.path.rsplit("/", 1)[0] + "/"
                parent_url = remote._replace(
                    path=parent_path, query="", fragment=""
                ).geturl()

                remote_entries = list_directory(
                    parent_url,
                    self.profile["username"],
                    self.profile["password"],
                )
                remote_names = {
                    entry.get("name")
                    for entry in remote_entries
                    if entry.get("name")
                }
                if filename not in remote_names:
                    result["missing_on_server"].append(str(local_path))
                    result["kept"] += 1
                    continue

                with tempfile.TemporaryDirectory(prefix="nuage-edition-check-") as temp_dir:
                    remote_path = Path(temp_dir) / filename
                    download_file(
                        remote_url,
                        self.profile["username"],
                        self.profile["password"],
                        remote_path,
                        lambda *_: None,
                    )
                    if file_sha256(local_path) == file_sha256(remote_path):
                        shutil.rmtree(edition_dir)
                        result["removed"] += 1
                    else:
                        result["modified"].append(str(local_path))
                        result["kept"] += 1

            except Exception as exc:
                result["kept"] += 1
                result["errors"].append(f"{edition_dir}: {exc}")

        self.completed.emit(result)
