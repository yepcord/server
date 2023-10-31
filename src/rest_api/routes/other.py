"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2023 RuslanUC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from quart import Blueprint

from ...yepcord.config import Config
from ...yepcord.errors import InvalidDataErr, Errors

# Base path is /
other = Blueprint('other', __name__)


@other.get("/api/v9/auth/location-metadata")
async def api_auth_locationmetadata():
    return {
        "consent_required": False,
        "country_code": "US",
        "promotional_email_opt_in": {"required": True, "pre_checked": False}
    }


@other.post("/api/v9/science")
async def api_science():
    return "", 204


@other.get("/api/v9/experiments")
async def api_experiments():
    return {"fingerprint": "0.A", "assignments": [], "guild_experiments": []}


@other.get("/api/v9/applications/detectable")
async def api_applications_detectable():
    return []


@other.get("/api/v9/users/@me/survey")
async def api_users_me_survey():
    return {"survey": None}


@other.get("/api/v9/users/@me/affinities/guilds")
async def api_users_me_affinities_guilds():
    return {"guild_affinities": []}


@other.get("/api/v9/users/@me/affinities/users")
async def api_users_me_affinities_users():
    return {"user_affinities": [], "inverse_user_affinities": []}


@other.get("/api/v9/users/@me/library")
async def api_users_me_library():
    return []


@other.get("/api/v9/users/@me/billing/payment-sources")
async def api_users_me_billing_paymentsources():
    return []


@other.get("/api/v9/users/@me/billing/country-code")
async def api_users_me_billing_countrycode():
    return {"country_code": "US"}


@other.get("/api/v9/users/@me/billing/localized-pricing-promo")
async def api_users_me_billing_localizedpricingpromo():
    return {"country_code": "US", "localized_pricing_promo": None}


@other.get("/api/v9/users/@me/billing/user-trial-offer")
async def api_users_me_billing_usertrialoffer():
    return {"message": "404: Not Found", "code": 0}, 404


@other.get("/api/v9/users/@me/billing/subscriptions")
async def api_users_me_billing_subscriptions():
    return [{
        "items": [{"id": 1, "plan_id": 511651880837840896, "quantity": 1200}], "id": 1, "type": 2,
        "created_at": 1640995200000, "canceled_at": None, "current_period_start": 1640995200000,
        "current_period_end": 4794595201000, "status": "idk", "payment_source_id": 0, "payment_gateway": None,
        "payment_gateway_plan_id": None, "payment_gateway_subscription_id": None, "trial_id": None,
        "trial_ends_at": None, "renewal_mutations": None, "streak_started_at": 1640995200000, "currency": "USD",
        "metadata": None
    }]


@other.get("/api/v9/users/@me/billing/subscription-slots")
async def api_users_me_billing_subscriptionslots():
    return []


@other.get("/api/v9/users/@me/guilds/premium/subscription-slots")
async def api_users_me_guilds_premium_subscriptionslots():
    return []


@other.get("/api/v9/outbound-promotions")
async def api_outboundpromotions():
    return []


@other.get("/api/v9/users/@me/applications/<aid>/entitlements")
async def api_users_me_applications_id_entitlements(aid):
    return []


@other.get("/api/v9/store/published-listings/skus/<int:sku>/subscription-plans")
async def api_store_publishedlistings_skus_id_subscriptionplans(sku):
    if sku == 978380684370378762:
        return [
            {"id": "978380692553465866", "name": "Premium Basic Monthly", "interval": 1, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "978380684370378762", "currency": "usd", "price": 0,
             "price_tier": None}
        ]
    elif sku == 521846918637420545:
        return [
            {"id": "511651871736201216", "name": "Premium Classic Monthly", "interval": 1, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "521846918637420545", "currency": "usd", "price": 0,
             "price_tier": None},
            {"id": "511651876987469824", "name": "Premium Classic Yearly", "interval": 2, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "521846918637420545", "currency": "usd", "price": 0,
             "price_tier": None}
        ]
    elif sku == 521847234246082599:
        return [
            {"id": "642251038925127690", "name": "Premium Quarterly", "interval": 1, "interval_count": 3,
             "tax_inclusive": True, "sku_id": "521847234246082599", "currency": "usd", "price": 0,
             "price_tier": None},
            {"id": "511651880837840896", "name": "Premium Monthly", "interval": 1, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "521847234246082599", "currency": "usd", "price": 0,
             "price_tier": None},
            {"id": "511651885459963904", "name": "Premium Yearly", "interval": 2, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "521847234246082599", "currency": "usd", "price": 0,
             "price_tier": None}
        ]
    elif sku == 590663762298667008:
        return [
            {"id": "590665532894740483", "name": "Server Premium Monthly", "interval": 1, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "590663762298667008", "discount_price": 0, "currency": "usd",
             "price": 0, "price_tier": None},
            {"id": "590665538238152709", "name": "Server Boost Yearly", "interval": 2, "interval_count": 1,
             "tax_inclusive": True, "sku_id": "590663762298667008", "discount_price": 0, "currency": "usd",
             "price": 0, "price_tier": None}
        ]
    return []


@other.get("/api/v9/users/@me/outbound-promotions/codes")
async def api_users_me_outboundpromotions_codes():
    return []


@other.get("/api/v9/users/@me/entitlements/gifts")
async def api_users_me_entitlements_gifts():
    return []


@other.get("/api/v9/users/@me/activities/statistics/applications")
async def api_users_me_activities_statistics_applications():
    return []


@other.get("/api/v9/users/@me/billing/payments")
async def api_users_me_billing_payments():
    return []


@other.route("/api/v9/users/@me/settings-proto/3", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_3():
    return {"settings": ""}


@other.route("/api/v9/users/@me/settings-proto/<int:t>", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_type(t):
    raise InvalidDataErr(400, Errors.make(50035, {"type": {
        "code": "BASE_TYPE_CHOICES", "message": "Value must be one of (<UserSettingsTypes.PRELOADED_USER_SETTINGS: 1>, "
                                                "<UserSettingsTypes.FRECENCY_AND_FAVORITES_SETTINGS: 2>, "
                                                "<UserSettingsTypes.TEST_SETTINGS: 3>)."
    }}))


@other.get("/api/v9/applications/<int:app_id>/skus")
async def application_skus(app_id: int):
    return []


@other.get("/api/v9/applications/<int:app_id>/subscription-group-listings")
async def application_sub_group_list(app_id: int):
    return {"items": []}


@other.get("/api/v9/applications/<int:app_id>/listings")
async def application_listings(app_id: int):
    return []


# OAuth


@other.get("/api/v9/oauth2/tokens")
async def api_oauth_tokens():
    return []


# Stickers & gifs


@other.get("/api/v9/sticker-packs")
async def api_stickerpacks_get():
    return {"sticker_packs": []}


# Instance-related


@other.get("/api/v9/gateway")
async def api_gateway():
    return {"url": f"wss://{Config.GATEWAY_HOST}"}


@other.get("/api/v9/instance")
async def instance_info():
    return {
        "name": "YEPCord",
        "features": [
            "OLD_USERNAMES",
            "REMOTE_AUTH_V1",
            "SETTINGS_PROTO",
        ],
    }
