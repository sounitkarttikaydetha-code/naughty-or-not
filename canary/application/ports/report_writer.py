"""
Report Writer Port.
Defines contracts for producing PDF dossiers and Excel spreadsheets.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class ReportWriterPort(ABC):
    """Port for rendering compliance artifacts."""

    @abstractmethod
    def generate_pdf_report(self, data: Dict[str, Any]) -> bytes:
        """Render formal PDF audit report with mandatory Canary banner & footer."""
        pass

    @abstractmethod
    def generate_excel_report(self, data: Dict[str, Any]) -> bytes:
        """Render full Excel audit spreadsheet with mandatory Canary banner."""
        pass
