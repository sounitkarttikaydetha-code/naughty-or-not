"""
Report Generation Use Case.
Renders PDF or Excel compliance reports with mandatory Canary notice.
"""
from typing import Any, Dict

from canary.application.identity.permissions import require_permission, Action
from canary.application.ports.idp import UserContext
from canary.application.ports.report_writer import ReportWriterPort

CANARY_NOTICE = "Canary build — for evaluation only. Not for screening decisions."


class ReportsUseCase:
    def __init__(self, report_writer: ReportWriterPort):
        self.report_writer = report_writer

    def generate_pdf(self, report_data: Dict[str, Any], user: UserContext) -> bytes:
        """Generate PDF dossier with mandatory Canary header/footer."""
        require_permission(user, Action.GENERATE_REPORTS)
        data = dict(report_data)
        data["canary_banner"] = CANARY_NOTICE
        data["generated_by"] = user.display_name or user.user_id
        return self.report_writer.generate_pdf_report(data)

    def generate_excel(self, report_data: Dict[str, Any], user: UserContext) -> bytes:
        """Generate Excel workbook with mandatory Canary banner."""
        require_permission(user, Action.GENERATE_REPORTS)
        data = dict(report_data)
        data["canary_banner"] = CANARY_NOTICE
        data["generated_by"] = user.display_name or user.user_id
        return self.report_writer.generate_excel_report(data)
