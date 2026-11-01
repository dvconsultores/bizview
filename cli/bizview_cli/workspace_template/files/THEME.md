# Temas: cómo escribir uno fuera de Bizview

Un tema es **un archivo de datos**: colores y unas pocas decisiones de forma. Nunca CSS, nunca una
fuente, nunca marcado. Cualquiera —una persona o cualquier IA— puede escribirlo aquí fuera y entra
en Bizview sólo si `bizview theme validate` lo acepta.

El contrato completo es `.bizview/schemas/theme.schema.json`. Este documento es la página que le
das a una IA para que produzca el archivo.

## Qué tiene que producir

Un archivo `themes/<id>.yaml` por tema, con esta forma exacta:

```yaml
id: acme-azul
name: "Acme · azul"
name_en: "Acme · blue"
version: 1
strategy: categorical          # categorical | sequential (una sola familia de color)
light:
  surface: "#FFFFFF"           # fondo de la página
  card: "#F8FAFC"             # fondo de tarjetas
  text: "#0F172A"             # texto principal
  muted: "#64748B"            # texto secundario y etiquetas de eje
  grid: "#E2E8F0"             # líneas de rejilla
  primary: "#0B5FFF"          # acento de la interfaz
  positive: "#16A34A"
  negative: "#DC2626"
  neutral: "#64748B"
  delta_positive: "#BBF7D0"    # fondo de la píldora de subida
  delta_negative: "#FECDD3"    # fondo de la píldora de bajada
  series:                      # de 3 a 8 colores, en el orden en que se pintan las barras
    - "#0B5FFF"
    - "#F59E0B"
    - "#10B981"
    - "#8B5CF6"
    - "#EF4444"
    - "#06B6D4"
    - "#F97316"
    - "#84CC16"
dark:                          # las mismas claves, sobre el fondo oscuro
  surface: "#0B1220"
  card: "#111C2E"
  text: "#E2E8F0"
  muted: "#94A3B8"
  grid: "#1E293B"
  primary: "#60A5FA"
  positive: "#4ADE80"
  negative: "#FB7185"
  neutral: "#CBD5E1"
  delta_positive: "#14532D"
  delta_negative: "#7F1D1D"
  series:
    - "#60A5FA"
    - "#FBBF24"
    - "#34D399"
    - "#A78BFA"
    - "#F87171"
    - "#22D3EE"
    - "#FB923C"
    - "#A3E635"
shape:                         # opcional; cada valor sale de una lista cerrada
  radius: md                   # sm | md | lg
  density: normal              # compact | normal
  kpi_scale: lg                # md | lg | xl
  font: sans                   # sans | serif | mono
  badge: filled                # filled | outline
```

## Las reglas que se comprueban

El validador mide, no opina. Un tema se rechaza si:

| Regla | Valor |
|---|---|
| Claves | sólo las de arriba; cualquier otra se rechaza (un tema es dato, no CSS) |
| Colores | `#RRGGBB`, sin alfa; `series` con 3 a 8 entradas |
| Tamaño | 20 KB como máximo |
| `text` sobre `surface` | contraste ≥ 4.5:1 |
| `primary` sobre `surface` | ≥ 3:1 |
| Cada serie sobre `surface` | ≥ 3:1 |
| Series vecinas | distancia ΔE ≥ 10 (en un tema `sequential`, escalón de L* ≥ 5) |
| `positive` frente a `negative` | ΔE ≥ 25 (no se confunden) |
| `grid` sobre `surface` | < 1.8:1 (una rejilla no compite con los datos) |

Se comprueba en `light` y en `dark`, cada uno contra su propio fondo. Cada rechazo nombra el par de
tokens y la medida: `light.text vs light.surface: 3.9:1 (needs 4.5:1)`.

## Cómo iterar sin el servidor

```sh
bizview theme validate themes/acme-azul.yaml      # 0 válido · 1 problemas · 2 no se pudo leer
bizview theme preview themes/acme-azul.yaml --out preview.svg
```

`preview.svg` dibuja la misma tarjeta que la página Apariencia (un indicador con su píldora, cuatro
barras y una línea de dos series), en claro y en oscuro, con los colores del tema.

## La instrucción para una IA

> Escribe **sólo** el archivo YAML, sin explicación y sin bloque de código. Parte de la guía de
> marca, la captura o la descripción que te doy. Respeta las claves de la lista, usa `#RRGGBB` y
> comprueba el contraste de `text` sobre `surface` (≥ 4.5:1), de `primary` y de cada serie sobre
> `surface` (≥ 3:1) y que ninguna serie se parezca a su vecina. Si no puedes cumplir una regla con
> los colores de la marca, oscurece o aclara el color en lugar de cambiar la regla.

## Cómo entra en Bizview

Se sube en **Administración → Apariencia** (se valida otra vez, y si algo falla verás cada problema
con su ruta), o se copia en `themes/<id>.yaml` dentro del proyecto y entra con el proyecto al
importarlo. Un tema del producto no se puede reemplazar ni eliminar; para cambiarlo, duplícalo con
otro `id`.

El informe que lo usa lo nombra en `report.yaml`:

```yaml
layout:
  theme:
    id: acme-azul      # el tema del informe
    mode: auto         # auto | light | dark
```

`mode: dark` deja el área del informe en oscuro aunque la persona tenga la aplicación en claro; el
PDF siempre se genera con la variante clara. `palette:` se sigue aceptando como alias obsoleto de
`id` durante una versión.
