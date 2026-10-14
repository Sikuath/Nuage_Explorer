"""Feuille de style Qt de l’application."""

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

QFrame#sidebarSeparator {
    background-color: #d8e2ed;
    border: none;
    max-height: 1px;
    margin-top: 5px;
    margin-bottom: 5px;
}

QTreeView#localTree {
    background-color: transparent;
    border: none;
    outline: none;
    color: #334155;
    font-size: 12px;
    padding: 2px;
}

QTreeView#localTree::item {
    padding: 4px 2px;
    border-radius: 4px;
}

QTreeView#localTree::item:hover {
    background-color: #e5eef8;
}

QTreeView#localTree::item:selected {
    background-color: #d5e6fa;
    color: #1e40af;
}

"""

