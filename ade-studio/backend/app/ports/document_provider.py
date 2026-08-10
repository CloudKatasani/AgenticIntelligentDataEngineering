"""The port every file source implements.

Deliberately three methods. A provider lists, fetches, and reports whether it
can be reached — the same shape as ``SourceConnector``, so a SharePoint library
and a Snowflake schema are equally ordinary from the run engine's point of view.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.document import DocumentContent, DocumentRef, DocumentSpace


class DocumentProvider(ABC):
    kind_label: str = "files"

    def __init__(self, space: DocumentSpace) -> None:
        self.space = space

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """Whether this provider can run, and why not when it cannot.

        Returns a reason rather than raising, so the UI can show a source as
        configured-but-unreachable instead of failing at run time. The database
        connectors report their driver status the same way.
        """

    @abstractmethod
    def list(self, path: str = "") -> list[DocumentRef]:
        """Folders and files directly under ``path``."""

    @abstractmethod
    def fetch(self, ref_id: str) -> DocumentContent:
        """The bytes of one file."""

    def search(self, query: str) -> list[DocumentRef]:
        """Best-effort name search. Providers that cannot search return nothing."""
        return []
