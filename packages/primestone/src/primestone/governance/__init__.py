"""Brand Intelligence et gouvernance éditoriale (phase 20, ADR-0027)."""

from primestone.governance.service import (
    FOUNDER,
    GovernanceError,
    GovernanceService,
    Handler,
    register_handler,
)

__all__ = ["FOUNDER", "GovernanceError", "GovernanceService", "Handler", "register_handler"]
