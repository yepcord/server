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
from datetime import datetime
from os import urandom
from random import choice

from emoji import is_emoji
from quart import Blueprint, request
from quart_schema import validate_request, validate_querystring

from ..models.channels import ChannelUpdate, MessageCreate, MessageUpdate, InviteCreate, PermissionOverwriteModel, \
    WebhookCreate, SearchQuery, GetMessagesQuery, GetReactionsQuery, MessageAck, CreateThread
from ..utils import getUser, multipleDecorators, getChannel, getMessage, _getMessage, processMessageData
from ...gateway.events import MessageCreateEvent, TypingEvent, MessageDeleteEvent, MessageUpdateEvent, \
    DMChannelCreateEvent, DMChannelUpdateEvent, ChannelRecipientAddEvent, ChannelRecipientRemoveEvent, \
    DMChannelDeleteEvent, MessageReactionAddEvent, MessageReactionRemoveEvent, ChannelUpdateEvent, ChannelDeleteEvent, \
    WebhooksUpdateEvent, ThreadCreateEvent, ThreadMemberUpdateEvent, MessageAckEvent, GuildAuditLogEntryCreateEvent
from ...yepcord.ctx import getCore, getCDNStorage, getGw
from ...yepcord.enums import GuildPermissions, MessageType, ChannelType, WebhookType, GUILD_CHANNELS
from ...yepcord.errors import InvalidDataErr, Errors
from ...yepcord.models import User, Channel, Message, ReadState, Emoji, PermissionOverwrite, Webhook, ThreadMember, \
    ThreadMetadata, AuditLogEntry, Relationship
from ...yepcord.models.applications import Application
from ...yepcord.snowflake import Snowflake
from ...yepcord.utils import getImage, b64encode

# Base path is /api/vX/applications
teams = Blueprint('teams', __name__)


@teams.get("/", strict_slashes=False)
@getUser
async def get_channel(user: User):
    return []
