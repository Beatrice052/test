"""Analysis plan and phase routing labels."""

from typing import Literal

type AnalysisRoute = Literal["clarify", "unanswerable", "repair", "resolve"]


def route_after_validation(route: AnalysisRoute) -> str:
    return route
