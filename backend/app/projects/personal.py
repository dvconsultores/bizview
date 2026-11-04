"""Dependency-free personal-data helpers shared by readiness and origin."""

from __future__ import annotations

import re
import unicodedata
from itertools import pairwise
from typing import Any

import sqlglot
from sqlglot import exp


def _normalise_tokens(name: str) -> list[str]:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name or "")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return [t for t in re.split(r"[^a-z0-9]+", value.lower()) if t]


_PEOPLE = {
    # A bare `name`/`nombre` column is only personal when the table it lives in is about people:
    # a coin, product or category name is data, not personal data (owner, 2026-11-04: a report of
    # crypto listings could not be applied because its `name` column was flagged).
    "customer", "customers", "client", "clients", "cliente", "clientes",
    "user", "users", "usuario", "usuarios", "person", "persons", "persona", "personas",
    "patient", "patients", "paciente", "pacientes", "contact", "contacts", "contacto",
    "contactos", "employee", "employees", "empleado", "empleados", "staff", "member",
    "members", "miembro", "miembros", "subscriber", "subscribers", "suscriptor",
    "suscriptores", "lead", "leads", "prospect", "prospects", "owner", "titular",
    "beneficiary", "beneficiario", "beneficiarios", "driver", "conductor", "student",
    "estudiante", "estudiantes", "citizen", "ciudadano", "afiliado", "afiliados",
    "associate", "socio", "socios", "supplier", "suppliers", "proveedor", "proveedores",
    "vendor", "vendedor", "vendedores", "agent", "agente", "agentes",
}


def _about_people(context: str | None) -> bool:
    """Whether a table/dataset name says its rows are people (so a bare `name` is a person's)."""
    if not context:
        return False
    return bool(set(_normalise_tokens(context)) & _PEOPLE)


def personal_kind(name: str, data_type: str | None = None,
                  context: str | None = None) -> str | None:
    """Heuristic personal-data classification for a column name / type.

    `context` is the table or dataset the column belongs to: it decides the ambiguous names
    (`name`, `nombre`), which are personal only where the rows are people."""
    tokens = _normalise_tokens(name)
    if not tokens:
        return None
    toks = set(tokens)
    if toks & {"email", "emails", "correo", "correos", "mail"}:
        return "email"
    if toks & {"phone", "telefono", "telefonos", "celular", "movil", "mobile", "tel", "whatsapp"}:
        return "phone"
    if toks & {"cedula", "dni", "rif", "ssn", "passport", "pasaporte", "documento",
               "nif", "nie", "curp", "rut", "cuit"}:
        return "document_id"
    if any(a == "chat" and b == "id" for a, b in pairwise(tokens)) or toks & {"chatid", "telegram"}:
        return "chat_id"
    if toks & {"card", "tarjeta", "iban", "cuenta", "cvv"}:
        return "payment"
    if toks & {"nacimiento", "birth", "birthdate", "birthday", "dob", "born",
               "cumpleanos", "fechanacimiento"}:
        return "birth_date"
    if toks & {"apellido", "apellidos", "fullname", "firstname", "lastname", "surname"}:
        return "name"
    if tokens in (["name"], ["nombre"], ["nombres"]):
        return "name" if _about_people(context) else None
    if (toks & {"name", "nombre", "nombres"}) and (
        toks & {"first", "last", "full", "middle", "given", "family", "customer",
                "client", "cliente", "user", "usuario", "contact", "contacto",
                "person", "persona", "owner", "titular", "patient", "paciente", "completo"}
    ):
        return "name"
    if (data_type or "").lower() in {"json", "jsonb"} and toks & {
            "payload", "raw", "data", "body", "datos"}:
        return "payload"
    return None


def query_columns(sql_text: str) -> set[str]:
    """Origin column names a SQL query reads (best-effort)."""
    try:
        parsed = sqlglot.parse_one(sql_text, read="postgres")
    except Exception:
        return set()
    names: set[str] = set()
    for node in parsed.find_all(exp.Column):
        name = node.name
        if name and name != "*":
            names.add(name)
    return names


def query_tables(sql_text: str) -> set[str]:
    """Tables a SQL query reads, as 'schema.table' or 'table' (best-effort, lower case)."""
    try:
        parsed = sqlglot.parse_one(sql_text, read="postgres")
    except Exception:
        return set()
    if parsed is None:
        return set()
    ctes: set[str] = set()
    for cte in parsed.find_all(exp.CTE):
        if cte.alias:
            ctes.add(cte.alias.lower())
    tables: set[str] = set()
    for node in parsed.find_all(exp.Table):
        name = node.name
        if not name:
            continue
        if name.lower() in ctes:
            continue
        if node.db:
            tables.add(f"{node.db}.{name}".lower())
        else:
            tables.add(name.lower())
    return tables

def request_columns(request: Any) -> set[str]:
    """Column names a REST request reads from its fields mapping."""
    if not isinstance(request, dict):
        return set()
    fields = request.get("fields")
    if not isinstance(fields, dict):
        return set()
    names: set[str] = set()
    for key, path in fields.items():
        names.add(str(key))
        if isinstance(path, str):
            names.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", path))
    return names


def shape_personal(shape: Any, prefix: str = "") -> list[dict]:
    """Walk a describe shape and return personal columns with dotted paths."""
    found: list[dict] = []

    def walk(value: Any, current_prefix: str) -> None:
        if len(found) >= 200:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{current_prefix}.{key}" if current_prefix else str(key)
                kind = personal_kind(str(key))
                if kind is not None:
                    found.append({"column": path, "kind": kind})
                walk(child, path)
        elif isinstance(value, list):
            for item in value:
                walk(item, current_prefix)

    walk(shape, prefix)
    return found
