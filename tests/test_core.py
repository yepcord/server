from asyncio import get_event_loop
from json import dumps
from random import randint, choice
from typing import Coroutine, Any

import pytest as pt

from src.yepcord.classes.user import Session, UserId, UserSettings, UserData
from src.yepcord.config import Config
from src.yepcord.core import Core
from src.yepcord.enums import UserFlags as UserFlagsE, RelationshipType, ChannelType
from src.yepcord.errors import InvalidDataErr, MfaRequiredErr
from src.yepcord.snowflake import Snowflake
from src.yepcord.utils import b64decode, b64encode

VARS = {
    "user_id": Snowflake.makeId()
}

core = Core(b64decode(Config("KEY")))


@pt.fixture
def event_loop():
    loop = get_event_loop()
    yield loop
    loop.close()


@pt.fixture(name='testCore')
async def _setup_db():
    await core.initDB(
        host=Config("DB_HOST"),
        port=3306,
        user=Config("DB_USER"),
        password=Config("DB_PASS"),
        db=Config("DB_NAME"),
        autocommit=True
    )
    await core.initMCL()
    return core


@pt.mark.asyncio
async def test_register_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.register(VARS["user_id"], "Test Login", "test@yepcord.ml", "test_passw0rd", "2000-01-01")
    assert session is not None, "Account not registered: maybe you using already used database?"


@pt.mark.asyncio
async def test_register_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.register(VARS["user_id"], "Test Login 2", "test@yepcord.ml", "test_passw0rd", "2000-01-01")
        assert False, "Account already registered: must raise error!"
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_login_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.login("test@yepcord.ml", "test_passw0rd")
    assert session is not None, "Session not created: ???"


@pt.mark.asyncio
async def test_login_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.login("test@yepcord.ml", "wrong_password")
        await testCore.login("test123@yepcord.ml", "test_passw0rd")
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
async def test_validSession_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = await testCore.createSession(VARS["user_id"])
    assert await testCore.validSession(session)


@pt.mark.asyncio
async def test_validSession_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    session = Session(Snowflake.makeId(), 123456, "test123")
    assert not await testCore.validSession(session)


@pt.mark.asyncio
async def test_getUserSettings_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert await testCore.getUserSettings(UserId(VARS["user_id"])) is not None


@pt.mark.asyncio
async def test_getUserSettings_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert await testCore.getUserSettings(UserId(VARS["user_id"] + 1)) is None


@pt.mark.asyncio
async def test_getUserData_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert await testCore.getUserData(UserId(VARS["user_id"])) is not None


@pt.mark.asyncio
async def test_getUserData_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert await testCore.getUserData(UserId(VARS["user_id"] + 1)) is None


def changeSettings(settings: UserSettings) -> None:
    settings.inline_attachment_media = not settings.inline_attachment_media
    settings.show_current_game = not settings.show_current_game
    settings.view_nsfw_guilds = not settings.view_nsfw_guilds
    settings.enable_tts_command = not settings.enable_tts_command
    settings.render_reactions = not settings.render_reactions
    settings.gif_auto_play = not settings.gif_auto_play
    settings.stream_notifications_enabled = not settings.stream_notifications_enabled
    settings.animate_emoji = not settings.animate_emoji
    settings.afk_timeout = randint(0, 600)
    settings.view_nsfw_commands = not settings.view_nsfw_commands
    settings.detect_platform_accounts = not settings.detect_platform_accounts
    settings.explicit_content_filter = randint(0, 2)
    settings.default_guilds_restricted = not settings.default_guilds_restricted
    settings.allow_accessibility_detection = not settings.allow_accessibility_detection
    settings.native_phone_integration_enabled = not settings.native_phone_integration_enabled
    settings.friend_discovery_flags = randint(0, 6)
    settings.contact_sync_enabled = not settings.contact_sync_enabled
    settings.disable_games_tab = not settings.disable_games_tab
    settings.developer_mode = not settings.developer_mode
    settings.render_embeds = not settings.render_embeds
    settings.animate_stickers = randint(0, 1)
    settings.message_display_compact = not settings.message_display_compact
    settings.convert_emoticons = not settings.convert_emoticons
    settings.passwordless = not settings.passwordless
    settings.personalization = not settings.personalization
    settings.usage_statistics = not settings.usage_statistics
    settings.inline_embed_media = not settings.inline_embed_media
    settings.use_thread_sidebar = not settings.use_thread_sidebar
    settings.use_rich_chat_input = not settings.use_rich_chat_input
    settings.expression_suggestions_enabled = not settings.expression_suggestions_enabled
    settings.view_image_descriptions = not settings.view_image_descriptions
    settings.status = "invisible" if settings.status == "online" else "online"
    settings.custom_status = {"text": f"test_{randint(0, 1000)}"}
    settings.theme = "light" if settings.theme == "dark" else "dark"
    settings.locale = "uk" if settings.locale == "en-US" else "en-US"
    settings.timezone_offset = randint(-600, 600)
    settings.activity_restricted_guild_ids = [randint(0, Snowflake.makeId())]
    settings.friend_source_flags = {"all": False, "mutual_friends": True, "mutual_guilds": False} \
        if settings.friend_source_flags["all"] == True else {"all": True}
    settings.guild_positions = [randint(0, Snowflake.makeId()), randint(0, Snowflake.makeId())]
    settings.guild_folders = [randint(0, Snowflake.makeId()), randint(0, Snowflake.makeId())]
    settings.restricted_guilds = [randint(0, Snowflake.makeId())]
    settings.render_spoilers = "IF_MODERATOR" if settings.render_spoilers == "ALWAYS" else "ALWAYS"


@pt.mark.asyncio
async def test_setSettings_success(testCore: Coroutine[Any, Any, Core]):
    """
    Test almost every field in UserSettings
    :param testCore:
    :return:
    """
    testCore = await testCore
    settings = await testCore.getUserSettings(UserId(VARS["user_id"]))
    changeSettings(settings)
    await testCore.setSettings(settings)
    new_settings = await testCore.getUserSettings(UserId(VARS["user_id"]))
    assert settings.getDiff(new_settings) == {}


@pt.mark.asyncio
async def test_setSettingsDiff_success(testCore: Coroutine[Any, Any, Core]):
    """
        Test almost every field in UserSettings
        :param testCore:
        :return:
        """
    testCore = await testCore
    settings = await testCore.getUserSettings(UserId(VARS["user_id"]))
    changed_settings = settings.copy()
    changeSettings(changed_settings)
    await testCore.setSettingsDiff(settings, changed_settings)
    new_settings = await testCore.getUserSettings(UserId(VARS["user_id"]))
    assert changed_settings.getDiff(new_settings) == {}


def changeUserData(data: UserData) -> None:
    data.birth = "2001-01-01" if data.birth == "2000-01-01" else "2000-01-01"
    data.username = f"Changed username {randint(0, 1000)}"
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
async def test_setUserdata_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    userdata = await testCore.getUserData(UserId(VARS["user_id"]))
    changeUserData(userdata)
    await testCore.setUserdata(userdata)
    new_userdata = await testCore.getUserData(UserId(VARS["user_id"]))
    assert userdata.getDiff(new_userdata) == {}


@pt.mark.asyncio
async def test_getUserProfile_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUserProfile(VARS["user_id"], UserId(0))
    assert user is not None and user.id == VARS["user_id"]


@pt.mark.asyncio
async def test_getUserProfile_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.getUserProfile(VARS["user_id"] + 1, UserId(0))
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
    session1 = await core.register(VARS["user_id"] + 100000, "Test", "test1@yepcord.ml", "password", "2000-01-01")
    session2 = await core.register(VARS["user_id"] + 200000, "Test", "test2@yepcord.ml", "password", "2000-01-01")
    user1 = await core.getUser(session1.id)
    user2 = await core.getUser(session2.id)
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
    await testCore.changeUserName(user, "UserName")
    userdata = await testCore.getUserData(user)
    assert userdata.username == "UserName"


@pt.mark.asyncio
async def test_changeUserName_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore

    # Insert in userdata table 9999 users to trigger USERNAME_TOO_MANY_USERS error
    userdatas = []
    for d in range(1, 10000):
        userdatas.append((VARS["user_id"] + 100000 + d, d))
    async with testCore.db() as db:
        await db.cur.executemany(f'INSERT INTO `users`(`id`, `email`, `password`, `key`) VALUES '
                                 f'(%s, "", %s, "");', userdatas)
        await db.cur.executemany(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES '
                                 f'(%s, "2000-01-01", "NoDiscriminatorsLeft", %s);', userdatas)

    user = await core.getUser(VARS["user_id"])
    try:
        await testCore.changeUserName(user, "NoDiscriminatorsLeft")
        assert False
    except InvalidDataErr:
        pass  # ok


@pt.mark.asyncio
async def test_getUserByUsername_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    userdata = await core.getUserData(UserId(VARS["user_id"]))
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
    await testCore.checkRelationShipAvailable(UserId(VARS["user_id"] + 100000), UserId(VARS["user_id"] + 200000))


@pt.mark.asyncio
async def test_reqRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    await testCore.reqRelationship(UserId(VARS["user_id"] + 100000), UserId(VARS["user_id"] + 200000))


@pt.mark.asyncio
async def test_checkRelationShipAvailable_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    try:
        await testCore.checkRelationShipAvailable(UserId(VARS["user_id"] + 100000), UserId(VARS["user_id"] + 200000))
        assert False
    except InvalidDataErr:
        pass  # Ok


@pt.mark.asyncio
async def test_getRelationships_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    rels = await testCore.getRelationships(UserId(VARS["user_id"] + 100000))
    assert len(rels) == 1
    assert rels[0]["type"] == 3
    assert rels[0]["user_id"] == str(VARS["user_id"] + 200000)


@pt.mark.asyncio
async def test_getRelationships_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    rels = await testCore.getRelationships(UserId(0))
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
    users = await testCore.getRelatedUsers(UserId(VARS["user_id"] + 100000), True)
    assert len(users) == 1
    assert users[0] == VARS["user_id"] + 200000


@pt.mark.asyncio
async def test_accRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    await testCore.accRelationship(UserId(VARS["user_id"] + 100000), VARS["user_id"] + 200000)
    rel = await testCore.getRelationship(VARS["user_id"] + 100000, VARS["user_id"] + 200000)
    assert rel is not None
    assert rel.type == RelationshipType.FRIEND


@pt.mark.asyncio
async def test_delRelationship_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    await testCore.delRelationship(UserId(VARS["user_id"] + 100000), VARS["user_id"] + 200000)
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
    assert await testCore.validSession(session)
    await testCore.logoutUser(session)
    assert not await testCore.validSession(session)


@pt.mark.asyncio
async def test_getMfa(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    if settings.mfa:
        await testCore.setSettingsDiff(settings, settings.copy(mfa=None))
        settings = await testCore.getUserSettings(user)

    assert await testCore.getMfa(user) is None

    await testCore.setSettingsDiff(settings, settings.copy(mfa="a"*16))
    user = await testCore.getUser(VARS["user_id"])
    settings = await testCore.getUserSettings(user)
    mfa = await testCore.getMfa(user)
    assert mfa is not None
    assert mfa.key.lower() == "a"*16
    await testCore.setSettingsDiff(settings, settings.copy(mfa=None))

@pt.mark.asyncio
async def test_setBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await testCore.setBackupCodes(UserId(VARS["user_id"]), codes)
    db_codes = [code[0] for code in await testCore.getBackupCodes(UserId(VARS["user_id"]))]
    assert len(db_codes) == 10
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_clearBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    await testCore.clearBackupCodes(UserId(VARS["user_id"]))
    codes = await testCore.getBackupCodes(UserId(VARS["user_id"]))
    assert len(codes) == 0


@pt.mark.asyncio
async def test_getBackupCodes_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert len(await testCore.getBackupCodes(UserId(VARS["user_id"]))) == 0
    codes = ["".join([choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8)]) for _ in range(10)]
    await testCore.setBackupCodes(UserId(VARS["user_id"]), codes)
    assert len(db_codes := await testCore.getBackupCodes(UserId(VARS["user_id"]))) == 10
    db_codes = [code[0] for code in db_codes]
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_getMfaFromTicket_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    user = await testCore.getUser(VARS["user_id"])
    settings = await user.settings
    await testCore.setSettingsDiff(settings, settings.copy(mfa="b" * 16))

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
    await testCore.setSettingsDiff(settings, settings.copy(mfa="c" * 16))
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
    codes = list(await testCore.getBackupCodes(UserId(VARS["user_id"])))
    assert await testCore.useMfaCode(VARS["user_id"], codes[0][0])
    codes[0] = (codes[0][0], True)
    db_codes = await testCore.getBackupCodes(UserId(VARS["user_id"]))
    assert len(db_codes) == 10
    assert set(codes) == set(db_codes)


@pt.mark.asyncio
async def test_useMfaCode_fail(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    assert not await testCore.useMfaCode(VARS["user_id"], "invalid_code")


@pt.mark.asyncio
async def test_getDMChannelOrCreate_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getDMChannelOrCreate(VARS["user_id"] + 100000, VARS["user_id"] + 200000)
    assert channel is not None
    assert channel.type == ChannelType.DM
    assert set(channel.recipients) == {VARS["user_id"] + 100000, VARS["user_id"] + 200000}
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
    await testCore.getLastMessageIdForChannel(channel)
    assert channel.last_message_id is None or channel.last_message_id > 0


@pt.mark.asyncio
async def test_getChannelMessagesCount_success(testCore: Coroutine[Any, Any, Core]):
    testCore = await testCore
    channel = await testCore.getChannel(VARS["channel_id"])
    assert await testCore.getChannelMessagesCount(channel, Snowflake.makeId(False), 0) == 0


@pt.mark.asyncio
async def test_getPrivateChannels_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getPrivateChannels_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getChannelMessages_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getChannelMessages_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_editMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_editMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRelatedUsersToChannel_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRelatedUsersToChannel_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addMessageToReadStates_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addMessageToReadStates_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setReadState_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setReadState_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReadStates_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReadStates_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReadStatesJ_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReadStatesJ_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_delReadStateIfExists_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_delReadStateIfExists_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserNote_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserNote_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_putUserNote_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_putUserNote_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_putAttachment_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_putAttachment_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getAttachment_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getAttachment_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getAttachmentByUUID_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getAttachmentByUUID_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateAttachment_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateAttachment_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByChannelId_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByChannelId_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByChannel_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByChannel_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setFrecencySettingsBytes_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setFrecencySettingsBytes_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setFrecencySettings_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_setFrecencySettings_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getFrecencySettings_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getFrecencySettings_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_verifyEmail_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_verifyEmail_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByEmail_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserByEmail_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_changeUserEmail_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_changeUserEmail_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_mfaNonceToCode_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_mfaNonceToCode_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createDMGroupChannel_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createDMGroupChannel_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addUserToGroupDM_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addUserToGroupDM_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_removeUserFromGroupDM_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_removeUserFromGroupDM_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateChannelDiff_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateChannelDiff_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteChannel_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteChannel_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteMessagesAck_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteMessagesAck_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_pinMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_pinMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getLastPinnedMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getLastPinnedMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getLastPinTimestamp_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getLastPinTimestamp_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getPinnedMessages_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getPinnedMessages_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_unpinMessage_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_unpinMessage_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addReaction_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addReaction_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_removeReaction_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_removeReaction_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getMessageReactions_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getMessageReactions_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReactedUsers_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getReactedUsers_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_searchMessages_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_searchMessages_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createInvite_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createInvite_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getInvite_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getInvite_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuild_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuild_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRole_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRole_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRoles_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getRoles_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMember_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMember_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMembers_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMembers_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMembersIds_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMembersIds_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildChannels_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildChannels_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserGuilds_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getUserGuilds_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMemberCount_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildMemberCount_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuild_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuild_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateGuildDiff_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_updateGuildDiff_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_blockUser_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_blockUser_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmojis_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmojis_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addEmoji_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_addEmoji_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmoji_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmoji_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteEmoji_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteEmoji_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmojiByReaction_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getEmojiByReaction_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuildChannel_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuildChannel_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuildMember_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_createGuildMember_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildInvites_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_getGuildInvites_fail(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteInvite_success(testCore: Coroutine[Any, Any, Core]):
    ...


@pt.mark.asyncio
async def test_deleteInvite_fail(testCore: Coroutine[Any, Any, Core]):
    ...
