"""
    YEPCord: Free open source selfhostable fully discord-compatible chat
    Copyright (C) 2022-2024 RuslanUC

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

from asyncio import get_event_loop
from datetime import date
from json import dumps
from random import randint

import pytest as pt
import pytest_asyncio
from tortoise import Tortoise

from yepcord.yepcord.utils.mfa import MFA
from yepcord.yepcord.config import Config, ConfigModel
from yepcord.yepcord.enums import UserFlags as UserFlagsE, RelationshipType, ChannelType, GuildPermissions, MfaNonceType
from yepcord.yepcord.errors import InvalidDataErr, MfaRequiredErr
from yepcord.yepcord.gateway_dispatcher import GatewayDispatcher
from yepcord.yepcord.models import User, UserData, Session, Relationship, Guild, Channel, Role, PermissionOverwrite, \
    GuildMember, Message
from yepcord.yepcord.snowflake import Snowflake
from yepcord.yepcord.utils import b64encode, GeoIp

EMAIL_ID = Snowflake.makeId()
VARS = {
    "user_id": Snowflake.makeId()
}


@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await Tortoise.init(db_url=Config.DB_CONNECT_STRING, modules={"models": ["yepcord.yepcord.models"]})
    yield
    await Tortoise.close_connections()


@pt.mark.asyncio
async def test_register_success():
    user = await User.y.register("Test Login", f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd", "2000-01-01")
    VARS["user_id"] = user.id
    session = await Session.Y.create(user)

    assert session is not None, "Account not registered: maybe you using already used database?"

    user = await User.y.register("Test", f"{EMAIL_ID}_test2_1@yepcord.ml", "password", "2000-01-01")
    VARS[f"user_id_200001"] = user.id


@pt.mark.asyncio
async def test_register_fail():
    with pt.raises(InvalidDataErr):
        await User.y.register("Test Login 2", f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd", "2000-01-01")


@pt.mark.asyncio
async def test_login_success():
    session = await User.y.login(f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd")
    assert session is not None, "Session not created: ???"


@pt.mark.asyncio
async def test_login_fail():
    with pt.raises(InvalidDataErr):
        await User.y.login(f"{EMAIL_ID}_test@yepcord.ml", "wrong_password")
    with pt.raises(InvalidDataErr):
        await User.y.login(f"{EMAIL_ID}_test123@yepcord.ml", "test_passw0rd")


@pt.mark.asyncio
async def test_getUser_success():
    user = await User.y.get(VARS["user_id"])
    assert user is not None, "User not found: ???"


@pt.mark.asyncio
async def test_getUser_fail():
    user = await User.y.get(VARS["user_id"] + 1)
    assert user is None, f"User with id {VARS['user_id'] + 1} doesn't exists: must return None!"


def changeUserData(data: UserData) -> None:
    data.birth = "2001-01-01" if data.birth == "2000-01-01" else "2000-01-01"
    data.username = f"{EMAIL_ID}_Changed username {randint(0, 1000)}"
    data.discriminator = randint(1, 9999)
    data.bio = f"Test bio text {randint(0, 1000)}"
    data.public_flags = UserFlagsE.STAFF if data.flags == UserFlagsE.PARTNER else UserFlagsE.PARTNER
    data.phone = "38063" + str(randint(1, 9999999)).rjust(7, "0")
    data.premium = not data.premium
    data.accent_color = randint(1, 10000)
    data.avatar = "d41d8cd98f00b204e9800998ecf8427e"  # md5 of b''
    data.avatar_decoration = "d41d8cd98f00b204e9800998ecf8427e"  # md5 of b''
    data.banner = "d41d8cd98f00b204e9800998ecf8427e"  # md5 of b''
    data.banner_color = randint(1, 10000)


@pt.mark.asyncio  # May be removed, but not removing now because other tests depend on VARS["user_id"] + 100000
async def test_changeUserDiscriminator_fail():
    user = await User.y.register("Test", f"{EMAIL_ID}_test1@yepcord.ml", "password", "2000-01-01")
    VARS["user_id_100000"] = user.id
    user = await User.y.register("Test", f"{EMAIL_ID}_test2@yepcord.ml", "password", "2000-01-01")
    VARS["user_id_200000"] = user.id


@pt.mark.asyncio  # May be removed, but not removing now because other tests depend on VARS["user_id"] + 100000 + d
async def test_changeUserName_fail():
    username = f"NoDiscriminatorsLeft_{Snowflake.makeId()}"

    for d in range(1, 10):
        user_id = VARS["user_id"] + 100000 + d
        user = await User.create(id=user_id, email=f"test_user_{user_id}@test.yepcord.ml", password="123456")
        await UserData.create(id=user_id, user=user, birth=date(2000, 1, 1), username=username, discriminator=d)


@pt.mark.asyncio
async def test_getUserByUsername_success():
    userdata = await UserData.get(user__id=VARS["user_id"])
    user = await User.y.getByUsername(userdata.username, userdata.discriminator)
    assert user is not None
    assert user.id == VARS["user_id"]


@pt.mark.asyncio
async def test_getUserByUsername_fail():
    user = await User.y.getByUsername("ThisUserDoesNotExist", 9999)
    assert user is None


@pt.mark.asyncio
async def test_checkRelationShipAvailable_success():
    user1 = await User.get(id=VARS["user_id_100000"])
    user2 = await User.get(id=VARS["user_id_200000"])
    assert await Relationship.utils.available(user1, user2)


@pt.mark.asyncio
async def test_reqRelationship_success():
    user1 = await User.get(id=VARS["user_id_100000"])
    user2 = await User.get(id=VARS["user_id_200000"])
    assert await Relationship.utils.request(user2, user1)


@pt.mark.asyncio
async def test_checkRelationShipAvailable_fail():
    user1 = await User.get(id=VARS["user_id_100000"])
    user2 = await User.get(id=VARS["user_id_200000"])
    with pt.raises(InvalidDataErr):
        await Relationship.utils.available(user1, user2, raise_=True)


@pt.mark.asyncio
async def test_getRelationships_success():
    user = await User.get(id=VARS["user_id_100000"])
    rels = await user.get_relationships()
    assert len(rels) == 1
    assert rels[0].type == RelationshipType.PENDING
    assert rels[0].other_user(user).id == VARS["user_id_200000"]


@pt.mark.asyncio
async def test_getRelationships_fail():
    user = await User.get(id=VARS["user_id"] + 100001)
    rels = await user.get_relationships()
    assert len(rels) == 0


@pt.mark.asyncio
async def test_getRelationship_success():
    assert await Relationship.utils.exists(await User.get(id=VARS["user_id_100000"]),
                                           await User.get(id=VARS["user_id_200000"]))


@pt.mark.asyncio
async def test_getRelationship_fail():
    assert not await Relationship.utils.exists(await User.get(id=VARS["user_id"] + 100001),
                                               await User.get(id=VARS["user_id_200000"]))
    assert not await Relationship.utils.exists(await User.get(id=VARS["user_id"] + 100001),
                                               await User.get(id=VARS[f"user_id_200001"]))


@pt.mark.asyncio
async def test_getRelatedUsers_success():
    user = await User.get(id=VARS["user_id_100000"])
    users = await user.get_related_users()
    assert len(users) == 1
    assert users[0].id == VARS["user_id_200000"]


@pt.mark.asyncio
async def test_accRelationship_success():
    user = await User.get(id=VARS["user_id_100000"])
    user2 = await User.get(id=VARS["user_id_200000"])
    await Relationship.utils.accept(user2, user)
    rel = await Relationship.utils.get(await User.get(id=VARS["user_id_100000"]),
                                       await User.get(id=VARS["user_id_200000"]))
    assert rel is not None
    assert rel.type == RelationshipType.FRIEND


@pt.mark.asyncio
async def test_delRelationship_success():
    user = await User.get(id=VARS["user_id_100000"])
    user2 = await User.get(id=VARS["user_id_200000"])
    await Relationship.utils.delete(user, user2)
    assert not await Relationship.utils.exists(await User.get(id=VARS["user_id_100000"]),
                                               await User.get(id=VARS["user_id_200000"]))


@pt.mark.asyncio
async def test_logoutUser_success():
    user = await User.y.get(VARS["user_id"])
    session = await Session.Y.create(user)
    assert await Session.get_or_none(id=session.id) is not None
    await session.delete()
    assert await Session.get_or_none(id=session.id) is None


@pt.mark.asyncio
async def test_getMfa():
    user = await User.y.get(VARS["user_id"])
    settings = await user.settings
    if settings.mfa:
        settings.mfa = None
        await settings.save(update_fields=["mfa"])

    assert await user.mfa is None

    settings.mfa = "a" * 16
    await settings.save(update_fields=["mfa"])
    user = await User.y.get(VARS["user_id"])
    settings = await user.settings
    mfa = await user.mfa
    assert mfa is not None
    assert mfa.key.lower() == "a" * 16
    settings.mfa = None
    await settings.save(update_fields=["mfa"])


@pt.mark.asyncio
async def test_getMfaFromTicket_success():
    user = await User.y.get(VARS["user_id"])
    settings = await user.settings
    settings.mfa = "b" * 16
    await settings.save(update_fields=["mfa"])

    try:
        await User.y.login(user.email, "test_passw0rd")
        assert False
    except MfaRequiredErr as e:
        ticket = b64encode(dumps([e.uid, "login"])) + f".{e.sid}.{e.sig}"

    mfa = await MFA.get_from_ticket(ticket)
    assert mfa is not None
    assert mfa.key.lower() == "b" * 16


@pt.mark.asyncio
async def test_generateUserMfaNonce():
    user = await User.y.get(VARS["user_id"])
    settings = await user.settings
    settings.mfa = "c" * 16
    await settings.save(update_fields=["mfa"])
    user = await User.y.get(VARS["user_id"])
    VARS["mfa_nonce"] = await user.generate_mfa_nonce()


@pt.mark.asyncio
async def test_verifyUserMfaNonce():
    user = await User.y.get(VARS["user_id"])
    nonce, regenerate_nonce = VARS["mfa_nonce"]
    await user.verify_mfa_nonce(nonce, MfaNonceType.NORMAL)
    await user.verify_mfa_nonce(regenerate_nonce, MfaNonceType.REGENERATE)
    for args in ((nonce, MfaNonceType.REGENERATE), (regenerate_nonce, MfaNonceType.NORMAL)):
        with pt.raises(InvalidDataErr):
            await user.verify_mfa_nonce(*args)
    del VARS["mfa_nonce"]


@pt.mark.asyncio
async def test_getDMChannelOrCreate_success():
    user1 = await User.y.get(VARS["user_id_100000"])
    user2 = await User.y.get(VARS["user_id_200000"])
    channel = await Channel.Y.get_dm(user1, user2)
    channel2 = await Channel.Y.get_dm(user1, user2)
    assert channel is not None
    assert channel.type == ChannelType.DM
    assert channel.id == channel2.id
    assert set(await channel.recipients.all()) == {user1, user2}
    VARS["channel_id"] = channel.id


@pt.mark.asyncio
async def test_getChannel_success():
    channel = await Channel.Y.get(VARS["channel_id"])
    assert channel is not None
    assert channel.type == ChannelType.DM


@pt.mark.asyncio
async def test_getChannel_fail():
    channel = await Channel.Y.get(0)
    assert channel is None


@pt.mark.asyncio
async def test_getLastMessageIdForChannel_success():
    channel = await Channel.Y.get(VARS["channel_id"])
    assert await channel.get_last_message_id() is None or await channel.get_last_message_id() > 0


@pt.mark.asyncio
async def test_getChannelMessagesCount_success():
    channel = await Channel.Y.get(VARS["channel_id"])
    assert await Message.filter(channel=channel).count() == 0


@pt.mark.asyncio
async def test_geoip():
    assert GeoIp.get_language_code("1.1.1.1") == "en-US"
    assert GeoIp.get_language_code("134.249.127.127") == "uk"
    assert GeoIp.get_language_code("103.21.236.200") == "de"
    assert GeoIp.get_language_code("109.241.127.127") == "pl"
    assert GeoIp.get_language_code("5.65.127.127") == "en-GB"

    assert GeoIp.get_language_code("255.255.255.255") == "en-US"
    assert GeoIp.get_language_code("255.255.255.255", "uk") == "uk"


def test_config():
    ConfigModel()  # shows key warning
    assert ConfigModel(GATEWAY_KEEP_ALIVE_DELAY=1).GATEWAY_KEEP_ALIVE_DELAY == 5
    assert ConfigModel(GATEWAY_KEEP_ALIVE_DELAY=151).GATEWAY_KEEP_ALIVE_DELAY == 150
    assert ConfigModel(BCRYPT_ROUNDS=2).BCRYPT_ROUNDS == 15
    assert ConfigModel(BCRYPT_ROUNDS=32).BCRYPT_ROUNDS == 15


@pt.mark.asyncio
async def test_gw_channel_filter():
    user = await User.y.get(VARS["user_id"])
    user2 = await User.y.get(VARS["user_id_100000"])
    guild = await Guild.create(owner=user, name="test")
    await GuildMember.create(guild=guild, user=user)
    role = await Role.create(id=guild.id, name="@everyone", guild=guild)
    role1 = await Role.create(name="1", guild=guild, permissions=0)
    channel = await Channel.create(guild=guild, name="test", type=ChannelType.GUILD_TEXT)

    gw = GatewayDispatcher.getInstance()

    assert await gw.getChannelFilter(channel, GuildPermissions.VIEW_CHANNEL) == \
           {"role_ids": [role.id], "user_ids": [user.id], "exclude": []}

    await PermissionOverwrite.create(channel=channel, target_role=role,
                                     deny=GuildPermissions.VIEW_CHANNEL, type=0, allow=0)

    assert await gw.getChannelFilter(channel, GuildPermissions.VIEW_CHANNEL) == \
           {"role_ids": [], "user_ids": [user.id], "exclude": []}

    await PermissionOverwrite.create(channel=channel, target_role=role1,
                                     allow=GuildPermissions.VIEW_CHANNEL, type=0, deny=0)
    await PermissionOverwrite.create(channel=channel, target_user=user,
                                     deny=GuildPermissions.VIEW_CHANNEL, type=1, allow=0)
    await PermissionOverwrite.create(channel=channel, target_user=user2,
                                     deny=GuildPermissions.VIEW_CHANNEL, type=1, allow=0)

    assert await gw.getChannelFilter(channel, GuildPermissions.VIEW_CHANNEL) == \
           {"role_ids": [role1.id], "user_ids": [user.id], "exclude": []}
