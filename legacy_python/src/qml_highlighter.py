"""Syntax highlighter Python untuk editor skrip (Mode Programmer).

Dipasang ke QTextDocument milik TextArea QML (lewat QQuickTextDocument).
Ringan & fail-safe: highlight murni tampilan, tidak mengubah isi teks.
"""

import keyword
import re

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    """Pewarnaan sintaks Python sederhana (keyword, builtin, string, angka, komentar)."""

    _IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
    _NUMBER = re.compile(r"\b\d+\.?\d*\b")
    _STRING = re.compile(r"(\"\"\".*?\"\"\"|'''.*?'''|\".*?\"|'.*?')")

    def __init__(self, document):
        super().__init__(document)
        self._kw = _fmt("#569CD6", bold=True)
        self._builtin = _fmt("#4EC9B0")
        self._string = _fmt("#CE9178")
        self._number = _fmt("#B5CEA8")
        self._comment = _fmt("#6A9955", italic=True)
        self._keywords = set(keyword.kwlist)
        self._builtins = {
            "True", "False", "None", "ctx", "self", "PARAMS", "on_bar",
            "abs", "min", "max", "round", "len", "range", "sum", "float", "int",
            "bool", "str", "enumerate", "sorted", "zip", "map", "filter", "all", "any",
            "return", "def", "if", "elif", "else", "for", "while",
        }

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        try:
            # Angka
            for m in self._NUMBER.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), self._number)
            # Identifier -> keyword / builtin
            for m in self._IDENT.finditer(text):
                w = m.group()
                if w in self._keywords:
                    self.setFormat(m.start(), len(w), self._kw)
                elif w in self._builtins:
                    self.setFormat(m.start(), len(w), self._builtin)
            # String (setelah identifier agar menimpa)
            for m in self._STRING.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), self._string)
            # Komentar (paling akhir, dari '#' ke akhir baris)
            hash_pos = text.find("#")
            if hash_pos >= 0:
                self.setFormat(hash_pos, len(text) - hash_pos, self._comment)
        except Exception:  # noqa: BLE001 - highlight tak boleh crash editor
            pass
