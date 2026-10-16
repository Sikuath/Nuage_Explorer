"""Fenêtre de messagerie académique IMAP/SMTP pour Nuage Explorer.

Les paramètres et le mot de passe de messagerie sont enregistrés dans le vault
déjà déverrouillé par Nuage Explorer. Aucun second mot de passe maître n'est demandé.
"""
import email
from email.utils import getaddresses, parseaddr
import imaplib
import re
import smtplib
import ssl
import time
from email.header import decode_header
from email.message import EmailMessage
from html import escape

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QTextBrowser,
    QDialog, QDialogButtonBox, QLineEdit, QSpinBox, QComboBox,
    QMessageBox, QTextEdit, QSplitter, QMenu,
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
    """Extrait le corps d'un courriel en privilégiant la version texte."""
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
        # Le rendu HTML est effectué ensuite par QTextBrowser. Les ressources
        # distantes et les pixels de suivi sont retirés avant affichage.
        return "\n\n".join(html_parts)
    return "(Ce message ne contient pas de corps texte affichable.)"


def _body_as_plain_text(source):
    """Convertit sommairement un corps HTML en texte pour une réponse citée."""
    text = source or ""
    if re.search(r"<\s*(?:html|body|div|p|table|span|h[1-6]|br)\b", text, flags=re.I):
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
        text = re.sub(r"</\s*(?:p|div|tr|li|h[1-6])\s*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    import html
    text = html.unescape(text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text.strip()


def _prepare_mail_html(source):
    """Prépare un corps HTML pour QTextBrowser sans charger de contenu distant."""
    html = source or ""
    # Ne conserver que le contenu du body, lorsqu'il existe.
    match = re.search(r"<body\b[^>]*>(.*?)</body\s*>", html, flags=re.I | re.S)
    if match:
        html = match.group(1)
    else:
        html = re.sub(r"<!DOCTYPE[^>]*>", "", html, flags=re.I | re.S)
        html = re.sub(r"<head\b[^>]*>.*?</head\s*>", "", html, flags=re.I | re.S)
        html = re.sub(r"</?html\b[^>]*>", "", html, flags=re.I)
    # Supprimer scripts, styles externes, images (dont les pixels de suivi)
    # et les balises de métadonnées. QTextBrowser ne doit pas charger d'images distantes.
    html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.I | re.S)
    html = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", html, flags=re.I | re.S)
    html = re.sub(r"<img\b[^>]*>", "", html, flags=re.I | re.S)
    html = re.sub(r"<meta\b[^>]*>", "", html, flags=re.I | re.S)
    html = re.sub(r"<link\b[^>]*>", "", html, flags=re.I | re.S)
    # Retirer les liens de suivi vides laissés par les images supprimées.
    html = re.sub(r"<a\b[^>]*>\s*</a\s*>", "", html, flags=re.I | re.S)
    return html.strip()


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


def _mailbox_name(raw_name):
    """Décode un nom de dossier renvoyé par IMAP (UTF-7 modifié)."""
    raw_name = raw_name.strip()
    if raw_name.startswith(b'"') and raw_name.endswith(b'"'):
        raw_name = raw_name[1:-1].replace(b'\\"', b'"').replace(b'\\\\', b'\\')
    try:
        return imaplib.IMAP4._decode_utf7(raw_name.decode("ascii"))
    except (AttributeError, UnicodeDecodeError, UnicodeEncodeError):
        return raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else raw_name


def _list_mailboxes(client):
    """Renvoie les dossiers IMAP et identifie celui des messages envoyés."""
    status, rows = client.list()
    if status != "OK":
        raise RuntimeError("Impossible de récupérer la liste des dossiers IMAP.")

    folders = []
    for row in rows or []:
        if not row:
            continue
        if isinstance(row, bytes):
            line = row.decode("ascii", errors="replace")
        else:
            line = str(row)
        match = re.match(r'^\((.*?)\)\s+(?:"[^"]*"|NIL)\s+(.+)$', line)
        if not match:
            continue
        flags = match.group(1).lower()
        name = _mailbox_name(match.group(2).encode("ascii", errors="replace"))
        if not name:
            continue
        lowered = name.casefold()
        is_inbox = lowered == "inbox"
        is_sent = ("\\sent" in flags or any(token in lowered for token in (
            "sent", "envoy", "outbox", "gesendet", "inviat", "inviati", "éléments envoyés"
        )))
        is_trash = ("\\trash" in flags or any(token in lowered for token in (
            "trash", "corbeille", "poubelle", "deleted", "éléments supprimés"
        )))
        label = "Boîte de réception" if is_inbox else ("Messages envoyés" if is_sent else name)
        folders.append({"name": name, "label": label, "is_sent": is_sent, "is_trash": is_trash})

    if not any(folder["name"].casefold() == "inbox" for folder in folders):
        folders.insert(0, {"name": "INBOX", "label": "Boîte de réception", "is_sent": False, "is_trash": False})
    # Évite les doublons et garde en priorité le dossier signalé par le serveur.
    unique = {}
    for folder in folders:
        key = folder["name"].casefold()
        if key not in unique or folder["is_sent"]:
            unique[key] = folder
    return list(unique.values())


def _connect_imap(settings):
    client = imaplib.IMAP4_SSL(
        settings["imap_host"],
        int(settings.get("imap_port", 993)),
        ssl_context=ssl.create_default_context(),
        timeout=25,
    )
    client.login(settings["username"], settings["password"])
    return client


class MailFoldersWorker(QThread):
    folders_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)

    def run(self):
        client = None
        try:
            client = _connect_imap(self.settings)
            folders = _list_mailboxes(client)
            # Récupère le nombre total de messages de chaque dossier.
            # Un dossier inaccessible est conservé avec un compteur inconnu.
            for folder in folders:
                try:
                    status, data = client.select(folder["name"], readonly=True)
                    if status == "OK" and data and data[0]:
                        folder["count"] = int(data[0])
                    else:
                        folder["count"] = None
                except Exception:
                    folder["count"] = None
            self.folders_ready.emit(folders)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class MailListWorker(QThread):
    messages_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, settings, limit=50, folder="INBOX", parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.limit = limit
        self.folder = folder

    def run(self):
        client = None
        try:
            client = _connect_imap(self.settings)
            status, _ = client.select(self.folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Impossible d'ouvrir le dossier IMAP : {self.folder}")
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
                    "to": _decode_mime(parsed.get("To", "")),
                    "date": _decode_mime(parsed.get("Date", "")),
                })
            self.messages_ready.emit(results)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class MailMessageWorker(QThread):
    message_ready = Signal(str, str, str, str, str)
    failed = Signal(str)

    def __init__(self, settings, message_id, folder="INBOX", parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.message_id = str(message_id)
        self.folder = folder

    def run(self):
        client = None
        try:
            client = _connect_imap(self.settings)
            status, _ = client.select(self.folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Impossible d'ouvrir le dossier IMAP : {self.folder}")
            status, data = client.fetch(self.message_id.encode("ascii"), "(BODY.PEEK[])")
            if status != "OK" or not data or not data[0]:
                raise RuntimeError("Le message n'a pas pu être téléchargé.")
            parsed = email.message_from_bytes(data[0][1])
            subject = _decode_mime(parsed.get("Subject", "")) or "(Sans objet)"
            sender = _decode_mime(parsed.get("From", ""))
            recipient = _decode_mime(parsed.get("To", ""))
            date = _decode_mime(parsed.get("Date", ""))
            body = _message_body(parsed)
            self.message_ready.emit(subject, sender, recipient, date, body)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class MailReplyDataWorker(QThread):
    """Récupère les en-têtes et le corps nécessaires à une réponse."""
    reply_data_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, settings, message_id, folder="INBOX", reply_all=False, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.message_id = str(message_id)
        self.folder = folder
        self.reply_all = reply_all

    def run(self):
        client = None
        try:
            client = _connect_imap(self.settings)
            status, _ = client.select(self.folder, readonly=True)
            if status != "OK":
                raise RuntimeError(f"Impossible d'ouvrir le dossier IMAP : {self.folder}")
            status, data = client.fetch(self.message_id.encode("ascii"), "(BODY.PEEK[])")
            if status != "OK" or not data or not data[0]:
                raise RuntimeError("Le message n'a pas pu être téléchargé pour préparer la réponse.")
            parsed = email.message_from_bytes(data[0][1])
            sender_header = parsed.get("Reply-To") or parsed.get("From", "")
            sender_addresses = [addr for _, addr in getaddresses([str(sender_header)]) if addr]
            if not sender_addresses:
                raise RuntimeError("L'adresse de l'expéditeur est absente ou invalide.")
            recipients = list(sender_addresses)
            if self.reply_all:
                original_headers = [str(parsed.get("To", "")), str(parsed.get("Cc", ""))]
                own_address = self.settings.get("email", "").casefold()
                for _, addr in getaddresses(original_headers):
                    if addr and addr.casefold() != own_address and addr.casefold() not in {x.casefold() for x in recipients}:
                        recipients.append(addr)
            subject = _decode_mime(parsed.get("Subject", "")) or "(Sans objet)"
            if not subject.casefold().startswith("re:"):
                subject = "Re: " + subject
            original_body = _body_as_plain_text(_message_body(parsed))
            date = _decode_mime(parsed.get("Date", ""))
            quote = "\n".join("> " + line for line in original_body.splitlines())
            body = f"\n\nLe {date}, {sender_header} a écrit :\n{quote}" if original_body else f"\n\n--- Message d'origine ---\nDe : {sender_header}\nDate : {date}"
            result = {
                "to": ", ".join(recipients),
                "subject": subject,
                "body": body,
                "in_reply_to": parsed.get("Message-ID", ""),
                "references": " ".join(x for x in (parsed.get("References", ""), parsed.get("Message-ID", "")) if x).strip(),
            }
            self.reply_data_ready.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass


class MailActionWorker(QThread):
    """Déplace un message dans la corbeille ou le supprime définitivement."""
    action_done = Signal(str, str)
    failed = Signal(str)

    def __init__(self, settings, folder, message_id, operation, trash_folder=None, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.folder = folder
        self.message_id = str(message_id)
        self.operation = operation
        self.trash_folder = trash_folder

    def run(self):
        client = None
        try:
            client = _connect_imap(self.settings)
            status, _ = client.select(self.folder)
            if status != "OK":
                raise RuntimeError(f"Impossible d'ouvrir le dossier IMAP : {self.folder}")

            # La liste utilise des numéros de séquence, alors que les opérations
            # UID sont plus sûres si la boîte reçoit de nouveaux messages entre-temps.
            status, uid_data = client.fetch(self.message_id.encode("ascii"), "(UID)")
            if status != "OK" or not uid_data or not uid_data[0]:
                raise RuntimeError("Impossible d'identifier le message sur le serveur IMAP.")
            uid_match = re.search(rb"\bUID\s+(\d+)", uid_data[0][0] if isinstance(uid_data[0], tuple) else uid_data[0])
            if not uid_match:
                raise RuntimeError("Le serveur IMAP n'a pas fourni l'identifiant unique du message.")
            uid = uid_match.group(1)
            capabilities = {
                cap.decode("ascii", errors="ignore") if isinstance(cap, bytes) else str(cap)
                for cap in getattr(client, "capabilities", ())
            }
            trash_flags = "(\\Deleted)"

            if self.operation == "trash":
                if not self.trash_folder:
                    raise RuntimeError("Aucun dossier Corbeille n'a été détecté dans le compte IMAP.")
                # MOVE est préférable car il déplace le message en une opération.
                try:
                    status, _ = client.uid("MOVE", uid, client._quote(self.trash_folder))
                except Exception:
                    status = "NO"
                if status != "OK":
                    # Repli pour les serveurs sans extension MOVE. UIDPLUS permet
                    # d'expurger uniquement ce message, sans toucher aux autres.
                    if "UIDPLUS" not in capabilities:
                        raise RuntimeError("Le serveur ne prend pas en charge MOVE ni UIDPLUS ; déplacement annulé pour éviter de supprimer d'autres messages marqués.")
                    status, _ = client.uid("COPY", uid, client._quote(self.trash_folder))
                    if status != "OK":
                        raise RuntimeError(f"Impossible de déplacer le message vers {self.trash_folder}.")
                    status, _ = client.uid("STORE", uid, "+FLAGS", trash_flags)
                    if status != "OK":
                        raise RuntimeError("Le message a été copié dans la corbeille mais n'a pas pu être retiré du dossier d'origine.")
                    status, _ = client.uid("EXPUNGE", uid)
                    if status != "OK":
                        raise RuntimeError("Le message a été copié dans la corbeille, mais son retrait du dossier d'origine a échoué.")
                self.action_done.emit("trash", self.folder)
            elif self.operation == "delete":
                if "UIDPLUS" not in capabilities:
                    raise RuntimeError("Le serveur ne prend pas en charge UIDPLUS : l'effacement définitif ciblé n'est pas disponible sans risquer de supprimer d'autres messages marqués.")
                status, _ = client.uid("STORE", uid, "+FLAGS", trash_flags)
                if status != "OK":
                    raise RuntimeError("Le serveur IMAP n'a pas accepté la suppression du message.")
                if "UIDPLUS" in capabilities:
                    status, _ = client.uid("EXPUNGE", uid)
                    if status != "OK":
                        raise RuntimeError("Le serveur a marqué le message comme supprimé, mais n'a pas confirmé son effacement définitif.")
                self.action_done.emit("delete", self.folder)
            else:
                raise RuntimeError("Opération de messagerie inconnue.")
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

    def __init__(self, settings, parent=None, draft=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.draft = dict(draft or {})
        self.setWindowTitle("Répondre" if self.draft else "Nouveau message")
        self.resize(650, 500)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.to_edit = QLineEdit(self.draft.get("to", ""))
        self.subject_edit = QLineEdit(self.draft.get("subject", ""))
        form.addRow("À :", self.to_edit)
        form.addRow("Objet :", self.subject_edit)
        layout.addLayout(form)

        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("Écris ton message…")
        self.body_edit.setPlainText(self.draft.get("body", ""))
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
        if self.draft.get("in_reply_to"):
            message["In-Reply-To"] = self.draft["in_reply_to"]
        if self.draft.get("references"):
            message["References"] = self.draft["references"]
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

        # SMTP a accepté le message : on en ajoute une copie dans le dossier
        # IMAP des envoyés, comme le ferait un client de messagerie classique.
        archive_error = None
        imap_client = None
        try:
            imap_client = _connect_imap(self.settings)
            folders = _list_mailboxes(imap_client)
            sent_folder = next((f["name"] for f in folders if f["is_sent"]), None)
            if not sent_folder:
                archive_error = "Aucun dossier IMAP des messages envoyés n'a été détecté."
            else:
                status, _ = imap_client.append(
                    sent_folder, "\\Seen", imaplib.Time2Internaldate(time.time()),
                    message.as_bytes()
                )
                if status != "OK":
                    archive_error = f"Le serveur IMAP a refusé l'archivage dans {sent_folder}."
        except Exception as exc:
            archive_error = f"{type(exc).__name__}: {exc}"
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

        if archive_error:
            QMessageBox.warning(
                self, "Message envoyé, copie non archivée",
                "Le courriel a bien été envoyé, mais sa copie n'a pas pu être "
                f"enregistrée dans les messages envoyés.\n\n{archive_error}"
            )
        else:
            QMessageBox.information(self, "Message envoyé", "Le courriel a été envoyé et une copie a été enregistrée dans les messages envoyés.")
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
        self.folders_worker = None
        self.reply_worker = None
        self.action_worker = None
        self.current_folder = "INBOX"
        self.mail_folders = []

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

        # Présentation à la Thunderbird : dossiers à gauche, liste des
        # messages au centre et lecture à droite.
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        folder_panel = QWidget()
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(0, 0, 8, 0)
        folder_title = QLabel("DOSSIERS")
        folder_title.setObjectName("muted")
        folder_layout.addWidget(folder_title)
        self.folder_list = QListWidget()
        self.folder_list.setMinimumWidth(185)
        self.folder_list.setMaximumWidth(280)
        self.folder_list.currentItemChanged.connect(self.select_folder)
        folder_layout.addWidget(self.folder_list, 1)
        main_splitter.addWidget(folder_panel)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.message_list = QListWidget()
        self.message_list.setMinimumWidth(260)
        self.message_list.currentItemChanged.connect(self.select_message)
        self.message_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_list.customContextMenuRequested.connect(self.show_message_context_menu)
        content_splitter.addWidget(self.message_list)

        self.message_view = QTextBrowser()
        self.message_view.setOpenExternalLinks(False)
        self.message_view.setPlaceholderText("Sélectionne un message pour le lire.")
        content_splitter.addWidget(self.message_view)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 2)
        main_splitter.addWidget(content_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([210, 840])
        root.addWidget(main_splitter, 1)

        self.status_label = QLabel("Prêt")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        if not self.settings:
            self.configure_account()
        else:
            self.load_folders()

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
        self.load_folders()

    def load_folders(self):
        if not self.settings:
            return
        if self.folders_worker is not None and self.folders_worker.isRunning():
            return
        self.folders_worker = MailFoldersWorker(self.settings, parent=self)
        self.folders_worker.folders_ready.connect(self.folders_loaded)
        self.folders_worker.failed.connect(self.mail_error)
        self.folders_worker.start()

    def folders_loaded(self, folders):
        """Affiche les dossiers à gauche avec leur nombre de messages."""
        previous = self.current_folder
        self.mail_folders = list(folders)
        self.folder_list.blockSignals(True)
        self.folder_list.clear()

        # Inbox d'abord, puis les autres dossiers dans l'ordre du serveur.
        folders = sorted(
            folders,
            key=lambda f: (f["name"].casefold() != "inbox", f["label"].casefold()),
        )
        for folder in folders:
            count = folder.get("count")
            if count is None:
                count_text = "(?)"
            else:
                count_text = f"({count})"
            if folder["name"].casefold() == "inbox":
                icon = "📥"
                label = "Boîte de réception"
            elif folder["is_sent"]:
                icon = "📤"
                label = "Messages envoyés"
            elif any(word in folder["name"].casefold() for word in ("draft", "brouillon")):
                icon = "📝"
                label = folder["label"]
            elif any(word in folder["name"].casefold() for word in ("trash", "corbeille", "deleted", "poubelle")):
                icon = "🗑"
                label = folder["label"]
            elif any(word in folder["name"].casefold() for word in ("junk", "spam", "indésirable")):
                icon = "⚠"
                label = folder["label"]
            else:
                icon = "📁"
                label = folder["label"]

            item = QListWidgetItem(f"{icon}  {label}  {count_text}")
            item.setData(Qt.ItemDataRole.UserRole, folder["name"])
            item.setToolTip(f"{folder['name']} — {count_text} message(s)")
            self.folder_list.addItem(item)

        index_to_select = 0
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == previous:
                index_to_select = i
                break
        if self.folder_list.count():
            self.folder_list.setCurrentRow(index_to_select)
        self.folder_list.blockSignals(False)

        selected = self.folder_list.currentItem()
        if selected is not None:
            self.current_folder = selected.data(Qt.ItemDataRole.UserRole) or "INBOX"
            self.refresh_messages()
        self.folders_worker = None

    def select_folder(self, current, previous=None):
        if current is None:
            return
        folder = current.data(Qt.ItemDataRole.UserRole)
        if not folder or folder == self.current_folder:
            return
        self.current_folder = folder
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
        self.list_worker = MailListWorker(
            self.settings, folder=self.current_folder, parent=self
        )
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
        folder_label = self.current_folder
        for i in range(self.folder_list.count()):
            folder_item = self.folder_list.item(i)
            if folder_item.data(Qt.ItemDataRole.UserRole) == self.current_folder:
                folder_label = folder_item.text().split("  ", 2)[1]
                break
        self.status_label.setText(
            f"{len(messages)} message(s) chargé(s) — {folder_label}."
        )
        if not messages:
            self.message_view.setPlainText(f"Le dossier « {folder_label} » est vide.")

    def list_finished(self):
        finished_folder = self.list_worker.folder if self.list_worker is not None else None
        self.refresh_button.setEnabled(True)
        self.list_worker = None
        # Si l'utilisateur a changé de dossier pendant le chargement, lance
        # maintenant le chargement du dossier réellement sélectionné.
        if finished_folder and finished_folder != self.current_folder:
            self.refresh_messages()

    def show_message_context_menu(self, position):
        """Menu contextuel façon Thunderbird pour le message sélectionné."""
        item = self.message_list.itemAt(position)
        if item is None:
            return
        self.message_list.setCurrentItem(item)
        menu = QMenu(self)
        reply_action = menu.addAction("↩ Répondre à l'expéditeur")
        reply_all_action = menu.addAction("↩ Répondre à tous")
        menu.addSeparator()
        trash_action = menu.addAction("🗑 Déplacer vers la corbeille")
        delete_action = menu.addAction("✖ Supprimer définitivement")
        chosen = menu.exec(self.message_list.mapToGlobal(position))
        message_id = item.data(Qt.ItemDataRole.UserRole)
        if chosen == reply_action:
            self.prepare_reply(message_id, reply_all=False)
        elif chosen == reply_all_action:
            self.prepare_reply(message_id, reply_all=True)
        elif chosen == trash_action:
            self.confirm_message_action(message_id, "trash")
        elif chosen == delete_action:
            self.confirm_message_action(message_id, "delete")

    def prepare_reply(self, message_id, reply_all=False):
        if self.reply_worker is not None and self.reply_worker.isRunning():
            return
        self.status_label.setText("Préparation de la réponse…")
        self.reply_worker = MailReplyDataWorker(
            self.settings, message_id, folder=self.current_folder,
            reply_all=reply_all, parent=self
        )
        self.reply_worker.reply_data_ready.connect(self.open_reply_dialog)
        self.reply_worker.failed.connect(self.mail_error)
        self.reply_worker.finished.connect(self.reply_finished)
        self.reply_worker.start()

    def open_reply_dialog(self, draft):
        dialog = SendMailDialog(self.settings, self, draft=draft)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_folders()
            self.refresh_messages()

    def reply_finished(self):
        self.reply_worker = None

    def confirm_message_action(self, message_id, operation):
        if self.action_worker is not None and self.action_worker.isRunning():
            return
        if operation == "trash":
            title = "Mettre à la corbeille"
            prompt = "Déplacer ce message vers la corbeille ?"
            trash_folder = next((
                f["name"] for f in self.mail_folders
                if f.get("is_trash") or any(word in f["name"].casefold() for word in ("trash", "corbeille", "poubelle", "deleted"))
            ), None)
        else:
            title = "Suppression définitive"
            prompt = "Supprimer définitivement ce message ? Cette action est irréversible."
            trash_folder = None
        answer = QMessageBox.question(
            self, title, prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText("Opération sur le message…")
        self.refresh_button.setEnabled(False)
        self.action_worker = MailActionWorker(
            self.settings, self.current_folder, message_id, operation,
            trash_folder=trash_folder, parent=self
        )
        self.action_worker.action_done.connect(self.message_action_done)
        self.action_worker.failed.connect(self.mail_error)
        self.action_worker.finished.connect(self.action_finished)
        self.action_worker.start()

    def message_action_done(self, operation, folder):
        if operation == "trash":
            self.status_label.setText("Message déplacé vers la corbeille.")
        else:
            self.status_label.setText("Message supprimé définitivement.")
        self.message_view.clear()
        self.load_folders()
        self.refresh_messages()

    def action_finished(self):
        self.action_worker = None
        self.refresh_button.setEnabled(True)

    def select_message(self, current, previous=None):
        if current is None or not self.settings:
            return
        if self.message_worker is not None and self.message_worker.isRunning():
            return
        message_id = current.data(Qt.ItemDataRole.UserRole)
        self.status_label.setText("Chargement du message…")
        self.message_worker = MailMessageWorker(
            self.settings, message_id, folder=self.current_folder, parent=self
        )
        self.message_worker.message_ready.connect(self.display_message)
        self.message_worker.failed.connect(self.mail_error)
        self.message_worker.finished.connect(self.message_finished)
        self.message_worker.start()

    def display_message(self, subject, sender, recipient, date, body):
        header = (
            f"<h2>{escape(subject)}</h2>"
            f"<p><b>De :</b> {escape(sender)}<br>"
            f"<b>À :</b> {escape(recipient)}<br>"
            f"<b>Date :</b> {escape(date)}</p><hr>"
        )
        # Les courriels HTML sont rendus avec leur mise en forme. Les images
        # distantes/pixels de suivi sont retirés dans _prepare_mail_html.
        if re.search(r"<\s*(?:html|body|div|p|table|span|h[1-6])\b", body, flags=re.I):
            rendered_body = _prepare_mail_html(body)
            self.message_view.setHtml(header + rendered_body)
        else:
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_folders()  # actualise aussi les compteurs des dossiers
            self.refresh_messages()

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
