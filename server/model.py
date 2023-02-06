from copy import deepcopy
from dataclasses import dataclass, field as _field
from typing import Optional, Any, get_type_hints

from schema import Schema, Use, Optional as sOptional

from server.utils import result_to_json

_DEFAULT_META = {"excluded": False, "nullable": False, "db_name": None, "default": None, "validation": None,
                 "id_field": False, "private": False}


@dataclass
class Field:
    name: str
    type: type
    excluded: bool = False
    nullable: bool = False
    db_name: Optional[str] = None
    default: Optional[Any] = None


class Model:
    __model_fields__ = {}
    __schema__ = None
    __id_field__ = None

    # Default __post_init__, checks all fields, deletes field if it's None and not nullable
    def __post_init__(self) -> None:
        for field in self.__model_fields__["all"]:
            if getattr(self, field.name, 0) is None and not field.nullable:
                if field.name in self.__dict__: delattr(self, field.name)

    def toJSON(self, for_db=True, with_private=True):
        schema = self.__schema__
        json = deepcopy(self.__dict__)
        if self.__id_field__ and self.__id_field__.name not in json:
            schema = schema.schema.copy()
            del schema[self.__id_field__]
            schema = Schema(schema)
        json = schema.validate(json)
        if not with_private:
            for pfield in self.__model_fields__["private_names"]:
                if pfield in json:
                    del json[pfield]
        if for_db:
            for field in self.__model_fields__["all"]:
                if field.name in self.__model_fields__["excluded_names"]:
                    if field.name in json:
                        del json[field.name]
                    continue
                if field.db_name is not None and field.name in json:
                    json[field.db_name] = json[field.name]
                    del json[field.name]
        return json

    @property
    async def json(self) -> dict:
        raise NotImplemented(f"Converter method for {self.__class__.__name__} is not defined!")

    def set(self, **kwargs):
        for k, v in kwargs.items():
            if k not in list(self.__dataclass_fields__):
                continue
            setattr(self, k, v)
        return self

    def get(self, item, default=None):
        if not hasattr(self, item):
            return default
        return getattr(self, item)

    def copy(self, **kwargs):
        return deepcopy(self).set(**kwargs)

    def getDiff(self, other) -> dict:
        this = self.toJSON()
        other = other.toJSON()
        diff = {}
        for k, v in this.items():
            if (l := other.get(k, v)) != this[k]:
                diff[k] = l
            if k in other:
                del other[k]
        diff.update(other)
        return diff


def _fromResult(cls, desc, result):
    desc = list(desc)
    fields = {field.db_name: field for field in cls.__model_fields__["all"] if field.db_name is not None and not field.excluded}
    for idx, field in enumerate(desc):
        field = field[0]
        if field in fields and not field.startswith("j_"):
            desc[idx] = (fields[field].name,)
    return cls(**result_to_json(desc, result))


def model(cls):
    cls.toJSON = Model.toJSON
    cls.to_json = Model.toJSON  # for backward compatibility, will be removed
    cls.fromResult = classmethod(_fromResult)
    cls.from_result = classmethod(_fromResult)  # for backward compatibility, will be removed
    cls.get = Model.get
    cls.set = Model.set
    cls.copy = Model.copy
    cls.getDiff = Model.getDiff
    cls.get_diff = Model.getDiff  # for backward compatibility, will be removed
    cls.__model_fields__ = {"all": [], "not_excluded": [], "excluded_names": [], "private_names": []}
    cls.__id_field__ = None
    schema = {}
    type_hints = get_type_hints(cls)
    for name, field in cls.__dataclass_fields__.items():
        if field.name in cls.__model_fields__["all"]:
            continue
        meta = field.metadata or _DEFAULT_META
        _type = type_hints[field.name]
        opt = _type == Optional[_type]
        _type = _type.__args__[0] if opt else _type
        s_name = sOptional(field.name) if opt else field.name
        schema[s_name] = Use(_type) if meta["validation"] is None else meta["validation"]
        _field = Field(field.name, _type, meta["excluded"], meta["nullable"], meta["db_name"], meta["default"])
        cls.__model_fields__["all"].append(_field)
        if not _field.excluded:
            cls.__model_fields__["not_excluded"].append(_field)
        else:
            cls.__model_fields__["excluded_names"].append(_field.name)
        if meta["private"]:
            cls.__model_fields__["private_names"].append(_field.name)
        if meta["id_field"]: cls.__id_field__ = _field
    cls.__schema__ = Schema(schema)
    return cls


def field(excluded=False, nullable=False, id_field=False, db_name=None, validation=None, private=False, *args, **kwargs) -> Any:
    default = kwargs["default"] if "default" in kwargs else None
    metadata = {
        "excluded": bool(excluded),
        "nullable": bool(nullable),
        "db_name": db_name,
        "default": default,
        "validation": validation,
        "id_field": bool(id_field),
        "private": bool(private),
    }
    return _field(*args, metadata=metadata, **kwargs)