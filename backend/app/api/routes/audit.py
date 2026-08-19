"""Read-only audit history and aggregate metrics endpoints."""

from fastapi import APIRouter, Depends, Query

from app.schemas.audit import AuditPageResponse, MetricsResponse
from app.services.audit import AuditRepository, get_audit_repository

router = APIRouter(tags=["audit"])


@router.get(
    "/audit",
    response_model=AuditPageResponse,
    summary="List recent WAF audit events",
)
def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repository: AuditRepository = Depends(get_audit_repository),
) -> AuditPageResponse:
    events, total = repository.list_events(
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return AuditPageResponse(
        items=events,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Return aggregate WAF decision counts",
)
def get_metrics(
    repository: AuditRepository = Depends(get_audit_repository),
) -> MetricsResponse:
    return MetricsResponse(**repository.metrics())
