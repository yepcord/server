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

import pytest_asyncio
from asyncio import get_event_loop
from datetime import date
from json import dumps
from random import randint, choice
from typing import Coroutine, Any

import pytest as pt

from src.yepcord.config import Config
from src.yepcord.core import Core
from src.yepcord.enums import UserFlags as UserFlagsE, RelationshipType, ChannelType
from src.yepcord.errors import InvalidDataErr, MfaRequiredErr
from src.yepcord.models import User, UserData, Session, database
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import b64decode, b64encode

EMAIL_ID = Snowflake.makeId()
VARS = {
    "user_id": Snowflake.makeId()
}

core = Core(b64decode(Config("KEY")))


@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    if not database.is_connected:
        await database.connect()
    yield
    if database.is_connected:
        await database.disconnect()


@pt.fixture(name='testCore')
async def _setup_db():
    return core


@pt.mark.asyncio
async def test_register_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.register(VARS["user_id"], "Test Login", f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd", "2000-01-01")
    assert session is not None, "Account not registered: maybe you using already used database?"


@pt.mark.asyncio
async def test_register_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.register(VARS["user_id"], "Test Login 2", f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd", "2000-01-01")
        assert False, "Account already registered: must raise error!"
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_login_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.login(f"{EMAIL_ID}_test@yepcord.ml", "test_passw0rd")
    assert session is not None, "Session not created: ???"


@pt.mark.asyncio
async def test_login_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.login(f"{EMAIL_ID}_test@yepcord.ml", "wrong_password")
        await testCore.login(f"{EMAIL_ID}_test123@yepcord.ml", "test_passw0rd")
        assert False, "Wrong login or password: must raise Error!"
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_getUser_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    assert user is not None, "User not found: ???"


@pt.mark.asyncio
async def test_getUser_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"] + 1)
    assert user is None, f"User with id {VARS['user_id'] + 1} doesn't exists: must return None!"


@pt.mark.asyncio
async def test_createSession_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.createSession(VARS["user_id"])
    assert session is not None


@pt.mark.asyncio
async def test_createSession_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.createSession(Snowflake.makeId())
    assert session is None


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


@pt.mark.asyncio
async def test_getUserProfile_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    _user = await User.objects.get(id=VARS["user_id"])
    user = await testCore.getUserProfile(VARS["user_id"], _user)
    assert user is not None and user == _user


@pt.mark.asyncio
async def test_getUserProfile_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.getUserProfile(VARS["user_id"] + 1, await User.objects.get(id=VARS["user_id"]))
        assert False
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_checkUserPassword_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    assert await testCore.checkUserPassword(user, "test_passw0rd")


@pt.mark.asyncio
async def test_checkUserPassword_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    assert not await testCore.checkUserPassword(user, "wrong_password")


@pt.mark.asyncio
async def test_changeUserDiscriminator_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await core.getUser(VARS["user_id"])
    assert await testCore.changeUserDiscriminator(user, randint(1, 9999))


@pt.mark.asyncio
async def test_changeUserDiscriminator_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore

    # Register 2 users with same nickname
    session1 = await core.register(VARS["user_id"] + 100000, "Test", f"{EMAIL_ID}_test1@yepcord.ml", "password", "2000-01-01")
    session2 = await core.register(VARS["user_id"] + 200000, "Test", f"{EMAIL_ID}_test2@yepcord.ml", "password", "2000-01-01")
    user1 = await core.getUser(session1.user.id)
    user2 = await core.getUser(session2.user.id)
    userdata2 = await user2.userdata

    # Try to change first user discriminator to second user discriminator
    assert not await testCore.changeUserDiscriminator(user1, userdata2.discriminator, True)
    try:
        await testCore.changeUserDiscriminator(user1, userdata2.discriminator, False)
        assert False
    except InvalidDataErr:
        pass


@pt.mark.asyncio
async def test_changeUserName_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await core.getUser(VARS["user_id"])
    await testCore.changeUserName(user, f"{EMAIL_ID}_UserName")
    userdata = await user.data
    assert userdata.username == f"{EMAIL_ID}_UserName"


@pt.mark.asyncio
async def test_changeUserName_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore

    # Insert in userdata table 9999 users to trigger USERNAME_TOO_MANY_USERS error
    username = f"NoDiscriminatorsLeft_{Snowflake.makeId()}"

    users = []
    userdatas = []
    for d in range(1, 10000):
        _id = VARS["user_id"] + 100000 + d
        users.append({"id": _id, "email": f"test_user_{_id}@test.yepcord.ml"})
        userdatas.append({"id": _id, "birth": date(2000, 1, 1), "username": username, "discriminator": d})

    await database.execute_many(
        query="INSERT INTO `users`(`id`, `email`, `password`) VALUES (:id, :email, \"123456\")",
        values=users
    )
    await database.execute_many(
        query="INSERT INTO `userdatas`(`id`, `user`, `birth`, `username`, `discriminator`, `flags`, `public_flags`) "
              "VALUES (:id, :id, :birth, :username, :discriminator, 0, 0)",
        values=userdatas
    )

    user = await core.getUser(VARS["user_id"])
    try:
        await testCore.changeUserName(user, username)
        assert False
    except InvalidDataErr:
        pass  # ok


@pt.mark.asyncio
async def test_getUserByUsername_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    userdata = await UserData.objects.get(user__id=VARS["user_id"])
    user = await testCore.getUserByUsername(userdata.username, userdata.discriminator)
    assert user is not None
    assert user.id == VARS["user_id"]


@pt.mark.asyncio
async def test_getUserByUsername_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUserByUsername("ThisUserDoesNotExist", 9999)
    assert user is None


@pt.mark.asyncio
async def test_checkRelationShipAvailable_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user1 = await User.objects.get(id=VARS["user_id"] + 100000)
    user2 = await User.objects.get(id=VARS["user_id"] + 200000)
    await testCore.checkRelationShipAvailable(user1, user2)


@pt.mark.asyncio
async def test_reqRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user1 = await User.objects.get(id=VARS["user_id"] + 100000)
    user2 = await User.objects.get(id=VARS["user_id"] + 200000)
    await testCore.reqRelationship(user1, user2)


@pt.mark.asyncio
async def test_checkRelationShipAvailable_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user1 = await User.objects.get(id=VARS["user_id"] + 100000)
    user2 = await User.objects.get(id=VARS["user_id"] + 200000)
    try:
        await testCore.checkRelationShipAvailable(user1, user2)
        assert False
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_getRelationships_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"] + 100000)
    rels = await testCore.getRelationships(user)
    assert len(rels) == 1
    assert rels[0]["type"] == 3
    assert rels[0]["user_id"] == str(VARS["user_id"] + 200000)


@pt.mark.asyncio
async def test_getRelationships_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"] + 100001)
    rels = await testCore.getRelationships(user)
    assert len(rels) == 0


@pt.mark.asyncio
async def test_getRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    rel = await testCore.getRelationship(VARS["user_id"] + 100000, VARS["user_id"] + 200000)
    assert rel is not None


@pt.mark.asyncio
async def test_getRelationship_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    rel = await testCore.getRelationship(VARS["user_id"] + 100001, VARS["user_id"] + 200000)
    assert rel is None
    rel = await testCore.getRelationship(VARS["user_id"] + 100001, VARS["user_id"] + 200001)
    assert rel is None


@pt.mark.asyncio
async def test_getRelatedUsers_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"] + 100000)
    users = await testCore.getRelatedUsers(user, True)
    assert len(users) == 1
    assert users[0] == VARS["user_id"] + 200000


@pt.mark.asyncio
async def test_accRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"] + 100000)
    await testCore.accRelationship(user, VARS["user_id"] + 200000)
    rel = await testCore.getRelationship(VARS["user_id"] + 100000, VARS["user_id"] + 200000)
    assert rel is not None
    assert rel.type == RelationshipType.FRIEND


@pt.mark.asyncio
async def test_delRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"] + 100000)
    await testCore.delRelationship(user, VARS["user_id"] + 200000)
    rel = await testCore.getRelationship(VARS["user_id"] + 100000, VARS["user_id"] + 200000)
    assert rel is None


@pt.mark.asyncio
async def test_changeUserPassword_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    await testCore.changeUserPassword(user, "test_password123")
    user = await testCore.getUser(VARS["user_id"])
    assert await testCore.checkUserPassword(user, "test_password123")


@pt.mark.asyncio
async def test_logoutUser_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.createSession(VARS["user_id"])
    assert await Session.objects.get_or_none(id=session.id) is not None
    await session.delete()
    assert await Session.objects.get_or_none(id=session.id) is None


@pt.mark.asyncio
async def test_getMfa(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    if settings.mfa:
        await settings.update(mfa=None)

    assert await testCore.getMfa(user) is None

    await settings.update(mfa="a"*16)
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    mfa = await testCore.getMfa(user)
    assert mfa is not None
    assert mfa.key.lower() == "a"*16
    await settings.update(mfa=None)

@pt.mark.asyncio
async def test_setBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"])
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await testCore.setBackupCodes(user, codes)
    db_codes = [code.code for code in await testCore.getBackupCodes(user)]
    assert len(db_codes) == 10
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_clearBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"])
    await testCore.clearBackupCodes(user)
    codes = await testCore.getBackupCodes(user)
    assert len(codes) == 0


@pt.mark.asyncio
async def test_getBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await User.objects.get(id=VARS["user_id"])
    assert len(await testCore.getBackupCodes(user)) == 0
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await testCore.setBackupCodes(user, codes)
    assert len(db_codes := await testCore.getBackupCodes(user)) == 10
    db_codes = [code.code for code in db_codes]
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_getMfaFromTicket_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    await settings.update(mfa="b" * 16)

    try:
        await testCore.login(user.email, "test_password123")
        assert False
    except MfaRequiredErr as e:
        ticket = b64encode(dumps([e.uid, "login"])) + f".{e.sid}.{e.sig}"

    mfa = await testCore.getMfaFromTicket(ticket)
    assert mfa is not None
    assert mfa.key.lower() == "b" * 16


@pt.mark.asyncio
async def test_generateUserMfaNonce(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    await settings.update(mfa="c"*16)
    user = await testCore.getUser(VARS["user_id"])
    VARS["mfa_nonce"] = await testCore.generateUserMfaNonce(user)


@pt.mark.asyncio
async def test_verifyUserMfaNonce(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    nonce, regenerate_nonce = VARS["mfa_nonce"]
    await core.verifyUserMfaNonce(user, nonce, False)
    await core.verifyUserMfaNonce(user, regenerate_nonce, True)
    for args in ((nonce, True), (regenerate_nonce, False)):
        try:
            await core.verifyUserMfaNonce(user, *args)
            assert False
        except InvalidDataErr:
            pass # Ok
    del VARS["mfa_nonce"]


@pt.mark.asyncio
async def test_useMfaCode_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    codes = list(await testCore.getBackupCodes(user))
    assert await testCore.useMfaCode(user, codes[0].code)
    codes[0].used = True
    db_codes = await testCore.getBackupCodes(user)
    assert len(db_codes) == 10
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_useMfaCode_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    assert not await testCore.useMfaCode(user, "invalid_code")


@pt.mark.asyncio
async def test_getDMChannelOrCreate_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user1 = await testCore.getUser(VARS["user_id"] + 100000)
    user2 = await testCore.getUser(VARS["user_id"] + 200000)
    channel = await testCore.getDMChannelOrCreate(user1, user2)
    channel2 = await testCore.getDMChannelOrCreate(user1, user2)
    assert channel is not None
    assert channel.type == ChannelType.DM
    assert channel.id == channel2.id
    assert set(await channel.recipients.all()) == {user1, user2}
    VARS["channel_id"] = channel.id


@pt.mark.asyncio
async def test_getChannel_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getChannel(VARS["channel_id"])
    assert channel is not None
    assert channel.type == ChannelType.DM


@pt.mark.asyncio
async def test_getChannel_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getChannel(0)
    assert channel is None


@pt.mark.asyncio
async def test_getLastMessageIdForChannel_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getChannel(VARS["channel_id"])
    assert channel.last_message_id is None or channel.last_message_id > 0


@pt.mark.asyncio
async def test_getChannelMessagesCount_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getChannel(VARS["channel_id"])
    assert await testCore.getChannelMessagesCount(channel) == 0
