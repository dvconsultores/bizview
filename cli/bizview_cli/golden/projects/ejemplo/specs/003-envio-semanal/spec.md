# Envío semanal de facturas del día

**Tipo**: distribucion

**Status**: Implemented

**Created**: 2026-10-01

**Input**: "Enviar cada lunes a las 07:00 el reporte facturas-dia (últimos 7 días) a administradores con PDF"

## Purpose

Distribuir automáticamente el reporte `facturas-dia` a los administradores cada lunes por la mañana, con los datos de los últimos 7 días y en formato PDF, para facilitar la revisión semanal de ventas sin intervención manual.

## Clarifications

- Q: ¿El envío debe ocurrir incluso si coincide con un día festivo que caiga en lunes? → A: Sí, se mantiene el horario fijo del lunes a las 07:00 sin excepciones por festivos; si se desea una regla distinta, deberá especificarse en una futura iteración.

## Distribution

**Reporte**: facturas-dia

| Frecuencia | Día | Hora | Periodo |
|------------|------|------|---------|
| semanal | lunes | 07:00 | last_7_days |

- Roles destinatarios: `admin`
- PDF adjunto: sí
- Enlace disponible: 7 días
- Compartir permitido: hasta 30 días

## Acceptance scenarios

1. Dado que es lunes a las 07:00, cuando se ejecuta la distribución, entonces se envía a los administradores un correo con el reporte `facturas-dia` en PDF y los datos del período `last_7_days`.
2. Dado que la distribución ya fue enviada, cuando un administrador abre el enlace, entonces puede acceder al reporte durante 7 días y compartirlo hasta un máximo de 30 días desde el envío.

## Success criteria

1. Los administradores reciben el PDF del reporte cada lunes a las 07:00 sin errores de validación (`bizview validate --write-lock` devuelve 0).

## Assumptions

- El reporte `facturas-dia` acepta el período `last_7_days` y su configuración de acceso ya contempla el rol `admin`.
