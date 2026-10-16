
"""Impression des documents PDF."""

from pathlib import Path

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QDialog, QMessageBox


def print_pdf(pdf_path, parent=None):
    """Ouvre le dialogue d'impression et imprime toutes les pages du PDF."""

    pdf_path = Path(pdf_path)

    if not pdf_path.is_file():
        QMessageBox.warning(
            parent,
            "Impression impossible",
            "Le fichier PDF est introuvable.",
        )
        return

    document = QPdfDocument(parent)
    status = document.load(str(pdf_path))

    if status == QPdfDocument.Status.Error:
        QMessageBox.warning(
            parent,
            "Impression impossible",
            "Le document PDF n'a pas pu être chargé.",
        )
        document.close()
        return

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setResolution(300)

    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimer le document PDF")

    if dialog.exec() != QDialog.DialogCode.Accepted:
        document.close()
        return

    painter = QPainter()

    if not painter.begin(printer):
        QMessageBox.warning(
            parent,
            "Impression impossible",
            "Impossible de démarrer l'impression.",
        )
        document.close()
        return

    try:
        printable_rect = printer.pageRect(
            QPrinter.Unit.DevicePixel
        )
        available_size = printable_rect.size()

        for page in range(document.pageCount()):
            page_size = document.pagePointSize(page)

            if page_size.width() <= 0 or page_size.height() <= 0:
                continue

            # Adapter la page à la zone imprimable sans la déformer.
            scale = min(
                available_size.width() / page_size.width(),
                available_size.height() / page_size.height(),
            )

            render_size = QSize(
                max(1, round(page_size.width() * scale)),
                max(1, round(page_size.height() * scale)),
            )

            image = document.render(page, render_size)

            if image.isNull():
                raise RuntimeError(
                    f"Impossible de rendre la page {page + 1}."
                )

            x = printable_rect.x() + (
                available_size.width() - image.width()
            ) // 2

            y = printable_rect.y() + (
                available_size.height() - image.height()
            ) // 2

            painter.drawImage(QPoint(x, y), image)

            if page < document.pageCount() - 1:
                if not printer.newPage():
                    raise RuntimeError(
                        "Impossible de préparer la page suivante."
                    )

    except Exception as exc:
        QMessageBox.warning(
            parent,
            "Erreur d'impression",
            str(exc),
        )

    finally:
        painter.end()
        document.close()
