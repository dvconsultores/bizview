from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from typing import Any

import yaml
from bizview_cli import authoring, layout, sqlsafety
from sqlalchemy.orm import Session

from app.assistant import auto, origin, preview, readiness
from app.assistant.commands import guard, pipeline, registry, resolve, runs
from app.assistant.commands.registry import REGISTRY
from app.engine import direct
from app.i18n import t
from app.projects import compose, fs, history
from app.projects import specs as project_specs
from app.projects.workview import real
from app.services.audit import record
from app.sources.describe import describe
from app.sources.service import by_name, list_all, secrets_of
from app.workspace.service import active

log = logging.getLogger(__name__)

_STAGE_OF_COMMAND = {
    "speckit-specify": "specify",
    "speckit-clarify": "clarify",
    "speckit-plan": "plan",
    "speckit-tasks": "tasks",
    "speckit-analyze": "analyze",
    "speckit-implement": "implement",
    "speckit-converge": "converge",
    "speckit-verify": "verify",
}
MAX_TOOL_RESULT_CHARS = 60_000
_MAX_STRING_CHARS = 200
_MAX_LIST_ITEMS = 500
_MAX_EDIT_OPS = 50
NOTES_TEXT_CHARS = 300
NOTES_MAX_ITEMS = 20
_DROP_KEYS = {
    "sample",
    "samples",
    "example",
    "examples",
    "value",
    "values",
    "rows",
    "data",
    "default",
    "host",
    "hostname",
    "port",
    "user",
    "username",
    "password",
    "secret",
    "token",
    "url",
    "dsn",
    "database",
    "dbname",
    "connection",
}


class ToolError(Exception):
    """Error de herramienta con mensaje en español."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sanitize(obj: Any) -> Any:
    """Devuelve una copia sin valores sensibles ni datos de filas."""
    if isinstance(obj, Mapping):
        result: dict[str, Any] = {}
        for key, value in obj.items():
            if key.lower() in _DROP_KEYS:
                continue
            result[key] = sanitize(value)
        return result
    if isinstance(obj, list):
        return [sanitize(item) for item in obj[:_MAX_LIST_ITEMS]]
    if isinstance(obj, str):
        return obj[:_MAX_STRING_CHARS]
    return obj


def compact_tables(description: Any) -> Any:
    """Table descriptions as one short text per column ("nombre tipo", "?" when nullable): the
    same structure in a fraction of the tokens (a source can have hundreds of columns)."""
    if not isinstance(description, dict) or not isinstance(description.get("tables"), list):
        return description
    tables = []
    for table in description["tables"]:
        if not isinstance(table, dict):
            continue
        cols = [f"{c.get('name')} {c.get('type')}{'?' if c.get('nullable') else ''}"
                for c in table.get("columns") or [] if isinstance(c, dict)]
        tables.append({k: v for k, v in {**table, "columns": cols}.items()
                       if k not in ("estimated_rows",) and v not in (None, [], "")})
    return {**description, "tables": tables,
            "columns_format": "«nombre tipo»; «?» al final = admite nulos"}


def _cap_describe_result(obj: Any) -> dict[str, Any]:
    """Cap describe_source output keeping as much as fits."""
    cleaned = sanitize(obj)
    text = json.dumps(cleaned, ensure_ascii=False, default=str)
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return cleaned

    if isinstance(cleaned, dict) and "tables" in cleaned:
        tables = cleaned["tables"]
        kept: list[dict[str, Any]] = []
        for table in tables:
            candidate = dict(cleaned)
            candidate["tables"] = [*kept, table]
            if len(json.dumps(candidate, ensure_ascii=False, default=str)) > MAX_TOOL_RESULT_CHARS:
                candidate["tables"] = kept
                candidate["truncated"] = True
                return candidate
            kept.append(table)
        cleaned["truncated"] = True
        return cleaned

    return {"truncated": True}


def _cap_workspace_result(obj: dict[str, Any]) -> dict[str, Any]:
    """Cap get_workspace output, dropping specs documents then artifact files."""
    text = json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return obj

    result = json.loads(json.dumps(obj, ensure_ascii=False, default=str))
    specs = result.get("specs")
    if isinstance(specs, dict):
        for value in specs.values():
            if isinstance(value, dict):
                value.pop("documents", None)
        if len(json.dumps(result, ensure_ascii=False, default=str)) <= MAX_TOOL_RESULT_CHARS:
            result["truncated"] = True
            return result

    for section in ("integrations", "reports"):
        artifacts = result.get(section)
        if isinstance(artifacts, dict):
            for value in artifacts.values():
                if isinstance(value, dict):
                    value.pop("files", None)
            if len(json.dumps(result, ensure_ascii=False, default=str)) <= MAX_TOOL_RESULT_CHARS:
                result["truncated"] = True
                return result

    result["truncated"] = True
    return result


def _bump(session: Any, key: str) -> None:
    """Incrementa un contador de stats reasignando el diccionario para que SQLAlchemy lo vea."""
    stats = dict(session.stats or {})
    stats[key] = int(stats.get(key) or 0) + 1
    session.stats = stats


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_sources",
        "description": (
            "Lista las fuentes de datos disponibles por nombre y tipo, y si admiten "
            "reportes directos (direct). «bi» es la base BI de esta instalación."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_source",
        "description": (
            "Describe la estructura de una fuente de datos (tablas, columnas, tipos y claves) "
            "y marca las columnas que parecen datos personales en `personal`; exclúyelas salvo "
            "que el usuario las pida. No devuelve filas ni credenciales. Si ya la consultaste "
            "en esta conversación devuelve la nota guardada; usa refresh: true para leerla de "
            "nuevo. Con name «bi» describe la base BI de esta instalación (tablas que un "
            "reporte directo puede leer)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre de la fuente"},
                "path": {
                    "type": ["string", "null"],
                    "description": "Ruta opcional dentro de la fuente",
                },
                "refresh": {
                    "type": ["boolean", "null"],
                    "description": "true para volver a leer la estructura",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "profile_source",
        "description": (
            "Perfil agregado de una tabla: total de filas y, por columna, proporción de nulos "
            "y número de valores distintos; mínimo y máximo solo en columnas de fecha. Nunca "
            "devuelve valores. En Supabase/REST solo el total de filas. Con name «bi» perfila "
            "una tabla (esquema.tabla) de la base BI en solo lectura. Si la tabla supera el "
            "umbral de filas para reportes directos devuelve warning."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre de la fuente"},
                "table": {
                    "type": "string",
                    "description": "Tabla como esquema.tabla (PostgreSQL), nombre de tabla "
                                   "(Supabase) o ruta (REST)",
                },
            },
            "required": ["name", "table"],
        },
    },
    {
        "name": "check_query",
        "description": (
            "Comprueba una consulta del borrador (path: integrations/<id>/queries/*.sql o "
            "requests/*.yaml), un reporte directo (path: reports/<id>/report.yaml con "
            "source = direct.source: ejecuta la consulta de KPI generada con LIMIT 0 en "
            "una sesión de solo lectura → columnas y tipos) o un SQL suelto contra la "
            "fuente sin leer filas: SQL de solo lectura ejecutado con LIMIT 0 → columnas "
            "y tipos de salida, comparadas con las columnas del dataset; petición GET de "
            "una página de tamaño 1 → si cada campo existe y su tipo JSON. Indica path o "
            "sql, no ambos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Nombre de la fuente"},
                "path": {"type": ["string", "null"], "description": "Archivo del borrador"},
                "sql": {"type": ["string", "null"], "description": "SQL suelto"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "get_workspace",
        "description": (
            "Obtiene el manifiesto, integraciones, reportes y specs "
            "del espacio de trabajo activo."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_current_spec",
        "description": (
            "Cambia la spec actual de la conversación a `spec_id` (una carpeta existente del "
            "proyecto). Úsala cuando el usuario pida trabajar sobre otra spec; nunca le pidas "
            "que la seleccione a mano. Queda registrada en la transcripción."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "spec_id": {"type": "string",
                            "description": "Carpeta de la spec, p. ej. 002-ventas-facturacion."},
            },
            "required": ["spec_id"],
        },
    },
    {
        "name": "get_authoring_guide",
        "description": (
            "Consulta la guía de autoría de Bizview. Temas disponibles: "
            "index, workspace, integration, request, report, spec, transform, "
            "example, example-direct, example-supabase, example-large, o "
            "fragment:<esquema>#<puntero> para un fragmento de esquema."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": ["string", "null"],
                    "description": "Tema o fragmento de esquema a consultar",
                }
            },
            "required": [],
        },
    },
    {
        "name": "propose_draft",
        "description": (
            "Escribe (crea o sobrescribe) los archivos indicados en la carpeta del proyecto "
            "de la conversación. Rutas relativas al proyecto: project.yaml, "
            "specs/NNN-nombre/spec.md|plan.md|tasks.md|..., integrations/<id>/..., "
            "reports/<id>/report.yaml, distributions/<id>.yaml. Los archivos no listados no "
            "se tocan. Un archivo existente debe haberse leído antes con read_draft."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "object",
                    "description": "Mapa de ruta (relativa al proyecto) a contenido de texto",
                    "additionalProperties": {"type": "string"},
                },
                "summary": {"type": "string", "description": "Resumen corto del cambio"},
            },
            "required": ["files"],
        },
    },
    {
        "name": "edit_draft",
        "description": (
            "Cambia archivos del proyecto. Cada operación puede ser: write (crear o "
            "sobrescribir; un archivo existente debe haberse leído antes), replace "
            "(reemplazar la única ocurrencia de old por new) o delete (eliminar un archivo "
            "leído antes)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ops": {
                    "type": "array",
                    "description": "Lista ordenada de operaciones sobre archivos del proyecto",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["write", "replace", "delete"],
                            },
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["op", "path"],
                    },
                    "minItems": 1,
                },
                "summary": {
                    "type": ["string", "null"],
                    "description": "Resumen corto del cambio",
                },
            },
            "required": ["ops"],
        },
    },
    {
        "name": "read_draft",
        "description": (
            "Lee el contenido actual de archivos del proyecto (incluye cambios hechos en el "
            "editor o por otras conversaciones). Devuelve siempre el contenido: si el archivo "
            "no cambió desde una lectura anterior lo dice, pero lo vuelve a incluir."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "description": "Rutas de archivos del proyecto a leer",
                    "items": {"type": "string"},
                    "minItems": 1,
                }
            },
            "required": ["paths"],
        },
    },
    {
        "name": "apply_fix",
        "description": (
            "Aplica el arreglo determinista que el validador ya calculó para un problema del "
            "proyecto (los que muestran «Arreglo:» y un id). Úsala en lugar de edit_draft para "
            "esos problemas: no reescribe el archivo a mano ni gasta tokens en YAML."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "problem_id": {
                    "type": "string",
                    "description": "Id del problema tal como aparece en la validación",
                }
            },
            "required": ["problem_id"],
        },
    },
    {
        "name": "run_preview",
        "description": (
            "Ejecuta la vista previa del borrador válido en esquemas temporales (nunca en los "
            "datos publicados) y devuelve el resultado: estado, filas por dataset y "
            "comprobaciones. Los reportes directos del borrador se muestran una vez en vivo "
            "desde su fuente (solo lectura, sin guardar valores). Necesaria para quedar "
            "«Listo para aplicar»; hay un máximo de vistas previas por conversación."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_command",
        "description": (
            "Avanza este run a una etapa de Spec Kit sobre una spec del proyecto: cierra la "
            "etapa anterior y abre la nueva con la misma ejecución auditada que /speckit-…. "
            "Después sigue trabajando con las herramientas de esa etapa. Úsala para encadenar "
            "specify → plan → tasks → implement; nunca pidas al usuario ejecutar el comando ni "
            "elegir la spec."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "enum": ["speckit-specify", "speckit-clarify", "speckit-plan",
                             "speckit-tasks", "speckit-implement", "speckit-converge",
                             "speckit-verify"],
                    "description": "Comando de la etapa a abrir.",
                },
                "spec": {
                    "type": ["string", "null"],
                    "description": "Carpeta NNN-nombre; nula solo cuando la etapa la crea "
                                   "(/speckit-specify).",
                },
                "arguments": {
                    "type": "string",
                    "description": "Resto de argumentos del comando (el objetivo o el tema).",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "apply_draft",
        "description": (
            "Aplica el proyecto de la conversación como una versión nueva del workspace: la "
            "misma validación, comprobaciones, bloqueo y auditoría que el botón Aplicar. Solo "
            "existe con un contrato vigente que permita aplicar, y como máximo las veces que el "
            "contrato indica."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_notes",
        "description": (
            "Guarda tus notas de trabajo de esta conversación: objetivo, decisiones, "
            "paso actual, hecho y siguiente. Se muestran en «## Estado» en cada ronda; "
            "úsalas para no repetir trabajo y para retomar tras «continúa»."
        ),
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {
                "goal": {
                    "type": ["string", "null"],
                    "description": "Objetivo actual de la conversación.",
                },
                "decisions_add": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Decisiones nuevas a añadir.",
                },
                "step": {
                    "type": ["string", "null"],
                    "description": "Paso actual del flujo de trabajo.",
                },
                "done_add": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Acciones completadas a añadir.",
                },
                "next": {
                    "type": ["string", "null"],
                    "description": "Siguiente acción a realizar.",
                },
            },
        },
    },
    {
        "name": "get_app_guide",
        "description": "guide.tool.get_app_guide",            # catalogue key (_localized)
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {"topic": {"type": ["string", "null"],
                                     "description": "guide.tool.get_app_guide.topic"}},
        },
    },
    {
        "name": "get_project_overview",
        "description": "guide.tool.get_project_overview",     # catalogue key (_localized)
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "finish_command",
        "description": (
            "Termina el comando en curso cuando su trabajo está hecho (no lo llames si "
            "esperas una respuesta del usuario). summary: una línea con lo que hizo."
        ),
        "parameters": {
            "type": "object",
            "required": ["summary"],
            "properties": {"summary": {"type": "string", "description": "Resumen de una línea."}},
        },
    },
    {
        "name": "suggest_command",
        "description": (
            "En un mensaje sin comando, propone al usuario el comando que hace lo que pide "
            "(se muestra un botón «Insertar»; no lo ejecuta). Máximo 3 por respuesta."
        ),
        "parameters": {
            "type": "object",
            "required": ["command", "spec"],
            "properties": {
                "command": {"type": "string",
                            "enum": [n for n in REGISTRY if REGISTRY[n].provider],
                            "description": "Nombre del comando, p. ej. speckit-plan."},
                "spec": {"type": "string",
                         "description": "Carpeta de la spec sobre la que corre el comando, "
                                        "p. ej. 002-ventas-facturacion. Cadena vacía para "
                                        "/speckit-specify, /speckit-constitution, /fix y /ayuda."},
                "arguments": {"type": ["string", "null"],
                              "description": "Resumen corto (máximo 160 caracteres) de lo que el "
                                             "comando hará, no el brief completo: el detalle va en "
                                             "el texto de tu respuesta."},
            },
        },
    },
]

MAX_SUGGESTIONS = 3
MAX_SUGGESTION_ARGUMENTS = 160
# Offered even after the discovery limit (023: the guide is never discovery).
ALWAYS_OFFERED = frozenset({"finish_command", "suggest_command", "get_app_guide"})
SUGGESTIONS_KEY = "turn_suggestions"


def command_run(session: Any) -> Any:
    """The running command of the turn (set by the service on the WorkView), or None."""
    return getattr(session, "command_run", None)


def command_def(session: Any) -> Any:
    run = command_run(session)
    return REGISTRY.get(run.command) if run is not None else None


DISCOVERY_TOOLS = frozenset(
    {"list_sources", "describe_source", "profile_source", "get_authoring_guide", "get_workspace"}
)
RUN_READS_KEY = "run_reads"
RUN_REREADS_KEY = "run_rereads"
MEMO_TOOLS = frozenset({"describe_source", "profile_source", "get_authoring_guide", "check_query"})
DRAFT_TOOLS = ("propose_draft", "edit_draft", "read_draft", "update_notes", "apply_fix")
REPEAT_NOTE = (
    "Ya consultaste esto en esta ejecución; usa el resultado anterior y "
    "avanza al borrador."
)
DISCOVERY_DONE_TEXT = (
    "Fase de descubrimiento terminada: propón ahora el borrador completo con "
    "propose_draft usando lo que ya sabes (notas de trabajo)."
)
RUN_CALLS_KEY = "run_calls"
RUN_DISCOVERY_KEY = "run_discovery"
BRIEF_CHARS = 300


def is_discovery(name: str, args: dict[str, Any]) -> bool:
    """True cuando la llamada cuenta como descubrimiento."""
    return name in DISCOVERY_TOOLS or (name == "check_query" and not args.get("path"))


def _norm_ref(value: str, kind: str | None) -> str:
    """Normaliza una referencia (tabla/ruta) para el memo del run."""
    return origin.normalise_table(kind, value).lstrip("/").casefold()


def normalise_target(tool: str, args: dict[str, Any], kind: str | None = None) -> str | None:
    """Devuelve la clave normalizada del objetivo de una herramienta memoizable, o None."""
    if tool == "describe_source":
        name = args.get("name")
        if not isinstance(name, str) or not name:
            return None
        src = name.strip().casefold()
        path = args.get("path")
        if isinstance(path, str) and path.strip():
            p = _norm_ref(path, kind)
        else:
            p = ""
        return f"{src}|{p}"
    if tool == "profile_source":
        name = args.get("name")
        table = args.get("table")
        if (not isinstance(name, str) or not name or not isinstance(table, str) or not table):
            return None
        src = name.strip().casefold()
        return f"{src}|{_norm_ref(table, kind)}"
    if tool == "get_authoring_guide":
        topic = args.get("topic")
        if topic is not None and not isinstance(topic, str):
            return None
        return topic or "index"
    if tool == "check_query":
        source = args.get("source")
        if not isinstance(source, str) or not source:
            return None
        src = source.strip().casefold()
        path = args.get("path")
        sql = args.get("sql")
        if isinstance(path, str) and path.strip():
            return f"{src}|path:{path.strip()}"
        if isinstance(sql, str) and sql.strip():
            return f"{src}|sql:{' '.join(sql.split())}"
        return None
    return None


def _source_kind(db: Session, name: str, args: dict[str, Any]) -> str | None:
    """Devuelve el kind de la fuente mencionada en los argumentos, o None."""
    source_name = None
    if name in ("describe_source", "profile_source"):
        candidate = args.get("name")
        if isinstance(candidate, str) and candidate:
            source_name = candidate
    elif name == "check_query":
        candidate = args.get("source")
        if isinstance(candidate, str) and candidate:
            source_name = candidate
    if source_name is None:
        return None
    source = by_name(db, source_name)
    return source.kind if source is not None else None


def reset_run(session: Any) -> None:
    """Limpia los contadores del run actual en working_state (solo reasigna si existen)."""
    state = session.working_state or {}
    if (RUN_CALLS_KEY in state or RUN_DISCOVERY_KEY in state or RUN_READS_KEY in state
            or RUN_REREADS_KEY in state):
        state = dict(state)
        state.pop(RUN_CALLS_KEY, None)
        state.pop(RUN_DISCOVERY_KEY, None)
        state.pop(RUN_READS_KEY, None)
        state.pop(RUN_REREADS_KEY, None)
        session.working_state = state


def discovery_count(session: Any) -> int:
    """Número de llamadas de descubrimiento en el run actual."""
    state = session.working_state or {}
    return int(state.get(RUN_DISCOVERY_KEY) or 0)


def has_draft(session: Any) -> bool:
    """True when the project has specs or artifacts (its metadata files do not count, 020)."""
    files = (session.draft or {}).get("files") or {}
    return any(path not in readiness.PROJECT_META for path in files)


LOCALIZED_TOOLS = frozenset({"get_app_guide", "get_project_overview"})


def _localized(spec: dict[str, Any]) -> dict[str, Any]:
    """Feature 023 tools carry catalogue keys; render them in the request language."""
    if spec["name"] not in LOCALIZED_TOOLS:
        return spec
    params = json.loads(json.dumps(spec["parameters"]))
    for prop in params.get("properties", {}).values():
        prop["description"] = t(prop["description"])
    return {**spec, "description": t(spec["description"]), "parameters": params}


# Feature 040 (D): the tools a stage may be sent. Offering the whole catalogue for every stage
# (and letting one turn run all of them) is what produced 626 tool calls and 14 M tokens for one
# integration. Guides and app topics are reached through `get_app_guide(topic)`, never one tool
# per topic.
MAX_TOOLS_PER_ROUND = 25

_PIPELINE_TOOLS = frozenset({"run_command", "finish_command", "set_current_spec"})

TOOL_GROUPS: dict[str, frozenset[str]] = {
    # A plain Auto message keeps the whole execution channel (028: a spent contract must not leave
    # the conversation with read tools only); a command narrows it.
    "default": (guard.INSPECTION_TOOLS
                | {"suggest_command", "finish_command", "run_command", "run_preview",
                   "apply_draft"}),
    "speckit-all": guard.INSPECTION_TOOLS | {"edit_draft", "run_preview"} | _PIPELINE_TOOLS,
    "speckit-constitution": guard.INSPECTION_TOOLS | {"edit_draft"} | _PIPELINE_TOOLS,
    "speckit-specify": (guard.INSPECTION_TOOLS
                        | {"propose_draft", "edit_draft"} | _PIPELINE_TOOLS),
    "speckit-clarify": guard.INSPECTION_TOOLS | {"edit_draft"} | _PIPELINE_TOOLS,
    "speckit-plan": guard.INSPECTION_TOOLS | {"propose_draft", "edit_draft"} | _PIPELINE_TOOLS,
    "speckit-tasks": guard.INSPECTION_TOOLS | {"edit_draft"} | _PIPELINE_TOOLS,
    "speckit-checklist": guard.INSPECTION_TOOLS | {"edit_draft"} | _PIPELINE_TOOLS,
    "speckit-analyze": guard.INSPECTION_TOOLS | _PIPELINE_TOOLS,
    "speckit-implement": (guard.INSPECTION_TOOLS
                          | {"propose_draft", "edit_draft", "check_query", "run_preview"}
                          | _PIPELINE_TOOLS),
    "speckit-converge": (guard.INSPECTION_TOOLS
                         | {"edit_draft", "check_query", "run_preview"} | _PIPELINE_TOOLS),
    "speckit-verify": (guard.INSPECTION_TOOLS | {"check_query", "run_preview"}
                       | _PIPELINE_TOOLS),
    "fix": (guard.INSPECTION_TOOLS
            | {"edit_draft", "check_query", "run_preview"} | _PIPELINE_TOOLS),
    "ayuda": guard.INSPECTION_TOOLS | _PIPELINE_TOOLS,
}


def tool_group(definition: Any) -> frozenset[str]:
    """The group of a command (a plain message gets the inspection group)."""
    return TOOL_GROUPS.get(getattr(definition, "name", "") or "default") or TOOL_GROUPS["default"]


def offered_tool_specs(session: Any, app_settings: Any) -> tuple[list[dict[str, Any]], bool]:
    """Devuelve las tool specs ofrecidas y si están restringidas a la fase de borrador.

    Feature 028: el modo de la conversación y el contrato vigente deciden el conjunto (FR-000,
    FR-003); `edit` conserva exactamente el comportamiento anterior. Feature 040: además, solo el
    grupo de la etapa en curso, con un techo duro de `MAX_TOOLS_PER_ROUND`.
    """
    definition = command_def(session)
    base = guard.allowed_tools(definition)
    contract = auto.contract_of(session)
    allowed = auto.offered_names(auto.mode_of(session), contract, frozenset(base))
    group = tool_group(definition)
    if auto.mode_of(session) == "ask":
        group = frozenset(group | auto.ASK_TOOLS)
    allowed = frozenset(allowed & group)
    offered = [_localized(spec) for spec in TOOL_SPECS if spec["name"] in allowed]
    if (not has_draft(session)
            and discovery_count(session) >= int(app_settings.ai_agent_discovery_limit)):
        specs = [t for t in offered if t["name"] in DRAFT_TOOLS or t["name"] in ALWAYS_OFFERED]
        return specs[:MAX_TOOLS_PER_ROUND], True
    return offered[:MAX_TOOLS_PER_ROUND], False


def _brief(name: str, result: dict[str, Any]) -> str:
    """Genera un resumen corto del resultado para el memo del run."""
    if not isinstance(result, dict):
        return ""
    text = ""
    error = result.get("error")
    if error:
        text = f"error: {error}"
    elif name == "profile_source":
        parts = [f"{result.get('row_count')} filas"]
        if result.get("solo_conteo"):
            parts.append("solo conteo (sin nulos ni distintos)")
        cols = result.get("columns") or []
        for c in cols[:20]:
            if isinstance(c, dict):
                parts.append(
                    f"{c.get('name')} (nulos {c.get('null_ratio')}, distintos {c.get('distinct')})"
                )
        text = "; ".join(parts)
    elif name == "check_query":
        if result.get("ok"):
            names = [
                c.get("name") for c in (result.get("columns") or [])
                if isinstance(c, dict) and c.get("name")
            ]
            if not names:
                names = [
                    f.get("column") for f in (result.get("fields") or [])
                    if isinstance(f, dict) and f.get("column")
                ]
            text = f"correcta; columnas: {', '.join(str(n) for n in names)}"
        else:
            parts = []
            missing = [str(x) for x in (result.get("missing") or [])]
            extra = [str(x) for x in (result.get("extra") or [])]
            undefined = [str(x) for x in (result.get("missing_columns") or [])]
            if missing:
                parts.append(f"faltan: {', '.join(missing)}")
            if extra:
                parts.append(f"sobran: {', '.join(extra)}")
            if undefined:
                parts.append(f"campos sin definir: {', '.join(undefined)}")
            text = "con errores" + (f"; {'; '.join(parts)}" if parts else "")
    return text[:BRIEF_CHARS]


def _repeat_result(
    session: Any, name: str, args: dict[str, Any], entry: dict[str, Any], kind: str | None
) -> tuple[dict[str, Any], str]:
    """Construye el resultado de una llamada repetida en el mismo run."""
    if name == "describe_source":
        path = args.get("path")
        norm_path = None
        if isinstance(path, str) and path.strip():
            norm_path = origin.normalise_table(kind, path)
            if not norm_path:
                norm_path = None
        cached = origin.cached_description(session, args["name"], norm_path)
        result = dict(sanitize(cached)) if cached else {
            "anterior": entry.get("brief") or entry.get("summary")
        }
        summary = t("assistant.summary.used_cached_structure", name=args['name'])
    elif name == "get_authoring_guide":
        # At most once per topic per run: later calls get the pointer, never the full guide again.
        result = {"ya_consultado": True, "topic": args.get("topic") or "index",
                  "summary": entry.get("summary") or "",
                  "note": t("assistant.summary.repeated_guide",
                            topic=args.get("topic") or "index")}
        summary = t("assistant.summary.repeated_guide", topic=args.get('topic') or 'index')
    else:
        result = {"anterior": entry.get("brief") or entry.get("summary")}
        summary = t("assistant.summary.repeated_cached", name=name)
    result["ya_consultado"] = True
    result["note"] = REPEAT_NOTE
    return result, summary


def _remember_call(session: Any, key: str, entry: dict[str, Any] | None, name: str,
                   summary: str, result: dict[str, Any], refresh: bool) -> None:
    """Actualiza el memo del run con la llamada actual (lee y reasigna working_state)."""
    state = dict(session.working_state or {})
    calls = dict(state.get(RUN_CALLS_KEY) or {})
    calls[key] = {
        "count": (int((entry or {}).get("count") or 0) + 1),
        "summary": summary[:BRIEF_CHARS],
        "brief": _brief(name, result),
        "refreshed": bool((entry or {}).get("refreshed")) or refresh,
    }
    state[RUN_CALLS_KEY] = calls
    session.working_state = state


def _bump_call(session: Any, key: str) -> None:
    """Incrementa el contador de una llamada repetida sin tocar summary ni brief."""
    state = dict(session.working_state or {})
    calls = dict(state.get(RUN_CALLS_KEY) or {})
    entry = dict(calls.get(key) or {})
    entry["count"] = int(entry.get("count") or 0) + 1
    calls[key] = entry
    state[RUN_CALLS_KEY] = calls
    session.working_state = state


def _check_query_deps(session: Any, path: str) -> str:
    """Devuelve el sufijo de memo para check_query: SHA del archivo y de la integración."""
    draft_files = (session.draft or {}).get("files") or {}
    text = draft_files.get(path)
    query_sha = readiness.file_sha(text)[:12] if text is not None else "-"
    spec_sha = "-"
    match = origin.QUERY_FILE.match(path) or origin.REQUEST_FILE.match(path)
    if match:
        iid = match.group(1)
        spec_text = draft_files.get(f"integrations/{iid}/integration.yaml")
        spec_sha = readiness.file_sha(spec_text)[:12] if spec_text is not None else "-"
    return f"{query_sha}|{spec_sha}"


_AUTO_CHANNEL = ("run_command", "run_preview", "apply_draft")


def _allowed_tools(session: Any) -> frozenset[str]:
    """The command guard's set, widened by the Auto tools when a contract is live (feature 028)."""
    base = frozenset(guard.allowed_tools(command_def(session)))
    return auto.offered_names(auto.mode_of(session), auto.contract_of(session), base)


def _guard_check(session: Any, name: str) -> None:
    """Feature 021's server-side limit, with the Auto tools of a live contract added."""
    if name in _allowed_tools(session):
        return
    try:
        guard.check_tool(command_def(session), name)
    except guard.GuardError as err:
        raise ToolError(str(err)) from err


def _authorisation_revoked(db: Session, run: Any) -> bool:
    """Feature 028 (edge): the super user that confirmed the contract lost the role mid-run."""
    from app.models import AppUser

    actor = db.get(AppUser, run.confirmed_by) if run.confirmed_by else None
    return actor is None or not actor.is_active or not actor.is_superuser


def _mode_check(db: Session, session: Any, name: str, args: dict[str, Any],
                app_settings: Any) -> None:
    """Feature 028: refusa la llamada si el modo o el contrato no la permiten (FR-000, FR-003).

    Se ejecuta antes del memo y del despacho, así que ninguna llamada fuera del contrato toca el
    proyecto, la fuente ni el proveedor. La denegación es un resultado de herramienta, no un error
    del turno: el modelo puede adaptarse o cerrar el run con `blocked:<reason>`.
    """
    # Feature 028 (owner, 2026-10-21): the first stage/preview/apply of an Auto turn opens the run
    # contract, so the conversation never falls back to read-only tools after a contract is spent.
    needs_contract = (name in _AUTO_CHANNEL and auto.mode_of(session) == "auto"
                      and auto.live_contract(session) is None)
    if needs_contract:
        from app.assistant import service as assistant_service

        assistant_service.ensure_auto_contract(db, session, goal=args.get("summary"))
    contract = auto.contract_of(session)
    refusal = auto.mode_gate(session, name, args, contract)
    if refusal is not None:
        raise ToolError(refusal.message)
    run = auto.live_contract(session)
    if contract is None or run is None:
        return
    if _authorisation_revoked(db, run):
        raise ToolError(t("assistant.run.revoked_role"))
    if name in ("describe_source", "profile_source", "check_query"):
        refusal = auto.source_refusal(contract, args.get("name") or args.get("source"),
                                      args.get("table"))
        if refusal is not None:
            raise ToolError(refusal.message)
    if name not in ("run_preview", "apply_draft", "run_command"):
        return
    limits = auto.limit_refusal(
        contract, run,
        previews=int(run.previews or 0) + 1 if name == "run_preview" else None,
        applies=int(run.applies or 0) + 1 if name == "apply_draft" else None,
        wall_clock=True, settings=app_settings)
    if limits is not None:
        raise ToolError(limits.message)


def run_tool(
    db: Session,
    actor: Any,
    session: Any,
    name: str,
    args: dict[str, Any],
    app_settings: Any,
    ip: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Ejecuta una herramienta con guardas de descubrimiento y repetición."""
    _mode_check(db, session, name, args, app_settings)
    _guard_check(session, name)
    if name == "describe_source":
        refresh = args.get("refresh")
        if refresh is not None and not isinstance(refresh, bool):
            raise ToolError("refresh debe ser true, false o nulo.")

    if is_discovery(name, args):
        state = dict(session.working_state or {})
        state[RUN_DISCOVERY_KEY] = int(state.get(RUN_DISCOVERY_KEY) or 0) + 1
        session.working_state = state

    key = None
    entry = None
    kind = None
    deps = None
    if name in MEMO_TOOLS:
        kind = _source_kind(db, name, args)
        target = normalise_target(name, args, kind)
        if name == "check_query" and target is not None:
            path = args.get("path")
            if isinstance(path, str) and path.strip():
                deps = _check_query_deps(session, path)
                target = f"{target}|{deps}"
        if target is not None:
            key = f"{name}:{target}"
            calls = dict((session.working_state or {}).get(RUN_CALLS_KEY) or {})
            entry = calls.get(key)

    refresh = name == "describe_source" and args.get("refresh") is True
    if key and entry is not None and not (refresh and not entry.get("refreshed")):
        if name == "check_query" and deps is not None:
            path = args.get("path")
            stored_deps = ((session.query_checks or {}).get(path) or {}).get("deps")
            if stored_deps != deps:
                entry = None
    if key and entry is not None and not (refresh and not entry.get("refreshed")):
        _bump_call(session, key)
        return _repeat_result(session, name, args, entry, kind)

    result, summary = _dispatch(db, actor, session, name, args, app_settings, ip)

    if key:
        if name == "check_query" and deps is not None:
            path = args.get("path")
            checks = dict(session.query_checks or {})
            entry_checks = dict(checks.get(path) or {})
            entry_checks["deps"] = deps
            checks[path] = entry_checks
            session.query_checks = checks
        _remember_call(session, key, entry, name, summary, result, refresh)

    return result, summary


def _dispatch(
    db: Session,
    actor: Any,
    session: Any,
    name: str,
    args: dict[str, Any],
    app_settings: Any,
    ip: str | None,
) -> tuple[dict[str, Any], str]:
    """Despacha la herramienta sin guardas de run."""
    if name == "list_sources":
        result, summary = _list_sources(db, app_settings)
        contract = auto.contract_of(session)
        if contract is not None and contract.sources:
            allowed = {item.name.strip().casefold() for item in contract.sources}
            result = {"sources": [src for src in result["sources"]
                                  if str(src.get("name", "")).strip().casefold() in allowed]}
        return result, summary
    if name == "describe_source":
        return _describe_source(db, actor, session, args, app_settings, ip)
    if name == "profile_source":
        return _profile_source(db, actor, session, args, app_settings, ip)
    if name == "check_query":
        return _check_query(db, actor, session, args, app_settings, ip)
    if name == "get_workspace":
        return _get_workspace(db)
    if name == "get_authoring_guide":
        return _get_authoring_guide(args)
    if name == "propose_draft":
        return _propose_draft(db, session, args)
    if name == "edit_draft":
        return _edit_draft(db, session, args)
    if name == "apply_fix":
        return _guarded(lambda: _apply_fix(db, actor, session, args))
    if name == "read_draft":
        return _read_draft(session, args)
    if name == "update_notes":
        return _update_notes(db, session, args)
    if name == "finish_command":
        return _finish_command(db, session, args)
    if name == "get_app_guide":
        return _get_app_guide(args)
    if name == "get_project_overview":
        return _get_project_overview(db, session)
    if name == "suggest_command":
        return _suggest_command(db, session, args)
    if name == "set_current_spec":
        return _set_current_spec(db, session, args)
    if name == "run_command":
        return _run_command(db, session, args)
    if name == "apply_draft":
        return _guarded(lambda: _apply_draft(db, actor, session, app_settings, ip))
    if name == "run_preview":
        return _guarded(lambda: _run_preview(db, session, app_settings))
    raise ToolError("Herramienta desconocida.")


def _guarded(call) -> tuple[dict[str, Any], str]:
    """A product refusal (`ApiError`) becomes a tool result, not a dead turn.

    Preview and apply answer 409 with the reason when something still has to be fixed (not ready,
    a failing query check, a draft that changed). Inside a turn that reason belongs to the model —
    it can fix it and retry — so it is returned as a refusal instead of failing the whole run with
    "Ocurrió un error inesperado".
    """
    from app.errors import ApiError

    try:
        return call()
    except ApiError as err:
        detail = str(err.message)
        if err.extra.get("errors"):
            first = err.extra["errors"][0]
            path = first.get("path") if isinstance(first, dict) else None
            if path:
                detail = f"{detail} ({path})"
        raise ToolError(detail) from err


def _get_app_guide(args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Feature 023 plan §4: the index, one topic, or the closest topics."""
    from app.assistant import guide
    from app.i18n import current

    lang = guide.lang_of(current())
    topic = args.get("topic")
    if topic is not None and not isinstance(topic, str):
        raise ToolError("topic debe ser un texto o nulo.")
    loaded = guide.load()
    if not topic or not topic.strip():
        return ({"index": [{"id": m.id, "section": m.section, "title": m.title[lang],
                            "summary": m.summary[lang], "roles": list(m.roles)}
                           for m in loaded.topics]},
                t("assistant.summary.app_guide_index"))
    topic_id, closest = guide.resolve(topic, lang)
    found = guide.get(topic_id, lang) if topic_id else None
    if found is None:
        return ({"found": False,
                 "closest": [{"id": c, "title": loaded.meta(c).title[lang]} for c in closest],
                 "note": t("guide.not_found_note")},
                t("assistant.summary.app_guide", topic=topic.strip()[:60]))
    meta = found.meta
    return ({"id": meta.id, "title": meta.title[lang], "roles": list(meta.roles),
             "routes": list(meta.routes),
             "related": [{"id": r, "title": loaded.meta(r).title[lang]} for r in meta.related],
             "body": found.body},
            t("assistant.summary.app_guide", topic=meta.id))


def _get_project_overview(db: Session, session: Any) -> tuple[dict[str, Any], str]:
    """Feature 023 plan §7: the conversation's project as metadata (never rows or secrets)."""
    from app.assistant import overview

    project = getattr(session, "project", None)
    if project is None:
        raise ToolError(t("guide.no_project"))
    return overview.build(db, project), t("assistant.summary.project_overview")


def _finish_command(db: Session, session: Any,
                    args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    summary = args.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ToolError("summary debe ser un texto de una línea.")
    summary = summary.strip().splitlines()[0][:300]
    run = command_run(session)
    if run is not None and run.command == "speckit-specify":
        # A brief may establish several specs: name every one, with its stage.
        folders: list[str] = []
        for entry in run.files or []:
            match = re.match(r"^specs/(\d{3}-[a-z0-9-]+)/spec\.md$", entry.get("path") or "")
            if match and match.group(1) not in folders:
                folders.append(match.group(1))
        stages = {item["folder"]: item.get("stage") for item in
                  project_specs.list_specs(db, session.project)}
        if folders:
            listed = ", ".join(f"{folder} ({stages.get(folder) or '-'})" for folder in folders)
            summary = t("commands.specify_summary", summary=summary[:180], specs=listed)[:300]
    return {"finished": True, "summary": summary}, summary


def _suggest_command(db: Session, session: Any,
                     args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    name = args.get("command")
    name = name.strip().lstrip("/").replace(".", "-").lower() if isinstance(name, str) else ""
    if name not in REGISTRY or not REGISTRY[name].provider:
        raise ToolError("Comando desconocido; usa uno de: "
                        + ", ".join(n for n in REGISTRY if REGISTRY[n].provider))
    spec = args.get("spec")
    spec = spec.strip() if isinstance(spec, str) else ""
    folders: list[str] = []
    if db is not None and getattr(session, "project", None) is not None:
        folders = [item["folder"] for item in project_specs.list_specs(db, session.project)]
    if REGISTRY[name].needs_spec:
        if not spec:
            raise ToolError("Indica la spec de la sugerencia en `spec` (una de: "
                            + (", ".join(folders) or "el proyecto no tiene specs") + ").")
        if folders and spec not in folders:
            raise ToolError(t("commands.spec_not_found", spec=spec,
                              specs=", ".join(folders)))
    arguments = args.get("arguments")
    arguments = arguments.strip() if isinstance(arguments, str) else ""
    if name == "speckit-implement" and not arguments and spec:
        # 040 (B): the honest action for unticked tasks is implementing them, named one by one.
        open_ids = pipeline.open_tasks(session.files(), spec)
        if open_ids:
            arguments = f"--only {','.join(open_ids[:12])}"
    prior = (session.working_state or {}).get(SUGGESTIONS_KEY) or []
    if any(s.get("command") == name for s in prior):
        # The button is already on screen: another call adds nothing and used to loop the turn.
        raise ToolError(f"Ya sugeriste /{name} en esta respuesta; no la repitas, termina tu "
                        "respuesta con el resumen.")
    if len(arguments) > MAX_SUGGESTION_ARGUMENTS:
        # A button with a brief inside is unreadable: the button names the command, the reply text
        # carries the detail. Reject instead of silently truncating so the model fixes its call.
        raise ToolError(f"Los argumentos de la sugerencia deben resumir en "
                        f"{MAX_SUGGESTION_ARGUMENTS} caracteres o menos; escribe el detalle en tu "
                        "respuesta.")
    working = dict(session.working_state or {})
    suggestions = list(working.get(SUGGESTIONS_KEY) or [])
    if len(suggestions) >= MAX_SUGGESTIONS:
        raise ToolError(f"Máximo {MAX_SUGGESTIONS} sugerencias por respuesta.")
    item: dict[str, Any] = {"command": name, "arguments": arguments}
    if spec:
        item["spec"] = spec
    suggestions.append(item)
    working[SUGGESTIONS_KEY] = suggestions
    session.working_state = working
    # The command text carries the spec explicitly, so the button re-runs on the right one.
    parts = [f"/{name}"]
    if spec and spec not in arguments:
        parts.append(spec)
    if arguments:
        parts.append(arguments)
    text = " ".join(parts)
    return {"suggested": text, "spec": spec or None}, t(
        "assistant.summary.suggested_command", command=text)


def _set_current_spec(db: Session, session: Any,
                      args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """The agent's way to change the conversation's spec (never ask the user to pick it)."""
    spec = args.get("spec_id")
    spec = spec.strip() if isinstance(spec, str) else ""
    folders = [item["folder"] for item in project_specs.list_specs(db, session.project)]
    if spec not in folders:
        raise ToolError(t("commands.spec_not_found", spec=spec or "-",
                          specs=", ".join(folders) or "-"))
    session.current_spec = spec
    summary = t("commands.spec_current", spec=spec)
    return {"spec": spec}, summary


def _run_command(db: Session, session: Any,
                 args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Feature 028: switch the run to the next Spec Kit stage (never ask the human to run it).

    The stage is a real `assistant_command_run` row: same registry definition, same tool set, same
    audit and same token ceiling as the composer's `/speckit-…`. The provider loop is not nested;
    the model keeps working in this turn with the new stage's tools.
    """
    name = args.get("command")
    name = name.strip() if isinstance(name, str) else ""
    definition = REGISTRY.get(name)
    if definition is None or not name.startswith("speckit-"):
        raise ToolError(f"Etapa desconocida: {name or '-'}.")
    arguments = args.get("arguments")
    arguments = arguments.strip() if isinstance(arguments, str) else ""
    only: tuple[str, ...] = ()
    if name == "speckit-implement":
        # 040 (B): the stage may be opened for the open tasks only.
        arguments, only = resolve.strip_only(arguments)
    requested = args.get("spec")
    requested = requested.strip() if isinstance(requested, str) else ""
    target = arguments or requested

    listed = project_specs.list_specs(db, session.project)
    folders = [item["folder"] for item in listed]
    resolution = resolve.resolve(listed, target, session.current_spec)
    spec = resolution.spec if resolution.spec in folders else None

    # 039/040: inside `/speckit-all` the plan decides the next stage; the model only opens it.
    plan = pipeline.state_of(db, session.id)
    plan_at: tuple[int, int] | None = None
    if plan is not None:
        if name == "speckit-all":
            raise ToolError(t("pipeline.no_restart"))
        plan = _plan_grow(db, session, plan, spec)
        # 040: the state machine decides where the plan goes before the model's request is read.
        project_files = session.files()
        plan = pipeline.routed_state(db, plan, project_files) or plan
        plan_at = _plan_position(db, plan, name, spec, project_files)
        index, _cursor = plan_at
        spec = plan["specs"][index] if plan.get("specs") else None
        target = pipeline.STAGE_COMMANDS[pipeline.STAGES[_cursor]]
        if target != name:
            # 040: the state machine routed this request to another stage (verify → implement);
            # the run is opened with the definition of the stage that will actually run.
            definition, name = REGISTRY[target], target
    if spec is not None and spec != session.current_spec:
        session.current_spec = spec
    if definition.needs_spec and spec is None:
        raise ToolError(t("commands.spec_not_found", spec=target or "-",
                          specs=", ".join(folders) or "-"))
    if only:
        known = pipeline.task_ids(session.files().get(f"specs/{spec}/tasks.md")) if spec else []
        unknown = [task for task in only if task not in known]
        if unknown:
            raise ToolError(t("commands.only_unknown", tasks=", ".join(unknown), spec=spec or "-",
                              known=", ".join(known) or "—"))

    current = command_run(session)
    if current is not None and current.status in ("running", "waiting"):
        runs.finish(current, "completed")
        if isinstance((current.result or {}).get(pipeline.PIPELINE_KEY), dict):
            # 040 (C): the finished stage leaves one line, not its tool results (015 FR-012).
            _stage_summary_message(db, session, current)
    if plan is not None:
        # 039 FR-003: a stage is not opened once the contract has spent its token budget, even
        # inside the turn that is spending it.
        live = auto.live_contract(session)
        refusal = auto.limit_refusal(auto.contract_of(session), live,
                                     tokens=int(getattr(live, "tokens", 0) or 0))
        if refusal is not None:
            raise ToolError(refusal.message)
    # Feature 028 (FR-004): in Auto the contract answers the stage's gates; the run never waits
    # for a "yes" from the human.
    preflight = runs.preflight(definition, spec, session.files())
    if preflight.missing:
        raise ToolError(preflight.message)
    if plan is not None and plan_at is not None:
        plan = pipeline.advance(plan, *plan_at)
    stage = runs.create(
        db, session_id=session.id, project_id=session.project_id, definition=definition,
        arguments=arguments, locale=getattr(session, "command_locale", None) or "es",
        spec=spec, resolved_from=resolution.source or "current",
        reserved_number=session.next_spec() if name == "speckit-specify" else None,
        result={**({"only": list(only)} if only else {}),
                # 040 (C): where this stage's own context starts.
                "history_from": _history_mark(db, session.id)},
        pipeline=plan)
    if plan is not None and plan.get("id") is None:
        plan = {**plan, "id": stage.id}
        stage.result = {**(stage.result or {}), pipeline.PIPELINE_KEY: plan}
    if preflight.pending and spec:
        _approve_without_asking(db, session, stage, spec, preflight.pending)
    session.command_run = stage
    auto_run = auto.live_contract(session)
    if auto_run is not None:
        auto_run.stage = _STAGE_OF_COMMAND.get(name)
    summary = t("commands.auto_stage", command=name, spec=spec or "-")
    round_ = int((plan or {}).get("round") or 0)
    if round_:
        summary = t("commands.auto_stage_round", command=name, spec=spec or "-", round=round_)
    payload = {
        "stage": name,
        "spec": spec,
        "resolved_from": resolution.source,
        "instruction": registry.prompt_body(name, getattr(session, "command_locale", None) or "es"),
        "files": sorted(folders),
    }
    if plan is not None:
        payload["pipeline"] = pipeline.position(plan)
    return payload, summary


def _history_mark(db: Session, session_id: int) -> int:
    """The id of the newest stored message: the start of the stage's own context (040 C)."""
    from sqlalchemy import func, select

    from app.models import AssistantMessage

    return int(db.scalar(select(func.max(AssistantMessage.id))
                         .where(AssistantMessage.session_id == session_id)) or 0)


def _stage_summary_message(db: Session, session: Any, run: Any) -> None:
    """One `✔ <stage> — …` line in the transcript, so the next stage need not replay the tools."""
    from app.models import AssistantMessage

    db.add(AssistantMessage(session_id=session.id, role="assistant",
                            content=runs.stage_summary(run, getattr(session, "command_locale",
                                                                    None))))
    db.flush()


_STAGE_DOCS = {"specify": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}  # C12: stage artifacts


def _plan_position(db: Session, plan: dict[str, Any], name: str,
                   spec: str | None, files: dict[str, str] | None = None) -> tuple[int, int]:
    """(spec_index, stage_index) the model asked for, refused when it is not the plan's next one.

    The two judging stages (`analyze`, `verify`) have no writers, so the only way to fix what they
    find is to re-open the stage that owns the file (US2 AC3, US4 AC2). That rewind is allowed, and
    only from those two, with the cycle caps of the contract.
    """
    at = pipeline.next_position(plan)
    if at is None:
        if plan.get("until") in pipeline.STAGES:
            raise ToolError(t("pipeline.until", stage=plan["until"]))
        raise ToolError(t("pipeline.finished"))
    index, cursor = at
    requested = pipeline.COMMAND_STAGES.get(name)
    current_index = int(plan.get("cursor") or 0)
    current = pipeline.STAGES[current_index - 1] if current_index else None
    expected = pipeline.STAGES[cursor]
    if (requested is not None and requested != expected and current in _JUDGING_STAGES
            and pipeline.STAGES.index(requested) < current_index):
        target_spec = plan["specs"][index] if plan.get("specs") else None
        _repair_cycle(db, plan, target_spec, current, requested)
        return index, pipeline.STAGES.index(requested)
    if (requested == "verify" and expected == "implement"
            and plan.get("after_implement") in ("converge", "verify")):
        # 040 FR-003: verify does not start while tasks are open (or while fixing a failed one);
        # the state machine already routed to implement, so the request opens that instead of
        # failing the run for it.
        return index, cursor
    if not plan.get("specs"):
        if name != "speckit-specify":
            raise ToolError(t("pipeline.order", expected="/speckit-specify", stage="specify",
                              step=f"{cursor + 1}/{pipeline.TOTAL}"))
        return index, cursor
    expected_spec = plan["specs"][index]
    doc = _STAGE_DOCS.get(requested or "")
    if (doc is not None and pipeline.STAGES.index(requested) < cursor
            and f"specs/{expected_spec}/{doc}" not in (files or {})):
        # C12: the stage completed without its artifact; reopening it is the plan's own repair.
        return index, pipeline.STAGES.index(requested)
    if pipeline.STAGE_COMMANDS[expected] != name:
        raise ToolError(t("pipeline.order", expected=f"/{pipeline.STAGE_COMMANDS[expected]} "
                                                     f"{expected_spec}",
                          stage=name, step=f"{cursor + 1}/{pipeline.TOTAL}"))
    if spec is not None and spec != expected_spec:
        raise ToolError(t("pipeline.order", expected=f"/{name} {expected_spec}",
                          stage=name, step=f"{cursor + 1}/{pipeline.TOTAL}"))
    _verify_cycle(db, plan, expected_spec, expected)
    return index, cursor


_JUDGING_STAGES = ("analyze", "verify")
MAX_ANALYZE_ROUNDS = 1


def _repair_cycle(db: Session, plan: dict[str, Any], spec: str | None, stage: str,
                  requested: str) -> None:
    """The caps of the rewind: analyze re-runs once, verify three times, converge twice."""
    if spec is None:
        return
    if stage == "analyze":
        rounds = len(pipeline.stage_runs(db, plan, "speckit-analyze", spec))
        if rounds > MAX_ANALYZE_ROUNDS:
            raise ToolError(t("pipeline.analyze_failed", rounds=rounds, spec=spec))
    if requested == "converge":
        rounds = len(pipeline.stage_runs(db, plan, "speckit-converge", spec))
        if rounds >= pipeline.MAX_ROUNDS:
            raise ToolError(t("pipeline.converge_failed", rounds=rounds, spec=spec))


def _verify_cycle(db: Session, plan: dict[str, Any], spec: str, stage: str) -> None:
    """Verify is capped at 3 cycles: the fourth attempt is not a stage, it is a stop (US4 AC2)."""
    if stage != "verify":
        return
    done = pipeline.verify_runs(db, plan, spec)
    if len(done) >= pipeline.MAX_VERIFY_CYCLES:
        verdict = pipeline.last_verify(db, plan, spec) or {}
        if not verdict.get("ok", False):
            raise ToolError(t("pipeline.verify_failed", cycles=pipeline.MAX_VERIFY_CYCLES,
                              spec=spec))


def _plan_grow(db: Session, session: Any, plan: dict[str, Any],
               spec: str | None) -> dict[str, Any]:
    """Fill the pipeline's spec list the first time its specify run establishes one."""
    if plan.get("specs"):
        return plan
    created = pipeline.specs_from_runs(db, plan.get("id"))
    if spec is not None:
        created.append(spec)
    if not created:
        return plan
    rows = project_specs.list_specs(db, session.project)
    keep = set(created)
    return {**plan, "specs": pipeline.ordered_specs([row for row in rows
                                                     if row["folder"] in keep])}


def _approve_without_asking(db: Session, session: Any, stage: Any, spec: str,
                            pending: dict[str, Any]) -> None:
    """Answer a stage gate with the product's rule instead of asking the super user (FR-004).

    The gates of 021 are confirmations of work already written in the spec (its status, its
    checklist, its clarifications); the run contract is the authorisation, so Auto approves them
    and records that it did.
    """
    if "approve_spec" in (pending.get("gates") or []):
        # `fs.apply_ops` writes from its own session, so the stage row has to be visible outside
        # this transaction: the revision's `command_run_id` is a foreign key to it. Without this
        # commit the approval raised a ForeignKeyViolation and the turn ended with "Ocurrió un
        # error inesperado" (reported with /speckit-tasks over a Draft spec).
        db.commit()
        # `project_id`, not `session.project`: the composer's path starts the run before the
        # relationship is loaded.
        results = fs.apply_ops(session.project_id, runs.approve_ops(spec, session.files()),
                               {"kind": "system", "user_id": None, "session_id": session.id,
                                "command": f"/{stage.command}", "command_run_id": stage.id})
        for item in results:
            runs.add_file(stage, item["path"], item["op"], item["revision_id"])
        session.refresh()
    stage.pending = None
    stage.status = "running"
    db.flush()


def _apply_draft(db: Session, actor: Any, session: Any, app_settings: Any,
                 ip: str | None) -> tuple[dict[str, Any], str]:
    """Feature 028: the button's apply, authorised by the contract (014 FR-006 as amended)."""
    from app.assistant import service as assistant_service
    from app.workspace.service import version_json

    version, revalidated = assistant_service.apply_draft(db, actor, session, ip)
    auto_run = auto.live_contract(session)
    if auto_run is not None:
        auto_run.applies = int(auto_run.applies or 0) + 1
        auto_run.version_id = version.id
        assistant_service.arm_auto_watch(db, session, auto_run, version)
    payload = version_json(version) or {}
    payload["revalidated"] = bool(revalidated)
    return payload, t("assistant.summary.applied", version=version.id)


def _list_sources(db: Session, app_settings: Any) -> tuple[dict[str, Any], str]:
    sources = sorted(
        ({"name": src.name, "kind": src.kind, "direct": bool(src.direct_reports)}
         for src in list_all(db)),
        key=lambda item: item["name"],
    )
    if app_settings.direct_reports_bi:
        sources.insert(0, {"name": "bi", "kind": "postgresql",
                           "label": "BI de esta instalación", "direct": True})
    return {"sources": sources}, t("assistant.summary.listed_sources")


def _describe_bi(
    db: Session,
    actor: Any,
    session: Any,
    refresh: bool,
    app_settings: Any,
    ip: str | None,
) -> tuple[dict[str, Any], str]:
    if not refresh:
        cached = origin.cached_description(session, "bi", None)
        if cached:
            return sanitize(cached), t("assistant.summary.used_cached_structure", name="bi")

    record(
        db,
        "source_described",
        actor_id=getattr(actor, "id", None),
        ip=ip,
        detail={"source": "bi", "via": "assistant", "session": session.id},
    )
    try:
        description = direct.describe_bi()
        cleaned = _cap_describe_result(compact_tables(origin.flag_personal(description)))
        cleaned["note"] = (
            "Base BI de esta instalación: solo tablas que un reporte directo "
            "puede leer (nunca tablas del producto)."
        )
        origin.remember_description(session, "bi", None, cleaned)
        db.add(real(session))
        db.flush()
        return cleaned, t("assistant.summary.consulted_bi_structure")
    except direct.DirectError as e:
        return {"error": e.message}, t("assistant.summary.consulted_structure_failed", name="bi")
    except Exception as e:
        log.info("describe_bi failed: %s", type(e).__name__)
        return {
            "error": "No se pudo leer la estructura de la fuente."
        }, "No se pudo consultar la estructura de «bi»."


def _describe_source(
    db: Session,
    actor: Any,
    session: Any,
    args: dict[str, Any],
    app_settings: Any,
    ip: str | None,
) -> tuple[dict[str, Any], str]:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("El nombre de la fuente es obligatorio.")

    path = args.get("path")
    if path is not None and not isinstance(path, str):
        raise ToolError("La ruta debe ser texto o nula.")
    refresh = args.get("refresh")
    if refresh is not None and not isinstance(refresh, bool):
        raise ToolError("refresh debe ser true, false o nulo.")

    if name.strip().lower() == "bi" and app_settings.direct_reports_bi:
        return _describe_bi(db, actor, session, bool(refresh), app_settings, ip)

    source = by_name(db, name)
    if source is None:
        return {"error": "No existe una fuente con ese nombre."}, (
            f"Intentó consultar la fuente «{name}» sin éxito."
        )

    if source.kind in ("supabase", "rest") and isinstance(path, str):
        path = origin.normalise_table(source.kind, path) or None

    if not refresh:
        cached = origin.cached_description(session, name, path)
        if cached:
            return sanitize(cached), t("assistant.summary.used_cached_structure", name=name)

    record(
        db,
        "source_described",
        actor_id=getattr(actor, "id", None),
        ip=ip,
        detail={"source": name, "via": "assistant", "session": session.id},
    )
    try:
        description = describe(
            source.kind,
            source.settings,
            secrets_of(source),
            app_settings,
            path,
        )
        cleaned = _cap_describe_result(compact_tables(origin.flag_personal(description)))
        origin.remember_description(session, name, path, cleaned)
        db.add(real(session))
        db.flush()
        return cleaned, t("assistant.summary.consulted_structure", name=name)
    except Exception:
        return {
            "error": "No se pudo leer la estructura de la fuente."
        }, f"No se pudo consultar la estructura de «{name}»."

def _get_workspace(db: Session) -> tuple[dict[str, Any], str]:
    version = active(db)
    if version is None:
        return {"workspace": None, "note": (
            "Aún no hay una versión aplicada. No hace falta crear nada antes: propón el borrador "
            "completo (integración y reporte con sus specs) y, al aplicarlo, será la primera "
            "versión del espacio de trabajo.")}, "Aún no hay una versión aplicada."

    workspace_data: dict[str, Any] = {
        "workspace": version.artifacts.get("workspace", {}),
        "integrations": version.artifacts.get("integrations", {}),
        "reports": version.artifacts.get("reports", {}),
        "specs": version.specs or {},
    }
    cleaned = _cap_workspace_result(workspace_data)
    return cleaned, t("assistant.summary.consulted_workspace")




def _get_authoring_guide(args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    topic = args.get("topic")
    if topic is not None and not isinstance(topic, str):
        raise ToolError("El tema debe ser texto o nulo.")
    result = authoring.guide(topic)
    summary_topic = topic or "index"
    return result, t("assistant.summary.consulted_guide", topic=summary_topic)


def _snippet(text: str) -> str:
    """Recorta un texto para mostrarlo en mensajes de error."""
    return text[:80] + "…" if len(text) > 80 else text


def _probe_fragments(files: dict[str, str]) -> dict[str, Any]:
    """Devuelve fragmentos de esquema orientativos para una prueba suelta."""
    fragments: dict[str, Any] = {}
    for path in files:
        if path == "bizview.yaml":
            fragments[path] = authoring.guide("workspace")["schema"]
        elif path.endswith("/integration.yaml"):
            fragments[path] = authoring.guide("integration")["schema"]
        elif "/requests/" in path and path.endswith(".yaml"):
            fragments[path] = authoring.guide("request")["schema"]
        elif path.endswith("/report.yaml"):
            fragments[path] = authoring.guide("report")["schema"]
        elif path.endswith(".sql"):
            fragments[path] = {
                "note": (
                    "una única instrucción SELECT/WITH de solo lectura; "
                    "los incrementales filtran con :window_start y :window_end"
                )
            }
        else:
            fragments[path] = {"note": authoring.RULES}
    return fragments


def _seen(session: Any) -> dict[str, str]:
    """Shas the agent read or wrote per project path (research R5)."""
    return dict((session.working_state or {}).get("seen") or {})


def _remember(session: Any, shas: dict[str, str]) -> None:
    state = dict(session.working_state or {})
    state["seen"] = {**(state.get("seen") or {}), **shas}
    session.working_state = state


def _reject_foreign(path: str) -> None:
    """A path that names another project, or an absolute one, is not a path of this project (037).

    The validator composes every project under `projects/<slug>/…`, and a stale fix or a model can
    carry one of those paths back. Reporting it as "missing" taught the agent the file was not
    there; the truth is that it is out of scope.
    """
    parts = path.replace("\\", "/").split("/")
    if path.startswith("/") or "\\" in path or parts[:1] == ["projects"]:
        raise ToolError(t("projects.path_outside_project", path=path))


def _check_path(path: str) -> None:
    _reject_foreign(path)
    if not layout.is_allowed(path):
        raise ToolError(
            f"{path}: ruta no permitida en el proyecto. Rutas permitidas: {layout.ALLOWED_TEXT}"
        )
    try:
        fs.check_rel(path)
    except fs.ProjectPathError as err:
        raise ToolError(str(err)) from err


# --- 026 FR-012/SC-004: el borrador es declarativo, nunca código ejecutable ----------------------
# `is_allowed` ya fija las rutas aceptadas (YAML, SQL y markdown) y `tree.check_paths` los tamaños;
# lo que falta es el contenido: el modelo no escribe código que el producto ejecute. La detección
# es estructural —un script no es un documento YAML de clave-valor— y, dentro de un documento de
# datos, se miran las claves y los valores ya cargados, nunca el texto en bruto: así un comentario
# de SQL o un texto descriptivo en español o inglés no se confunde con código.
EXECUTABLE_MARKERS: tuple[str, ...] = ("<script", "</html", "javascript:", "<?php")

# Firmas de una sentencia de código: no describen un reporte, una integración ni una distribución.
CODE_STATEMENTS = re.compile(
    r"""(?m)^\s*(?:
        \#!                                                       # intérprete
      | (?:def|class|function)\s+\w+\s*(?:\(|\Z)                  # def x( / class X (clave YAML)
      | import\s+[A-Za-z_][\w.]*(?:\s+as\s+\w+)?\s*(?:$|[,;#])    # import módulo
      | from\s+[\w.]+\s+import\b                                  # from módulo import
      | (?:const|let|var)\s+\w+\s*=                               # const x =
      | require\s*\(                                              # require(
    )""",
    re.VERBOSE,
)

# Aperturas de un documento que no es markdown: un `.md` del proyecto empieza por su título.
CODE_OPENINGS: tuple[str, ...] = (
    "<!doctype", "<html", "<script", "<?php", "#!", "import ", "from ", "def ", "class ",
    "const ", "let ", "var ", "function ", "export ", "require(", "package ", "using ",
)


def _data_marker(doc: Any) -> str | None:
    """El primer marcador ejecutable o sentencia de código en los datos ya cargados.

    El recorrido es iterativo y lleva los contenedores ya vistos: un documento con anclas YAML
    recursivas (`&x [*x]`) no puede multiplicar el trabajo.
    """
    seen: set[int] = set()
    pending: list[Any] = [doc]
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            lowered = value.lower()
            marker = next((m for m in EXECUTABLE_MARKERS if m in lowered), None)
            if marker is not None:
                return marker
            found = CODE_STATEMENTS.search(value)
            if found is not None:
                return found.group(0).strip()
        elif isinstance(value, dict | list):
            if id(value) in seen:
                continue
            seen.add(id(value))
            if isinstance(value, dict):
                pending += [part for item in value.items() for part in item]
            else:
                pending += list(value)
    return None


def _content_problem(path: str, code: str, message: str, project: str | None) -> dict[str, Any]:
    """Un problema de borrador con la forma que usa la validación del proyecto (015)."""
    return {"entry": path, "code": code, "message": message, "level": "error", "file": path,
            "path": "/", "expected": None, "fix": None, "line": 1, "project": project}


def _executable_problem(path: str, marker: str, project: str | None) -> dict[str, Any]:
    return _content_problem(path, "draft_executable_content",
                            t("assistant.draft_executable_content", file=path, marker=marker),
                            project)


def _declarative_problems(path: str, text: str, project: str | None) -> list[dict[str, Any]]:
    """Contenido aceptado de una ruta permitida: YAML de datos, markdown o SQL de solo lectura."""
    if path.endswith(".sql"):
        problems = sqlsafety.check_query(text)
        if not problems:
            return []
        return [_content_problem(
            path, "draft_sql_not_read_only",
            t("assistant.draft_sql_not_read_only", file=path,
              error="; ".join(p.message for p in problems[:3])), project)]
    if path.endswith(".yaml"):
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as err:
            return [_content_problem(
                path, "draft_content_not_declarative",
                t("assistant.draft_yaml_invalid", file=path, error=str(err)[:200]), project)]
        if not isinstance(doc, dict):
            return [_content_problem(
                path, "draft_content_not_declarative",
                t("assistant.draft_yaml_not_mapping", file=path), project)]
        marker = _data_marker(doc)
        return [_executable_problem(path, marker, project)] if marker is not None else []
    # Markdown: documentación del proyecto. Solo se rechaza el archivo que no es markdown sino un
    # documento de código o de HTML (su primera línea lo delata); citar código en prosa es legítimo.
    first = next((line.strip().lower() for line in text.splitlines() if line.strip()), "")
    opening = next((o for o in CODE_OPENINGS if first.startswith(o)), None)
    return [_executable_problem(path, opening.strip(), project)] if opening else []


def _content_problems(ops: list[dict[str, Any]], project: str | None) -> list[dict[str, Any]]:
    """Los problemas de contenido de las operaciones que escriben (FR-012).

    Un archivo que pasa el límite de tamaño lo rechaza el camino de escritura de 014 con su propio
    error; aquí solo se mira el contenido de lo que puede llegar a escribirse.
    """
    problems: list[dict[str, Any]] = []
    for op in ops:
        content = op.get("content")
        if op.get("op") == "delete" or not isinstance(content, str):
            continue
        if len(content.encode("utf-8")) > fs.MAX_FILE_BYTES:
            continue
        problems += _declarative_problems(str(op.get("path", "")), content, project)
    return problems


def _rejected(db: Session, session: Any, problems: list[dict[str, Any]]) -> dict[str, Any]:
    """Un borrador rechazado: no se escribió nada y el proyecto sigue como estaba."""
    validation = dict(session.validation or {"valid": False, "errors": [], "warnings": []})
    validation["valid"] = False
    validation["errors"] = problems + list(validation.get("errors") or [])
    validation["warnings"] = list(validation.get("warnings") or [])
    session.validation = validation
    db.add(real(session))
    db.flush()
    return validation


def _agent_actor(session: Any) -> dict[str, Any]:
    run = command_run(session)
    return {
        "kind": "agent",
        "user_id": None,
        "session_id": session.id,
        "command": f"/{run.command}" if run is not None else "agent",
        "command_run_id": run.id if run is not None else None,
    }


def _guard_writes(session: Any, ops: list[dict[str, Any]], current: dict[str, str]) -> None:
    """Paths the running command may change (021 plan §3); the first new spec folder of
    /speckit-specify becomes the run's spec and the conversation's current spec."""
    run, definition = command_run(session), command_def(session)
    if run is None or definition is None:
        raise ToolError(t("commands.write_needs_command"))
    spec_text = current.get(f"specs/{run.spec}/spec.md", "") if run.spec else ""
    stored = run.result if isinstance(run.result, dict) else {}
    ctx = guard.Context(
        definition=definition, spec=run.spec,
        kind=layout.spec_kind(spec_text) if spec_text else None,
        reserved_number=run.reserved_number,
        plan_text=current.get(f"specs/{run.spec}/plan.md", "") if run.spec else "",
        installation_block=guard.installation_block(),
        files=current,
        only=tuple(stored.get("only") or ()))
    try:
        folder = guard.check_ops(ctx, [{"op": op["op"], "path": op["path"],
                                        "content": op.get("content", "")} for op in ops])
    except guard.GuardError as err:
        if err.code == "path_other_spec":
            # The run stays inspectable: the product can offer to re-run it on that spec.
            run.result = {**(run.result or {}), "misrouted_to": err.params.get("owner"),
                          "error": str(err)}
        raise ToolError(str(err)) from err
    if definition.name == "speckit-specify":
        # A brief may establish several specs: the last one written becomes the current spec.
        created = guard.created_folders(ctx, ops)
        if created:
            folder = created[-1]
    if folder:
        run.spec = folder
        session.current_spec = folder


_PLAIN_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _requests_checked(session: Any, ops: list[dict[str, Any]]) -> None:
    """Feature 041: a check that RAN for the path is authority enough to write its `fields`.

    The checker cannot read a shape while `records` itself is wrong, so demanding keys or `ok`
    recreated the deadlock (the file could only fail while it was still unfixed). Any stored
    check entry for the path allows the write; keys, when present, still validate plain tokens so
    a wrong column name names the real ones.
    """
    definition = command_def(session)
    if definition is None or definition.name not in ("speckit-implement", "fix"):
        return
    for op in ops:
        path = op.get("path") or ""
        if op.get("op") != "write" or not origin.REQUEST_FILE.match(str(path)):
            continue
        try:
            document = yaml.safe_load(op.get("content") or "")
        except yaml.YAMLError:
            continue                     # the validator reports the YAML error with its line
        # A renamed column is legal — what must exist in the shape is the mapped key, so only
        # plain top-level paths are judged here; nested or indexed paths belong to the check.
        fields = dict(document.get("fields") or {}) if isinstance(document, dict) else {}
        entry = dict((session.query_checks or {}).get(path) or {})
        # A skeleton without `fields` may always be written (C8): check_query needs the file to
        # exist, so demanding a check first made a new request file impossible to create.
        if fields and not entry:
            raise ToolError(t("assistant.check_request_first", path=path))
        keys = [str(key) for key in entry.get("keys") or []]
        missing: list[str] = []
        for path_value in fields.values():
            token = str(path_value)
            if token.startswith("$"):
                token = token[1:]
            if token.startswith("."):
                token = token[1:]
            if keys and _PLAIN_KEY.match(token) and token not in keys:
                missing.append(token)
        if missing:
            raise ToolError(t("assistant.check_request_missing",
                              columns=", ".join(missing), path=path,
                              keys=", ".join(keys) or "—"))


def _write_ops(db: Session, session: Any, ops: list[dict[str, Any]]) -> dict[str, Any]:
    """Write project files as the agent, then validate the project."""
    _requests_checked(session, ops)
    _guard_writes(session, ops, session.files())
    rejected = _content_problems(ops, session.project.slug)
    if rejected:
        return _rejected(db, session, rejected)
    try:
        results = fs.apply_ops(session.project.id, ops, _agent_actor(session))
    except fs.FileChanged as err:
        raise ToolError(f"{err}; léelo con read_draft y vuelve a aplicar tu cambio") from err
    except fs.ProjectPathError as err:
        raise ToolError(str(err)) from err
    _remember(session, {r["path"]: r["sha256"] for r in results if r["sha256"]})
    run = command_run(session)
    if run is not None:
        for item in results:
            runs.add_file(run, item["path"], item["op"], item["revision_id"])
    session.refresh()
    validation = compose.validate_project(db, session.project)
    session.validation = validation
    _bump(session, "validations")
    db.add(real(session))
    db.flush()
    return validation


def _draft_result(session: Any, validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid": validation.get("valid", False),
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "files": sorted(session.files()),
        "readiness": readiness.compute(session),
    }


def _is_spec(path: str) -> bool:
    return path.startswith("specs/") and path.endswith("/spec.md")


def _propose_draft(
    db: Session,
    session: Any,
    args: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    files = args.get("files")
    if not isinstance(files, dict) or not files or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in files.items()
    ):
        raise ToolError("Los archivos deben ser un mapa de rutas a texto.")
    for path in files:
        _check_path(path)

    current = session.files()
    if (not any(_is_spec(p) for p in files) and not any(_is_spec(p) for p in current)
            and len(files) <= 2):
        _bump(session, "probes")
        db.add(real(session))
        db.flush()
        return (
            {
                "probe": True,
                "stored": False,
                "message": (
                    "Esto parece una prueba suelta: no se guardó ni se validó. "
                    "Un proyecto debe incluir sus specs (spec.md, plan.md, tasks.md) "
                    "y los artefactos completos; usa get_authoring_guide('example') "
                    "para ver un proyecto completo y válido."
                ),
                "fragments": _probe_fragments(files),
            },
            f"Prueba de borrador sin guardar ({len(files)} archivos).",
        )

    seen = _seen(session)
    ops = []
    for path, text in files.items():
        base = None
        if path in current:
            base = history.sha(current[path])
            if seen.get(path) != base:
                raise ToolError(
                    f"{path} ya existe y no lo has leído en su versión actual; "
                    "léelo con read_draft antes de reemplazarlo"
                )
        ops.append(
            {"op": "write", "path": path, "content": text, "base_sha256": base, "force": False}
        )

    validation = _write_ops(db, session, ops)
    return _draft_result(session, validation), t(
        "assistant.summary.proposed_draft", count=len(files)
    )


def _apply_fix(db: Session, actor: Any, session: Any,
               args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Apply the deterministic correction the validator published for one problem (035 FR-014).

    The agent must use this instead of writing the same YAML by hand: the fix is data the validator
    produced, so there is nothing to hallucinate and nothing to pay for.
    """
    from app.api.appearance import preset_of
    from app.models import Project
    from app.projects import fixes as project_fixes
    from app.projects import service as projects

    problem_id = args.get("problem_id")
    if not isinstance(problem_id, str) or not problem_id.strip():
        raise ToolError("Falta problem_id: usa el id que devolvió la validación.")
    project = db.get(Project, session.project_id) if session.project_id else None
    if project is None:
        raise ToolError("Esta conversación no tiene proyecto.")
    problems = projects.revalidate(db, project)["validation"]
    match = next((item for item in [*problems.get("errors", []), *problems.get("warnings", [])]
                  if item.get("problem_id") == problem_id), None)
    if match is None:
        raise ToolError(
            "Ese problema ya no existe (o cambió): vuelve a validar y usa el id actual.")
    fix = match.get("fix_data")
    if not isinstance(fix, dict):
        raise ToolError("Ese problema no tiene un arreglo determinista: corrígelo con edit_draft.")
    # Feature 037: a fix is a path of this project or it is not applied at all.
    _check_path(str(fix.get("file") or ""))
    try:
        fs.resolve_project_path(project.id, str(fix["file"]), db=db)
    except fs.ProjectPathError as err:
        raise ToolError(str(err)) from err
    state = project_fixes.apply_fixes(db, actor, project, [{**fix, "problem_id": problem_id}],
                                      None, installation_palette=preset_of(db))
    session.refresh()
    result = state["results"][0] if state.get("results") else {}
    return ({"applied": {"problem_id": problem_id, "file": fix["file"],
                         "diff": result.get("diff")},
             "validation": state.get("validation")},
            t("assistant.summary.fix_applied", file=fix["file"]))

def _edit_draft(
    db: Session,
    session: Any,
    args: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    ops = args.get("ops")
    if not isinstance(ops, list) or not ops:
        raise ToolError("Las operaciones deben ser una lista no vacía.")
    if len(ops) > _MAX_EDIT_OPS:
        raise ToolError(f"Máximo {_MAX_EDIT_OPS} operaciones por llamada.")

    current = dict(session.files())
    seen = _seen(session)
    fs_ops: list[dict[str, Any]] = []
    touched: set[str] = set()
    for index, op in enumerate(ops, start=1):
        if not isinstance(op, dict):
            raise ToolError(f"La operación {index} debe ser un objeto.")
        op_type = op.get("op")
        path = op.get("path")
        if op_type not in ("write", "replace", "delete") or not isinstance(path, str):
            raise ToolError(
                f"La operación {index} debe tener op write|replace|delete y path de texto."
            )
        _check_path(path)

        if op_type == "write":
            content = op.get("content")
            if not isinstance(content, str):
                raise ToolError(f"La operación {index} (write) requiere content de texto.")
            base = history.sha(current[path]) if path in current else None
            if base is not None and path not in touched and seen.get(path) != base:
                raise ToolError(
                    f"La operación {index}: {path} cambió desde que lo leíste; "
                    "léelo con read_draft"
                )
            fs_ops.append({"op": "write", "path": path, "content": content,
                           "base_sha256": base, "force": False})
            current[path] = content
        elif op_type == "replace":
            old = op.get("old")
            new = op.get("new")
            if not isinstance(old, str) or not old or not isinstance(new, str):
                raise ToolError(
                    f"La operación {index} (replace) requiere old no vacío y new de texto."
                )
            if path not in current:
                raise ToolError(
                    f"La operación {index} no encontró el archivo {path} para reemplazar."
                )
            count = current[path].count(old)
            if count == 0:
                raise ToolError(
                    f"La operación {index} no encontró «{_snippet(old)}» "
                    f"en {path} (0 ocurrencias)."
                )
            if count > 1:
                raise ToolError(
                    f"La operación {index} encontró {count} ocurrencias de "
                    f"«{_snippet(old)}» en {path}; debe ser exactamente una."
                )
            text = current[path].replace(old, new, 1)
            fs_ops.append({"op": "write", "path": path, "content": text,
                           "base_sha256": history.sha(current[path]), "force": False})
            current[path] = text
        else:
            if path not in current:
                raise ToolError(f"La operación {index} no encontró el archivo {path}.")
            base = history.sha(current[path])
            if path not in touched and seen.get(path) != base:
                raise ToolError(
                    f"La operación {index}: borra {path} solo después de leerlo con read_draft"
                )
            fs_ops.append({"op": "delete", "path": path, "base_sha256": base})
            del current[path]
        touched.add(path)

    validation = _write_ops(db, session, fs_ops)
    return _draft_result(session, validation), t(
        "assistant.summary.edited_draft", count=len(ops)
    )


def _read_draft(
    session: Any,
    args: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    paths = args.get("paths")
    if not isinstance(paths, list) or not paths:
        raise ToolError("Las rutas deben ser una lista no vacía.")
    if not all(isinstance(p, str) for p in paths):
        raise ToolError("Las rutas deben ser texto.")

    session.refresh()
    files = session.files()
    if not files:
        raise ToolError("El proyecto está vacío; usa propose_draft primero.")

    state = dict(session.working_state or {})
    reads = dict(state.get(RUN_READS_KEY) or {})
    rereads = dict(state.get(RUN_REREADS_KEY) or {})
    result_files: dict[str, str] = {}
    unchanged: dict[str, str] = {}
    missing: list[str] = []
    truncated: list[str] = []
    total = 0
    for path in paths:
        _reject_foreign(path)
        if path not in files:
            missing.append(path)
            continue
        content = files[path]
        digest = history.sha(content)
        # The hash is *extra* information, never a substitute for the content (2026-10-26). The
        # provider payload keeps the data of the newest exchange only — history.build replays older
        # results as their one-line summary — so answering «sin cambios» left the model unable to
        # see the file again: the run ended saying «no puedo leer el contenido real de
        # integration.yaml» and the reader gave up (20M tokens, `limit:rounds`, three runs).
        if reads.get(path) == digest:
            unchanged[path] = digest
            rereads[path] = int(rereads.get(path, 0)) + 1
        else:
            rereads[path] = 0
        if total + len(content) <= MAX_TOOL_RESULT_CHARS:
            result_files[path] = content
            total += len(content)
            reads[path] = digest          # remembered only to say "did not change"
        else:
            remaining = MAX_TOOL_RESULT_CHARS - total
            if remaining > 0:
                result_files[path] = content[:remaining]
                total += remaining
            truncated.append(path)

    requested = [path for path in paths if path not in missing]
    over = [path for path in requested if rereads.get(path, 0) >= 2]
    if over and len(over) == len(requested):
        raise ToolError(t("assistant.read_repeat", paths=", ".join(sorted(over))))
    state[RUN_READS_KEY] = reads
    state[RUN_REREADS_KEY] = rereads
    session.working_state = state
    _remember(session, {path: history.sha(files[path]) for path in result_files})
    note = None
    if unchanged:
        note = "sin cambios desde la lectura anterior (el contenido va incluido)"
    summary = f"Leyó {len(result_files)} archivos del proyecto."
    if unchanged:
        hashes = ", ".join(f"{path}: {digest[:12]}" for path, digest in unchanged.items())
        summary = f"{note} ({hashes})."
    return (
        {
            "files": result_files,
            "unchanged": unchanged,
            "note": note,
            "missing": missing,
            "truncated": truncated,
            "available": sorted(files),
        },
        summary,
    )


def _profile_source(
    db: Session,
    actor: Any,
    session: Any,
    args: dict[str, Any],
    app_settings: Any,
    ip: str | None,
) -> tuple[dict[str, Any], str]:
    try:
        result, summary = origin.profile_source(db, actor, session, args, app_settings, ip)
    except origin.OriginToolError as e:
        raise ToolError(e.message) from e
    return sanitize(result), summary


def _check_query(
    db: Session,
    actor: Any,
    session: Any,
    args: dict[str, Any],
    app_settings: Any,
    ip: str | None,
) -> tuple[dict[str, Any], str]:
    try:
        result, summary = origin.check_query(db, actor, session, args, app_settings, ip)
    except origin.OriginToolError as e:
        raise ToolError(e.message) from e
    cleaned = sanitize(result)
    path = args.get("path")
    if isinstance(path, str) and origin.REQUEST_FILE.match(path) and isinstance(cleaned, dict):
        # 040 (E): the shape this check read is what `/speckit-implement` must write `fields` from.
        checks = dict(session.query_checks or {})
        entry = dict(checks.get(path) or {})
        entry.update({"ok": bool(cleaned.get("ok")),
                      "keys": [str(key) for key in cleaned.get("keys") or []]})
        checks[path] = entry
        session.query_checks = checks
        db.add(real(session))
        db.flush()
    if session.draft and args.get("path") and isinstance(cleaned, dict) and "ok" in cleaned:
        cleaned["readiness"] = readiness.compute(session)
    return cleaned, summary


def _run_preview(db: Session, session: Any, app_settings: Any) -> tuple[dict[str, Any], str]:
    if session.status != "open":
        raise ToolError("La conversación no está abierta.")
    if not session.draft or not (session.validation or {}).get("valid"):
        raise ToolError("El borrador debe ser válido antes de la vista previa; "
                        "corrige los errores de validación.")
    if (session.preview or {}).get("status") == "pending":
        raise ToolError("Ya hay una vista previa en curso; espera a que termine.")
    # Feature 028: an authorised Auto run fixes and retries without a preview cap (owner: no
    # limits); a contract that sets `limits.previews` is still enforced by `_guard_check`.
    limit = None if auto.live_contract(session) is not None else app_settings.ai_chat_max_previews
    if limit is not None and int((session.stats or {}).get("previews") or 0) >= limit:
        raise ToolError(f"Se alcanzó el máximo de {limit} vistas previas en esta conversación.")

    _bump(session, "previews")
    try:
        with db.begin_nested():
            result = preview.run_draft_preview(db, session, time_limit_s=120)
    except preview.PreviewBusy:
        raise ToolError("Ya hay una vista previa en curso; espera a que termine.") from None
    except Exception:
        log.exception("No se pudo ejecutar la vista previa")
        raise ToolError("No se pudo ejecutar la vista previa; revisa el borrador "
                        "e inténtalo de nuevo.") from None
    db.add(real(session))
    db.flush()
    checks = [
        {"dataset": c.get("dataset"), "type": c.get("type"), "ok": bool(c.get("ok"))}
        for item in (result.get("integrations") or {}).values()
        for c in item.get("checks") or []
    ]
    return {
        "status": result["status"],
        "lines": preview.outcome_lines(result),
        "checks": checks,
        "readiness": readiness.compute(session),
    }, ("Ejecutó una vista previa (correcta)." if result["status"] == "succeeded"
        else "Ejecutó una vista previa (con errores).")


def _update_notes(db: Session, session: Any, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Guarda las notas de trabajo en el estado de la sesión."""
    for field in ("goal", "step", "next"):
        value = args.get(field)
        if value is not None and not isinstance(value, str):
            raise ToolError(f"{field} debe ser texto o nulo.")
    for field in ("decisions_add", "done_add"):
        value = args.get(field)
        if value is not None and not isinstance(value, list):
            raise ToolError(f"{field} debe ser una lista de textos.")
        if value is not None and not all(isinstance(item, str) for item in value):
            raise ToolError(f"{field} debe ser una lista de textos.")

    if all(args.get(field) is None
           for field in ("goal", "step", "next", "decisions_add", "done_add")):
        raise ToolError("Indica al menos un campo de las notas.")

    state = dict(session.working_state or {})
    for field in ("goal", "step", "next"):
        value = args.get(field)
        if value is not None:
            cleaned = value.strip()[:NOTES_TEXT_CHARS]
            if cleaned:
                state[field] = cleaned
            else:
                state.pop(field, None)

    for field, key in (("decisions_add", "decisions"), ("done_add", "done")):
        value = args.get(field)
        if value is not None:
            existing = state.get(key)
            items = list(existing) if isinstance(existing, list) else []
            for item in value:
                cleaned = item.strip()[:NOTES_TEXT_CHARS]
                if cleaned:
                    items.append(cleaned)
            state[key] = items[-NOTES_MAX_ITEMS:]

    session.working_state = state

    result = {
        "goal": state.get("goal"),
        "step": state.get("step"),
        "done": state.get("done", []),
        "next": state.get("next"),
        "decisions": state.get("decisions", []),
    }

    db.add(real(session))
    db.flush()
    return (result, t("assistant.summary.updated_notes"))
