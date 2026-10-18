from tests.conftest import PASSWORD, client, make_user, signed_in, sql


def test_anonymous_me_spanish():
    resp = client().get('/api/me')
    assert resp.status_code == 401
    body = resp.json()
    assert body['error']['message'] == 'Tu sesión terminó. Ingresa de nuevo.'
    assert body['error']['key'] == 'auth.session_ended'


def test_anonymous_me_english_header():
    resp = client().get('/api/me', headers={'Accept-Language': 'en-US'})
    assert resp.status_code == 401
    body = resp.json()
    assert body['error']['message'] == 'Your session has ended. Please sign in again.'


def test_account_locale_wins():
    u = make_user('locale@example.com')
    sql("UPDATE app_user SET locale = 'en' WHERE id = :i", i=u.id)
    c = signed_in('locale@example.com')
    resp = c.patch('/api/me/preferences', json={}, headers={'Accept-Language': 'es'})
    assert resp.status_code == 422
    body = resp.json()
    assert body['error']['message'] == 'Check the data you entered.'
    assert body['error']['key'] == 'common.validation'


def test_config_default_locale():
    resp = client().get('/api/config')
    assert resp.status_code == 200
    assert resp.json()['default_locale'] == 'es'


def test_preferences_locale_en(user):
    c = signed_in('user@example.com')
    resp = c.patch('/api/me/preferences', json={'locale': 'en'})
    assert resp.status_code == 200
    resp = c.get('/api/me')
    assert resp.json()['locale'] == 'en'


def test_preferences_locale_es_then_theme_dark(user):
    c = signed_in('user@example.com')
    resp = c.patch('/api/me/preferences', json={'locale': 'es'})
    assert resp.status_code == 200
    resp = c.patch('/api/me/preferences', json={'theme': 'dark'})
    assert resp.status_code == 200
    resp = c.get('/api/me')
    data = resp.json()
    assert data['locale'] == 'es'
    assert data['theme'] == 'dark'


def test_preferences_locale_none(user):
    c = signed_in('user@example.com')
    resp = c.patch('/api/me/preferences', json={'locale': None})
    assert resp.status_code == 200
    resp = c.get('/api/me')
    assert resp.json()['locale'] is None


def test_preferences_empty_payload(user):
    c = signed_in('user@example.com')
    resp = c.patch('/api/me/preferences', json={})
    assert resp.status_code == 422


def test_preferences_invalid_locale(user):
    c = signed_in('user@example.com')
    resp = c.patch('/api/me/preferences', json={'locale': 'fr'})
    assert resp.status_code == 422


def test_preferences_anonymous():
    resp = client().patch(
        '/api/me/preferences',
        json={'locale': 'en'},
        headers={'X-Requested-With': 'fetch'}
    )
    assert resp.status_code == 401


def test_login_invalid_credentials_english():
    response = client().post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": PASSWORD},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["key"] == "auth.invalid_credentials"
    assert body["error"]["message"] == "Incorrect email or password."


def test_login_locked_english():
    make_user("lock-en@example.com")
    response = None
    for _ in range(5):
        response = client().post(
            "/api/auth/login",
            json={"email": "lock-en@example.com", "password": "wrong-password"},
            headers={"Accept-Language": "en"},
        )
    assert response.status_code == 423
    body = response.json()
    assert "15 min" in body["error"]["message"]
    assert body["error"]["params"] == {"minutes": 15}


def test_mfa_conflict_english():
    make_user("mfa-en@example.com")
    sql("UPDATE app_user SET locale = 'en' WHERE email = 'mfa-en@example.com'")
    c = signed_in("mfa-en@example.com")
    assert c.post("/api/auth/reauth", json={"password": PASSWORD}).status_code == 204
    response = c.post("/api/me/mfa/disable", json={"code": "000000"})
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["message"] == "Two-step verification is not active."


def test_login_invalid_credentials_spanish_default():
    make_user("spanish-default@example.com")
    response = client().post(
        "/api/auth/login",
        json={"email": "spanish-default@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["message"] == "Correo o contraseña incorrectos."


def test_unknown_report_english():
    make_user("rep-en@example.com")
    c = signed_in("rep-en@example.com")
    r = c.get("/api/reports/does-not-exist/data", headers={"Accept-Language": "en"})
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["key"] == "report.not_found"
    assert body["error"]["message"] == "This report does not exist."
