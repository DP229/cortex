"""
Cortex Test Records API - Verification Test Management

EN 50128 Table A.3 verification test records:
- Create, read, update verification test records
- Link tests to requirements they verify
- Record test execution results
- Track verification status per requirement
- Support unit, integration, system, and acceptance test types

All endpoints require authentication and appropriate permissions.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from pydantic import BaseModel, Field
import structlog

from cortex.auth_routes import get_current_active_user_from_request
from cortex.security.rbac import Permission, ROLE_PERMISSIONS
from cortex.models import User, TestRecord, Requirement, VerificationStatus
from cortex.audit import log_audit, AuditAction
from cortex.database import get_database_manager

logger = structlog.get_logger()
router = APIRouter(prefix="/test-records", tags=["Verification Test Records"])


# === Pydantic Models ===

class TestRecordCreateRequest(BaseModel):
    """Create a verification test record"""
    test_id: str = Field(..., description="Unique test ID, e.g. TEST-SIG-001-01")
    requirement_id: str = Field(..., description="UUID of the requirement this test verifies")
    test_type: str = Field(..., description="unit_test, integration_test, system_test, acceptance_test")
    test_description: str = Field(..., description="What this test verifies")
    expected_results: Optional[str] = None
    test_environment: Optional[str] = Field(default=None, description="Platform, configuration")


class TestRecordExecuteRequest(BaseModel):
    """Record test execution results"""
    test_results: str = Field(..., description="Actual test output/results")
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    status: str = Field(..., description="passed, failed, blocked, pending")
    test_artifacts: Optional[List[str]] = Field(default=None, description="Paths to logs, screenshots")


class TestRecordUpdateRequest(BaseModel):
    """Update a test record"""
    test_description: Optional[str] = None
    expected_results: Optional[str] = None
    test_environment: Optional[str] = None
    test_artifacts: Optional[List[str]] = None


class TestRecordResponse(BaseModel):
    id: str
    test_id: str
    requirement_id: str
    test_type: str
    test_description: str
    test_results: Optional[str]
    expected_results: Optional[str]
    status: str
    executed_by: Optional[str]
    executed_at: Optional[str]
    test_environment: Optional[str]
    test_artifacts: Optional[List[str]]
    passed_count: int
    failed_count: int
    blocked_count: int
    is_closed: bool
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class RequirementVerificationStatus(BaseModel):
    """Summary of verification status for a requirement"""
    requirement_id: str
    verification_status: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pending_tests: int
    blocked_tests: int


# === Helpers ===

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_permission(user: User, permission: Permission) -> None:
    user_perms = ROLE_PERMISSIONS.get(user.role, set())
    perm_values = {p.value for p in user_perms}
    if permission.value not in perm_values and "*" not in perm_values:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission.value}' required",
        )


def _test_to_response(t: TestRecord) -> TestRecordResponse:
    return TestRecordResponse(
        id=str(t.id),
        test_id=str(t.test_id),
        requirement_id=str(t.requirement_id),
        test_type=str(t.test_type),
        test_description=t.test_description,
        test_results=t.test_results,
        expected_results=t.expected_results,
        status=str(t.status),
        executed_by=str(t.executed_by) if t.executed_by else None,
        executed_at=t.executed_at.isoformat() if t.executed_at else None,
        test_environment=t.test_environment,
        test_artifacts=t.test_artifacts,
        passed_count=t.passed_count,
        failed_count=t.failed_count,
        blocked_count=t.blocked_count,
        is_closed=t.is_closed,
        created_at=t.created_at.isoformat() if t.created_at else None,
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
    )


# === Endpoints ===

@router.post("/", response_model=TestRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_test_record(
    req: TestRecordCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Create a verification test record linked to a requirement.

    **Requires:** `test_record:write` permission

    **EN 50128:** Each requirement must have at least one corresponding
    verification test record (Table A.3).
    """
    require_permission(current_user, Permission.TEST_RECORD_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        # Verify requirement exists
        requirement = session.query(Requirement).filter(
            Requirement.id == req.requirement_id
        ).first()
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{req.requirement_id}' not found",
            )

        # Check for duplicate test_id
        existing = session.query(TestRecord).filter(
            TestRecord.test_id == req.test_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Test ID '{req.test_id}' already exists",
            )

        test_record = TestRecord(
            test_id=req.test_id,
            requirement_id=req.requirement_id,
            test_type=req.test_type,
            test_description=req.test_description,
            expected_results=req.expected_results,
            test_environment=req.test_environment,
            status=VerificationStatus.PENDING.value,
            passed_count=0,
            failed_count=0,
            blocked_count=0,
            is_closed=False,
        )
        session.add(test_record)
        session.commit()
        session.refresh(test_record)
        response = _test_to_response(test_record)

    log_audit(
        action=AuditAction.TEST_RECORD_CREATE.value,
        user_id=current_user.id,
        resource_type="test_record",
        resource_id=response.id,
        ip_address=get_client_ip(request),
        details={
            "test_id": req.test_id,
            "requirement_id": req.requirement_id,
            "test_type": req.test_type,
        },
    )

    return response


@router.get("/", response_model=List[TestRecordResponse])
async def list_test_records(
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
    test_id: Optional[str] = Query(default=None, description="Filter by test ID prefix"),
    requirement_id: Optional[str] = Query(default=None, description="Filter by requirement UUID"),
    test_type: Optional[str] = Query(default=None, description="Filter by test type"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    executed_by: Optional[str] = Query(default=None, description="Filter by executor UUID"),
    is_closed: Optional[bool] = Query(default=None, description="Filter by closed status"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    List verification test records with optional filters.

    **Requires:** `test_record:read` permission
    """
    require_permission(current_user, Permission.TEST_RECORD_READ)

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(TestRecord)

        if test_id:
            query = query.filter(TestRecord.test_id.ilike(f"{test_id}%"))
        if requirement_id:
            query = query.filter(TestRecord.requirement_id == requirement_id)
        if test_type:
            query = query.filter(TestRecord.test_type == test_type)
        if status_filter:
            query = query.filter(TestRecord.status == status_filter)
        if executed_by:
            query = query.filter(TestRecord.executed_by == executed_by)
        if is_closed is not None:
            query = query.filter(TestRecord.is_closed == is_closed)

        results = query.order_by(TestRecord.test_id).offset(offset).limit(limit).all()
        response = [_test_to_response(t) for t in results]

    return response


@router.get("/{test_uuid}", response_model=TestRecordResponse)
async def get_test_record(
    test_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get a test record by UUID.

    **Requires:** `test_record:read` permission
    """
    require_permission(current_user, Permission.TEST_RECORD_READ)

    db = get_database_manager()
    with db.get_session() as session:
        test_record = session.query(TestRecord).filter(
            TestRecord.id == test_uuid
        ).first()

        if not test_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test record '{test_uuid}' not found",
            )
        response = _test_to_response(test_record)

    return response


@router.patch("/{test_uuid}", response_model=TestRecordResponse)
async def update_test_record(
    test_uuid: str,
    update: TestRecordUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Update a test record (before execution).

    **Requires:** `test_record:write` permission

    **EN 50128:** Test records cannot be modified after execution without
    documented change control.
    """
    require_permission(current_user, Permission.TEST_RECORD_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        test_record = session.query(TestRecord).filter(
            TestRecord.id == test_uuid
        ).first()

        if not test_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test record '{test_uuid}' not found",
            )

        # Cannot modify executed test record
        if test_record.executed_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify an executed test record. Create a new version.",
            )

        if update.test_description is not None:
            test_record.test_description = update.test_description
        if update.expected_results is not None:
            test_record.expected_results = update.expected_results
        if update.test_environment is not None:
            test_record.test_environment = update.test_environment
        if update.test_artifacts is not None:
            test_record.test_artifacts = update.test_artifacts

        session.commit()
        session.refresh(test_record)
        response = _test_to_response(test_record)

    log_audit(
        action=AuditAction.TEST_RECORD_UPDATE.value,
        user_id=current_user.id,
        resource_type="test_record",
        resource_id=test_uuid,
        ip_address=get_client_ip(request),
        details={"updated_fields": update.model_dump(exclude_none=True)},
    )

    return response


@router.post("/{test_uuid}/execute", response_model=TestRecordResponse)
async def execute_test_record(
    test_uuid: str,
    execution: TestRecordExecuteRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Record test execution results and update requirement verification status.

    **Requires:** `test_record:write` permission

    **EN 50128:** Test execution must be documented with actual results.
    Requirement verification_status is updated based on all linked tests:
    - All tests passed → verified
    - Any test failed → failed
    - All pending/blocked → pending
    """
    require_permission(current_user, Permission.TEST_RECORD_WRITE)

    db = get_database_manager()
    with db.get_session() as session:
        test_record = session.query(TestRecord).filter(
            TestRecord.id == test_uuid
        ).first()

        if not test_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test record '{test_uuid}' not found",
            )

        if test_record.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute a closed test record",
            )

        # Record execution
        test_record.test_results = execution.test_results
        test_record.passed_count = execution.passed_count
        test_record.failed_count = execution.failed_count
        test_record.blocked_count = execution.blocked_count
        test_record.status = execution.status
        test_record.test_artifacts = execution.test_artifacts
        test_record.executed_by = current_user.id
        test_record.executed_at = datetime.utcnow()
        test_record.is_closed = True

        session.commit()
        session.refresh(test_record)

        # Update requirement verification_status based on all linked tests
        all_tests = session.query(TestRecord).filter(
            TestRecord.requirement_id == test_record.requirement_id
        ).all()

        if all_tests:
            statuses = [t.status for t in all_tests]
            if all(s == VerificationStatus.PASSED.value for s in statuses):
                new_verification_status = VerificationStatus.PASSED.value
            elif any(s == VerificationStatus.FAILED.value for s in statuses):
                new_verification_status = VerificationStatus.FAILED.value
            elif all(s in (VerificationStatus.PENDING.value, VerificationStatus.BLOCKED.value) for s in statuses):
                new_verification_status = VerificationStatus.PENDING.value
            else:
                new_verification_status = VerificationStatus.PENDING.value

            requirement = session.query(Requirement).filter(
                Requirement.id == test_record.requirement_id
            ).first()
            if requirement:
                requirement.verification_status = new_verification_status
                session.commit()

            response = _test_to_response(test_record)

    log_audit(
        action=AuditAction.TEST_EXECUTE.value,
        user_id=current_user.id,
        resource_type="test_record",
        resource_id=test_uuid,
        ip_address=get_client_ip(request),
        details={
            "test_id": response.test_id,
            "status": execution.status,
            "passed": execution.passed_count,
            "failed": execution.failed_count,
        },
    )

    return response


@router.get("/requirement/{requirement_uuid}/verification-status", response_model=RequirementVerificationStatus)
async def get_requirement_verification_status(
    requirement_uuid: str,
    request: Request,
    current_user: User = Depends(get_current_active_user_from_request),
):
    """
    Get verification status summary for a requirement.

    **Requires:** `test_record:read` permission

    Returns the requirement's verification_status and a breakdown of
    all linked test records by status.
    """
    require_permission(current_user, Permission.TEST_RECORD_READ)

    db = get_database_manager()
    with db.get_session() as session:
        requirement = session.query(Requirement).filter(
            Requirement.id == requirement_uuid
        ).first()

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_uuid}' not found",
            )

        tests = session.query(TestRecord).filter(
            TestRecord.requirement_id == requirement_uuid
        ).all()

        passed = sum(1 for t in tests if t.status == VerificationStatus.PASSED.value)
        failed = sum(1 for t in tests if t.status == VerificationStatus.FAILED.value)
        pending = sum(1 for t in tests if t.status == VerificationStatus.PENDING.value)
        blocked = sum(1 for t in tests if t.status == VerificationStatus.BLOCKED.value)

        response = RequirementVerificationStatus(
            requirement_id=str(requirement.id),
            verification_status=str(requirement.verification_status),
            total_tests=len(tests),
            passed_tests=passed,
            failed_tests=failed,
            pending_tests=pending,
            blocked_tests=blocked,
        )

    return response
