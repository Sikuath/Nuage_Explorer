
"""Feuille de style Qt de Nextcloud Explorer."""

STYLE = """
/* ==================================================
   BASE ET FOND DE FENÊTRE
   ================================================== */

* {
    font-family: "Segoe UI", sans-serif;
    font-size: 10pt;
}

QWidget {
    color: #263449;
}

QMainWindow,
QWidget#central {
    background-color: #f3f6fb;
}

QWidget#central {
    border: none;
}

QLabel {
    background-color: transparent;
}

/* Titres de la zone de travail */

QLabel#appTitle {
    color: #17263d;
    font-size: 23pt;
    font-weight: 700;
}

QLabel#muted {
    color: #75849a;
    font-size: 9pt;
}

QLabel#sectionTitle {
    color: #ffffff;
    font-size: 14pt;
    font-weight: 700;
}

/* ==================================================
   BARRE LATÉRALE
   ================================================== */

QFrame#sidebar {
    background-color: #17263d;
    border: none;
}

QFrame#sidebar QLabel {
    color: #dce6f4;
}

QFrame#sidebar QLabel#sectionTitle {
    color: #ffffff;
    font-size: 14pt;
    font-weight: 700;
}

QFrame#sidebar QLabel#muted {
    color: #92a6c1;
    font-size: 8pt;
    font-weight: 600;
}

QFrame#sidebar QFrame#sidebarSeparator {
    background-color: #30425d;
    border: none;
    max-height: 1px;
    margin-top: 5px;
    margin-bottom: 5px;
}

/* ==================================================
   BOUTONS
   ================================================== */

QPushButton {
    color: #34445b;
    background-color: #ffffff;
    border: 1px solid #d7e0ec;
    border-radius: 8px;
    padding: 9px 13px;
    min-height: 19px;
    font-weight: 500;
}

QPushButton:hover {
    color: #1d4f86;
    background-color: #edf4fd;
    border-color: #b7cde8;
}

QPushButton:pressed {
    background-color: #dce9fa;
    border-color: #91b3df;
}

QPushButton:disabled {
    color: #a6b0be;
    background-color: #edf0f5;
    border-color: #e0e5ec;
}

/* Action principale */

QPushButton#primary {
    color: #ffffff;
    background-color: #2563a6;
    border: 1px solid #2563a6;
    font-weight: 600;
}

QPushButton#primary:hover {
    color: #ffffff;
    background-color: #1e528d;
    border-color: #1e528d;
}

QPushButton#primary:pressed {
    background-color: #173f70;
    border-color: #173f70;
}

QPushButton#primary:disabled {
    color: #dce6f4;
    background-color: #8ba8ca;
    border-color: #8ba8ca;
}

/* Navigation de la barre latérale */

QFrame#sidebar QPushButton#navButton {
    color: #dce6f4;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    text-align: left;
    padding: 10px 12px;
    font-weight: 500;
}

QFrame#sidebar QPushButton#navButton:hover {
    color: #ffffff;
    background-color: #263b59;
    border-color: #304968;
}

QFrame#sidebar QPushButton#navButton:pressed {
    color: #ffffff;
    background-color: #304968;
}

QFrame#sidebar QPushButton#navButton:checked {
    color: #ffffff;
    background-color: #315783;
    border-color: #426b9a;
    font-weight: 600;
}

QFrame#sidebar QPushButton#navButton:disabled {
    color: #71839d;
    background-color: transparent;
    border-color: transparent;
}

/* ==================================================
   TABLEAU DES FICHIERS
   ================================================== */

QTableWidget {
    color: #263449;
    background-color: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #e0e7f0;
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: #dcecff;
    selection-color: #17365d;
    outline: none;
    padding: 4px;
}

QTableWidget::item {
    padding: 8px;
    border: none;
}

QTableWidget::item:hover {
    background-color: #edf4fd;
    color: #17365d;
}

QTableWidget::item:selected {
    background-color: #dcecff;
    color: #17365d;
}

QHeaderView {
    background-color: #f3f6fb;
}

QHeaderView::section {
    color: #61728a;
    background-color: #f3f6fb;
    font-size: 9pt;
    font-weight: 600;
    padding: 11px 9px;
    border: none;
    border-bottom: 1px solid #e0e7f0;
}

QTableCornerButton::section {
    background-color: #f3f6fb;
    border: none;
}

/* ==================================================
   ARBORESCENCE NUAGE
   ================================================== */

QFrame#sidebar QTreeWidget {
    color: #dce6f4;
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
    show-decoration-selected: 1;
}

QFrame#sidebar QTreeWidget::item {
    min-height: 25px;
    padding: 5px 3px;
    border-radius: 5px;
}

QFrame#sidebar QTreeWidget::item:hover {
    color: #ffffff;
    background-color: #263b59;
}

QFrame#sidebar QTreeWidget::item:selected {
    color: #ffffff;
    background-color: #315783;
}

/* ==================================================
   ARBORESCENCE LOCALE : WINDOWS ET CLÉS USB
   ================================================== */

QFrame#sidebar QTreeView#localTree {
    color: #dce6f4;
    background-color: transparent;
    border: none;
    outline: none;
    padding: 2px;
    show-decoration-selected: 1;
}

QFrame#sidebar QTreeView#localTree::item {
    min-height: 23px;
    padding: 4px 3px;
    border-radius: 5px;
}

QFrame#sidebar QTreeView#localTree::item:hover {
    color: #ffffff;
    background-color: #263b59;
}

QFrame#sidebar QTreeView#localTree::item:selected {
    color: #ffffff;
    background-color: #315783;
}

/* ==================================================
   CHAMPS DE SAISIE
   ================================================== */

QLineEdit,
QTextEdit,
QPlainTextEdit {
    color: #263449;
    background-color: #ffffff;
    border: 1px solid #d1dbe8;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #2563a6;
    selection-color: #ffffff;
}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus {
    border: 1px solid #5794d6;
}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled {
    color: #8a97a9;
    background-color: #edf1f6;
}

/* ==================================================
   LISTES ET MENUS DÉROULANTS
   ================================================== */

QComboBox {
    color: #263449;
    background-color: #ffffff;
    border: 1px solid #d1dbe8;
    border-radius: 7px;
    padding: 8px 10px;
    min-height: 18px;
}

QComboBox:hover {
    border-color: #a9c5ed;
}

QComboBox:focus {
    border-color: #5794d6;
}

QComboBox QAbstractItemView {
    color: #263449;
    background-color: #ffffff;
    border: 1px solid #d5dfeb;
    selection-background-color: #dcecff;
    selection-color: #17365d;
    outline: none;
    padding: 4px;
}

/* Menus contextuels */

QMenu {
    color: #263449;
    background-color: #ffffff;
    border: 1px solid #d5dfeb;
    padding: 5px;
}

QMenu::item {
    padding: 8px 28px 8px 12px;
    border-radius: 5px;
}

QMenu::item:selected {
    color: #17365d;
    background-color: #edf4fd;
}

QMenu::separator {
    height: 1px;
    background-color: #e4eaf2;
    margin: 5px 8px;
}

/* ==================================================
   BARRES DE DÉFILEMENT
   ================================================== */

QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    margin: 3px;
}

QScrollBar::handle:vertical {
    background-color: #c5d1e0;
    border-radius: 5px;
    min-height: 25px;
}

QScrollBar::handle:vertical:hover {
    background-color: #9eafc5;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    border: none;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    margin: 3px;
}

QScrollBar::handle:horizontal {
    background-color: #c5d1e0;
    border-radius: 5px;
    min-width: 25px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    border: none;
}

/* ==================================================
   BARRE D'ÉTAT
   ================================================== */

QLabel#status {
    color: #526780;
    background-color: #eaf0f8;
    padding: 10px 13px;
    border: 1px solid #e0e7f0;
    border-radius: 8px;
}

/* ==================================================
   BARRES DE PROGRESSION
   ================================================== */

QProgressBar {
    color: #263449;
    background-color: #e3eaf3;
    border: none;
    border-radius: 4px;
    text-align: center;
    min-height: 8px;
    max-height: 14px;
}

QProgressBar::chunk {
    background-color: #3478c5;
    border-radius: 4px;
}

QFrame#sidebar QProgressBar {
    color: #ffffff;
    background-color: #30425d;
    border: none;
    border-radius: 4px;
    text-align: center;
    min-height: 8px;
    max-height: 8px;
}

QFrame#sidebar QProgressBar::chunk {
    background-color: #65a9f3;
    border-radius: 4px;
}

/* ==================================================
   INFO-BULLES
   ================================================== */

QToolTip {
    color: #ffffff;
    background-color: #263449;
    border: 1px solid #40536c;
    padding: 6px 8px;
    border-radius: 5px;
}

/* ==================================================
   THÈME SOMBRE : ZONE CENTRALE
   ================================================== */

QMainWindow,
QWidget#central {
    background-color: #17263d;
    color: #dce6f4;
}

/* Textes de la zone centrale */

QWidget#central QLabel {
    color: #dce6f4;
    background-color: transparent;
}

QWidget#central QLabel#appTitle {
    color: #ffffff;
    font-size: 23pt;
    font-weight: 700;
}

QWidget#central QLabel#muted {
    color: #9aacc5;
    font-size: 9pt;
}

/* Boutons centraux */

QWidget#central QPushButton {
    color: #dce6f4;
    background-color: #263b59;
    border: 1px solid #405675;
    border-radius: 8px;
    padding: 9px 13px;
    min-height: 19px;
}

QWidget#central QPushButton:hover {
    color: #ffffff;
    background-color: #304968;
    border-color: #6486ae;
}

QWidget#central QPushButton:pressed {
    background-color: #315783;
}

QWidget#central QPushButton:disabled {
    color: #71839d;
    background-color: #202f46;
    border-color: #30425d;
}

/* Bouton principal d'importation */

QWidget#central QPushButton#primary {
    color: #ffffff;
    background-color: #3478c5;
    border: 1px solid #438bd8;
    font-weight: 600;
}

QWidget#central QPushButton#primary:hover {
    background-color: #438bd8;
    border-color: #65a9f3;
}

/* Tableau de fichiers */

QWidget#central QTableWidget {
    color: #dce6f4;
    background-color: #1d2e47;
    alternate-background-color: #223650;
    border: 1px solid #354b68;
    border-radius: 10px;
    gridline-color: transparent;
    selection-background-color: #315783;
    selection-color: #ffffff;
}

QWidget#central QTableWidget::item {
    color: #dce6f4;
    padding: 8px;
    border: none;
}

QWidget#central QTableWidget::item:hover {
    background-color: #293f5c;
    color: #ffffff;
}

QWidget#central QTableWidget::item:selected {
    background-color: #315783;
    color: #ffffff;
}

QWidget#central QHeaderView::section {
    color: #aebed3;
    background-color: #263b59;
    font-weight: 600;
    padding: 11px 9px;
    border: none;
    border-bottom: 1px solid #405675;
}

/* Barre d'état */

QWidget#central QLabel#status {
    color: #c8d6e8;
    background-color: #223650;
    border: 1px solid #354b68;
    border-radius: 8px;
    padding: 10px 13px;
}

/* Barre de progression */

QWidget#central QProgressBar {
    color: #ffffff;
    background-color: #30425d;
    border: none;
    border-radius: 4px;
}

QWidget#central QProgressBar::chunk {
    background-color: #65a9f3;
    border-radius: 4px;
}

/* Champs de saisie centraux */

QWidget#central QLineEdit,
QWidget#central QTextEdit,
QWidget#central QPlainTextEdit,
QWidget#central QComboBox {
    color: #dce6f4;
    background-color: #1d2e47;
    border: 1px solid #405675;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #315783;
    selection-color: #ffffff;
}

QWidget#central QLineEdit:focus,
QWidget#central QTextEdit:focus,
QWidget#central QPlainTextEdit:focus,
QWidget#central QComboBox:focus {
    border: 1px solid #65a9f3;
}

    /* ==================================================
       FENÊTRE D'APERÇU
       ================================================== */

    QDialog#previewDialog {
        background-color: #17263d;
        color: #dce6f4;
    }

    QDialog#previewDialog QLabel {
        color: #dce6f4;
        background-color: transparent;
    }

    QDialog#previewDialog QPdfView {
        background-color: #1d2e47;
        border: 1px solid #354b68;
        border-radius: 8px;
    }

    QDialog#previewDialog QPushButton {
        color: #dce6f4;
        background-color: #263b59;
        border: 1px solid #405675;
        border-radius: 8px;
        padding: 8px 14px;
        min-height: 20px;
    }

    QDialog#previewDialog QPushButton:hover {
        color: #ffffff;
        background-color: #304968;
        border-color: #6486ae;
    }

    QDialog#previewDialog QPushButton:pressed {
        background-color: #315783;
    }

"""
