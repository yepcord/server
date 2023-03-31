from pydantic import BaseModel, validator

ALLOWED_IMAGE_SIZES = [16, 20, 22, 24, 28, 32, 40, 44, 48, 56, 60, 64, 80, 96, 100, 128, 160, 240, 256, 300, 320, 480,
                        512, 600, 640, 1024, 1280, 1536, 2048, 3072, 4096]


# noinspection PyMethodParameters
class CdnImageSizeQuery(BaseModel):
    size: int = 128

    @validator("size")
    def validate_size(cls, value: int):
        if value is not None:
            if value not in ALLOWED_IMAGE_SIZES:
                value = min(ALLOWED_IMAGE_SIZES, key=lambda x: abs(x - value))  # Take closest
        return value