class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(cls.__class__, cls).__new__(cls)
        return cls._instance

    @classmethod
    def getInstance(cls):
        return cls._instance