#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEVIATHAN Banner — ASCII Art
============================
Mostrar al iniciar cualquier módulo de LEVIATHAN.
"""

BANNER = r"""
======================================================================
      ▄▄▄       ▄████▄   ██ █▀ █████  ██▀███   ▒█████   ███▄    █  
      ▒████▄    ▒██▀ ▀█   ██▄█▒  ▓█   ▀ ▓██ ▒ ██▒▒██▒  ██▒ ██ ▀█   █  
      ▒██  ▀█▄  ▒▓█    ▄ ▓███▄░  ▒███   ▓██ ░▄█ ▒▒██░  ██▒▓██  ▀█ ██▒ 
      ░██▄▄▄▄██ ▒▓▓▄ ▄██▒▓██ █▄  ▒▓█  ▄ ▒██▀▀█▄  ▒██   ██░▓██▒  ▐▌██▒
       ▓█   ▓██▒▒▓███▀ ░▒██▒ █▄ ░▒████▒░██▓ ▒██▒░ ████▓▒░▒██░   ▓██░
       ▒▒   ▓▒█░░ ░▒ ▒  ░▒ ▒▒ ▓░ ░░ ▒░ ░░ ▒▓ ░▒▓▒░ ▒░▒░▒░ ░ ▒░   ▒ ▒ 
        ▒   ▒▒ ░  ░  ▒   ░ ░▒ ▒░  ░ ░  ░  ░▒ ░ ▒░  ░ ▒ ▒░ ░ ░░   ░ ▒░
        ░   ▒   ░        ░ ░░ ░    ░     ░░   ░ ░ ░ ░ ▒     ░   ░ ░ 
            ░  ░░ ░      ░  ░      ░  ░   ░         ░ ░           ░ 
                 ░                                                    
======================================================================
   SOURCESEAL INTELLIGENCE | LEVIATHAN v3.0 | ARTO + SEAL ACTIVE
======================================================================
"""

SUBTITLE = "  Escaneo Distribuido | Explotación Autónoma | Inteligencia de Amenazas\n"


def show_banner():
    """Imprime el banner de LEVIATHAN."""
    print(BANNER)
    print(SUBTITLE)


def get_banner():
    """Retorna el banner como string."""
    return BANNER + "\n" + SUBTITLE


if __name__ == "__main__":
    show_banner()
