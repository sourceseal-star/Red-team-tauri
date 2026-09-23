---
name: Pydantic runtime compatibility
description: Compatibility constraint for strict manifest validation in the Termux/Replit Python runtime
---

Cuando se mantienen `root_validator` de Pydantic 1 en un entorno que puede ejecutar
Pydantic 2, hay que declarar `skip_on_failure=True`; de lo contrario el módulo
falla durante la importación, antes de que FastAPI pueda arrancar.

**Why:** El runtime actual usa Pydantic 2, mientras el fallback debe conservar
compatibilidad con instalaciones Termux que todavía pueden tener Pydantic 1.

**How to apply:** Preferir APIs compatibles entre ambas versiones y ejecutar
`py_compile` además de las pruebas HTTP después de cualquier cambio de esquema.