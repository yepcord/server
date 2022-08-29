from abc import ABC, abstractmethod
from typing import Optional, List

from aiomysql import create_pool, escape_string, Cursor, Connection

from .classes import User, Session, UserData, _User, UserSettings, Relationship, Channel, Message, ReadState, _Channel, \
    ChannelId, UserNote, UserConnection, Attachment
from .utils import json_to_sql, ChannelType, lsf


class Database:
    _instance = None

    def __getattr__(self, item):
        return getattr(Database._instance, item)

class DBConnection(ABC):
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

    @abstractmethod
    async def putUserConnection(self, uc: UserConnection) -> None: ...

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
    async def getFrecencySettings(self, uid) -> str: ...

class MySQL(Database):
    def __init__(self):
        self.pool = None

    def __call__(self):
        return MySqlConnection(self)

    async def init(self, *db_args, **db_kwargs):
        self.pool = await create_pool(*db_args, **db_kwargs)

    def __new__(cls, *args, **kwargs):
        if not isinstance(Database._instance, cls):
            Database._instance = super(MySQL, cls).__new__(cls)
        return Database._instance

class MySqlConnection:
    def __init__(self, mysql: MySQL):
        self.mysql: MySQL = mysql
        self.db: Connection = None
        self.cur: Cursor = None

    async def __aenter__(self):
        self.db = await self.mysql.pool.acquire()
        self.cur = await self.db.cursor()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cur.close()
        await self.mysql.pool.release(self.db)

    async def getUserByEmail(self, email: str) -> Optional[User]:
        await self.cur.execute(f'SELECT * FROM `users` WHERE `email`="{escape_string(email)}";')
        if (r := await self.cur.fetchone()):
            return User.from_result(self.cur.description, r)

    async def getUserByUsername(self, username: str, discriminator: int) -> Optional[User]:
        await self.cur.execute(f'SELECT `uid` FROM `userdata` WHERE `discriminator`={discriminator} AND `username`="{escape_string(username)}";')
        if (r := await self.cur.fetchone()):
            return User(r[0])

    async def registerUser(self, user: User, session: Session, data: UserData) -> None:
        await self.cur.execute(f'INSERT INTO `users` VALUES ({user.id}, "{escape_string(user.email)}", "{user.password}", "{user.key}");')
        await self.cur.execute(f'INSERT INTO `sessions` VALUES ({user.id}, {session.sid}, "{session.sig}");')
        await self.cur.execute(f'INSERT INTO `settings`(`uid`) VALUES ({user.id});')
        await self.cur.execute(f'INSERT INTO `userdata`(`uid`, `birth`, `username`, `discriminator`) VALUES ({user.id}, "{data.birth}", "{data.username}", {data.discriminator});')

    async def insertSession(self, session: Session) -> None:
        await self.cur.execute(f'INSERT INTO `sessions` VALUES ({session.id}, {session.sid}, "{session.sig}");')

    async def getUser(self, uid: int) -> Optional[User]:
        await self.cur.execute(f'SELECT * FROM `users` WHERE `id`={uid};')
        if (r := await self.cur.fetchone()):
            return User.from_result(self.cur.description, r)

    async def validSession(self, session: Session) -> bool:
        await self. cur.execute(f'SELECT `uid` FROM `sessions` WHERE `uid`={session.id} AND `sid`={session.sid} AND `sig`="{session.sig}";')
        return bool(await self.cur.fetchone())

    async def getUserSettings(self, user: _User) -> UserSettings:
        await self.cur.execute(f'SELECT * FROM `settings` WHERE `uid`={user.id};')
        r = await self.cur.fetchone()
        return UserSettings.from_result(self.cur.description, r)

    async def getUserData(self, user: _User) -> UserSettings:
        await self.cur.execute(f'SELECT * FROM `userdata` WHERE `uid`={user.id};')
        r = await self.cur.fetchone()
        return UserData.from_result(self.cur.description, r)

    async def setSettings(self, settings: UserSettings) -> None:
        if not (j := settings.to_sql_json(settings.to_typed_json, with_values=True)):
            return
        await self.cur.execute(f'UPDATE `settings` SET {json_to_sql(j)} WHERE `uid`={settings.uid};')

    async def setSettingsDiff(self, before: UserSettings, after: UserSettings) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `settings` SET {diff} WHERE `uid`={before.uid};')

    async def setUserData(self, data: UserData) -> None:
        if not (j := data.to_sql_json(data.to_typed_json, with_values=True)):
            return
        await self.cur.execute(f'UPDATE `userdata` SET {json_to_sql(j)} WHERE `uid`={data.uid};')

    async def setUserDataDiff(self, before: UserData, after: UserData) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        if diff:
            await self.cur.execute(f'UPDATE `userdata` SET {diff} WHERE `uid`={before.uid};')

    async def relationShipAvailable(self, tUser: User, cUser: User) -> bool:
        await self.cur.execute(f'SELECT * FROM `relationships` WHERE (`u1`={tUser.id} AND `u2`={cUser.id}) OR (`u1`={cUser.id} AND `u2`={tUser.id});')
        return not bool(self.cur.fetchone())

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
        if (r := await self.cur.fetchone()):
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

    async def getBackupCodes(self, user: _User) -> list:
        await self.cur.execute(f'SELECT `code`, `used` FROM `mfa_codes` WHERE `uid`={user.id} LIMIT 10;')
        return await self.cur.fetchall()

    async def useMfaCode(self, uid: int, code: str) -> None:
        await self.cur.execute(f'UPDATE `mfa_codes` SET `used`=true WHERE `code`="{escape_string(code)}" AND `uid`={uid} LIMIT 1;')

    async def getChannel(self, channel_id: int) -> Optional[Channel]:
        await self.cur.execute(f'SELECT * FROM `channels` WHERE `id`={channel_id};')
        if (r := await self.cur.fetchone()):
            return Channel.from_result(self.cur.description, r)

    async def getDMChannel(self, u1: int, u2: int) -> Optional[Channel]:
        await self.cur.execute(f'SELECT * FROM `channels` WHERE JSON_CONTAINS(j_recipients, {u1}, "$") AND JSON_CONTAINS(j_recipients, {u2}, "$");')
        if (r := await self.cur.fetchone()):
            return Channel.from_result(self.cur.description, r)

    async def getLastMessageId(self, channel: _Channel, before: int, after: int) -> int:
        await self.cur.execute(f'SELECT `id` FROM `messages` WHERE `channel_id`={channel.id} AND `id` > {after} AND `id` < {before} ORDER BY `id` DESC LIMIT 1;')
        last = None
        if (r := await self.cur.fetchone()):
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
        if (r := await self.cur.fetchone()):
            return Message.from_result(self.cur.description, r)

    async def insertMessage(self, message: Message) -> None:
        q = json_to_sql(message.to_sql_json(message.to_typed_json, with_id=True), as_tuples=True)
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
                last = await self.getLastMessageId(ChannelId(channel_id), before=lsf() + 1, after=0)
            await self.cur.execute(f'INSERT INTO `read_states` (`uid`, `channel_id`, `last_read_id`, `count`) VALUES ({uid}, {channel_id}, {last}, {count});')

    async def delReadStateIfExists(self, uid: int, channel_id: int) -> bool:
        await self.cur.execute(f'DELETE FROM `read_states` WHERE `uid`={uid} and `channel_id`={channel_id};')
        return self.cur.rowcount > 0

    async def getUserNote(self, uid: int, target_uid: int) -> Optional[UserNote]:
        await self.cur.execute(f'SELECT * FROM `notes` WHERE `uid`={uid} AND `target_uid`={target_uid};')
        if (r := await self.cur.fetchone()):
            return UserNote.from_result(self.cur.description, r)

    async def putUserNote(self, note: UserNote) -> None:
        await self.cur.execute(f'UPDATE `notes` SET `note`="{note.note}" WHERE `uid`={note.uid} AND `target_uid`={note.target_uid}')
        if self.cur.rowcount == 0:
            q = json_to_sql(note.to_sql_json(note.to_typed_json), as_tuples=True)
            fields = ", ".join([f"`{f}`" for f, v in q])
            values = ", ".join([f"{v}" for f, v in q])
            await self.cur.execute(f'INSERT INTO `notes` ({fields}) VALUES ({values});')

    async def putUserConnection(self, uc: UserConnection) -> None:
        q = json_to_sql(uc.to_sql_json(uc.to_typed_json, with_id=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await self.cur.execute(f'INSERT INTO `connections` ({fields}) VALUES ({values});')

    async def putAttachment(self, attachment: Attachment) -> None:
        q = json_to_sql(attachment.to_sql_json(attachment.to_typed_json, with_id=True), as_tuples=True)
        fields = ", ".join([f"`{f}`" for f, v in q])
        values = ", ".join([f"{v}" for f, v in q])
        await self.cur.execute(f'INSERT INTO `attachments` ({fields}) VALUES ({values});')

    async def getAttachment(self, id: int) -> Optional[Attachment]:
        await self.cur.execute(f'SELECT * FROM `attachments` WHERE `id`="{id}"')
        if (r := await self.cur.fetchone()):
            return Attachment.from_result(self.cur.description, r)

    async def getAttachmentByUUID(self, uuid: str) -> Optional[Attachment]:
        await self.cur.execute(f'SELECT * FROM `attachments` WHERE `uuid`="{uuid}"')
        if (r := await self.cur.fetchone()):
            return Attachment.from_result(self.cur.description, r)

    async def updateAttachment(self, before: Attachment, after: Attachment) -> None:
        diff = before.get_diff(after)
        diff = json_to_sql(diff)
        await self.cur.execute(f'UPDATE `attachments` SET {diff} WHERE `id`={before.id};')

    async def setFrecencySettings(self, uid: int, proto: str) -> None:
        await self.cur.execute(f'INSERT INTO `frecency_settings` (`uid`, `settings`) VALUES ({uid}, "{escape_string(proto)}") ON DUPLICATE KEY UPDATE `settings`="{escape_string(proto)}";')

    async def getFrecencySettings(self, uid: int) -> str:
        await self.cur.execute(f'SELECT `settings` FROM `frecency_settings` WHERE `uid`={uid};')
        if (r := await self.cur.fetchone()):
            return r[0]
        return ""