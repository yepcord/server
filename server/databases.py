from abc import ABC, abstractmethod
from json import dumps as jdumps
from re import sub
from time import time
from typing import Optional, List, Tuple, Dict

from aiomysql import create_pool, escape_string, Cursor, Connection

from .classes.channel import Channel, _Channel, ChannelId
from .classes.guild import Emoji, Invite, Guild, Role, _Guild, GuildBan
from .classes.message import Message, Attachment, Reaction, SearchFilter, ReadState
from .classes.user import Session, UserSettings, UserNote, User, _User, UserData, Relationship, GuildMember
from .ctx import Ctx
from .enums import ChannelType
from .snowflake import Snowflake
from .utils import json_to_sql


class Database:
    _instance = None

    def __getattr__(self, item):
        return getattr(Database._instance, item)

class DBConnection(ABC):

    @abstractmethod
    def dontCloseOnAExit(self): ...

    @abstractmethod
    async def close(self): ...

    @abstractmethod
    async def getUserByEmail(self, email: str) -> Optional[User]: ...

    @abstractmethod
    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]: ...

    @abstractmethod
    async def registerUser(self, user: User, session: Session, data: UserData) -> None: ...

    @abstractmethod
    async def insertSession(self, session: Session) -> None: ...

    @abstractmethod
    async def getUser(self, uid: int) -> Optional[User]: ...

    @abstractmethod
    async def validSession(self, session: Session) -> bool: ...

    @abstractmethod
    async def getUserSettings(self, user: _User) -> UserSettings: ...

    @abstractmethod
    async def getUserData(self, user: _User) -> UserData: ...

    @abstractmethod
    async def setSettings(self, settings: UserSettings) -> None: ...

    @abstractmethod
    async def setSettingsDiff(self, before: UserSettings, after: UserSettings) -> None: ...

    @abstractmethod
    async def setUserData(self, data: UserData) -> None: ...

    @abstractmethod
    async def setUserDataDiff(self, before: UserData, after: UserData) -> None: ...

    @abstractmethod
    async def relationShipAvailable(self, tUser: User, cUser: User) -> bool: ...

    @abstractmethod
    async def insertRelationShip(self, relationship: Relationship) -> None: ...

    @abstractmethod
    async def getRelationships(self, uid: int) -> List[Relationship]: ...

    @abstractmethod
    async def updateRelationship(self, cUser: int, tUser: int, ntype: int, otype: int): ...

    @abstractmethod
    async def getRelationship(self, u1: int, u2: int) -> Optional[Relationship]: ...

    @abstractmethod
    async def delRelationship(self, relationship: Relationship) -> None: ...

    @abstractmethod
    async def changeUserPassword(self, user: User, password: str) -> None: ...

    @abstractmethod
    async def logoutUser(self, sess: Session) -> None: ...

    @abstractmethod
    async def setBackupCodes(self, user: _User, codes: List[str]) -> None: ...

    @abstractmethod
    async def clearBackupCodes(self, user: _User) -> None: ...

    @abstractmethod
    async def getBackupCodes(self, user: _User) -> list: ...

    @abstractmethod
    async def useMfaCode(self, uid: int, code: str) -> None: ...

    @abstractmethod
    async def getChannel(self, channel_id: int) -> Optional[Channel]: ...

    @abstractmethod
    async def getDMChannel(self, u1: int, u2: int) -> Optional[Channel]: ...

    @abstractmethod
    async def getLastMessageId(self, channel: _Channel, before: int, after: int) -> int: ...

    @abstractmethod
    async def getChannelMessagesCount(self, channel: Channel, before: int, after: int) -> int: ...

    @abstractmethod
    async def createDMChannel(self, channel_id: int, recipients: List[int]) -> Channel: ...

    @abstractmethod
    async def getPrivateChannels(self, user: _User) -> List[Channel]: ...

    @abstractmethod
    async def getChannelMessages(self, channel, limit: int, before: int = None, after: int = None) -> List[Message]: ...

    @abstractmethod
    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]: ...

    @abstractmethod
    async def insertMessage(self, message: Message) -> None: ...

    @abstractmethod
    async def editMessage(self, before: Message, after: Message) -> Message: ...

    @abstractmethod
    async def deleteMessage(self, message: Message) -> None: ...

    @abstractmethod
    async def getReadStates(self, uid: int, channel_id: int=None) -> List[ReadState]: ...

    @abstractmethod
    async def setReadState(self, uid: int, channel_id: int, count: int, last: int = None) -> None: ...

    @abstractmethod
    async def delReadStateIfExists(self, uid: int, channel_id: int) -> bool: ...

    @abstractmethod
    async def getUserNote(self, uid: int, target_uid: int) -> Optional[UserNote]: ...

    @abstractmethod
    async def putUserNote(self, note: UserNote) -> None: ...

    #@abstractmethod # TODO: implement UserConnection
    #async def putUserConnection(self, uc: UserConnection) -> None: ...

    @abstractmethod
    async def putAttachment(self, attachment: Attachment) -> None: ...

    @abstractmethod
    async def getAttachment(self, id: int) -> Optional[Attachment]: ...

    @abstractmethod
    async def getAttachmentByUUID(self, uuid: str) -> Optional[Attachment]: ...

    @abstractmethod
    async def updateAttachment(self, before: Attachment, after: Attachment) -> None: ...

    @abstractmethod
    async def setFrecencySettings(self, uid: int, proto: bytes) -> None: ...

    @abstractmethod
    async def getFrecencySettings(self, uid: int) -> str: ...

    @abstractmethod
    async def verifyEmail(self, uid: int) -> None: ...

    @abstractmethod
    async def changeUserEmail(self, uid: int, email: str) -> None: ...

    @abstractmethod
    async def createDMGroupChannel(self, channel_id: int, recipients: List[int], owner_id: int) -> Channel: ...

    @abstractmethod
    async def updateChannelDiff(self, before: Channel, after: Channel) -> None: ...

    @abstractmethod
    async def deleteChannel(self, channel: Channel) -> None: ...

    @abstractmethod
    async def deleteMessagesAck(self, channel: Channel, user: User) -> None: ...

    @abstractmethod
    async def pinMessage(self, message: Message) -> None: ...

    @abstractmethod
    async def getPinnedMessages(self, channel_id: int) -> List[Message]: ...

    @abstractmethod
    async def getLastPinnedMessage(self, channel_id: int) -> Optional[Message]: ...

    @abstractmethod
    async def addReaction(self, reaction: Reaction) -> None: ...

    @abstractmethod
    async def removeReaction(self, reaction: Reaction) -> None: ...

    @abstractmethod
    async def getMessageReactions(self, message_id: int, user_id: int) -> list: ...

    @abstractmethod
    async def getReactedUsersIds(self, reaction: Reaction, limit: int) -> List[int]: ...

    @abstractmethod
    async def searchMessages(self, filter: SearchFilter) -> Tuple[List[Message], int]: ...

    @abstractmethod
    async def putInvite(self, invite: Invite) -> None: ...

    @abstractmethod
    async def getInvite(self, invite_id: int) -> Optional[Invite]: ...

    @abstractmethod
    async def createGuildChannel(self, channel: Channel) -> None: ...

    @abstractmethod
    async def createGuildMember(self, member: GuildMember) -> None: ...

    @abstractmethod
    async def createGuildRole(self, role: Role) -> None: ...

    @abstractmethod
    async def createGuild(self, guild: Guild, roles: List[Role], channels: List[Channel]) -> None: ...

    @abstractmethod
    async def getRole(self, role_id: int) -> Role: ...

    @abstractmethod
    async def getRoles(self, guild: Guild) -> List[Role]: ...

    @abstractmethod
    async def getGuildMember(self, guild: Guild, user_id: int) -> GuildMember: ...

    @abstractmethod
    async def getGuildChannels(self, guild: Guild) -> List[Channel]: ...

    @abstractmethod
    async def getGuildMembers(self, guild: _Guild) -> List[GuildMember]: ...

    @abstractmethod
    async def getGuildMembersIds(self, guild: _Guild) -> List[int]: ...

    @abstractmethod
    async def getUserGuilds(self, user: User) -> List[Guild]: ...

    @abstractmethod
    async def getGuildMemberCount(self, guild: Guild) -> int: ...

    @abstractmethod
    async def getGuild(self, guild_id: int) -> Optional[Guild]: ...

    @abstractmethod
    async def updateGuildDiff(self, before: Guild, after: Guild) -> None: ...

    @abstractmethod
    async def getRelationshipEx(self, u1: int, u2: int) -> Optional[Relationship]: ...

    @abstractmethod
    async def getGuildInvites(self, guild: Guild) -> List[Invite]: ...

    @abstractmethod
    async def deleteInvite(self, invite: Invite) -> None: ...

    @abstractmethod
    async def deleteGuildMember(self, member: GuildMember): ...

    @abstractmethod
    async def banGuildMember(self, member: GuildMember, reason: str) -> None: ...

    @abstractmethod
    async def getGuildBan(self, guild: Guild, user_id: int) -> Optional[GuildBan]: ...

    @abstractmethod
    async def getGuildBans(self, guild: Guild) -> List[GuildBan]: ...

    @abstractmethod
    async def bulkDeleteGuildMessagesFromBanned(self, guild: Guild, user_id: int, after_id: int) -> Dict[str, List[str]]: ...

    @abstractmethod
    async def updateRoleDiff(self, before: Role, after: Role) -> None: ...

    @abstractmethod
    async def deleteRole(self, role: Role) -> None: ...

    @abstractmethod
    async def getRolesMemberCounts(self, guild: Guild) -> Dict[int, int]: ...

    @abstractmethod
    async def updateMemberDiff(self, before: GuildMember, after: GuildMember) -> None: ...

    @abstractmethod
    async def getAttachments(self, message: Message) -> List[Attachment]: ...

    @abstractmethod
    async def getMemberRolesIds(self, member: GuildMember) -> List[int]: ...

    @abstractmethod
    async def setMemberRolesFromList(self, member: GuildMember, roles: List[int]) -> None: ...

    @abstractmethod
    async def getMemberRoles(self, member: GuildMember) -> List[Role]: ...

class MySQL(Database):
    def __init__(self):
        self.pool = None

    def __call__(self):
        if not Ctx.get("DB"):
            return MySqlConnection(self)
        return Ctx["DB"]

    async def init(self, *db_args, **db_kwargs):
        self.pool = await create_pool(*db_args, **db_kwargs)

    def __new__(cls, *args, **kwargs):
        if not isinstance(Database._instance, cls):
            Database._instance = super(MySQL, cls).__new__(cls)
        return Database._instance

class MySqlConnection:
    def __init__(self, mysql: MySQL):
        self.mysql: MySQL = mysql
        self.db: Optional[Connection] = None
        self.cur: Optional[Cursor] = None
        self.close_on_aexit = True

    def dontCloseOnAExit(self):
        self.close_on_aexit = False
        return self

    async def close(self):
        await self.cur.close()
        await self.mysql.pool.release(self.db)

    async def __aenter__(self):
        if not self.db and not self.cur:
            self.db = await self.mysql.pool.acquire()
            self.cur = await self.db.cursor()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.close_on_aexit:
            await self.close()

    async def getUserByEmail(self, email: str) -> Optional[User]:
        await self.cur.execute(f'SELECT * FROM `users` WHERE `email`="{escape_string(email)}";')
        if r := await self.cur.fetchone():
            return User.from_result(self.cur.description, r)

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        await self.cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{escape_string(username)}";')
        if r := await self.cur.fetchone():
            return User(r[0])

    async def registerUser(self, user: User, session: Session, data: UserData, settings: UserSettings) -> None:
        await self.cur.execute(f'INSERT INTO `users`(`id`, `email`, `password`, `key`) VALUES ({user.id}, "{escape_string(user.email)}", "{user.password}", "{user.key}");')
        await self.cur.execute(f'INSERT INTO `sessions` VALUES ({user.id}, {session.sid}, "{session.sig}");')
        await self.cur.execute(f'INSERT INTO `settings`(`uid`, `locale`) VALUES ({user.id}, "{settings.locale}");')
        await self.cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES ({user.id}, "{data.birth}", "{data.username}", {data.discriminator});')

    async def insertSession(self, session: Session) -> None:
        await self.cur.execute(f'INSERT INTO `sessions` VALUES ({session.id}, {session.sid}, "{session.sig}");')

    async def getUser(self, uid: int) -> Optional[User]:
        await self.cur.execute(f'SELECT * FROM `users` WHERE `id`={uid};')
        if r := await self.cur.fetchone():
            return User.from_result(self.cur.description, r)

    async def validSession(self, session: Session) -> bool:
        await self. cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={session.id} AND `sid`={session.sid} AND `sig`="{escape_string(session.sig)}";')
        return bool(await self.cur.fetchone())

    async def getUserSettings(self, user: _User) -> Optional[UserSettings]:
        await self.cur.execute(f'SELECT * FROM `settings` WHERE `uid`={user.id};')
        if r := await self.cur.fetchone():
            return UserSettings.from_result(self.cur.description, r)

    async def getUserData(self, user: _User) -> Optional[UserData]:
        await self.cur.execute(f'SELECT * FROM `userdata` WHERE `uid`={user.id};')
        if r := await self.cur.fetchone():
            return UserData.from_result(self.cur.description, r)

    async def setSettings(self, settings: UserSettings) -> None:
        if not (j := settings.toJSON(for_db=True)):
            return
        await self.cur.execute(f'UPDATE `settings` SET {json_to_sql(j)} WHERE `uid`={settings.uid};')

    async def setSettingsDiff(self, before: UserSettings, after: UserSettings) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `settings` SET {diff} WHERE `uid`={before.uid};')

    async def setUserData(self, data: UserData) -> None:
        if not (j := data.toJSON(for_db=True)):
            return
        await self.cur.execute(f'UPDATE `userdata` SET {json_to_sql(j)} WHERE `uid`={data.uid};')

    async def setUserDataDiff(self, before: UserData, after: UserData) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `userdata` SET {diff} WHERE `uid`={before.uid};')

    async def relationShipAvailable(self, tUser: _User, cUser: _User) -> bool:
        await self.cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={tUser.id} AND `u2`={cUser.id}) OR (`u1`={cUser.id} AND `u2`={tUser.id});')
        return not bool(await self.cur.fetchone())

    async def insertRelationShip(self, relationship: Relationship) -> None:
        await self.cur.execute(f'INSERT INTO `relationships` VALUES ({relationship.u1}, {relationship.u2}, {relationship.type});')

    async def getRelationships(self, uid: int) -> List[Relationship]:
        relationships = []
        await self.cur.execute(f'SELECT * FROM `relationships` WHERE `u1`={uid} OR `u2`={uid};')
        for r in await self.cur.fetchall():
            relationships.append(Relationship.from_result(self.cur.description, r))
        return relationships

    async def updateRelationship(self, cUser: int, tUser: int, ntype: int, otype: int):
        await self.cur.execute(f'UPDATE `relationships` SET `type`={ntype} WHERE `u1`={tUser} AND `u2`={cUser} AND `type`={otype};')

    async def getRelationship(self, u1: int, u2: int) -> Optional[Relationship]:
        await self.cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={u1} AND `u2`={u2}) OR (`u1`={u2} AND `u2`={u1});')
        if r := await self.cur.fetchone():
            return Relationship.from_result(self.cur.description, r)

    async def getRelationshipEx(self, u1: int, u2: int) -> Optional[Relationship]:
        await self.cur.execute(f'SELECT * FROM `relationships` WHERE `u1`={u1} AND `u2`={u2};')
        if r := await self.cur.fetchone():
            return Relationship.from_result(self.cur.description, r)

    async def delRelationship(self, relationship: Relationship) -> None:
        await self.cur.execute(f"DELETE FROM `relationships` WHERE `u1`={relationship.u1} AND `u2`={relationship.u2} LIMIT 1;")

    async def changeUserPassword(self, user: User, password: str) -> None:
        await self.cur.execute(f'UPDATE `users` SET `password`="{escape_string(password)}" WHERE `id`={user.id}')

    async def logoutUser(self, sess: Session) -> None:
        await self.cur.execute(f'DELETE FROM `sessions` WHERE `uid`={sess.uid} AND `sid`={sess.sid} AND `sig`="{sess.sig}" LIMIT 1;')

    async def setBackupCodes(self, user: _User, codes: List[str]) -> None:
        codes = [(str(user.id), code) for code in codes]
        await self.cur.executemany('INSERT INTO `mfa_codes` (`uid`, `code`) VALUES (%s, %s)', codes)

    async def clearBackupCodes(self, user: _User) -> None:
        await self.cur.execute(f'DELETE FROM `mfa_codes` WHERE `uid`={user.id} LIMIT 10;')

    async def getBackupCodes(self, user: _User) -> List[Tuple[str, bool]]:
        await self.cur.execute(f'SELECT `code`, `used` FROM `mfa_codes` WHERE `uid`={user.id} LIMIT 10;')
        return await self.cur.fetchall()

    async def useMfaCode(self, uid: int, code: str) -> None:
        await self.cur.execute(f'UPDATE `mfa_codes` SET `used`=true WHERE `code`="{escape_string(code)}" AND `uid`={uid} LIMIT 1;')

    async def getChannel(self, channel_id: int) -> Optional[Channel]:
        await self.cur.execute(f'SELECT * FROM `channels` WHERE `id`={channel_id};')
        if r := await self.cur.fetchone():
            return Channel.from_result(self.cur.description, r)

    async def getDMChannel(self, u1: int, u2: int) -> Optional[Channel]:
        await self.cur.execute(f'SELECT * FROM `channels` WHERE JSON_CONTAINS(j_recipients, {u1}, "$") AND JSON_CONTAINS(j_recipients, {u2}, "$") AND `type`={ChannelType.DM};')
        if r := await self.cur.fetchone():
            return Channel.from_result(self.cur.description, r)

    async def getLastMessageId(self, channel: _Channel, before: int, after: int) -> int:
        await self.cur.execute(f'SELECT `id` FROM `messages` WHERE `channel_id`={channel.id} AND `id` > {after} AND `id` < {before} ORDER BY `id` DESC LIMIT 1;')
        last = None
        if r := await self.cur.fetchone():
            last = r[0]
        return last

    async def getChannelMessagesCount(self, channel: Channel, before: int, after: int) -> int:
        await self.cur.execute(f'SELECT COUNT(`id`) as count FROM `messages` WHERE `channel_id`={channel.id} AND `id` > {after} AND `id` < {before};')
        return (await self.cur.fetchone())[0]

    async def createDMChannel(self, channel_id: int, recipients: List[int]) -> Channel:
        await self.cur.execute(f'INSERT INTO `channels` (`id`, `type`, `j_recipients`) VALUES ({channel_id}, {ChannelType.DM}, "{recipients}");')
        return Channel(channel_id, ChannelType.DM, recipients=recipients)

    async def getPrivateChannels(self, user: _User) -> List[Channel]:
        channels = []
        await self.cur.execute(f'SELECT * FROM channels WHERE JSON_CONTAINS(channels.j_recipients, {user.id}, "$");')
        for r in await self.cur.fetchall():
            channels.append(Channel.from_result(self.cur.description, r))
        return channels

    async def getChannelMessages(self, channel, limit: int, before: int = None, after: int = None) -> List[Message]:
        messages = []
        where = [f"`channel_id`={channel.id}"]
        if before:
            where.append(f"`id` < {before}")
        if after:
            where.append(f"`id` > {after}")
        where = " AND ".join(where)
        await self.cur.execute(f'SELECT * FROM `messages` WHERE {where} ORDER BY `id` DESC LIMIT {limit};')
        for r in await self.cur.fetchall():
            messages.append(Message.from_result(self.cur.description, r))
        return messages

    async def getMessage(self, channel: Channel, message_id: int) -> Optional[Message]:
        await self.cur.execute(f'SELECT * FROM `messages` WHERE `channel_id`={channel.id} AND `id`={message_id};')
        if r := await self.cur.fetchone():
            return Message.from_result(self.cur.description, r)

    async def insertMessage(self, message: Message) -> None:
        q = json_to_sql(message.toJSON(for_db=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await self.cur.execute(f'INSERT INTO `messages` ({fields}) VALUES ({values});')

    async def editMessage(self, before: Message, after: Message) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        await self.cur.execute(f'UPDATE `messages` SET {diff} WHERE `id`={before.id} AND `channel_id`={before.channel_id}')

    async def deleteMessage(self, message: Message) -> None:
        await self.cur.execute(f'DELETE FROM `messages` WHERE `id`={message.id};')

    async def getReadStates(self, uid: int, channel_id: int=None) -> List[ReadState]:
        states = []
        where = [f"`uid`={uid}"]
        if channel_id:
            where.append(f"`channel_id`={channel_id}")
        where = " AND ".join(where)
        await self.cur.execute(f'SELECT * FROM `read_states` WHERE {where};')
        for r in await self.cur.fetchall():
            states.append(ReadState.from_result(self.cur.description, r))
        return states

    async def setReadState(self, uid: int, channel_id: int, count: int, last: int = None) -> None:
        if not last: last = "`last_read_id`"
        await self.cur.execute(f'UPDATE `read_states` set `count`={count}, `last_read_id`={last} WHERE `uid`={uid} and `channel_id`={channel_id};')
        if self.cur.rowcount == 0:
            if not last:
                last = await self.getLastMessageId(ChannelId(channel_id), before=Snowflake.makeId(False), after=0)
            await self.cur.execute(f'INSERT INTO `read_states` (`uid`, `channel_id`, `last_read_id`, `count`) VALUES ({uid}, {channel_id}, {last}, {count});')

    async def delReadStateIfExists(self, uid: int, channel_id: int) -> bool:
        await self.cur.execute(f'DELETE FROM `read_states` WHERE `uid`={uid} and `channel_id`={channel_id};')
        return self.cur.rowcount > 0

    async def getUserNote(self, uid: int, target_uid: int) -> Optional[UserNote]:
        await self.cur.execute(f'SELECT * FROM `notes` WHERE `uid`={uid} AND `target_uid`={target_uid};')
        if r := await self.cur.fetchone():
            return UserNote.from_result(self.cur.description, r)

    async def putUserNote(self, note: UserNote) -> None:
        await self.cur.execute(f'UPDATE `notes` SET `note`="{note.note}" WHERE `uid`={note.user_id} AND `target_uid`={note.note_user_id}')
        if self.cur.rowcount == 0:
            q = json_to_sql(note.toJSON(), as_tuples=True)
            fields = ", ".join([f"`{f}`" for f, v in q])
            values = ", ".join([f"{v}" for f, v in q])
            await self.cur.execute(f'INSERT INTO `notes` ({fields}) VALUES ({values});')

    #async def putUserConnection(self, uc: UserConnection) -> None: # TODO: implement UserConnection
    #    q = json_to_sql(uc.to_sql_json(uc.to_typed_json, with_id=True), as_tuples=True)
    #    fields = ", ".join([f"`{f}`" for f, v in q])
    #    values = ", ".join([f"{v}" for f, v in q])
    #    await self.cur.execute(f'INSERT INTO `connections` ({fields}) VALUES ({values});')

    async def putAttachment(self, attachment: Attachment) -> None:
        q = json_to_sql(attachment.toJSON(for_db=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await self.cur.execute(f'INSERT INTO `attachments` ({fields}) VALUES ({values});')

    async def getAttachment(self, id: int) -> Optional[Attachment]:
        await self.cur.execute(f'SELECT * FROM `attachments` WHERE `id`="{id}"')
        if r := await self.cur.fetchone():
            return Attachment.fromResult(self.cur.description, r)

    async def getAttachmentByUUID(self, uuid: str) -> Optional[Attachment]:
        await self.cur.execute(f'SELECT * FROM `attachments` WHERE `uuid`="{uuid}"')
        if r := await self.cur.fetchone():
            return Attachment.fromResult(self.cur.description, r)

    async def updateAttachment(self, before: Attachment, after: Attachment) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        await self.cur.execute(f'UPDATE `attachments` SET {diff} WHERE `id`={before.id};')

    async def setFrecencySettings(self, uid: int, proto: str) -> None:
        await self.cur.execute(f'INSERT INTO `frecency_settings` (`uid`, `settings`) VALUES ({uid}, "{escape_string(proto)}") ON DUPLICATE KEY UPDATE `settings`="{escape_string(proto)}";')

    async def getFrecencySettings(self, uid: int) -> str:
        await self.cur.execute(f'SELECT `settings` FROM `frecency_settings` WHERE `uid`={uid};')
        if r := await self.cur.fetchone():
            return r[0]
        return ""

    async def verifyEmail(self, uid: int) -> None:
        await self.cur.execute(f'UPDATE `users` SET `verified`=true WHERE `id`={uid};')

    async def changeUserEmail(self, uid: int, email: str) -> None:
        await self.cur.execute(f'UPDATE `users` SET `email`="{escape_string(email)}", `verified`=false WHERE `id`={uid};')

    async def createDMGroupChannel(self, channel_id: int, recipients: List[int], owner_id: int) -> Channel:
        await self.cur.execute(f'INSERT INTO `channels` (`id`, `type`, `j_recipients`, `owner_id`) VALUES ({channel_id}, {ChannelType.GROUP_DM}, "{escape_string(jdumps(recipients))}", {owner_id});')
        return Channel(channel_id, ChannelType.GROUP_DM, recipients=recipients, owner_id=owner_id, icon=None, name=None)

    async def updateChannelDiff(self, before: Channel, after: Channel) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `channels` SET {diff} WHERE `id`={before.id};')

    async def deleteChannel(self, channel: Channel) -> None:
        if channel.type == ChannelType.GROUP_DM:
            await self.cur.execute(f"DELETE FROM `channels` WHERE `id`={channel.id} AND JSON_LENGTH(j_recipients) = 0;")
        elif channel.type in (ChannelType.GUILD_TEXT, ChannelType.GUILD_VOICE, ChannelType.GUILD_CATEGORY):
            await self.cur.execute(f"DELETE FROM `channels` WHERE `id`={channel.id};")
        await self.cur.execute(f"DELETE FROM `read_states` WHERE `channel_id`={channel.id};")
        # TODO: delete all messages in channel

    async def deleteMessagesAck(self, channel: Channel, user: User) -> None:
        await self.cur.execute(f"DELETE FROM `read_states` WHERE `uid`={user.id} AND `channel_id`={channel.id};")

    async def pinMessage(self, message: Message) -> None:
        e = message.extra_data
        e.update({"pinned_at": time()})
        sql = json_to_sql({"pinned": True, "extra_data": e})
        await self.cur.execute(f'UPDATE `messages` SET {sql} WHERE `id`={message.id};')

    async def getPinnedMessages(self, channel_id: int) -> List[Message]:
        messages = []
        await self.cur.execute(f'SELECT * FROM `messages` WHERE `channel_id`={channel_id} AND `pinned`=true;')
        for r in await self.cur.fetchall():
            messages.append(Message.from_result(self.cur.description, r))
        return messages

    async def getLastPinnedMessage(self, channel_id: int) -> Optional[Message]:
        await self.cur.execute(f'SELECT * FROM `messages` WHERE `channel_id`={channel_id} AND `pinned`=true ORDER BY `id` DESC LIMIT 1;')
        if r := await self.cur.fetchone():
            return Message.from_result(self.cur.description, r)

    async def unpinMessage(self, message: Message) -> None:
        e = message.extra_data
        del e["pinned_at"]
        sql = json_to_sql({"pinned": False, "extra_data": e})
        await self.cur.execute(f'UPDATE `messages` SET {sql} WHERE `id`={message.id};')

    async def addReaction(self, reaction: Reaction) -> None:
        sql = json_to_sql(reaction.toJSON(for_db=True), as_list=True)
        ssql = " AND ".join(sql)
        await self.cur.execute(f'SELECT * FROM `reactions` WHERE {ssql} LIMIT 1;')
        if await self.cur.fetchone():
            return
        sql = json_to_sql(reaction.toJSON(for_db=True), as_tuples=True)
        fields = ", ".join([r[0] for r in sql])
        isql = ", ".join([str(r[1]) for r in sql])
        await self.cur.execute(f'INSERT INTO `reactions` ({fields}) VALUES ({isql});')

    async def removeReaction(self, reaction: Reaction) -> None:
        sql = json_to_sql(reaction.toJSON(for_db=True), as_list=True, is_none=True)
        dsql = " AND ".join(sql)
        await self.cur.execute(f'DELETE FROM `reactions` WHERE {dsql} LIMIT 1;')

    async def getMessageReactions(self, message_id: int, user_id: int) -> list:
        reactions = []
        await self.cur.execute(
            f'SELECT `emoji_name` as ename, `emoji_id` as eid, COUNT(*) AS ecount, ' +
            f'(SELECT COUNT(*) > 0 FROM `reactions` WHERE `emoji_name`=ename AND (`emoji_id`=eid OR (`emoji_id` IS NULL AND eid IS NULL)) AND `user_id`={user_id}) as me ' +
            f'FROM `reactions` WHERE `message_id`={message_id} GROUP BY CONCAT(`emoji_name`, `emoji_id`) COLLATE utf8mb4_unicode_520_ci;'
        ) #                                                                    utf8mb4_unicode_520_ci for emoji --^^^^^^^^^^^^^^^^^^^^
        for r in await self.cur.fetchall():
            reactions.append({"emoji": {"id": str(r[1]) if r[1] else None, "name": r[0]}, "count": r[2], "me": bool(r[3])})
        return reactions

    async def getReactedUsersIds(self, reaction: Reaction, limit: int) -> List[int]:
        sql = json_to_sql(reaction.toJSON(for_db=True), as_list=True, is_none=True)
        sql = [s for s in sql if "user_id" not in s]
        sql = " AND ".join(sql)
        await self.cur.execute(f'SELECT `user_id` FROM `reactions` WHERE {sql} LIMIT {limit};')
        return [r[0] for r in await self.cur.fetchall()]

    async def searchMessages(self, filter: SearchFilter) -> Tuple[List[Message], int]:
        messages = []
        where = filter.to_sql()
        await self.cur.execute(f'SELECT * FROM `messages` WHERE {where};')
        for r in await self.cur.fetchall():
            messages.append(Message.from_result(self.cur.description, r))
        where = sub(r' LIMIT \d+,?\d*', "", where)
        await self.cur.execute(f'SELECT COUNT(*) as c FROM `messages` WHERE {where};')
        total = (await self.cur.fetchone())[0]
        return messages, total

    async def putInvite(self, invite: Invite) -> None:
        sql = json_to_sql(invite.toJSON(for_db=True), as_tuples=True)
        fields = ", ".join([r[0] for r in sql])
        isql = ", ".join([str(r[1]) for r in sql])
        await self.cur.execute(f'INSERT INTO `invites` ({fields}) VALUES ({isql});')

    async def getInvite(self, invite_id: int) -> Optional[Invite]:
        await self.cur.execute(f'SELECT * FROM `invites` WHERE `id`={invite_id}')
        if r := await self.cur.fetchone():
            return Invite.from_result(self.cur.description, r)

    async def createGuildChannel(self, channel: Channel) -> None:
        fields, values = json_to_sql(channel.toJSON(for_db=True), for_insert=True)
        await self.cur.execute(f'INSERT INTO `channels` ({fields}) VALUES ({values})')

    async def createGuildMember(self, member: GuildMember) -> None:
        fields, values = json_to_sql(member.toJSON(for_db=True), for_insert=True)
        await self.cur.execute(f'INSERT INTO `guild_members` ({fields}) VALUES ({values})')

    async def createGuildRole(self, role: Role) -> None:
        fields, values = json_to_sql(role.toJSON(for_db=True), for_insert=True)
        await self.cur.execute(f'INSERT INTO `roles` ({fields}) VALUES ({values})')

    async def createGuild(self, guild: Guild, roles: List[Role], channels: List[Channel], members: List[GuildMember]) -> None:
        fields, values = json_to_sql(guild.toJSON(for_db=True), for_insert=True)
        await self.cur.execute(f'INSERT INTO `guilds` ({fields}) VALUES ({values})')
        for role in roles:
            await self.createGuildRole(role)
        for channel in channels:
            await self.createGuildChannel(channel)
        for member in members:
            await self.createGuildMember(member)

    async def getRole(self, role_id: int) -> Role:
        await self.cur.execute(f'SELECT * FROM `roles` WHERE `id`={role_id} LIMIT 1;')
        if r := await self.cur.fetchone():
            return Role.from_result(self.cur.description, r)

    async def getRoles(self, guild: Guild) -> List[Role]:
        roles = []
        await self.cur.execute(f'SELECT * FROM `roles` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            roles.append(Role.from_result(self.cur.description, r))
        return roles

    async def getGuildMember(self, guild: Guild, user_id: int) -> GuildMember:
        await self.cur.execute(f'SELECT * FROM `guild_members` WHERE `user_id`={user_id} AND `guild_id`={guild.id} LIMIT 1;')
        if r := await self.cur.fetchone():
            return GuildMember.from_result(self.cur.description, r)

    async def getGuildMembers(self, guild: _Guild) -> List[GuildMember]:
        members = []
        await self.cur.execute(f'SELECT * FROM `guild_members` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            members.append(GuildMember.from_result(self.cur.description, r))
        return members

    async def getGuildMembersIds(self, guild: _Guild) -> List[int]:
        await self.cur.execute(f'SELECT `user_id` FROM `guild_members` WHERE `guild_id`={guild.id};')
        return [r[0] for r in await self.cur.fetchall()]

    async def getGuildChannels(self, guild: Guild) -> List[Channel]:
        channels = []
        await self.cur.execute(f'SELECT * FROM `channels` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            channels.append(Channel.from_result(self.cur.description, r))
        return channels

    async def getUserGuilds(self, user: User) -> List[Guild]:
        guilds = []
        await self.cur.execute(f'SELECT * FROM `guilds` WHERE `id` IN (SELECT `guild_id` FROM `guild_members` WHERE `user_id`={user.id});')
        for r in await self.cur.fetchall():
            guilds.append(Guild.from_result(self.cur.description, r))
        return guilds

    async def getGuildMemberCount(self, guild: Guild) -> int:
        await self.cur.execute(f'SELECT COUNT(*) as c FROM `guild_members` WHERE `guild_id`={guild.id};')
        if r := await self.cur.fetchone():
            return r[0]
        return 0

    async def getGuild(self, guild_id: int) -> Optional[Guild]:
        await self.cur.execute(f'SELECT * FROM `guilds` WHERE `id`={guild_id};')
        if r := await self.cur.fetchone():
            return Guild.from_result(self.cur.description, r)

    async def updateGuildDiff(self, before: Guild, after: Guild) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `guilds` SET {diff} WHERE `id`={before.id};')

    async def addEmoji(self, emoji: Emoji) -> None:
        fields, values = json_to_sql(emoji.toJSON(for_db=True), for_insert=True)
        await self.cur.execute(f'INSERT INTO `emojis` ({fields}) VALUES ({values})')

    async def getEmoji(self, emoji_id: int) -> Optional[Emoji]:
        await self.cur.execute(f'SELECT * FROM `emojis` WHERE `id`={emoji_id};')
        if r := await self.cur.fetchone():
            return Emoji.from_result(self.cur.description, r)

    async def getEmojis(self, guild_id: int) -> List[Emoji]:
        emojis = []
        await self.cur.execute(f'SELECT * FROM `emojis` WHERE `guild_id`={guild_id};')
        for r in await self.cur.fetchall():
            emojis.append(Emoji.from_result(self.cur.description, r))
        return emojis

    async def deleteEmoji(self, emoji: Emoji) -> None:
        await self.cur.execute(f'DELETE FROM `emojis` WHERE `id`={emoji.id} LIMIT 1;')

    async def getGuildInvites(self, guild: Guild) -> List[Invite]:
        invites = []
        await self.cur.execute(f'SELECT * FROM `invites` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            invites.append(Invite.from_result(self.cur.description, r))
        return invites

    async def deleteInvite(self, invite: Invite) -> None:
        await self.cur.execute(f'DELETE FROM `invites` WHERE `id`={invite.id} LIMIT 1;')

    async def deleteGuildMember(self, member: GuildMember):
        await self.cur.execute(f'DELETE FROM `guild_members` WHERE `user_id`={member.user_id} AND `guild_id`={member.guild_id} LIMIT 1;')

    async def banGuildMember(self, member: GuildMember, reason: str) -> None:
        reason = f'"{escape_string(reason)}"' if reason is not None else "NULL"
        await self.cur.execute(f'INSERT INTO `guild_bans` (`user_id`, `guild_id`, `reason`) '
                               f'VALUES ({member.user_id}, {member.guild_id}, {reason})')

    async def getGuildBan(self, guild: Guild, user_id: int) -> Optional[GuildBan]:
        await self.cur.execute(f'SELECT * FROM `guild_bans` WHERE `guild_id`={guild.id} AND `user_id`={user_id};')
        if r := await self.cur.fetchone():
            return GuildBan.from_result(self.cur.description, r)

    async def getGuildBans(self, guild: Guild) -> List[GuildBan]:
        bans = []
        await self.cur.execute(f'SELECT * FROM `guild_bans` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            bans.append(GuildBan.from_result(self.cur.description, r))
        return bans

    async def bulkDeleteGuildMessagesFromBanned(self, guild: Guild, user_id: int, after_id: int) -> Dict[int, List[int]]:
        await self.cur.execute(f'SELECT `id`, `channel_id` FROM `messages` WHERE `guild_id`={guild.id} '
                                f'AND `author`={user_id} AND `id`>{after_id};')
        messages = await self.cur.fetchall()
        ids = [(message[0],) for message in messages]
        await self.cur.executemany(f'DELETE FROM `messages` WHERE `id`=%s;', ids)
        result = {}
        for message in messages:
            if message[1] not in result:
                result[message[1]] = []
            result[message[1]].append(message[0])
        return result

    async def updateRoleDiff(self, before: Role, after: Role) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `roles` SET {diff} WHERE `id`={before.id};')

    async def deleteRole(self, role: Role) -> None:
        await self.cur.execute(f'DELETE FROM `roles` WHERE `id`={role.id} LIMIT 1;')

    async def getRolesMemberCounts(self, guild: Guild) -> Dict[int, int]:
        counts = {}
        await self.cur.execute(f'SELECT `id`, (SELECT count(*) FROM `guild_members_roles` WHERE `role_id`=`id`) '
                               f'AS member_count FROM `roles` WHERE `guild_id`={guild.id};')
        for r in await self.cur.fetchall():
            counts[r[0]] = r[1]

        return counts

    async def updateMemberDiff(self, before: GuildMember, after: GuildMember) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `guild_members` SET {diff} WHERE '
                                   f'`guild_id`={before.guild_id} AND `user_id`={before.id};')

    async def getAttachments(self, message: Message) -> List[Attachment]:
        attachments = []
        await self.cur.execute(f'SELECT * FROM `attachments` WHERE `message_id`={message.id};')
        for r in await self.cur.fetchall():
            attachments.append(Attachment.from_result(self.cur.description, r))
        return attachments

    async def getMemberRolesIds(self, member: GuildMember) -> List[int]:
        await self.cur.execute(f'SELECT `role_id` FROM `guild_members_roles` WHERE `user_id`={member.user_id}')
        return [r[0] for r in await self.cur.fetchall()]

    async def setMemberRolesFromList(self, member: GuildMember, roles: List[int]) -> None:
        delete = []
        create = []
        current_roles = await self.getMemberRolesIds(member)
        for role in roles:
            if role not in current_roles:
                create.append(role)
        for role in current_roles:
            if role not in roles:
                delete.append(role)
        if create:
            await self.cur.executemany(f'INSERT INTO `guild_members_roles` VALUES ({member.id}, %s);', create)
        if delete:
            await self.cur.executemany(f'DELETE FROM `guild_members_roles` WHERE `user_id`={member.id} AND '
                                       f'`role_id`=%s;', delete)

    async def getMemberRoles(self, member: GuildMember) -> List[Role]:
        roles = []
        await self.cur.execute(f'SELECT * FROM `roles` WHERE `id` IN (SELECT `role_id` FROM `guild_members_roles` WHERE '
                               f'`user_id`={member.id});')
        for r in await self.cur.fetchall():
            roles.append(Role.from_result(self.cur.description, r))
        return roles