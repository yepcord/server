from pydantic import BaseModel


class UserProfileQuery(BaseModel):
    with_mutual_guilds: bool = False
    mutual_friends_count: bool = False
    guild_id: int = 0

    def __init__(self, **data):
        for arg in ("with_mutual_guilds", "mutual_friends_count"):
            if arg in data:
                data[arg] = data[arg].lower() == "true"
        super().__init__(**data)