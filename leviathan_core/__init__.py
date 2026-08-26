#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN Core v3.0
===================
Sistema modular de Red Team con 22 módulos.
"""
__version__ = "3.0.0"
__author__ = "Harold Paredes / SourceSeal Red Team"

# Banner disponible para mostrar al iniciar
def show_banner():
    from leviathan_core.banner import show_banner as _show
    _show()
