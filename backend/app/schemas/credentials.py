"""Credential rules shared by registration and profile updates."""
from typing import Annotated
from pydantic import AfterValidator, Field

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
Username = Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$"),
                     AfterValidator(str.lower)]
Password = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
