"""Point d’entrée de Nuage Explorer."""
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from nuage_explorer.common import obtain_vault, clear_preview_temp
from nuage_explorer.main_window import MainWindow
from nuage_explorer.style import STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setApplicationName("Nextcloud Explorer")

    cleanup_errors = clear_preview_temp()
    if cleanup_errors:
        QMessageBox.warning(
            None,
            "Nettoyage temporaire incomplet",
            "Certains fichiers temporaires n'ont pas pu être supprimés :\\n\\n"
            + "\\n".join(cleanup_errors[:10]),
        )

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
