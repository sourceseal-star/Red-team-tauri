#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN REPORTERS - Módulos de Informes
==========================================
Paquete de generadores de informes.
"""

from .json_reporter import JSONReporter
from .html_reporter import HTMLReporter
from .pdf_reporter import PDFReporter

__all__ = [
    "JSONReporter",
    "HTMLReporter",
    "PDFReporter"
]


def register_all():
    """Registra todos los reporters."""
    return [
        JSONReporter(),
        HTMLReporter(),
        PDFReporter()
    ]
