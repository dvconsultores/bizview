# Implementation plan: Envío semanal de facturas del día

**Spec**: [spec.md](./spec.md)

## Summary

Implementar una distribución YAML que programe el envío del reporte `facturas-dia` cada lunes a las 07:00, dirigida al rol `admin`, con PDF adjunto y las reglas de compartición definidas en la spec.

## Artifacts

| Archivo | Propósito |
|---------|-----------|
| `distributions/envio-semanal.yaml` | Define la programación, destinatarios y opciones de entrega/compartición de la distribución |

## Mapping

- `id`: `envio-semanal`
- `spec`: `specs/003-envio-semanal`
- `report`: `facturas-dia`
- `subscriptions[0].frequency`: `weekly`
- `subscriptions[0].weekday`: `0` (lunes)
- `subscriptions[0].hour`: `7`
- `subscriptions[0].period`: `last_7_days`
- `subscriptions[0].recipients.roles`: `[admin]`
- `subscriptions[0].attach_pdf`: `true`
- `subscriptions[0].link_days`: `7`
- `share.allowed`: `true`
- `share.max_days`: `30`

## Verification

Ejecutar `bizview validate --write-lock` y confirmar que no hay errores; si los hay, corregirlos y repetir hasta validación limpia.
