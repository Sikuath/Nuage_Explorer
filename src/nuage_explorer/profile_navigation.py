"""Méthodes de MainWindow regroupées par fonctionnalité."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView

class ProfileNavigationMixin:
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
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return

        self.vault_data = new_data
        self.profile = new_profile
        self.url_stack = [self.profile["url"]]
        self.rebuild_tree()
        self.account_label.setText(f"●  Connecté à Nextcloud\n{self.profile['username']}")
        self.home_button.setChecked(True)
        self.refresh()
        self.start_edition_cleanup()
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
        """Reconstruit la racine de l'arborescence Nextcloud."""
        self.tree.clear()
        self.tree_root = None

        if not self.profile:
            return

        root = QTreeWidgetItem(["☁  Mon Nextcloud"])
        root.setData(0, Qt.ItemDataRole.UserRole, self.profile["url"])
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
            self.status_label.setText("Impossible de charger les sous-dossiers.")
            QMessageBox.warning(self, "Erreur WebDAV", str(exc))
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

            name = entry.get("name") or (parsed.path.rstrip("/").split("/")[-1])

            child = QTreeWidgetItem([f"📁  {name}"])
            child.setData(0, Qt.ItemDataRole.UserRole, child_url)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, False)

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
            current_url = current_item.data(0, Qt.ItemDataRole.UserRole)
            if current_url:
                stack.append(current_url.rstrip("/") + "/")
            current_item = current_item.parent()

        self.url_stack = list(reversed(stack))
        self.home_button.setChecked(item == self.tree_root)
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
            f"✓  {shown} élément(s)   •   Connexion WebDAV réussie • © 2026 Sikuath — Code sous licence MIT"
        )
    def go_up(self):
        if len(self.url_stack) > 1:
            self.url_stack.pop()
            self.refresh()
