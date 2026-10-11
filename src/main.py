
import sys
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
    QProgressDialog,
)

from vault import (
    create_vault,
    get_vault_path,
    unlock_vault,
    save_vault,
    InvalidVaultError,
    VaultError,
)
from webdav import list_directory, download_file, WebDAVError


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
        sidebar.setFixedWidth(215)

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
            QAbstractItemView.SelectionMode.SingleSelection
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
            self.download_worker is not None
            and self.download_worker.isRunning()
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
