
"""Carnet d'adresses partagé sur NUAGE, au format vCard 3.0."""

import os
import re
import tempfile
import uuid
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QMessageBox, QDialogButtonBox, QComboBox,
)

from .common import (
    list_directory,
    download_file,
    upload_file,
    WebDAVError,
)
CONTACT_GROUPS = [
    "Physique-chimie",
    "Administration",
    "Club astro",
    "FSU",
    "Autres",
]

DEFAULT_CONTACT_GROUP = "Autres"

def _escape_vcard(value):
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _unescape_vcard(value):
    value = value.replace("\\n", "\n").replace("\\N", "\n")
    value = value.replace("\\,", ",").replace("\\;", ";")
    return value.replace("\\\\", "\\")


def _parse_vcard(content):
    """Lit les champs utiles d'un fichier vCard 3.0."""
    # Les lignes vCard peuvent être repliées sur la ligne suivante.
    lines = []
    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)

    contacts = []
    current = None

    for line in lines:
        if line.upper() == "BEGIN:VCARD":
            current = {}
            continue
        if line.upper() == "END:VCARD":
            if current and (current.get("email") or current.get("name")):
                current.setdefault("uid", str(uuid.uuid4()))
                current.setdefault("group", DEFAULT_CONTACT_GROUP)
                contacts.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.split(";", 1)[0].upper()
        value = _unescape_vcard(value)

        if key == "UID":
            current["uid"] = value
        elif key == "FN":
            current["name"] = value
        elif key == "EMAIL":
            current["email"] = value
        elif key == "TEL":
            current["phone"] = value
        elif key == "CATEGORIES":
            group = value.strip()
            current["group"] = (
                group if group in CONTACT_GROUPS
                else DEFAULT_CONTACT_GROUP
            )

    # Évite les doublons d'identifiant.
    unique = {}
    for contact in contacts:
        unique[contact["uid"]] = contact
    return list(unique.values())


def _make_vcard(contacts):
    """Produit un carnet vCard 3.0 compatible avec les logiciels courants."""
    lines = []
    for contact in contacts:
        lines.extend([
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{_escape_vcard(contact.get('uid') or uuid.uuid4())}",
            f"FN:{_escape_vcard(contact.get('name', ''))}",
            f"CATEGORIES:{_escape_vcard(contact.get('group', DEFAULT_CONTACT_GROUP))}",
        ])
        if contact.get("email"):
            lines.append(f"EMAIL;TYPE=INTERNET:{_escape_vcard(contact['email'])}")
        if contact.get("phone"):
            lines.append(f"TEL;TYPE=CELL:{_escape_vcard(contact['phone'])}")
        lines.append("END:VCARD")

    return ("\r\n".join(lines) + ("\r\n" if lines else "")).encode("utf-8")


def _webdav_locations(profile):
    """Construit les URL à partir du profil NUAGE actif."""
    root = (profile.get("url") or "").rstrip("/") + "/"
    username = profile.get("username", "")
    password = profile.get("password", "")

    if not root.strip("/") or not username:
        raise RuntimeError("Le profil NUAGE actif est incomplet.")

    return root + "Mail/", username, password


def load_contacts(profile):
    """Télécharge le carnet partagé ; renvoie une liste vide s'il n'existe pas."""
    folder_url, username, password = _webdav_locations(profile)

    entries = list_directory(folder_url, username, password)
    exists = any(
        not item.get("is_directory")
        and item.get("name", "").casefold() == "contacts.vcf"
        for item in entries
    )
    if not exists:
        return []

    fd, local_path = tempfile.mkstemp(suffix=".vcf")
    os.close(fd)
    try:
        download_file(
            folder_url + "contacts.vcf",
            username,
            password,
            local_path,
        )
        with open(local_path, "r", encoding="utf-8-sig") as file:
            return _parse_vcard(file.read())
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass

def save_contacts(profile, contacts):
    """Envoie le carnet vCard sur NUAGE sous le nom contacts.vcf."""
    folder_url, username, password = _webdav_locations(profile)

    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / "contacts.vcf"

        with open(local_path, "wb") as file:
            file.write(_make_vcard(contacts))

        upload_file(
            local_path,
            folder_url,
            username,
            password,
            overwrite=True,
        )

class ContactSelectionDialog(QDialog):
    """Sélection multiple de contacts pour la rédaction d'un courriel."""

    def __init__(self, contacts, parent=None):
        super().__init__(parent)
        self.contacts = list(contacts or [])

        self.setWindowTitle("Choisir les destinataires")
        self.resize(520, 520)

        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Rechercher un nom ou une adresse e-mail…"
        )
        self.search_edit.textChanged.connect(self.filter_contacts)
        layout.addWidget(self.search_edit)

        self.group_filter = QComboBox()
        self.group_filter.addItem("Tous les groupes", "")
        for group in CONTACT_GROUPS:
            self.group_filter.addItem(group, group)
        self.group_filter.currentIndexChanged.connect(
            self.filter_by_group
        )
        layout.addWidget(self.group_filter)

        self.contact_list = QListWidget()
        self.contact_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection
        )
        layout.addWidget(self.contact_list, 1)

        actions = QHBoxLayout()
        self.select_all_button = QPushButton("Tout sélectionner")
        self.select_all_button.clicked.connect(
            lambda: self.set_all_checked(True)
        )
        actions.addWidget(self.select_all_button)

        self.clear_button = QPushButton("Tout décocher")
        self.clear_button.clicked.connect(
            lambda: self.set_all_checked(False)
        )
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)

        self.count_label = QLabel()
        layout.addWidget(self.count_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Ajouter les contacts"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate()
        self.update_count()

    def _populate(self):
        self.contact_list.clear()

        contacts = sorted(
            self.contacts,
            key=lambda c: (
                c.get("name") or c.get("email") or ""
            ).casefold(),
        )

        for contact in contacts:
            email = (contact.get("email") or "").strip()
            if not email:
                continue

            name = (contact.get("name") or "").strip()
            label = f"{name} <{email}>" if name else email

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, contact)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self.contact_list.addItem(item)

        self.contact_list.itemChanged.connect(
            lambda _item: self.update_count()
        )

    def filter_by_group(self, _index=None):
        self.filter_contacts(self.search_edit.text())

    def filter_contacts(self, text):
        query = text.strip().casefold()
        selected_group = self.group_filter.currentData()

        for index in range(self.contact_list.count()):
            item = self.contact_list.item(index)
            contact = item.data(Qt.ItemDataRole.UserRole)

            searchable = (
                (contact.get("name") or "")
                + " "
                + (contact.get("email") or "")
            ).casefold()

            group = contact.get("group", DEFAULT_CONTACT_GROUP)

            visible = (
                query in searchable
                and (
                    not selected_group
                    or group == selected_group
                )
            )
            item.setHidden(not visible)

    def set_all_checked(self, checked):
        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        for index in range(self.contact_list.count()):
            item = self.contact_list.item(index)
            if not item.isHidden():
                item.setCheckState(state)

        self.update_count()

    def update_count(self):
        count = sum(
            self.contact_list.item(index).checkState()
            == Qt.CheckState.Checked
            for index in range(self.contact_list.count())
        )
        self.count_label.setText(
            f"{count} contact(s) sélectionné(s)"
        )

    def selected_contacts(self):
        selected = []

        for index in range(self.contact_list.count()):
            item = self.contact_list.item(index)

            if item.checkState() == Qt.CheckState.Checked:
                selected.append(
                    item.data(Qt.ItemDataRole.UserRole)
                )

        return selected

class ContactEditDialog(QDialog):
    """Formulaire d'ajout ou de modification d'un contact."""

    def __init__(self, contact=None, parent=None):
        super().__init__(parent)
        contact = contact or {}
        self.setWindowTitle(
            "Modifier le contact" if contact else "Nouveau contact"
        )
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(contact.get("name", ""))
        self.email_edit = QLineEdit(contact.get("email", ""))
        self.phone_edit = QLineEdit(contact.get("phone", ""))
        self.group_combo = QComboBox()
        self.group_combo.addItems(CONTACT_GROUPS)
        group = contact.get("group", DEFAULT_CONTACT_GROUP)
        self.group_combo.setCurrentText(
            group if group in CONTACT_GROUPS else DEFAULT_CONTACT_GROUP
        )

        form.addRow("Nom et prénom :", self.name_edit)
        form.addRow("Adresse électronique :", self.email_edit)
        form.addRow("Téléphone (facultatif) :", self.phone_edit)
        form.addRow("Groupe :", self.group_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_contact(self, uid=None):
        return {
            "uid": uid or str(uuid.uuid4()),
            "name": self.name_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "group": self.group_combo.currentText(),
        }

    def accept(self):
        name = self.name_edit.text().strip()
        address = self.email_edit.text().strip()
        if not name or not address or not re.fullmatch(
            r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", address
        ):
            QMessageBox.warning(
                self,
                "Contact incomplet",
                "Renseigne un nom et une adresse électronique valide.",
            )
            return
        super().accept()


class ContactBookDialog(QDialog):
    """Gestion du carnet d'adresses hébergé sur NUAGE."""

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = dict(profile or {})
        self.contacts = []
        self.setWindowTitle("Carnet d'adresses — NUAGE")
        self.resize(600, 450)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Les contacts sont partagés dans Mail/contacts.vcf sur NUAGE."
        ))
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Rechercher un nom, une adresse e-mail ou un groupe…"
        )
        self.search_edit.textChanged.connect(self._refresh_list)
        layout.addWidget(self.search_edit)

        self.contact_list = QListWidget()
        self.group_filter = QComboBox()

        self.group_filter.addItem("Tous les groupes", "")
        for group in CONTACT_GROUPS:
            self.group_filter.addItem(group, group)
        self.group_filter.currentIndexChanged.connect(
            self._refresh_list
        )
        layout.addWidget(self.group_filter)
        self.contact_list.itemDoubleClicked.connect(
            lambda _item: self.edit_contact()
        )
        layout.addWidget(self.contact_list, 1)

        buttons = QHBoxLayout()
        add_button = QPushButton("＋ Ajouter")
        edit_button = QPushButton("Modifier")
        delete_button = QPushButton("Supprimer")
        refresh_button = QPushButton("↻ Recharger")
        close_button = QPushButton("Fermer")

        add_button.clicked.connect(self.add_contact)
        edit_button.clicked.connect(self.edit_contact)
        delete_button.clicked.connect(self.delete_contact)
        refresh_button.clicked.connect(self.reload_contacts)
        close_button.clicked.connect(self.accept)

        for button in (
            add_button, edit_button, delete_button,
            refresh_button, close_button,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.reload_contacts()

    def reload_contacts(self):
        try:
            self.contacts = load_contacts(self.profile)
            self._refresh_list()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Carnet indisponible",
                "Impossible de lire le carnet d'adresses sur NUAGE.\n\n"
                f"{type(exc).__name__}: {exc}",
            )

    def _refresh_list(self, *_args):
        query = self.search_edit.text().strip().casefold()
        selected_group = self.group_filter.currentData()

        self.contact_list.clear()
        self.contacts.sort(
            key=lambda c: c.get("name", "").casefold()
        )

        for contact in self.contacts:
            group = contact.get("group", DEFAULT_CONTACT_GROUP)

            if selected_group and group != selected_group:
                continue

            searchable = " ".join([
                contact.get("name", ""),
                contact.get("email", ""),
                contact.get("phone", ""),
                group,
            ]).casefold()

            if query not in searchable:
                continue

            item = QListWidgetItem(
                f"{contact.get('name', '')}  —  "
                f"{contact.get('email', '')}  [{group}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, contact["uid"])

            if contact.get("phone"):
                item.setToolTip(contact["phone"])

            self.contact_list.addItem(item)

    def _selected_contact(self):
        item = self.contact_list.currentItem()
        if item is None:
            QMessageBox.information(
                self, "Aucun contact", "Sélectionne d'abord un contact."
            )
            return None
        uid = item.data(Qt.ItemDataRole.UserRole)
        return next((c for c in self.contacts if c["uid"] == uid), None)

    def _save(self):
        try:
            save_contacts(self.profile, self.contacts)
            self._refresh_list()
            return True
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Enregistrement impossible",
                "Le carnet n'a pas pu être enregistré sur NUAGE.\n\n"
                f"{type(exc).__name__}: {exc}",
            )
            return False

    def add_contact(self):
        dialog = ContactEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        contact = dialog.get_contact()
        if any(
            c.get("email", "").casefold() == contact["email"].casefold()
            for c in self.contacts
        ):
            QMessageBox.warning(
                self, "Contact existant",
                "Cette adresse est déjà présente dans le carnet.",
            )
            return

        self.contacts.append(contact)
        if not self._save():
            self.contacts.remove(contact)

    def edit_contact(self):
        old = self._selected_contact()
        if old is None:
            return

        dialog = ContactEditDialog(old, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated = dialog.get_contact(uid=old["uid"])
        if any(
            c["uid"] != old["uid"]
            and c.get("email", "").casefold() == updated["email"].casefold()
            for c in self.contacts
        ):
            QMessageBox.warning(
                self, "Contact existant",
                "Cette adresse est déjà présente dans le carnet.",
            )
            return

        index = self.contacts.index(old)
        self.contacts[index] = updated
        if not self._save():
            self.contacts[index] = old

    def delete_contact(self):
        contact = self._selected_contact()
        if contact is None:
            return

        answer = QMessageBox.question(
            self,
            "Supprimer le contact",
            f"Supprimer « {contact.get('name', '')} » du carnet partagé ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        index = self.contacts.index(contact)
        self.contacts.pop(index)
        if not self._save():
            self.contacts.insert(index, contact)
