import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.snowflake import Snowflake
from .utils import TestClientType, create_users, rel_request, rel_count, rel_delete, rel_accept, rel_block


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_relationship_request():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    headers = {"Authorization": user1["token"]}

    response = await client.post('/api/v9/users/@me/relationships', headers=headers,
                                 json={"username": user1["username"], "discriminator": user1["discriminator"]})
    assert response.status_code == 400
    response = await client.post('/api/v9/users/@me/relationships', headers=headers,
                                 json={"username": user2["username"],
                                       "discriminator": str((int(user2["discriminator"]) + 1) % 10000)})
    assert response.status_code == 400

    assert await rel_count(client, user1) == 0
    assert await rel_count(client, user2) == 0
    assert await rel_request(client, user1, user2) == 204

    assert await rel_request(client, user1, user2) == 400


@pt.mark.asyncio
async def test_relationship_accept():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))
    headers = {"Authorization": user1["token"]}

    assert await rel_request(client, user1, user2) == 204
    assert await rel_accept(client, user1, user2) == 204

    assert await rel_count(client, user1) == 1
    assert await rel_count(client, user2) == 1

    response = await client.get(f"/api/v9/users/{user2['id']}/profile", headers=headers)
    assert response.status_code == 200

    assert await rel_request(client, user1, user2) == 400


@pt.mark.asyncio
async def test_relationship_accept_without_request():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))

    assert await rel_accept(client, {"id": Snowflake.makeId()}, user2) == 404
    assert await rel_accept(client, user1, user2) == 204

    assert await rel_count(client, user1) == 1
    assert await rel_count(client, user2) == 1


@pt.mark.asyncio
async def test_relationship_decline():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))

    assert await rel_request(client, user1, user2) == 204
    assert await rel_delete(client, user1, user2) == 204

    assert await rel_count(client, user1) == 0
    assert await rel_count(client, user2) == 0

    assert await rel_request(client, user1, user2) == 204


@pt.mark.asyncio
async def test_relationship_remove():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))

    assert await rel_request(client, user1, user2) == 204
    assert await rel_accept(client, user1, user2) == 204

    assert await rel_count(client, user1) == 1
    assert await rel_count(client, user2) == 1

    assert await rel_delete(client, user1, user2) == 204

    assert await rel_delete(client, {"id": Snowflake.makeId()}, user2) == 204

    assert await rel_count(client, user1) == 0
    assert await rel_count(client, user2) == 0

    assert await rel_request(client, user1, user2) == 204


@pt.mark.asyncio
async def test_relationship_block():
    client: TestClientType = app.test_client()
    user1, user2 = (await create_users(client, 2))

    assert await rel_block(client, user2, user1) == 204  # Block first user

    assert await rel_request(client, user1, user2) == 400  # Try to send request from first user to second
    assert await rel_request(client, user2, user1) == 400  # Try to send request from second user to first

    assert await rel_count(client, user1) == 0  # First user has no relationships
    assert await rel_count(client, user2) == 1  # Second user has 1 relationship (blocked first user)

    assert await rel_block(client, user1, user2) == 204  # Block seconds user

    assert await rel_count(client, user1) == 1  # First user has 1 relationship (blocked second user)
    assert await rel_count(client, user2) == 1  # Second user has 1 relationship (blocked first user)

    assert await rel_delete(client, user2, user1) == 204  # Unblock
    assert await rel_delete(client, user1, user2) == 204  # Unblock

    assert await rel_request(client, user1, user2) == 204  # Try to send request from first user to second

    assert await rel_count(client, user1) == 1
    assert await rel_count(client, user2) == 1

    assert await rel_block(client, user2, user1) == 204
