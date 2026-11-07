"""Feature 058, US4: an authored distribution names lists, and apply resolves those names.

The YAML carries no addresses (constitution II); it carries the names of lists the installation owns.
Applying is the moment the project meets the installation, so a name nobody created is refused there,
naming it, instead of delivering to nobody for a month.
"""
import pytest

from app.db import get_sessionmaker
from app.errors import ApiError
from app.mail import lists as mail_lists
from app.models import AppUser
from app.projects import distributions
from tests.conftest import make_user, signed_in, sql
from tests.test_runner import origin as origin  # fixture
from tests.test_runner import pg_source as pg_source  # fixture
from tests.test_project_distributions import WEEKLY, OWNED, counts, project, version
from tests.test_project_distributions import run_sync
from tests.test_vibe_reporting import applied as applied  # fixture
from tests.test_vibe_reporting import workspace as workspace  # fixture

BY_LIST = {**WEEKLY, "recipients": {"roles": ["admin"], "lists": ["Gerencia comercial"]}}


def make_list(name="Gerencia comercial") -> int:
    c = signed_in("root@example.com")
    row = c.post("/api/mail/lists", json={"name": name, "visibility": "compartida"}).json()
    c.put(f"/api/mail/lists/{row['id']}/members",
          json={"members": [{"address": "ana@cliente.com"}]})
    return row["id"]


def test_a_list_name_becomes_a_list_recipient(project):
    list_id = make_list()
    assert run_sync(version(BY_LIST)) == counts(created=1)
    stored = sql(f"SELECT recipients {OWNED}")[0][0]
    assert stored == [{"role": "admin"}, {"list": list_id}]


def test_a_missing_list_refuses_the_apply_and_names_it(project):
    with pytest.raises(ApiError) as error:
        run_sync(version(BY_LIST))
    assert error.value.status == 409
    assert error.value.code == "distribution_list_missing"
    assert "Gerencia comercial" in str(error.value)
    assert sql("SELECT count(*) FROM email_subscription")[0][0] == 0


def test_the_name_is_matched_case_insensitively(project):
    list_id = make_list("Gerencia Comercial")
    assert run_sync(version({**WEEKLY, "recipients": {"lists": ["gerencia comercial"]}})) == \
        counts(created=1)
    assert sql(f"SELECT recipients {OWNED}")[0][0] == [{"list": list_id}]


def test_the_shared_list_wins_over_a_personal_one_with_the_same_name(project):
    owner = make_user("empleado@example.com", full_name="Empleado")
    signed_in(owner.email).post("/api/mail/lists", json={"name": "Equipo"})
    shared_id = make_list("Equipo")
    assert run_sync(version({**WEEKLY, "recipients": {"lists": ["Equipo"]}})) == counts(created=1)
    assert sql(f"SELECT recipients {OWNED}")[0][0] == [{"list": shared_id}]


def test_roles_and_lists_together(project):
    list_id = make_list()
    assert run_sync(version(BY_LIST)) == counts(created=1)
    recipients = sql(f"SELECT recipients {OWNED}")[0][0]
    assert {"role": "admin"} in recipients and {"list": list_id} in recipients
