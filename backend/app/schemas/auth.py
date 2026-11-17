from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    # The token is validated by lookup, not by shape - the bounds exist only to
    # cap request size. A malformed or unknown token gets the same generic 400
    # as an expired one, so nothing about token format is revealed.
    token: str = Field(min_length=1, max_length=256)
    # NOTE: the project has no pre-existing password policy (UserCreate.password
    # is an unconstrained str), so there was nothing to reuse. A reset must not
    # be able to set an empty/trivial password, hence these bounds; the upper
    # bound also stops a huge input from being fed to Argon2. Registration is
    # deliberately NOT changed here - see docs/decisions/0005-password-reset.md.
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    # Validated by lookup, not shape; bounds only cap request size. Unknown,
    # expired and used tokens all get the same generic 400.
    token: str = Field(min_length=1, max_length=256)


class ResendVerificationRequest(BaseModel):
    email: EmailStr
