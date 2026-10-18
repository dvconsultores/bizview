"""Schema property descriptions served by the authoring guide (feature 017, FR-001)."""

import pytest

from bizview_cli import authoring
from bizview_cli.validate import SCHEMAS

FRAGMENT_TOPIC = (
    "fragment:integration#/properties/datasets/additionalProperties/properties/"
    "extract/oneOf/0/properties/query"
)


def _escape(name: str) -> str:
    return name.replace("~", "~0").replace("/", "~1")


def _pointers(schema, pointer=""):
    """RFC 6901 pointers of property schemas that lack a non-empty description."""
    if isinstance(schema, dict):
        props = schema.get("properties")
        if isinstance(props, dict):
            for name, prop_schema in props.items():
                if not (isinstance(prop_schema, dict)
                        and isinstance(prop_schema.get("description"), str)
                        and prop_schema["description"].strip()):
                    yield pointer + "/properties/" + _escape(name)
        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict):
                for name, prop_schema in value.items():
                    yield from _pointers(prop_schema,
                                         pointer + "/properties/" + _escape(name))
            else:
                yield from _pointers(value, pointer + "/" + _escape(key))
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            yield from _pointers(item, pointer + "/" + str(index))


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_all_properties_have_description(name):
    missing = [f"{name}:{p}" for p in sorted(_pointers(SCHEMAS[name].schema))]
    assert not missing, f": {', '.join(missing)}"


def test_walker_detects_missing_descriptions():
    schema = {
        "properties": {
            "a": {"type": "string"},
            "b": {
                "description": "x",
                "oneOf": [{"properties": {"c": {}}}],
            },
        }
    }
    assert sorted(_pointers(schema)) == [
        "/properties/a",
        "/properties/b/oneOf/0/properties/c",
    ]


def test_guide_exposes_descriptions():
    report = authoring.guide("report")
    views_desc = report["schema"]["properties"]["views"]["description"]
    assert isinstance(views_desc, str) and views_desc.strip()

    fragment = authoring.guide(FRAGMENT_TOPIC)
    assert isinstance(fragment["fragment"]["description"], str)
    assert "queries/" in fragment["fragment"]["description"]
