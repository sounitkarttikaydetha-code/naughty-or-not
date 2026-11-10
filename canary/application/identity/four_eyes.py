"""
Four-Eyes Principle Enforcement Layer.
Rule: A preparer cannot review, approve, or close their own check.
"""


class FourEyesViolationError(Exception):
    """Raised when an actor attempts to review or approve their own submission."""
    pass


def enforce_four_eyes_rule(preparer_id: str, reviewer_id: str) -> None:
    """
    Assert that the reviewer is distinct from the preparer.
    Case-insensitive normalized comparison on user identifiers.
    """
    if not preparer_id or not reviewer_id:
        raise FourEyesViolationError("Both preparer identity and reviewer identity are required for review.")

    prep_clean = preparer_id.strip().lower()
    rev_clean = reviewer_id.strip().lower()

    if prep_clean == rev_clean:
        raise FourEyesViolationError(
            f"Four-eyes violation: Preparer '{preparer_id}' cannot review, approve, or close their own check. "
            f"A distinct authorized Reviewer or Compliance officer must perform this review."
        )
