import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


STYLE = """
QWidget {
    background-color: #171a21;
    color: #e6e8ee;
    font-family: Segoe UI;
    font-size: 14px;
}
QLabel#title {
    font-size: 26px;
    font-weight: 600;
}
QLabel#subtitle {
    color: #a5adbd;
}
QLineEdit {
    background-color: #242936;
    border: 1px solid #41495a;
    border-radius: 7px;
    padding: 11px;
    selection-background-color: #4779bd;
}
QPushButton {
    background-color: #356ac3;
    border: none;
    border-radius: 7px;
    padding: 11px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #447bd6;
}
"""


class UnlockDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nuage Explorer — Déverrouillage")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(16)

        title = QLabel("Nuage Explorer")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Déverrouillez votre coffre")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.password = QLineEdit()
        self.password.setPlaceholderText("Mot de passe maître")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self.accept)

        button = QPushButton("Déverrouiller")
        button.clicked.connect(self.accept)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.password)
        layout.addWidget(button)

    def master_password(self):
        return self.password.text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nuage Explorer")
        self.resize(1000, 650)

        welcome = QLabel(
            "Bienvenue dans Nuage Explorer\n\n"
            "Le coffre sera intégré à cette interface à l'étape suivante."
        )
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.setCentralWidget(welcome)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    unlock = UnlockDialog()
    if unlock.exec() != QDialog.DialogCode.Accepted:
        return

    # Le mot de passe n'est pas enregistré.
    # L'authentification réelle sera ajoutée à l'étape suivante.
    password = unlock.master_password()
    if not password:
        return

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
