from pydantic import BaseModel


class GetInviteQuery(BaseModel):
    with_counts: bool = False

    def __init__(self, **data):
        if "with_counts" in data:
            data["with_counts"] = data["with_counts"].lower() == "true"
        super().__init__(**data)
