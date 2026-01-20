import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app.utils.deps as deps


class _User:
    def __init__(
        self,
        *,
        id: int = 1,
        username: str = "u",
        role: str = deps.Role.USER,
        is_active: bool = True,
        phone_verified: bool = False,
        email_verified: bool = False,
    ) -> None:
        self.id = id
        self.username = username
        self.role = role
        self.is_active = is_active
        self.phone_verified = phone_verified
        self.email_verified = email_verified


class _Result:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _DB:
    def __init__(self, user):
        self._user = user
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _Result(self._user)


def _cred(token: str = "t") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials_401(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _DB(_User())
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=None)
    assert e.value.status_code == 401
    assert e.value.headers and e.value.headers.get("WWW-Authenticate")


@pytest.mark.asyncio
async def test_get_current_user_decode_failed_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: None)
    db = _DB(_User())
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=_cred("bad"))
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_sub_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {})
    db = _DB(_User())
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=_cred())
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_sub_not_int_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "abc"})
    db = _DB(_User())
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=_cred())
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_user_not_found_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "1"})
    db = _DB(None)
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=_cred())
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_inactive_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "1"})
    db = _DB(_User(is_active=False))
    with pytest.raises(HTTPException) as e:
        await deps.get_current_user(db=db, credentials=_cred())
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "2"})
    u = _User(id=2)
    db = _DB(u)
    got = await deps.get_current_user(db=db, credentials=_cred())
    assert got is u


@pytest.mark.asyncio
async def test_get_current_user_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "1"})

    db = _DB(_User())
    assert await deps.get_current_user_optional(db=db, credentials=None) is None

    got = await deps.get_current_user_optional(db=db, credentials=_cred())
    assert got is not None

    monkeypatch.setattr(deps, "decode_token", lambda _t: None)
    assert await deps.get_current_user_optional(db=db, credentials=_cred("bad")) is None


@pytest.mark.asyncio
async def test_require_admin_moderator_lawyer() -> None:
    admin = _User(role=deps.Role.ADMIN)
    user = _User(role=deps.Role.USER)
    moderator = _User(role=deps.Role.MODERATOR)
    lawyer = _User(role=deps.Role.LAWYER)

    assert await deps.require_admin(admin) is admin
    with pytest.raises(HTTPException) as e1:
        await deps.require_admin(user)
    assert e1.value.status_code == 403

    assert await deps.require_moderator(moderator) is moderator
    assert await deps.require_moderator(admin) is admin
    with pytest.raises(HTTPException) as e2:
        await deps.require_moderator(user)
    assert e2.value.status_code == 403

    assert await deps.require_lawyer(lawyer) is lawyer
    with pytest.raises(HTTPException) as e3:
        await deps.require_lawyer(user)
    assert e3.value.status_code == 403


@pytest.mark.asyncio
async def test_require_verified_flags() -> None:
    u = _User(phone_verified=False, email_verified=False)
    with pytest.raises(HTTPException) as e1:
        await deps.require_phone_verified(u)
    assert e1.value.status_code == 403

    with pytest.raises(HTTPException) as e2:
        await deps.require_email_verified(u)
    assert e2.value.status_code == 403

    u2 = _User(phone_verified=True, email_verified=False)
    with pytest.raises(HTTPException) as e3:
        await deps.require_user_verified(u2)
    assert e3.value.status_code == 403

    u3 = _User(phone_verified=True, email_verified=True)
    assert await deps.require_user_verified(u3) is u3

    lawyer_bad = _User(role=deps.Role.LAWYER, phone_verified=False)
    with pytest.raises(HTTPException) as e4:
        await deps.require_lawyer_phone_verified(lawyer_bad)
    assert e4.value.status_code == 403

    lawyer_ok = _User(role=deps.Role.LAWYER, phone_verified=True, email_verified=False)
    assert await deps.require_lawyer_phone_verified(lawyer_ok) is lawyer_ok

    with pytest.raises(HTTPException) as e5:
        await deps.require_lawyer_verified(lawyer_ok)
    assert e5.value.status_code == 403

    lawyer_ok2 = _User(role=deps.Role.LAWYER, phone_verified=True, email_verified=True)
    assert await deps.require_lawyer_verified(lawyer_ok2) is lawyer_ok2
