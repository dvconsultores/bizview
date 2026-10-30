# Fuente Supabase

## Para qué sirve

Lee datos de un proyecto Supabase a través de su API REST, sin abrir la base de datos.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. En [Abrir Nueva fuente](app:/admin/fuentes/nueva) elige el **Tipo de fuente** Supabase.
2. Escribe la URL del proyecto (también se acepta terminada en `/rest/v1`).
3. Pega una service key; se recomienda una clave de solo lectura.
4. Pulsa **Probar conexión** y luego **Guardar**.

## Opciones

- BizView solo hace lecturas (GET) contra Supabase.
- Para lógica con varias tablas (uniones, cálculos), crea una vista en Supabase y léela como una
  tabla.

## Problemas frecuentes

- La conciliación (comparar totales con el origen) no está disponible para Supabase; solo para
  PostgreSQL.
