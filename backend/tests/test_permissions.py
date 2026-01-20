import pytest
from fastapi import HTTPException

from app.utils.permissions import (
    Permission,
    Role,
    has_any_role,
    has_permission,
    has_role,
    is_owner_or_admin,
    require_any_role,
    require_owner_or_admin,
    require_permission,
    require_role,
)


class _User:
    def __init__(self, *, id: int, username: str = "u", role: str = Role.USER):
        self.id = id
        self.username = username
        self.role = role


class _Post:
    def __init__(self, *, user_id: int):
        self.user_id = user_id


def test_has_permission_role_mapping() -> None:
    user = _User(id=1, role=Role.USER)
    assert has_permission(user, Permission.POST_READ) is True
    assert has_permission(user, Permission.POST_DELETE) is False
    assert has_permission(None, Permission.POST_READ) is False


def test_has_role_and_any_role() -> None:
    admin = _User(id=1, role=Role.ADMIN)
    assert has_role(admin, Role.ADMIN) is True
    assert has_role(admin, Role.USER) is False
    assert has_any_role(admin, [Role.USER, Role.ADMIN]) is True
    assert has_any_role(admin, [Role.MODERATOR]) is False
    assert has_any_role(None, [Role.ADMIN]) is False


def test_is_owner_or_admin() -> None:
    owner = _User(id=1, role=Role.USER)
    other = _User(id=2, role=Role.USER)
    admin = _User(id=3, role=Role.ADMIN)
    moderator = _User(id=4, role=Role.MODERATOR)

    assert is_owner_or_admin(owner, 1) is True
    assert is_owner_or_admin(other, 1) is False
    assert is_owner_or_admin(admin, 1) is True
    assert is_owner_or_admin(moderator, 1) is True
    assert is_owner_or_admin(None, 1) is False


@pytest.mark.asyncio
async def test_require_permission_decorator() -> None:
    @require_permission(Permission.POST_DELETE)
    async def delete_post(*, current_user):
        return "ok"

    admin = _User(id=1, role=Role.ADMIN)
    assert await delete_post(current_user=admin) == "ok"

    user = _User(id=2, role=Role.USER)
    with pytest.raises(HTTPException) as e1:
        await delete_post(current_user=user)
    assert e1.value.status_code == 403

    with pytest.raises(HTTPException) as e2:
        await delete_post(current_user=None)
    assert e2.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_and_any_role_decorators() -> None:
    @require_role(Role.ADMIN)
    async def admin_only(*, current_user):
        return "ok"

    @require_any_role([Role.ADMIN, Role.MODERATOR])
    async def mod_or_admin(*, current_user):
        return "ok"

    admin = _User(id=1, role=Role.ADMIN)
    moderator = _User(id=2, role=Role.MODERATOR)
    user = _User(id=3, role=Role.USER)

    assert await admin_only(current_user=admin) == "ok"
    with pytest.raises(HTTPException) as e1:
        await admin_only(current_user=user)
    assert e1.value.status_code == 403

    assert await mod_or_admin(current_user=admin) == "ok"
    assert await mod_or_admin(current_user=moderator) == "ok"
    with pytest.raises(HTTPException) as e2:
        await mod_or_admin(current_user=user)
    assert e2.value.status_code == 403

    with pytest.raises(HTTPException) as e3:
        await admin_only(current_user=None)
    assert e3.value.status_code == 401

    with pytest.raises(HTTPException) as e4:
        await mod_or_admin(current_user=None)
    assert e4.value.status_code == 401


@pytest.mark.asyncio
async def test_require_owner_or_admin_decorator() -> None:
    @require_owner_or_admin("post.user_id")
    async def update_post(*, post, current_user):
        return "ok"

    post = _Post(user_id=1)
    owner = _User(id=1, role=Role.USER)
    admin = _User(id=2, role=Role.ADMIN)
    other = _User(id=3, role=Role.USER)

    assert await update_post(post=post, current_user=owner) == "ok"
    assert await update_post(post=post, current_user=admin) == "ok"

    with pytest.raises(HTTPException) as e1:
        await update_post(post=post, current_user=other)
    assert e1.value.status_code == 403

    with pytest.raises(HTTPException) as e2:
        await update_post(post=None, current_user=admin)
    assert e2.value.status_code == 500

    with pytest.raises(HTTPException) as e3:
        await update_post(post=post, current_user=None)
    assert e3.value.status_code == 401
