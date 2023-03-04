from quart import Blueprint

from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.utils import c_json

# Base path is /
other = Blueprint('other', __name__)


@other.get("/api/v9/auth/location-metadata")
async def api_auth_locationmetadata():
    return c_json("{\"consent_required\": false, \"country_code\": \"US\", \"promotional_email_opt_in\": {\"required\": true, \"pre_checked\": false}}")


@other.post("/api/v9/science")
async def api_science():
    return "", 204


@other.get("/api/v9/experiments")
async def api_experiments():
    return c_json("{\"fingerprint\":\"0.A\",\"assignments\":[],\"guild_experiments\":[]}")


@other.get("/api/v9/applications/detectable")
async def api_applications_detectable():
    return c_json("[]")

@other.get("/api/v9/users/@me/survey")
async def api_users_me_survey():
    return c_json("{\"survey\":null}")


@other.get("/api/v9/users/@me/affinities/guilds")
async def api_users_me_affinities_guilds():
    return c_json("{\"guild_affinities\":[]}")


@other.get("/api/v9/users/@me/affinities/users")
async def api_users_me_affinities_users():
    return c_json("{\"user_affinities\":[],\"inverse_user_affinities\":[]}")


@other.get("/api/v9/users/@me/library")
async def api_users_me_library():
    return c_json("[]")


@other.get("/api/v9/users/@me/billing/payment-sources")
async def api_users_me_billing_paymentsources():
    return c_json("[]")


@other.get("/api/v9/users/@me/billing/country-code")
async def api_users_me_billing_countrycode():
    return c_json("{\"country_code\": \"US\"}")


@other.get("/api/v9/users/@me/billing/localized-pricing-promo")
async def api_users_me_billing_localizedpricingpromo():
    return c_json("{\"country_code\": \"US\", \"localized_pricing_promo\": null}")


@other.get("/api/v9/users/@me/billing/user-trial-offer")
async def api_users_me_billing_usertrialoffer():
    return c_json("{\"message\": \"404: Not Found\", \"code\": 0}", 404)


@other.get("/api/v9/users/@me/billing/subscriptions")
async def api_users_me_billing_subscriptions():
    return c_json("[{\"items\": [{\"id\": 1, \"plan_id\": 511651880837840896, \"quantity\": 1200}], \"id\": 1, \"type\": 2, \"created_at\": 1640995200000, \"canceled_at\": null, \"current_period_start\": 1640995200000, \"current_period_end\": 4794595201000, \"status\": \"idk\", \"payment_source_id\": 0, \"payment_gateway\": null, \"payment_gateway_plan_id\": null, \"payment_gateway_subscription_id\": null, \"trial_id\": null, \"trial_ends_at\": null, \"renewal_mutations\": null, \"streak_started_at\": 1640995200000, \"currency\": \"USD\", \"metadata\": null}]")


@other.get("/api/v9/users/@me/billing/subscription-slots")
async def api_users_me_billing_subscriptionslots():
    return c_json("[]")


@other.get("/api/v9/users/@me/guilds/premium/subscription-slots")
async def api_users_me_guilds_premium_subscriptionslots():
    return c_json("[]")


@other.get("/api/v9/outbound-promotions")
async def api_outboundpromotions():
    return c_json("[]")


@other.get("/api/v9/users/@me/applications/<aid>/entitlements")
async def api_users_me_applications_id_entitlements(aid):
    return c_json("[]")


@other.get("/api/v9/store/published-listings/skus/<int:sku>/subscription-plans")
async def api_store_publishedlistings_skus_id_subscriptionplans(sku):
    if sku == 978380684370378762:
        return c_json("[{\"id\": \"978380692553465866\",\"name\": \"Premium Basic Monthly\",\"interval\": 1,\"interval_count\": 1,\"tax_inclusive\": true,\"sku_id\": \"978380684370378762\",\"currency\": \"usd\",\"price\": 0,\"price_tier\": null}]")
    elif sku == 521846918637420545:
        return c_json("[{\"id\":\"511651871736201216\",\"name\":\"Premium Classic Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651876987469824\",\"name\":\"Premium Classic Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521846918637420545\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 521847234246082599:
        return c_json("[{\"id\":\"642251038925127690\",\"name\":\"Premium Quarterly\",\"interval\":1,\"interval_count\":3,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651880837840896\",\"name\":\"Premium Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"511651885459963904\",\"name\":\"Premium Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"521847234246082599\",\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    elif sku == 590663762298667008:
        return c_json("[{\"id\":\"590665532894740483\",\"name\":\"Server Premium Monthly\",\"interval\":1,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null},{\"id\":\"590665538238152709\",\"name\":\"Server Boost Yearly\",\"interval\":2,\"interval_count\":1,\"tax_inclusive\":true,\"sku_id\":\"590663762298667008\",\"discount_price\":0,\"currency\":\"usd\",\"price\":0,\"price_tier\":null}]")
    return c_json("[]")


@other.get("/api/v9/users/@me/outbound-promotions/codes")
async def api_users_me_outboundpromotions_codes():
    return c_json("[]")


@other.get("/api/v9/users/@me/entitlements/gifts")
async def api_users_me_entitlements_gifts():
    return c_json("[]")


@other.get("/api/v9/users/@me/activities/statistics/applications")
async def api_users_me_activities_statistics_applications():
    return c_json("[]")


@other.get("/api/v9/users/@me/billing/payments")
async def api_users_me_billing_payments():
    return c_json("[]")


@other.route("/api/v9/users/@me/settings-proto/3", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_3():
    return c_json("{\"settings\": \"\"}")


@other.route("/api/v9/users/@me/settings-proto/<int:t>", methods=["GET", "PATCH"])
async def api_users_me_settingsproto_type(t):
    raise InvalidDataErr(400, Errors.make(50035, {"type": {"code": "BASE_TYPE_CHOICES", "message":
        "Value must be one of (<UserSettingsTypes.PRELOADED_USER_SETTINGS: 1>, <UserSettingsTypes.FRECENCY_AND_FAVORITES_SETTINGS: 2>, <UserSettingsTypes.TEST_SETTINGS: 3>)."}}))


@other.get("/api/v9/gateway")
async def api_gateway():
    return c_json("{\"url\": \"wss://gateway.yepcord.ml\"}")


# OAuth


@other.get("/api/v9/oauth2/tokens")
async def api_oauth_tokens():
    return c_json("[]")


# Stickers & gifs


@other.get("/api/v9/sticker-packs")
async def api_stickerpacks_get():
    return c_json('{"sticker_packs": []}') # TODO