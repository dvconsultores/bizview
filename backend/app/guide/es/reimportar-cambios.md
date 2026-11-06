# Reimportar cambios

## Para qué sirve

Cuando tu IA devuelve una segunda versión del mismo proyecto, se importa otra vez y queda como una
revisión nueva: el proyecto es el mismo, con su historial y sus tableros.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

1. Pide a tu IA el cambio concreto sobre el mismo paquete.
2. Abre [Proyectos](app:/proyectos) y pulsa **Importar proyecto**.
3. Elige el zip. BizView reconoce el identificador y avisa de que es una revisión del proyecto que ya
   existe.
4. Revisa el resumen: cuántos archivos se añaden, cambian o se eliminan, y qué identificadores se
   tocan.
5. Importa. El proyecto queda en borrador con esos cambios.
6. Pulsa **Aplicar proyecto** cuando esté listo.

Si prefieres un proyecto aparte, marca la casilla de copia: se crea con otro identificador y con
identificadores de artefacto nuevos.

## Opciones

- Todo queda en el historial: se puede comparar una revisión con otra y volver atrás.
- Si el borrador tiene cambios hechos en el editor, BizView pide confirmación antes de reemplazarlo.
- Sin la CLI también funciona: la importación valida igual.

## Problemas frecuentes

- Un zip con otro identificador crea un proyecto nuevo en vez de una revisión: revisa `project.yaml`.
- Un cambio que renombra un reporte cambia su URL `/r/<id>`; los enlaces ya compartidos dejan de
  funcionar.

## Relacionados

- Reimportar un proyecto
- Historial del proyecto
- Corregir los problemas
