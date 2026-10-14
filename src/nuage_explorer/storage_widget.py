
"""Widget de stockage NUAGE avec récupération asynchrone du quota."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .storage import get_storage_quota


class StorageWorker(QThread):
    """Interroge le quota sans bloquer l'interface graphique."""

    result_ready = Signal(object)

    def __init__(self, profile):
        super().__init__()
        self.profile = dict(profile)

    def run(self):
        result = get_storage_quota(
            self.profile.get("url", ""),
            self.profile.get("username", ""),
            self.profile.get("password", ""),
        )
        self.result_ready.emit(result)


class StorageWidget(QWidget):
    """Affichage compact du stockage dans la barre latérale."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._profile = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(6)

        separator = QFrame()
        separator.setObjectName("sidebarSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        title = QLabel("⚙ Stockage Nextcloud")
        title.setObjectName("muted")
        layout.addWidget(title)

        self.storage_label = QLabel("Quota indisponible")
        self.storage_label.setObjectName("muted")
        self.storage_label.setWordWrap(True)
        layout.addWidget(self.storage_label)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)
        self.storage_bar.setTextVisible(False)
        self.storage_bar.setFixedHeight(6)
        self.storage_bar.setMaximumWidth(240)
        self.storage_bar.setToolTip(
            "Utilisation de l'espace de stockage Nextcloud"
        )
        layout.addWidget(self.storage_bar)

    def set_profile(self, profile):
        """Associe le widget au profil actif."""
        self._profile = dict(profile) if profile else None

        if self._profile:
            self.refresh()
        else:
            self.storage_label.setText("Quota indisponible")
            self.storage_bar.setValue(0)

    def refresh(self):
        """Demande une actualisation asynchrone du quota."""
        if not self._profile:
            self.storage_label.setText("Quota indisponible")
            self.storage_bar.setValue(0)
            return

        # Ne pas lancer plusieurs requêtes simultanées.
        if self._worker is not None and self._worker.isRunning():
            return

        self.storage_label.setText("Actualisation du stockage…")

        worker = StorageWorker(self._profile)
        self._worker = worker
        worker.result_ready.connect(self._display_quota)
        worker.start()

    def shutdown(self):
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(10000)
            
    def _display_quota(self, quota):
        if quota is None:
            self.storage_label.setText("Quota indisponible")
            self.storage_bar.setValue(0)
            self.storage_bar.setToolTip(
                "Le serveur ne communique pas le quota "
                "ou la requête n'a pas abouti."
            )
            return

        used = quota["used"]
        total = quota["total"]
        available = quota["available"]

        # Go décimaux pour correspondre à l'affichage du portail.
        used_gb = used / 1_000_000_000
        total_gb = total / 1_000_000_000
        available_gb = available / 1_000_000_000
        percent = min(100, round(used * 100 / total))

        self.storage_label.setText(
            f"{used_gb:.1f}".replace(".", ",")
            + " Go utilisés sur "
            + f"{total_gb:.1f}".replace(".", ",")
            + " Go"
        )

        self.storage_bar.setValue(percent)
        self.storage_bar.setToolTip(
            f"{percent} % utilisés — "
            f"{available_gb:.1f}".replace(".", ",")
            + " Go disponibles"
        )
