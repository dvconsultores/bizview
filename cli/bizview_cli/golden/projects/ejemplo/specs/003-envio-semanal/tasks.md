# Tasks: Envío semanal de facturas del día

**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

- [X] T001 Crear `distributions/envio-semanal.yaml` con los campos definidos en el plan
- [X] T002 Implementar el horario exactamente como indica la spec: semanal, lunes, 07:00, período `last_7_days`
- [X] T003 Ejecutar `bizview validate` y corregir todos los errores hasta validación limpia
- [X] T004 Establecer Status en `Implemented` y ejecutar `bizview validate --write-lock` antes del commit
