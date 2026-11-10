"""
Role Definitions for Clearance Check Canary.
5 Enterprise Roles:
- Screener: Screens entities, submits cases
- Reviewer: Screens, reviews and approves cases (cannot review own cases)
- Compliance: Full compliance review, dispositioning, report exports
- Administrator: Configuration, source refreshes, metrics
- Auditor: Read-only access across all records, cannot screen or mutate
"""
from enum import Enum


class Role(str, Enum):
    SCREENER = "Screener"
    REVIEWER = "Reviewer"
    COMPLIANCE = "Compliance"
    ADMINISTRATOR = "Administrator"
    AUDITOR = "Auditor"  # Read-only
