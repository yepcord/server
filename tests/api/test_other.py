import pytest as pt
import pytest_asyncio

from src.rest_api.main import app
from src.yepcord.config import Config
from tests.api.utils import TestClientType, create_users


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    for func in app.before_serving_funcs:
        await app.ensure_async(func)()
    yield
    for func in app.after_serving_funcs:
        await app.ensure_async(func)()


@pt.mark.asyncio
async def test_unknown_endpoints():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    response = await client.get(f"/api/v9/unknown_endpoint", headers=headers)
    assert response.status_code == 501
    response = await client.get(f"/api/v9/unknown_endpoint")
    assert response.status_code == 501
    response = await client.get(f"/api/v9/unknown/nested/endpoint")
    assert response.status_code == 501
    response = await client.post(f"/api/v9/unknown_endpoint_post")
    assert response.status_code == 501
    response = await client.post(f"/api/v9/unknown/nested/endpoint/post")
    assert response.status_code == 501


@pt.mark.asyncio
async def test_hardcoded_endpoints():
    client: TestClientType = app.test_client()

    resp = await client.get(f"/api/v9/auth/location-metadata")
    assert resp.status_code == 200

    resp = await client.post(f"/api/v9/science")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v9/experiments")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/applications/detectable")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/survey")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/affinities/guilds")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/affinities/users")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/library")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/payment-sources")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/country-code")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/localized-pricing-promo")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/user-trial-offer")
    assert resp.status_code == 404

    resp = await client.get(f"/api/v9/users/@me/billing/subscriptions")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/subscription-slots")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/guilds/premium/subscription-slots")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/outbound-promotions")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/applications/0/entitlements")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/store/published-listings/skus/978380684370378762/subscription-plans")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v9/store/published-listings/skus/521846918637420545/subscription-plans")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v9/store/published-listings/skus/521847234246082599/subscription-plans")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v9/store/published-listings/skus/590663762298667008/subscription-plans")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v9/store/published-listings/skus/1/subscription-plans")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/outbound-promotions/codes")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/entitlements/gifts")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/activities/statistics/applications")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/billing/payments")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/settings-proto/3")
    assert resp.status_code == 200

    resp = await client.patch(f"/api/v9/users/@me/settings-proto/3")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/users/@me/settings-proto/4")
    assert resp.status_code == 400

    resp = await client.patch(f"/api/v9/users/@me/settings-proto/4")
    assert resp.status_code == 400

    resp = await client.get(f"/api/v9/gateway")
    assert resp.status_code == 200
    assert await resp.get_json() == {"url": f"wss://{Config.GATEWAY_HOST}"}

    resp = await client.get(f"/api/v9/oauth2/tokens")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/sticker-packs")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v9/instance")
    assert resp.status_code == 200
    json = await resp.get_json()
    assert "name" in json
    assert "features" in json


@pt.mark.asyncio
async def test_gifs_trending():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.get("/api/v9/gifs/trending", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert json["categories"]

    resp = await client.get("/api/v9/gifs/trending", headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v9/gifs/trending-gifs", headers=headers)
    assert resp.status_code == 200
    resp = await client.get("/api/v9/gifs/trending-gifs", headers=headers)
    assert resp.status_code == 200

    resp = await client.post("/api/v9/gifs/select", headers=headers)
    assert resp.status_code == 204
    resp = await client.post("/api/v9/gifs/select", headers=headers)
    assert resp.status_code == 204


@pt.mark.asyncio
async def test_gifs_search_suggest():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.get("/api/v9/gifs/search?q=cat", headers=headers)
    assert resp.status_code == 200
    assert len(await resp.get_json()) > 0

    resp = await client.get("/api/v9/gifs/search?q=cat", headers=headers)
    assert resp.status_code == 200

    resp = await client.get("/api/v9/gifs/suggest?q=cat&limit=5", headers=headers)
    assert resp.status_code == 200
    json = await resp.get_json()
    assert 0 < len(json) <= 5

    resp = await client.get("/api/v9/gifs/suggest?q=cat&limit=5", headers=headers)
    assert resp.status_code == 200


@pt.mark.asyncio
async def test_harvest():
    client: TestClientType = app.test_client()
    user = (await create_users(client, 1))[0]
    headers = {"Authorization": user["token"]}

    resp = await client.get("/api/v9/users/@me/harvest", headers=headers)
    assert resp.status_code == 204

