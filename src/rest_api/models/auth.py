from pydantic import BaseModel


class Register(BaseModel):
    username: str
    email: str
    password: str
    date_of_birth: str = "2000-01-01"


class Login(BaseModel):
    login: str
    password: str


class MfaLogin(BaseModel):
    ticket: str
    code: str


class ViewBackupCodes(BaseModel):
    password: str


class VerifyEmail(BaseModel):
    token: str
