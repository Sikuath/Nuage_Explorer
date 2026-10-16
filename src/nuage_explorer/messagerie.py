"""Fenêtre de messagerie académique IMAP/SMTP pour Nuage Explorer.

Les paramètres et le mot de passe de messagerie sont enregistrés dans le vault
déjà déverrouillé par Nuage Explorer. Aucun second mot de passe maître n'est demandé.
"""
import email
import imaplib
import smtplib
import ssl
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextBrowser,
    QDialog, QDialogButtonBox, QLineEdit, QSpinBox, QComboBox,
    QMessageBox, QTextEdit, QSplitter, QProgressBar,
)

from .common import save_vault, VaultError
from .style import STYLE


def _decode_mime(value):
    """Décode un en-tête MIME en texte lisible."""
    if not value:
        return ""
    parts = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            for encoding in (charset, "utf-8", "latin-1"):
                if not encoding:
                    continue
                try:
                    chunk = chunk.decode(encoding, errors="replace")
                    break
                except (LookupError, UnicodeDecodeError):
                    continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
        parts.append(str(chunk))
    return "".join(parts)


def _message_body(message):
    """Extrait le corps texte d'un courriel, sans afficher son HTML brut."""
    plain_parts = []
    html_parts = []

    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            raw = part.get_payload()
            if isinstance(raw, str):
                text = raw
            else:
                continue
        else:
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except LookupError:
                text = payload.decode("utf-8", errors="replace")
        if content_type == "text/plain":
            plain_parts.append(text)
        else:
            html_parts.append(text)

    if plain_parts:
        return "\n\n".join(plain_parts)
    if html_parts:
        # L'HTML distant est volontairement affiché comme texte pour éviter
        # le chargement de contenus externes dans le navigateur intégré.
        return "\n\n".join(html_parts)
    return "(Ce message ne contient pas de corps texte affichable.)"


class MailSettingsDialog(QDialog):
    """Configuration IMAP/SMTP enregistrée dans le vault."""

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration de la messagerie")
        self.setMinimumWidth(480)
        settings = settings or {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.email_edit = QLineEdit(settings.get("email", ""))
        self.username_edit = QLineEdit(
            settings.get("username", settings.get("email", ""))
        )
        self.password_edit = QLineEdit(settings.get("password", ""))
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.imap_host_edit = QLineEdit(settings.get("imap_host", ""))
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(int(settings.get("imap_port", 993)))

        self.smtp_host_edit = QLineEdit(settings.get("smtp_host", ""))
        self.smtp_port_spin = QSpinBox()
        self.smtp_port_spin.setRange(1, 65535)
        self.smtp_port_spin.setValue(int(settings.get("smtp_port", 465)))

        self.smtp_security = QComboBox()
        self.smtp_security.addItem("SSL/TLS (port généralement 465)", "ssl")
        self.smtp_security.addItem("STARTTLS (port généralement 587)", "starttls")
        index = self.smtp_security.findData(settings.get("smtp_security", "ssl"))
        self.smtp_security.setCurrentIndex(max(index, 0))

        form.addRow("Adresse électronique :", self.email_edit)
        form.addRow("Identifiant :", self.username_edit)
        form.addRow("Mot de passe :", self.password_edit)
        form.addRow("Serveur IMAP :", self.imap_host_edit)
        form.addRow("Port IMAP :", self.imap_port_spin)
        form.addRow("Serveur SMTP :", self.smtp_host_edit)
        form.addRow("Port SMTP :", self.smtp_port_spin)
        form.addRow("Sécurité SMTP :", self.smtp_security)
        layout.addLayout(form)

        note = QLabel(
            "Les paramètres dépendent de ton académie. "
            "Le mot de passe est stocké dans le vault chiffré."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            "email": self.email_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "imap_host": self.imap_host_edit.text().strip(),
            "imap_port": self.imap_port_spin.value(),
            "smtp_host": self.smtp_host_edit.text().strip(),
            "smtp_port": self.smtp_port_spin.value(),
            "smtp_security": self.smtp_security.currentData(),
        }

    def accept(self):
        settings = self.get_settings()
        required = (
            settings["email"], settings["username"], settings["password"],
            settings["imap_host"], settings["smtp_host"],
        )
        if not all(required):
            QMessageBox.warning(
                self, "Configuration incomplète",
                "Renseigne l'adresse, l'identifiant, le mot de passe "
                "et les deux serveurs."
            )
            return
        super().accept()


class MailListWorker(QThread):
    messages_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, settings, limit=50, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.limit = limit

    def run(self):
        client = None
        try:
            context = ssl.create_default_context()
            client = imaplib.IMAP4_SSL(
                self.settings["imap_host"],
                int(self.settings.get("imap_port", 993)),
                ssl_context=context,
                timeout=25,
            )
            client.login(
                self.settings["username"],
                self.settings["password"],
            )
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("Impossible d'ouvrir le dossier de réception.")

            status, data = client.search(None, "ALL")
            if status != "OK":
                raise RuntimeError("Impossible de récupérer la liste des messages.")

            ids = data[0].split() if data and data[0] else []
            ids = ids[-self.limit:]
            results = []

            for sequence in reversed(ids):
                status, fetched = client.fetch(sequence, "(BODY.PEEK[HEADER])")
                if status != "OK" or not fetched or not fetched[0]:
                    continue
                raw = fetched[0][1]
                parsed = email.message_from_bytes(raw)
                results.append({
                    "id": sequence.decode("ascii", errors="ignore"),
                    "subject": _decode_mime(parsed.get("Subject", "")) or "(Sans objet)",
                    "sender": _decode_mime(parsed.get("From", "")),
                    "date": _decode_mime(parsed.get("Date", "")),
                })

            self.messages_ready.emit(results)
        except Exception as exc:
            self.failed.emit(
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class MailMessageWorker(QThread):
    message_ready = Signal(str, str, str, str)
    failed = Signal(str)

    def __init__(self, settings, message_id, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.message_id = message_id

    def run(self):
        client = None
        try:
            client = imaplib.IMAP4_SSL(
                self.settings["imap_host"],
                int(self.settings.get("imap_port", 993)),
                ssl_context=ssl.create_default_context(),
                timeout=25,
            )
            client.login(self.settings["username"], self.settings["password"])
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("Impossible d'ouvrir le dossier de réception.")
            status, data = client.fetch(
                self.message_id.encode("ascii"),
                "(BODY.PEEK[])",
            )
            if status != "OK" or not data or not data[0]:
                raise RuntimeError("Le message n'a pas pu être téléchargé.")
            parsed = email.message_from_bytes(data[0][1])
            subject = _decode_mime(parsed.get("Subject", "")) or "(Sans objet)"
            sender = _decode_mime(parsed.get("From", ""))
            date = _decode_mime(parsed.get("Date", ""))
            body = _message_body(parsed)
            self.message_ready.emit(subject, sender, date, body)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class SendMailDialog(QDialog):
    """Fenêtre simple de rédaction et d'envoi d'un courriel."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.setWindowTitle("Nouveau message")
        self.resize(650, 500)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.to_edit = QLineEdit()
        self.subject_edit = QLineEdit()
        form.addRow("À :", self.to_edit)
        form.addRow("Objet :", self.subject_edit)
        layout.addLayout(form)

        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Écris ton message…")
        layout.addWidget(self.body_edit, 1)

        buttons = QDialogButtonBox()
        self.send_button = buttons.addButton(
            "Envoyer", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.cancel_button = buttons.addButton(
            "Annuler", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.send_button.clicked.connect(self.send_message)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def send_message(self):
        recipient = self.to_edit.text().strip()
        if not recipient or "@" not in recipient:
            QMessageBox.warning(self, "Destinataire invalide", "Renseigne une adresse de destinataire.")
            return
        if not self.settings.get("smtp_host"):
            QMessageBox.warning(self, "SMTP non configuré", "Configure le serveur SMTP avant l'envoi.")
            return

        message = EmailMessage()
        message["From"] = self.settings["email"]
        message["To"] = recipient
        message["Subject"] = self.subject_edit.text().strip()
        message.set_content(self.body_edit.toPlainText())

        try:
            host = self.settings["smtp_host"]
            port = int(self.settings.get("smtp_port", 465))
            security = self.settings.get("smtp_security", "ssl")
            context = ssl.create_default_context()

            if security == "starttls":
                with smtplib.SMTP(host, port, timeout=25) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(
                        self.settings["username"],
                        self.settings["password"],
                    )
                    server.send_message(message)
            else:
                with smtplib.SMTP_SSL(
                    host, port, timeout=25, context=context
                ) as server:
                    server.login(
                        self.settings["username"],
                        self.settings["password"],
                    )
                    server.send_message(message)
        except Exception as exc:
            QMessageBox.critical(
                self, "Envoi impossible",
                f"Le message n'a pas été envoyé.\n\n{type(exc).__name__}: {exc}"
            )
            return

        QMessageBox.information(self, "Message envoyé", "Le courriel a été envoyé.")
        super().accept()


class MessagerieWindow(QMainWindow):
    """Fenêtre indépendante de messagerie, reliée au vault de Nuage Explorer."""

    def __init__(self, vault_path, master_password, vault_data, parent=None):
        super().__init__(parent)
        self.vault_path = vault_path
        self.master_password = master_password
        self.vault_data = vault_data
        self.settings = dict(vault_data.get("mail_account", {}))
        self.list_worker = None
        self.message_worker = None

        self.setWindowTitle("Messagerie académique — Nuage Explorer")
        self.setStyleSheet(STYLE)
        self.resize(1050, 700)
        self.setMinimumSize(760, 480)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Messagerie académique")
        title.setObjectName("appTitle")
        title_box.addWidget(title)
        self.account_label = QLabel(
            self.settings.get("email", "Compte non configuré")
        )
        self.account_label.setObjectName("muted")
        title_box.addWidget(self.account_label)
        header.addLayout(title_box)
        header.addStretch()

        self.back_button = QPushButton("← Retour à Nuage Explorer")
        self.back_button.clicked.connect(self.return_to_nuage)
        header.addWidget(self.back_button)

        self.settings_button = QPushButton("⚙ Configuration")
        self.settings_button.clicked.connect(self.configure_account)
        header.addWidget(self.settings_button)

        self.refresh_button = QPushButton("↻ Actualiser")
        self.refresh_button.clicked.connect(self.refresh_messages)
        header.addWidget(self.refresh_button)

        self.compose_button = QPushButton("✉ Nouveau message")
        self.compose_button.setObjectName("primary")
        self.compose_button.clicked.connect(self.compose_message)
        header.addWidget(self.compose_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.message_list = QListWidget()
        self.message_list.setMinimumWidth(280)
        self.message_list.currentItemChanged.connect(self.select_message)
        splitter.addWidget(self.message_list)

        self.message_view = QTextBrowser()
        self.message_view.setOpenExternalLinks(False)
        self.message_view.setPlaceholderText("Sélectionne un message pour le lire.")
        splitter.addWidget(self.message_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        if not self.settings:
            self.configure_account()
        elif self.settings:
            self.refresh_messages()

    def configure_account(self):
        dialog = MailSettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            if not self.settings:
                self.status_label.setText("Configure le compte pour commencer.")
            return

        new_settings = dialog.get_settings()
        new_data = dict(self.vault_data)
        new_data["mail_account"] = new_settings
        try:
            save_vault(
                self.vault_path,
                self.master_password,
                new_data,
            )
        except (VaultError, OSError) as exc:
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"Les paramètres n'ont pas été enregistrés dans le vault.\n\n{exc}"
            )
            return

        # Met à jour le dictionnaire partagé pour que les deux fenêtres
        # conservent la même version des données déverrouillées.
        self.vault_data.clear()
        self.vault_data.update(new_data)
        if self.parent() is not None and hasattr(self.parent(), "vault_data"):
            self.parent().vault_data = self.vault_data

        self.settings = new_settings
        self.account_label.setText(self.settings["email"])
        self.status_label.setText("Configuration enregistrée dans le vault chiffré.")
        self.refresh_messages()

    def refresh_messages(self):
        if not self.settings:
            QMessageBox.information(
                self, "Compte non configuré",
                "Configure d'abord la messagerie académique."
            )
            return
        if self.list_worker is not None and self.list_worker.isRunning():
            return

        self.message_list.clear()
        self.message_view.clear()
        self.status_label.setText("Connexion au serveur IMAP…")
        self.refresh_button.setEnabled(False)
        self.list_worker = MailListWorker(self.settings, parent=self)
        self.list_worker.messages_ready.connect(self.messages_loaded)
        self.list_worker.failed.connect(self.mail_error)
        self.list_worker.finished.connect(self.list_finished)
        self.list_worker.start()

    def messages_loaded(self, messages):
        self.message_list.clear()
        for message in messages:
            label = (
                f"{message['subject']}\n"
                f"{message['sender']}\n"
                f"{message['date']}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, message["id"])
            self.message_list.addItem(item)
        self.status_label.setText(
            f"{len(messages)} message(s) chargé(s) depuis la boîte de réception."
        )
        if not messages:
            self.message_view.setPlainText("La boîte de réception est vide.")

    def list_finished(self):
        self.refresh_button.setEnabled(True)
        self.list_worker = None

    def select_message(self, current, previous=None):
        if current is None or not self.settings:
            return
        if self.message_worker is not None and self.message_worker.isRunning():
            return
        message_id = current.data(Qt.ItemDataRole.UserRole)
        self.status_label.setText("Chargement du message…")
        self.message_worker = MailMessageWorker(
            self.settings, message_id, parent=self
        )
        self.message_worker.message_ready.connect(self.display_message)
        self.message_worker.failed.connect(self.mail_error)
        self.message_worker.finished.connect(self.message_finished)
        self.message_worker.start()

    def display_message(self, subject, sender, date, body):
        header = (
            f"<h2>{escape(subject)}</h2>"
            f"<p><b>De :</b> {escape(sender)}<br>"
            f"<b>Date :</b> {escape(date)}</p><hr>"
        )
        # Le contenu est traité comme texte, pas comme HTML actif.
        self.message_view.setHtml(header + f"<pre>{escape(body)}</pre>")
        self.status_label.setText("Message chargé.")

    def message_finished(self):
        self.message_worker = None

    def mail_error(self, message):
        self.status_label.setText("Une erreur est survenue.")
        QMessageBox.warning(
            self, "Erreur de messagerie",
            "La messagerie n'a pas pu effectuer l'opération.\n\n" + message
        )

    def compose_message(self):
        if not self.settings:
            self.configure_account()
            if not self.settings:
                return
        dialog = SendMailDialog(self.settings, self)
        dialog.exec()

    def return_to_nuage(self):
        parent = self.parent()
        if parent is not None:
            parent.show()
            parent.raise_()
            parent.activateWindow()
        self.hide()

    def closeEvent(self, event):
        # La fenêtre principale reste ouverte.
        event.accept()
