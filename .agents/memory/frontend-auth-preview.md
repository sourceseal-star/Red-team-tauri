---
name: Frontend authentication preview behavior
description: Protected dashboard routes must fail visibly without causing a reload loop
---

Las respuestas 401/403 del dashboard deben limpiar una sesión inválida y mostrar un aviso accionable sin recargar continuamente la aplicación. Una pestaña nueva sin token también debe mostrar el estado de autenticación de forma visible.

**Why:** El preview podía quedar como una pantalla negra cuando un token local vencido disparaba recargas repetidas antes de que el operador pudiera corregir la sesión.

**How to apply:** Mantener el interceptor global como capa de aviso y conservar las rutas protegidas; nunca resolver el problema eliminando la autenticación ni mostrando credenciales en el cliente.