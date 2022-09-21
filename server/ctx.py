from contextvars import ContextVar, copy_context


class _Ctx:
    _CTX = ContextVar("ctx")
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(_Ctx, cls).__new__(cls)
        return cls._instance

    def get(self, item, default=None):
        self._init()
        return self.__class__._CTX.get().get(item, default)

    def set(self, key, value):
        self._init()
        self.__class__._CTX.get()[key] = value

    def _init(self):
        v = self.__class__._CTX
        if v not in copy_context():
            v.set({})
        return self

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.set(key, value)

Ctx = _Ctx()