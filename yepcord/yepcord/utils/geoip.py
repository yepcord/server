import os
from typing import Optional

import maxminddb


class GeoIp:
    COUNTRY_TO_LANG = {
        "UA": "uk", "US": "en-US", "BG": "bg", "CZ": "cs", "DK": "da", "DE": "de", "GR": "el", "GB": "en-GB",
        "ES": "es-ES", "FI": "fi", "FR": "fr", "IN": "hi", "HR": "hr", "HU": "hu", "IT": "it", "JP": "ja",
        "KR": "ko", "LT": "lt", "NL": "nl", "NO": "no", "PL": "pl", "BR": "pt-BR", "RO": "ro", "RU": "RU",
        "SE": "sv-SE", "TH": "th", "TR": "tr", "VN": "vi", "CN": "zh-CN", "TW": "zh-TW",
    }
    IP_DATABASE: Optional[maxminddb.Reader] = None

    @classmethod
    def get_language_code(cls, ip: str, default: str = "en-US") -> str:
        if cls.IP_DATABASE is None and not os.path.exists("other/ip_database.mmdb"):
            return default

        if cls.IP_DATABASE is None:
            cls.IP_DATABASE = maxminddb.open_database("other/ip_database.mmdb")

        try:
            country_code = cls.IP_DATABASE.get(ip)
            country_code = country_code["country"]["iso_code"] if country_code is not None else default
        except (ValueError, KeyError):
            return default

        return cls.COUNTRY_TO_LANG.get(country_code, default)
