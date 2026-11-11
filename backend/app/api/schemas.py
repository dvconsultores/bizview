from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import AppUser

Role = Literal["admin", "user"]
Theme = Literal["system", "light", "dark"]


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=256)


class CreateUserIn(BaseModel):
    email: str = Field(max_length=300)
    full_name: str = Field(max_length=200)
    role: Role = "user"
    # Convergence 054b: None creates an account for Google/Telegram with no password.
    temporary_password: str | None = Field(default=None, max_length=256)


class UpdateUserIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    role: Role | None = None
    is_active: bool | None = None


class MfaIn(BaseModel):
    code: str | None = Field(default=None, max_length=12)
    recovery_code: str | None = Field(default=None, max_length=20)


class CodeIn(BaseModel):
    code: str = Field(max_length=12)


class ReauthIn(BaseModel):
    password: str = Field(max_length=128)


class ResetPasswordIn(BaseModel):
    temporary_password: str = Field(max_length=256)


from pydantic import model_validator  # noqa: E402


class PreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theme: Theme | None = None
    locale: str | None = Field(default=None, pattern="^(es|en)$")

    @model_validator(mode='after')
    def check_not_empty(self):
        if not self.model_fields_set:
            raise ValueError('empty')
        return self


class GrantsIn(BaseModel):
    codes: list[str] = Field(max_length=100)


def user_json(u: AppUser, *, password_change_required: bool | None = None) -> dict:
    """The account as JSON. `password_change_required` is the *session's* answer (convergence
    054b): a Google/Telegram session skips the forced change even though the flag is still set;
    the admin listings and the badges keep reading the account's own value."""
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_superuser": u.is_superuser,
        "is_active": u.is_active,
        "must_change_password": (u.must_change_password if password_change_required is None
                                 else password_change_required),
        "has_password": u.password_hash is not None,
        "auth_provider": u.auth_provider,
        "locked_until": u.locked_until,
        "last_login_at": u.last_login_at,
        "created_at": u.created_at,
        "mfa_enabled": u.totp_enabled_at is not None,
        "theme": u.theme,
        "locale": u.locale,
    }
