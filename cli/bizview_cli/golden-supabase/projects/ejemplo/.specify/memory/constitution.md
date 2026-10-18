# Constitución del proyecto

**Version**: 1.0.0 | **Ratified**: 2026-10-01

## Principios

1. Sin especificación no hay trabajo: todo cambio exige spec previa y aprobación.
2. Las especificaciones se numeran por proyecto con prefijo incremental (001, 002, 003...).
3. Los artefactos son declarativos: SQL de solo lectura o YAML; nada de lógica imperativa incrustada.
4. Queda prohibido incluir credenciales, secretos o valores de filas reales en specs o artefactos.
5. Se reutilizan integraciones existentes; no se duplican orígenes de datos sin necesidad justificada.
6. Las distribuciones se definen únicamente por roles de acceso; nunca por personas concretas.
7. Antes de commitear se ejecuta `bizview validate --write-lock` y se corrigen todos los errores.
