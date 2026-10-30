# Fuente «<nombre>» — estructura

<!-- Plantilla. Bizview la genera con `bizview describe "<nombre>"`; si la escribes a mano, sigue
este formato y nunca incluyas credenciales, hosts, filas ni datos personales. Borra la sección
que no aplique. -->

Tipo: postgresql | rest | soap · Zona horaria de los datos: <America/Caracas> ·
Notas: <volumen aproximado, frecuencia de cambio, limitaciones del plan o de la API>

## PostgreSQL

### Esquema `<schema>`

#### Tabla `<tabla>` — ~<n> filas · fecha: `<columna_fecha>` (<min> → <max>)

| Columna | Tipo | Nulo | Clave | Personal | Nota |
|---|---|---|---|---|---|
| id | integer | no | PK | | |
| created_at | timestamptz | no | | | fecha del registro |
| customer_email | text | sí | | **sí** | excluir salvo petición explícita |
| total_amount | numeric(12,2) | no | | | |
| status | text | no | | | valores: draft, paid, cancelled |
| order_id | uuid | sí | FK → orders.id | | |

<!-- repite por tabla; incluye solo las tablas relevantes para el encargo -->

## REST

Base: configurada en Bizview (no se incluye) · Autenticación: gestionada por Bizview ·
Presupuesto: <llamadas/mes del plan>.

### Petición `<nombre>` — GET `<ruta relativa>`

Params: `<clave=valor>`. Paginación: `<none | page | offset | cursor>` (<detalle>).
`records: "$.<ruta al array u objeto>"`. Campos por elemento:

| JSONPath | Tipo | Nota |
|---|---|---|
| `$.id` | integer | clave primaria |
| `$.created_at` | timestamptz (ISO 8601) | usar como fecha |
| `$.amount` | numeric | |
| `$.customer.email` | text | **personal**, excluir |

<!-- repite por petición -->

## SOAP

Operación `<nombre>`: entrada `<tipo>` (campos…), salida `<tipo>` (campos…).

## Observaciones

- <qué no existe en la fuente y la IA no debe inventar>
- <campos calculables a partir de otros>
- <datos personales: lista de columnas>
