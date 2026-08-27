from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LinkedInCredentials:
    """Credentials required by LinkedIn MCP tools."""

    access_token: str
    person_urn: str


class CredentialError(RuntimeError):
    """Safe credential-loading failure that never includes secret values."""


@runtime_checkable
class CredentialProvider(Protocol):
    """Provider interface for retrieving LinkedIn runtime credentials.

    Production secret stores can implement this protocol without requiring any
    changes to the MCP tools.
    """

    def get_credentials(self) -> LinkedInCredentials:
        """Return the credentials needed for LinkedIn API operations."""


class FileCredentialProvider:
    """Load LinkedIn credentials from local files.

    This provider preserves the project's existing local-development workflow.
    Secret values are stripped before use and are never included in exceptions.
    """

    def __init__(self, access_token_file: Path, person_urn_file: Path) -> None:
        self.access_token_file = access_token_file
        self.person_urn_file = person_urn_file

    @staticmethod
    def _read_secret(path: Path, *, label: str) -> str:
        if not path.exists():
            raise CredentialError(f"Missing {label} credential file.")
        if not path.is_file():
            raise CredentialError(f"The {label} credential path is not a file.")

        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CredentialError(f"Could not read the {label} credential file.") from exc

        if not value:
            raise CredentialError(f"The {label} credential file is empty.")
        return value

    def get_credentials(self) -> LinkedInCredentials:
        access_token = self._read_secret(
            self.access_token_file,
            label="LinkedIn access token",
        )
        person_urn = self._read_secret(
            self.person_urn_file,
            label="LinkedIn person URN",
        )
        return LinkedInCredentials(
            access_token=access_token,
            person_urn=person_urn,
        )
