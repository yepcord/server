from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ..ctx import getCore
from ..utils import sf_ts

if TYPE_CHECKING:
    from ..classes.user import UserData, UserSettings, GuildMember, UserId


async def discord_UserData(userdata: UserData) -> dict:
    return {
        "id": str(userdata.uid),
        "username": userdata.username,
        "avatar": userdata.avatar,
        "avatar_decoration": userdata.avatar_decoration,
        "discriminator": userdata.s_discriminator,
        "public_flags": userdata.public_flags
    }

async def discord_UserSettings(settings: UserSettings) -> dict:
    data = settings.toJSON()
    data["mfa"] = bool(data["mfa"])
    return data

async def discord_GuildMember(member: GuildMember) -> dict:
    userdata = await getCore().getUserData(UserId(member.user_id))
    return {
        "avatar": member.avatar,
        "communication_disabled_until": member.communication_disabled_until,
        "flags": member.flags,
        "joined_at": datetime.utcfromtimestamp(member.joined_at).strftime("%Y-%m-%dT%H:%M:%S.000000+00:00"),
        "nick": member.nick,
        "is_pending": False,  # TODO
        "pending": False,  # TODO
        "premium_since": datetime.utcfromtimestamp(int(sf_ts(member.user_id) / 1000)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "roles": member.roles,
        "user": await userdata.json,
        "mute": member.mute,
        "deaf": member.deaf
    }