import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

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
)

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
    WebDAVError,
)


STYLE = """
* {
    font-family: "Segoe UI", sans-serif;
    font-size: 10pt;
}

QWidget {
    color: #263449;
}

QMainWindow, QWidget#central {
    background: #f3f6fb;
}

QFrame#sidebar {
    background: #e8eef7;
    border: none;
}

QLabel#appTitle {
    color: #17365d;
    font-size: 19pt;
    font-weight: 700;
}

QLabel#sectionTitle {
    color: #17365d;
    font-size: 12pt;
    font-weight: 600;
}

QLabel#muted {
    color: #718096;
}

QLabel#status {
    color: #526780;
    background: #e8eef7;
    padding: 8px 12px;
    border-radius: 7px;
}

QPushButton {
    background: #ffffff;
    border: 1px solid #d4deeb;
    border-radius: 8px;
    padding: 8px 12px;
}

QPushButton:hover {
    background: #e5efff;
    border-color: #9bbbe8;
}

QPushButton:pressed {
    background: #d7e7ff;
}

QPushButton#primary {
    color: white;
    background: #2563a6;
    border: 1px solid #2563a6;
    font-weight: 600;
}

QPushButton#primary:hover {
    background: #174f8c;
}

QPushButton#navButton {
    text-align: left;
    padding: 11px 12px;
    border: none;
    background: transparent;
    border-radius: 8px;
}

QPushButton#navButton:hover {
    background: #dce7f5;
}

QPushButton#navButton:checked {
    color: #164e88;
    background: #d2e5ff;
    font-weight: 600;
}

QLineEdit {
    background: white;
    border: 1px solid #cdd8e7;
    border-radius: 7px;
    padding: 9px;
    selection-background-color: #2563a6;
}

QLineEdit:focus {
    border: 1px solid #4c91d9;
}

QTableWidget {
    background: white;
    alternate-background-color: #f7f9fc;
    border: 1px solid #e0e7f0;
    border-radius: 10px;
    gridline-color: #edf1f6;
    selection-background-color: #dcecff;
    selection-color: #17365d;
    outline: none;
}

QTableWidget::item {
    padding: 7px;
    border: none;
}

QTableWidget::item:selected {
    background: #dcecff;
    color: #17365d;
}

QHeaderView::section {
    background: #f5f8fc;
    color: #60728a;
    font-weight: 600;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #e0e7f0;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 3px;
}

QScrollBar::handle:vertical {
    background: #c5d1e0;
    border-radius: 5px;
    min-height: 25px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QTreeWidget {
    background: transparent;
    border: none;
    outline: none;
    padding: 4px;
}

QTreeWidget::item {
    padding: 6px 2px;
    border-radius: 5px;
}

QTreeWidget::item:hover {
    background: #dce7f5;
}

QTreeWidget::item:selected {
    background: #d2e5ff;
    color: #164e88;
}
"""


def obtain_vault():
    path = get_vault_path()

    if path.exists():
        while True:
            password, ok = QInputDialog.getText(
                None,
                "Nuage Explorer",
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
                    "Mot de passe incorrect ou coffre endommagé.",
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
                None, "Mot de passe trop court",
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
                None, "Erreur",
                "Les deux mots de passe sont différents.",
            )
            continue

        try:
            data = create_vault(path, password)
            return path, password, data
        except VaultError as exc:
            QMessageBox.critical(None, "Erreur", str(exc))
            return None


class ProfileDialog(QDialog):
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compte NUAGE")
        self.setMinimumWidth(550)

        profile = profile or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Connexion à NUAGE")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        explanation = QLabel(
            "Configure ton accès WebDAV. Le mot de passe "
            "d'application sera conservé dans le coffre chiffré."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        form.setSpacing(12)

        self.url = QLineEdit(profile.get("url", ""))
        self.url.setPlaceholderText(
            "https://serveur/remote.php/dav/files/identifiant/"
        )

        self.username = QLineEdit(profile.get("username", ""))

        self.password = QLineEdit(profile.get("password", ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mot de passe d'application")

        form.addRow("Adresse WebDAV", self.url)
        form.addRow("Identifiant", self.username)
        form.addRow("Mot de passe", self.password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setText("Tester et enregistrer")
        buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setObjectName("primary")
        buttons.accepted.connect(self.test_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def test_and_accept(self):
        url = self.url.text().strip()
        username = self.username.text().strip()
        password = self.password.text()

        if not url or not username or not password:
            QMessageBox.warning(
                self, "Informations manquantes",
                "Renseigne les trois champs.",
            )
            return

        if not url.startswith("https://"):
            QMessageBox.warning(
                self, "Adresse incorrecte",
                "L'adresse doit commencer par https://",
            )
            return

        url = url.rstrip("/") + "/"

        try:
            entries = list_directory(url, username, password)
        except WebDAVError as exc:
            QMessageBox.warning(self, "Connexion impossible", str(exc))
            return

        self.profile = {
            "name": "NUAGE",
            "url": url,
            "username": username,
            "password": password,
        }

        QMessageBox.information(
            self, "Connexion réussie",
            f"Connexion WebDAV validée.\n"
            f"{len(entries)} éléments reçus.",
        )
        self.accept()


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

    def __init__(
        self, files, destination, username, password, parent=None
    ):
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
                overall = int(
                    (index + percent / 100) / total * 100
                )
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
                results["failed"].append(
                    (name, str(exc))
                )

            self.progress.emit(
                int((index + 1) / total * 100)
            )

        self.completed.emit(results)

class DeleteWorker(QThread):
    completed = Signal(dict)

    def __init__(
        self,
        files,
        username,
        password,
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.username = username
        self.password = password

    def run(self):
        results = {
            "success": [],
            "failed": [],
        }

        for file in self.files:
            name = file["name"]

            try:
                delete_file(
                    file["url"],
                    self.username,
                    self.password,
                )
                results["success"].append(name)

            except Exception as exc:
                results["failed"].append(
                    (name, str(exc))
                )

        self.completed.emit(results)

class MainWindow(QMainWindow):
    def __init__(self, vault_path, master_password, vault_data):
        super().__init__()

        self.vault_path = vault_path
        self.master_password = master_password
        self.vault_data = vault_data
        self.profile = self.get_profile()
        self.url_stack = []

        # Références conservées pendant le téléchargement
        self.download_worker = None
        self.download_dialog = None
        self.upload_worker = None
        self.upload_dialog = None
        self.multi_upload_worker = None
        self.multi_upload_dialog = None
        self.multi_download_worker = None
        self.multi_download_dialog = None
        self.delete_worker = None
        self.delete_dialog = None
        self.multi_download_skipped = 0

        self.setWindowTitle("Nuage Explorer")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barre latérale
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 22, 14, 16)
        side.setSpacing(9)

        brand = QLabel("☁  Nuage Explorer")
        brand.setObjectName("sectionTitle")
        side.addWidget(brand)
        side.addSpacing(20)

        nav_label = QLabel("ESPACE PERSONNEL")
        nav_label.setObjectName("muted")
        side.addWidget(nav_label)

        self.home_button = QPushButton("☁   Mon NUAGE")
        self.home_button.setObjectName("navButton")
        self.home_button.setCheckable(True)
        self.home_button.setChecked(True)
        self.home_button.clicked.connect(self.go_home)
        side.addWidget(self.home_button)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemExpanded.connect(self.load_tree_children)
        self.tree.itemClicked.connect(self.tree_item_clicked)
        side.addWidget(self.tree, 1)

        self.tree_root = None

        self.settings_button = QPushButton("⚙   Compte et connexion")
        self.settings_button.setObjectName("navButton")
        self.settings_button.clicked.connect(self.configure_profile)
        side.addWidget(self.settings_button)

        side.addStretch()

        self.account_label = QLabel("●  Non connecté")
        self.account_label.setObjectName("muted")
        self.account_label.setWordWrap(True)
        side.addWidget(self.account_label)

        root.addWidget(sidebar)

        # Zone principale
        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(26, 22, 26, 18)
        main.setSpacing(15)
        root.addWidget(content, 1)

        top = QHBoxLayout()
        heading_box = QVBoxLayout()

        heading = QLabel("Mes fichiers")
        heading.setObjectName("appTitle")
        heading_box.addWidget(heading)

        self.subtitle = QLabel("Tes documents, accessibles depuis NUAGE")
        self.subtitle.setObjectName("muted")
        heading_box.addWidget(self.subtitle)

        top.addLayout(heading_box)
        top.addStretch()

        self.upload_button = QPushButton("↑  Importer des fichiers")
        self.upload_button.setObjectName("primary")
        self.upload_button.clicked.connect(self.import_file)
        top.addWidget(self.upload_button)

        self.mkdir_button = QPushButton("+  Nouveau dossier")
        self.mkdir_button.clicked.connect(self.create_folder)
        top.addWidget(self.mkdir_button)

        self.refresh_button = QPushButton("↻  Actualiser")
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)

        main.addLayout(top)

        # Chemin courant et navigation
        path_bar = QHBoxLayout()
        path_bar.setSpacing(8)

        self.back_button = QPushButton("←")
        self.back_button.setToolTip("Dossier parent")
        self.back_button.setFixedWidth(42)
        self.back_button.clicked.connect(self.go_up)
        path_bar.addWidget(self.back_button)

        self.path_label = QLabel("Aucun compte configuré")
        self.path_label.setObjectName("muted")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_bar.addWidget(self.path_label, 1)

        main.addLayout(path_bar)

        # Tableau de fichiers
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Nom", "Taille", "Modifié le", "Type"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table.customContextMenuRequested.connect(
            self.show_context_menu
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        self.table.itemDoubleClicked.connect(self.open_item)
        main.addWidget(self.table, 1)

        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("status")
        main.addWidget(self.status_label)

        # Connexion initiale
        if self.profile:
            self.url_stack = [self.profile["url"]]
            self.rebuild_tree()
            self.account_label.setText(
                f"●  Connecté à NUAGE\n{self.profile['username']}"
            )
            self.refresh()
        else:
            self.path_label.setText(
                "Configure ton compte pour commencer"
            )
            self.status_label.setText(
                "Aucun compte configuré. Ouvre « Compte et connexion »."
            )

    def get_profile(self):
        profiles = self.vault_data.get("profiles", [])
        return profiles[0] if profiles else None

    def configure_profile(self):
        dialog = ProfileDialog(self.profile, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_profile = dialog.profile
        new_data = dict(self.vault_data)
        new_data["profiles"] = [new_profile]

        try:
            save_vault(
                self.vault_path,
                self.master_password,
                new_data,
            )
        except (VaultError, OSError) as exc:
            QMessageBox.critical(
                self, "Enregistrement impossible", str(exc)
            )
            return

        self.vault_data = new_data
        self.profile = new_profile
        self.url_stack = [self.profile["url"]]
        self.rebuild_tree()
        self.account_label.setText(
            f"●  Connecté à NUAGE\n{self.profile['username']}"
        )
        self.home_button.setChecked(True)
        self.refresh()

    def go_home(self):
        if not self.profile:
            self.configure_profile()
            return

        self.url_stack = [self.profile["url"]]
        self.home_button.setChecked(True)
        if self.tree_root is not None:
            self.tree.setCurrentItem(self.tree_root)
        self.refresh()


    def rebuild_tree(self):
        """Reconstruit la racine de l'arborescence NUAGE."""
        self.tree.clear()
        self.tree_root = None

        if not self.profile:
            return

        root = QTreeWidgetItem(["☁  Mon NUAGE"])
        root.setData(
            0, Qt.ItemDataRole.UserRole, self.profile["url"]
        )
        root.setData(0, Qt.ItemDataRole.UserRole + 1, False)

        self.tree.addTopLevelItem(root)
        self.tree_root = root
        root.setExpanded(True)

    def load_tree_children(self, item):
        """Charge les sous-dossiers à la première ouverture."""
        loaded = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if loaded:
            return

        url = item.data(0, Qt.ItemDataRole.UserRole)
        if not url or not self.profile:
            return

        item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        item.takeChildren()

        try:
            entries = list_directory(
                url,
                self.profile["username"],
                self.profile["password"],
            )
        except WebDAVError as exc:
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            item.addChild(QTreeWidgetItem(["Chargement…"]))
            self.status_label.setText(
                "Impossible de charger les sous-dossiers."
            )
            QMessageBox.warning(
                self, "Erreur WebDAV", str(exc)
            )
            return

        current = urlsplit(url)

        for entry in entries:
            href = entry.get("href", "")
            if not href or not entry.get("is_directory", False):
                continue

            child_url = urljoin(url, href)
            parsed = urlsplit(child_url)

            if parsed.netloc.lower() != current.netloc.lower():
                continue

            if parsed.path.rstrip("/") == current.path.rstrip("/"):
                continue

            name = entry.get("name") or (
                parsed.path.rstrip("/").split("/")[-1]
            )

            child = QTreeWidgetItem([f"📁  {name}"])
            child.setData(
                0, Qt.ItemDataRole.UserRole, child_url
            )
            child.setData(
                0, Qt.ItemDataRole.UserRole + 1, False
            )

            # Le faux enfant permet d'afficher le triangle
            # même avant le chargement des sous-dossiers.
            child.addChild(QTreeWidgetItem(["Chargement…"]))
            item.addChild(child)

    def tree_item_clicked(self, item, column):
        """Affiche dans le tableau le dossier choisi à gauche."""
        url = item.data(0, Qt.ItemDataRole.UserRole)

        if not url or item.text(0) == "Chargement…":
            return

        # Reconstruit le chemin de navigation depuis la racine.
        stack = []
        current_item = item

        while current_item is not None:
            current_url = current_item.data(
                0, Qt.ItemDataRole.UserRole
            )
            if current_url:
                stack.append(current_url.rstrip("/") + "/")
            current_item = current_item.parent()

        self.url_stack = list(reversed(stack))
        self.home_button.setChecked(
            item == self.tree_root
        )
        self.refresh()

    def refresh(self):
        if not self.profile or not self.url_stack:
            return

        current_url = self.url_stack[-1]
        self.table.setRowCount(0)
        self.path_label.setText(current_url)
        self.status_label.setText("Connexion en cours…")

        try:
            entries = list_directory(
                current_url,
                self.profile["username"],
                self.profile["password"],
            )
        except WebDAVError as exc:
            self.status_label.setText("La connexion a échoué.")
            QMessageBox.warning(self, "Erreur WebDAV", str(exc))
            return

        current = urlsplit(current_url)
        shown = 0

        for entry in entries:
            href = entry.get("href", "")
            if not href:
                continue

            item_url = urljoin(current_url, href)
            parsed = urlsplit(item_url)

            # Ne pas accepter un lien vers un autre serveur.
            if parsed.netloc.lower() != current.netloc.lower():
                continue

            # Masquer le dossier actuellement ouvert.
            if parsed.path.rstrip("/") == current.path.rstrip("/"):
                continue

            is_directory = entry.get("is_directory", False)
            name = entry.get("name") or parsed.path.rstrip("/").split("/")[-1]
            size = entry.get("size")
            modified = entry.get("modified") or "—"

            if is_directory:
                display_name = f"📁   {name}"
                size_text = "—"
                kind = "Dossier"
            else:
                display_name = f"📄   {name}"

                if size is None:
                    size_text = "—"
                elif size < 1024:
                    size_text = f"{size} o"
                elif size < 1024 * 1024:
                    size_text = f"{size / 1024:.1f} Ko"
                else:
                    size_text = f"{size / (1024 * 1024):.1f} Mo"

                kind = "Fichier"

            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(display_name)
            name_item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "url": item_url,
                    "is_directory": is_directory,
                    "name": name,
                },
            )

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(size_text))
            self.table.setItem(row, 2, QTableWidgetItem(modified))
            self.table.setItem(row, 3, QTableWidgetItem(kind))
            shown += 1

        self.back_button.setEnabled(len(self.url_stack) > 1)
        self.status_label.setText(
            f"✓  {shown} élément(s)   •   Connexion WebDAV réussie"
        )

    def open_item(self, item):
        data = self.table.item(item.row(), 0).data(
            Qt.ItemDataRole.UserRole
        )

        if not data:
            return

        if data["is_directory"]:
            self.url_stack.append(data["url"].rstrip("/") + "/")
            self.refresh()
            return

        # Éviter deux téléchargements simultanés.
        if (
            (self.download_worker is not None
             and self.download_worker.isRunning())
            or
            (self.multi_download_worker is not None
             and self.multi_download_worker.isRunning())
        ):
            QMessageBox.information(
                self,
                "Téléchargement en cours",
                "Attends la fin du téléchargement actuel.",
            )
            return

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Télécharger le fichier",
            data["name"],
            "Tous les fichiers (*)",
        )

        if not destination:
            return

        self.download_dialog = QProgressDialog(
            f"Téléchargement de {data['name']}…",
            None,
            0,
            100,
            self,
        )
        self.download_dialog.setWindowTitle("Téléchargement")
        self.download_dialog.setCancelButton(None)
        self.download_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.download_dialog.setMinimumDuration(300)
        self.download_dialog.setValue(0)
        self.download_dialog.show()

        self.download_worker = DownloadWorker(
            data["url"],
            self.profile["username"],
            self.profile["password"],
            destination,
            self,
        )

        self.download_worker.progress.connect(
            self.download_progress
        )
        self.download_worker.succeeded.connect(
            self.download_succeeded
        )
        self.download_worker.failed.connect(
            self.download_failed
        )
        self.download_worker.finished.connect(
            self.download_thread_finished
        )
        self.download_worker.start()
    
    def show_context_menu(self, position):
        item = self.table.itemAt(position)
        if item is None:
            return

        row = item.row()
        selected_rows = {
            index.row()
            for index in self.table.selectionModel().selectedRows()
        }

        if row not in selected_rows:
            self.table.clearSelection()
            self.table.selectRow(row)

        selected_rows = sorted({
            index.row()
            for index in self.table.selectionModel().selectedRows()
        })

        has_files = False

        for selected_row in selected_rows:
            name_item = self.table.item(selected_row, 0)
            data = name_item.data(Qt.ItemDataRole.UserRole)

            if data and not data["is_directory"]:
                has_files = True
                break

        menu = QMenu(self)

        download_action = menu.addAction("⬇  Télécharger")
        download_action.setEnabled(has_files)
        download_action.triggered.connect(
            self.download_selected
        )

        delete_action = menu.addAction("🗑  Supprimer")
        delete_action.setEnabled(has_files)
        delete_action.triggered.connect(
            self.delete_selected
        )

        menu.exec(
            self.table.viewport().mapToGlobal(position)
        )

    def delete_selected(self):
        if not self.profile or not self.url_stack:
            return

        if (
            self.delete_worker is not None
            and self.delete_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Suppression en cours",
                "Attends la fin de la suppression actuelle.",
            )
            return

        rows = sorted({
            index.row()
            for index in self.table.selectionModel().selectedRows()
        })

        files = []

        for row in rows:
            item = self.table.item(row, 0)
            if item is None:
                continue

            data = item.data(Qt.ItemDataRole.UserRole)

            if data and not data["is_directory"]:
                files.append({
                    "url": data["url"],
                    "name": data["name"],
                })

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier",
                "Sélectionne au moins un fichier à supprimer.",
            )
            return

        names = "\n".join(
            f"• {file['name']}" for file in files[:10]
        )
        if len(files) > 10:
            names += f"\n… et {len(files) - 10} autre(s) fichier(s)"

        answer = QMessageBox.warning(
            self,
            "Confirmer la suppression",
            f"Tu vas supprimer définitivement "
            f"{len(files)} fichier(s) de NUAGE :\n\n"
            f"{names}\n\n"
            "Cette opération peut être irréversible. "
            "Continuer ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.delete_dialog = QProgressDialog(
            "Suppression des fichiers…",
            None,
            0,
            len(files),
            self,
        )
        self.delete_dialog.setWindowTitle(
            "Suppression NUAGE"
        )
        self.delete_dialog.setCancelButton(None)
        self.delete_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.delete_dialog.setMinimumDuration(300)
        self.delete_dialog.setValue(0)
        self.delete_dialog.show()

        self.delete_worker = DeleteWorker(
            files,
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.delete_worker.completed.connect(
            self.delete_completed
        )
        self.delete_worker.finished.connect(
        self.delete_thread_finished
        )
        self.delete_worker.start()

    def delete_completed(self, results):
        if self.delete_dialog is not None:
            self.delete_dialog.close()
            self.delete_dialog = None

        successes = results["success"]
        failures = results["failed"]

        self.refresh()

        summary = (
            f"Suppressions réussies : {len(successes)}\n"
            f"Échecs : {len(failures)}"
        )

        if failures:
            details = "\n".join(
                f"• {name} : {message}"
                for name, message in failures
            )
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.status_label.setText(
            f"Suppression terminée : {len(successes)} supprimé(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self,
                "Bilan des suppressions",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bilan des suppressions",
                summary,
            )

    def delete_thread_finished(self):
        self.delete_worker = None

    def download_selected(self):
        if not self.profile or not self.url_stack:
            return

        if (
            (self.download_worker is not None
             and self.download_worker.isRunning())
            or
            (self.multi_download_worker is not None
             and self.multi_download_worker.isRunning())
        ):
            QMessageBox.information(
                self,
                "Téléchargement en cours",
                "Attends la fin du téléchargement actuel.",
            )
            return

        rows = sorted({
            index.row()
            for index in self.table.selectionModel().selectedRows()
        })

        files = []
        skipped_directories = 0

        for row in rows:
            item = self.table.item(row, 0)
            data = item.data(Qt.ItemDataRole.UserRole)

            if not data:
                continue

            if data["is_directory"]:
                skipped_directories += 1
                continue

            files.append({
                "url": data["url"],
                "name": data["name"],
            })

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier",
                "Sélectionne au moins un fichier à télécharger.",
            )
            return

        destination = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination",
        )
        if not destination:
            return

        # Vérifier les éventuels fichiers déjà présents.
        existing = [
            item for item in files
            if (Path(destination) / Path(item["name"]).name).exists()
        ]

        skipped_existing = 0

        if existing:
            answer = QMessageBox.question(
                self,
                "Fichiers déjà présents",
                f"{len(existing)} fichier(s) existent déjà dans "
                f"le dossier choisi.\n\n"
                "Oui : remplacer les fichiers existants.\n"
                "Non : conserver les fichiers existants et les ignorer.\n"
                "Annuler : abandonner le téléchargement.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Cancel:
                return

            if answer == QMessageBox.StandardButton.No:
                existing_names = {
                    item["name"] for item in existing
                }
                files = [
                    item for item in files
                    if item["name"] not in existing_names
                ]
                skipped_existing = len(existing)

        if not files:
            QMessageBox.information(
                self,
                "Aucun téléchargement",
                "Tous les fichiers sélectionnés existent déjà.",
            )
            return

        self.multi_download_skipped = (
            skipped_existing + skipped_directories
        )

        self.multi_download_dialog = QProgressDialog(
            "Préparation du téléchargement…",
            None,
            0,
            100,
            self,
        )
        self.multi_download_dialog.setWindowTitle(
            "Téléchargement multiple"
        )
        self.multi_download_dialog.setCancelButton(None)
        self.multi_download_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.multi_download_dialog.setMinimumDuration(300)
        self.multi_download_dialog.setValue(0)
        self.multi_download_dialog.show()

        self.multi_download_worker = MultiDownloadWorker(
            files,
            destination,
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_download_worker.progress.connect(
            self.multi_download_progress
        )
        self.multi_download_worker.current_file.connect(
            self.multi_download_current_file
        )
        self.multi_download_worker.completed.connect(
            self.multi_download_completed
        )
        self.multi_download_worker.finished.connect(
            self.multi_download_thread_finished
        )
        self.multi_download_worker.start()

        self.status_label.setText(
            f"Téléchargement de {len(files)} fichier(s)…"
        )

    def multi_download_progress(self, percent):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.setValue(percent)

    def multi_download_current_file(self, name):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.setLabelText(
                f"Téléchargement de {name}…"
            )

    def multi_download_completed(self, results):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.close()
            self.multi_download_dialog = None

        successes = results["success"]
        failures = results["failed"]
        skipped = self.multi_download_skipped

        summary = (
            f"Téléchargements réussis : {len(successes)}\n"
            f"Échecs : {len(failures)}\n"
            f"Éléments ignorés : {skipped}"
        )

        if failures:
            details = "\n".join(
                f"• {name} : {message}"
                for name, message in failures
            )
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.status_label.setText(
            f"Téléchargement terminé : {len(successes)} réussi(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self, "Bilan des téléchargements", summary
            )
        else:
            QMessageBox.information(
                self, "Bilan des téléchargements", summary
            )

    def multi_download_thread_finished(self):
        self.multi_download_worker = None

    def download_progress(self, percent):
        if self.download_dialog is not None:
            self.download_dialog.setValue(percent)

    def download_succeeded(self, destination):
        if self.download_dialog is not None:
            self.download_dialog.setValue(100)
            self.download_dialog.close()
            self.download_dialog = None

        self.status_label.setText("✓  Téléchargement terminé")

        QMessageBox.information(
            self,
            "Téléchargement terminé",
            f"Fichier enregistré ici :\n\n{destination}",
        )

    def download_failed(self, message):
        if self.download_dialog is not None:
            self.download_dialog.close()
            self.download_dialog = None

        self.status_label.setText("Le téléchargement a échoué.")

        QMessageBox.warning(
            self,
            "Erreur de téléchargement",
            message,
        )

    def download_thread_finished(self):
        self.download_worker = None

    def go_up(self):
        if len(self.url_stack) > 1:
            self.url_stack.pop()
            self.refresh()

    def create_folder(self):
        if not self.profile or not self.url_stack:
            QMessageBox.warning(
                self,
                "Compte non configuré",
                "Configure d'abord ton compte NUAGE.",
            )
            return

        name, ok = QInputDialog.getText(
            self,
            "Nouveau dossier",
            "Nom du dossier :",
        )

        if not ok:
            return

        name = name.strip()

        if not name:
            QMessageBox.warning(
                self,
                "Nom manquant",
                "Saisis un nom de dossier.",
            )
            return

        if (
            name in (".", "..")
            or "/" in name
            or "\\" in name
            or any(ord(char) < 32 for char in name)
        ):
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom ne doit pas contenir de barre oblique "
                "ni de caractère de contrôle.",
            )
            return

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue

            data = item.data(Qt.ItemDataRole.UserRole)

            if data and data["name"].casefold() == name.casefold():
                QMessageBox.warning(
                    self,
                    "Nom déjà utilisé",
                    "Un fichier ou un dossier porte déjà ce nom.",
                )
                return

        try:
            create_directory(
                self.url_stack[-1],
                name,
                self.profile["username"],
                self.profile["password"],
            )
        except WebDAVError as exc:
            QMessageBox.warning(
                self,
                "Création impossible",
                str(exc),
            )
            return

        self.refresh()
        self.status_label.setText(
            f"✓  Dossier « {name} » créé sur NUAGE."
        )

        QMessageBox.information(
            self,
            "Dossier créé",
            f"Le dossier « {name} » a bien été créé.",
        )

    def import_file(self):
        if not self.profile or not self.url_stack:
            QMessageBox.warning(
                self,
                "Compte non configuré",
                "Configure d'abord ton compte NUAGE.",
            )
            return

        if (
            self.upload_worker is not None
            and self.upload_worker.isRunning()
        ) or (
            self.multi_upload_worker is not None
            and self.multi_upload_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Import en cours",
                "Attends la fin de l'import actuel.",
            )
            return

        sources, _ = QFileDialog.getOpenFileNames(
            self,
            "Choisir les fichiers à importer",
            "",
            "Tous les fichiers (*)",
        )

        if not sources:
            return

        files = []
        existing_names = {
            self.table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )["name"].casefold()
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
            and self.table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )
            and not self.table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )["is_directory"]
        }

        overwrite_all = False
        skip_all = False

        for source in sources:
            filename = Path(source).name
            overwrite = False

            if filename.casefold() in existing_names:
                answer = QMessageBox.question(
                    self,
                    "Fichier déjà présent",
                    f"Le fichier « {filename} » existe déjà "
                    "dans ce dossier NUAGE.\n\n"
                    "Oui : remplacer ce fichier.\n"
                    "Non : ignorer ce fichier.\n"
                    "Annuler : abandonner tout l'import.",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.No,
                )

                if answer == QMessageBox.StandardButton.Cancel:
                    return

                if answer == QMessageBox.StandardButton.No:
                    continue

                overwrite = True

            files.append({
                "source": source,
                "name": filename,
                "overwrite": overwrite,
            })

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier à importer",
                "Aucun fichier n'a été retenu pour l'envoi.",
            )
            return

        self.multi_upload_dialog = QProgressDialog(
            "Préparation de l'envoi…",
            None,
            0,
            100,
            self,
        )
        self.multi_upload_dialog.setWindowTitle(
            "Import multiple vers NUAGE"
        )
        self.multi_upload_dialog.setCancelButton(None)
        self.multi_upload_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.multi_upload_dialog.setMinimumDuration(300)
        self.multi_upload_dialog.setValue(0)
        self.multi_upload_dialog.show()

        self.multi_upload_worker = MultiUploadWorker(
            files,
            self.url_stack[-1],
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_upload_worker.progress.connect(
            self.multi_upload_progress
        )
        self.multi_upload_worker.current_file.connect(
            self.multi_upload_current_file
        )
        self.multi_upload_worker.completed.connect(
            self.multi_upload_completed
        )
        self.multi_upload_worker.finished.connect(
            self.multi_upload_thread_finished
        )
        self.multi_upload_worker.start()

        self.status_label.setText(
            f"Envoi de {len(files)} fichier(s) vers NUAGE…"
        )


    def multi_upload_progress(self, percent):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setValue(percent)

    def multi_upload_current_file(self, name):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setLabelText(
                f"Envoi de {name} vers NUAGE…"
            )

    def multi_upload_completed(self, results):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setValue(100)
            self.multi_upload_dialog.close()
            self.multi_upload_dialog = None

        successes = results["success"]
        failures = results["failed"]

        summary = (
            f"Envois réussis : {len(successes)}\n"
            f"Échecs : {len(failures)}"
        )

        if failures:
            details = "\n".join(
                f"• {name} : {message}"
                for name, message in failures
            )
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.refresh()
        self.status_label.setText(
            f"Import terminé : {len(successes)} réussi(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self,
                "Bilan des imports",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bilan des imports",
                summary,
            )

    def multi_upload_thread_finished(self):
        self.multi_upload_worker = None

    def upload_progress(self, percent):
        if self.upload_dialog is not None:
            self.upload_dialog.setValue(percent)

    def upload_succeeded(self, destination_url):
        if self.upload_dialog is not None:
            self.upload_dialog.setValue(100)
            self.upload_dialog.close()
            self.upload_dialog = None

        self.status_label.setText("✓  Import terminé")
        self.refresh()

        QMessageBox.information(
            self,
            "Import terminé",
            "Le fichier a bien été envoyé vers NUAGE.",
        )

    def upload_failed(self, message):
        if self.upload_dialog is not None:
            self.upload_dialog.close()
            self.upload_dialog = None

        self.status_label.setText("L'import a échoué.")

        QMessageBox.warning(
            self,
            "Échec de l'import",
            message,
        )

    def upload_thread_finished(self):
        self.upload_worker = None


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setApplicationName("Nuage Explorer")

    result = obtain_vault()
    if result is None:
        return 0

    vault_path, master_password, vault_data = result
    window = MainWindow(vault_path, master_password, vault_data)
    window.show()

    if not window.profile:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, window.configure_profile)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
