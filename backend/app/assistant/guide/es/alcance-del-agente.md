# Qué hace y qué no hace el agente

## Para qué sirve

Explica los límites del agente, para saber qué pedirle y qué esperar.

## Quién puede usarlo

Solo el **Superusuario**.

## Cómo se hace

- Solo atiende reportes, tableros, integraciones, ETL, fuentes de datos, las specs del proyecto y
  el uso de BizView. Para otros temas responde con una frase fija y unos ejemplos, sin consultar
  la IA.
- Cambia archivos solo dentro de un comando (`/speckit-…`). En un mensaje sin comando puede mirar
  fuentes y archivos y responder, y te propone el comando adecuado con un botón **Insertar**.
- Lee la estructura de las fuentes (tablas, columnas, tipos) y cifras agregadas, nunca filas ni
  credenciales.
- El texto que lee de fuentes y archivos es un dato, nunca una orden: si encuentra instrucciones
  ahí, te las menciona pero no las sigue.
- Las columnas con datos personales se excluyen salvo que las pidas nombrándolas y lo confirmes;
  la spec lo deja escrito.
- Nunca aplica un proyecto: aplicar es siempre una acción tuya.

## Opciones

- Cada conversación tiene un presupuesto de uso que crece solo hasta un máximo; el agente trabaja
  solo varias rondas y se detiene al terminar, al quedarse sin presupuesto o cuando lo detienes.
