import pytest

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_user_service_create_and_duplicate_raises_value_error(test_session):
    u1 = await UserService.create(
        test_session,
        UserCreate(
            username="user1",
            email="u1@example.com",
            nickname=None,
            password="p@ssw0rd",
            agree_terms=True,
            agree_privacy=True,
            agree_ai_disclaimer=True,
        ),
    )
    assert u1.id is not None
    assert u1.username == "user1"
    assert u1.email == "u1@example.com"
    assert u1.nickname == "user1"
    assert u1.hashed_password != "p@ssw0rd"

    await test_session.commit()

    with pytest.raises(ValueError):
        await UserService.create(
            test_session,
            UserCreate(
                username="user1",
                email="u2@example.com",
                nickname=None,
                password="p@ssw0rd",
                agree_terms=True,
                agree_privacy=True,
                agree_ai_disclaimer=True,
            ),
        )

    u2 = await UserService.create(
        test_session,
        UserCreate(
            username="user2",
            email="u2@example.com",
            nickname="nick",
            password="p@ssw0rd",
            agree_terms=True,
            agree_privacy=True,
            agree_ai_disclaimer=True,
        ),
    )
    await test_session.commit()
    assert u2.username == "user2"


@pytest.mark.asyncio
async def test_user_service_update_phone_normalizes_and_resets_verification(test_session):
    user = User(username="user3", email="u3@example.com", nickname="user3", hashed_password="x")
    user.phone = "123"
    user.phone_verified = True
    user.phone_verified_at = None
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    updated = await UserService.update(test_session, user, UserUpdate(phone=" 456 "))
    assert updated.phone == "456"
    assert updated.phone_verified is False
    assert updated.phone_verified_at is None

    updated2 = await UserService.update(test_session, updated, UserUpdate(phone=None))
    assert updated2.phone is None
    assert updated2.phone_verified is False


@pytest.mark.asyncio
async def test_user_service_authenticate_and_taken_checks(test_session):
    _ = await UserService.create(
        test_session,
        UserCreate(
            username="loginuser",
            email="login@example.com",
            nickname=None,
            password="secret123",
            agree_terms=True,
            agree_privacy=True,
            agree_ai_disclaimer=True,
        ),
    )
    await test_session.commit()

    ok = await UserService.authenticate(test_session, "loginuser", "secret123")
    assert ok is not None

    bad = await UserService.authenticate(test_session, "loginuser", "wrong")
    assert bad is None

    missing = await UserService.authenticate(test_session, "missing", "secret123")
    assert missing is None

    assert await UserService.is_username_taken(test_session, "loginuser") is True
    assert await UserService.is_username_taken(test_session, "nope") is False
    assert await UserService.is_email_taken(test_session, "login@example.com") is True
    assert await UserService.is_email_taken(test_session, "nope@example.com") is False


@pytest.mark.asyncio
async def test_user_service_get_list_supports_keyword_and_pagination(test_session):
    for i in range(5):
        user = User(
            username=f"k{i}",
            email=f"k{i}@example.com",
            nickname=f"nick{i}",
            hashed_password="x",
        )
        test_session.add(user)
    await test_session.commit()

    users, total = await UserService.get_list(test_session, page=1, page_size=2)
    assert total >= 5
    assert len(users) == 2
    assert users[0].id > users[1].id

    users_kw, total_kw = await UserService.get_list(test_session, page=1, page_size=20, keyword="nick4")
    assert total_kw == 1
    assert len(users_kw) == 1
    assert users_kw[0].username == "k4"
