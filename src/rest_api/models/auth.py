from dataclasses import dataclass


@dataclass
class Register:
    username: str
    email: str
    password: str
    date_of_birth: str = "2000-01-01"


@dataclass
class Login:
    login: str
    password: str


@dataclass
class MfaLogin:
    ticket: str
    code: str


@dataclass
class ViewBackupCodes:
    password: str


@dataclass
class VerifyEmail:
    token: str
