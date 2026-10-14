import sys
import hashlib
import os
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
import shutil
import subprocess
import tempfile
import json
from odf.opendocument import (
    OpenDocumentText,
    OpenDocumentSpreadsheet,
    OpenDocumentPresentation,
)
from odf.text import P
from odf.table import Table, TableRow, TableCell
from odf.draw import Page
from PySide6.QtCore import QDir, QMimeData, QUrl
from PySide6.QtGui import QPixmap ,QDrag
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMenu,
    QProgressDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QScrollArea,
    QFileSystemModel,
    QTreeView,
)
try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    PDF_PREVIEW_AVAILABLE = True
except ImportError:
    QPdfDocument = None
    QPdfView = None
    PDF_PREVIEW_AVAILABLE = False

from vault import (
    create_vault,
    get_vault_path,
    unlock_vault,
    save_vault,
    InvalidVaultError,
    VaultError,
)
from webdav import (
    list_directory,
    download_file,
    upload_file,
    delete_file,
    create_directory,
    copy_resource,
    move_resource,
    rename_resource,
    WebDAVError,
)


# Fonctions partagées : gardées ici pour éviter de modifier leur comportement
# pendant cette première étape de modularisation.

def application_root() -> Path:
    """Retourne le dossier du projet ou celui de l'exécutable portable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # common.py est dans src/nuage_explorer ; le projet est deux niveaux au-dessus de src.
    return Path(__file__).resolve().parents[2]


def obtain_vault():
    path = get_vault_path()

    if path.exists():
        while True:
            password, ok = QInputDialog.getText(
                None,
                "Nextcloud Explorer",
                "Mot de passe maître :",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None

            try:
                data = unlock_vault(path, password)
                return path, password, data
            except InvalidVaultError:
                QMessageBox.warning(
                    None,
                    "Coffre verrouillé",
                    "Mot de passe incorrect.",
                )
            except VaultError as exc:
                QMessageBox.critical(None, "Erreur", str(exc))
                return None

    while True:
        password, ok = QInputDialog.getText(
            None,
            "Créer le coffre",
            "Choisis un mot de passe maître (12 caractères minimum) :",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None

        if len(password) < 12:
            QMessageBox.warning(
                None,
                "Mot de passe trop court",
                "Choisis au moins 12 caractères.",
            )
            continue

        confirmation, ok = QInputDialog.getText(
            None,
            "Confirmer le coffre",
            "Confirme le mot de passe maître :",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None

        if password != confirmation:
            QMessageBox.warning(
                None,
                "Erreur",
                "Les deux mots de passe sont différents.",
            )
            continue

        try:
            data = create_vault(path, password)
            return path, password, data
        except VaultError as exc:
            QMessageBox.critical(None, "Erreur", str(exc))
            return None



# Extensions utilisées par l’aperçu et les opérations sur les documents.
IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
    ".webp", ".tif", ".tiff", ".svg",
}

OFFICE_EXTENSIONS = {
    ".odt", ".ods", ".odp", ".odg",
    ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".rtf", ".csv",
    ".fodt", ".fods", ".fodp",
}

def find_libreoffice():
    """Recherche le lanceur de LibreOffice sous Windows."""
    executable = (
        shutil.which("soffice.com")
        or shutil.which("soffice.exe")
        or shutil.which("soffice")
    )

    if executable:
        path = Path(executable)
        console_launcher = path.with_name("soffice.com")

        if console_launcher.is_file():
            return console_launcher

        return path

    candidates = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.com"),
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.com"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend([
            Path(local_app_data)
            / "Programs"
            / "LibreOffice"
            / "program"
            / "soffice.com",
            Path(local_app_data)
            / "Programs"
            / "LibreOffice"
            / "program"
            / "soffice.exe",
        ])

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def file_sha256(path):
    """Calcule l'empreinte d'un fichier pour détecter les modifications."""
    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def clear_preview_temp():
    """Vide le dossier temporaire de Nextcloud Explorer au démarrage."""
    temp_root = application_root() / "temp"

    try:
        temp_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return [f"Impossible d'accéder à {temp_root} : {exc}"]

    errors = []

    for item in temp_root.iterdir():
        try:
            if item.is_symlink() or not item.is_dir():
                item.unlink()
            else:
                shutil.rmtree(item)
        except OSError as exc:
            errors.append(f"{item.name} : {exc}")

    return errors
