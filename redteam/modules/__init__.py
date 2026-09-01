"""Módulos locales extensibles de SourceSeal.

Cada módulo valida el engagement antes de operar y produce evidencia
auditable sellada con SHA-256. El watcher recarga módulos en caliente
cuando hay cambios, sin reiniciar el dashboard.
"""

from . import tactical_executor
from . import recon
from . import enumeration
from . import vulnerability
from . import reporting
