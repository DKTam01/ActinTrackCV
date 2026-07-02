"""Shared Qt dialog helpers for the ActinTrackCV GUI."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QMessageBox, QWidget


def information(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def warning(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def critical(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def ask_yes_no(
    parent: Optional[QWidget],
    title: str,
    text: str,
    *,
    informative: str = "",
) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setWindowTitle(title)
    box.setText(text)
    if informative:
        box.setInformativeText(informative)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return box.exec() == QMessageBox.StandardButton.Yes
