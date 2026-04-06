# Week 3 Progress: Consent Management (Days 15-16)

**Status:** ✅ COMPLETE  
**Duration:** Days 15-16 (2 days)  
**Completion Date:** Day 16

## Completed Tasks

### ✅ Day 15: Consent Management System

**Files Created:**
- `cortex/consent.py` (700+ lines)
- `cortex/consent_routes.py` (600+ lines)

**What was implemented:**

**Core Consent Features:**
- Consent creation and tracking
- Consent versioning and history
- Consent revocation workflow
- Expiration handling (auto-expire after set days)
- Authorization verification
- Template management

**Consent Types Supported:**
- Treatment consent (365-day default expiry)
- Research participation (730-day expiry)
- Data sharing with third parties (180-day expiry)
- AI agent processing (365-day expiry)
- Electronic communication
- Marketing

**Consent Lifecycle:**
1. **Create** - Patient grants/denies consent
2. **Track** - Store in encrypted format with expiry date
3. **Verify** - Check consent before processing data
4. **Revoke** - Patient can revoke at any time
5. **Expire** - Auto-expire based on consent type

**Consent Statuses:**
- `ACTIVE` - Valid consent
- `EXPIRED` - Past expiration date
- `REVOKED` - Patient revoked consent
- `PENDING` - Awaiting approval
- `SUSPENDED` - Temporarily suspended

**Default Templates:**
4 pre-built consent form templates:
- Treatment Consent
- Research Participation
- Data Sharing
- AI Agent Processing

### ✅ Day 16: Consent API Endpoints

**API Endpoints (10 endpoints):**

1. **POST /consent** - Create new consent
2. **GET /consent/{id}** - Get consent by ID
3. **GET /consent/patient/{id}** - Get all consents for patient
4. **POST /consent/{id}/revoke** - Revoke a consent
5. **POST /consent/verify** - Verify authorization
6. **GET /consent/expiring** - Get expiring consents
7. **POST /consent/template/generate** - Generate consent form
8. **GET /consent/templates** - List available templates

**Permission Requirements:**
- `consent:create` - Create consent
- `consent:read` - Read consent
- `consent:revoke` - Revoke consent
- `phi_access` - Access patient PHI
- `audit_read` - View expiring consents

**HIPAA Compliance:**
- ✅ All consent changes logged in audit trail
- ✅ Consent forms stored encrypted (AES-256-GCM)
- ✅ Revocation documented with reason
- ✅ Expiration tracking
- ✅ Authorization verification required

### ✅ Testing

**File Created:** `tests/test_consent.py` (350+ lines)

**Tests Implemented:**
- Consent creation (granted/denied)
- Consent retrieval
- Consent revocation
- Consent validation (active/expired/revoked)
- Consent status checking
- Template generation
- Expiring consents query
- Patient consent history
- Authorization verification

**Test Coverage:** 30+ test cases

### ✅ RBAC Integration

**Updated:** `cortex/security/rbac.py`

**New Permissions Added:**
- `consent:create` - Create consent records
- `consent:revoke` - Revoke consent

**Role Permissions Updated:**
- **Admin:** All consent permissions
- **Clinician:** Create, read, write, revoke consent
- **Researcher:** Read consent (anonymized only)
- **Auditor:** Read consent for audit

## Technical Specifications

**Consent Model:**
```python
ConsentRecord:
  - id: UUID
  - patient_id: UUID (FK)
  - consent_type: Enum
  - consented: bool
  - consent_date: datetime
  - expiry_date: datetime (optional)
  - consent_form_encrypted: text
  - obtained_by: UUID (FK → User)
  - notes: text
  - created_at: datetime
  - updated_at: datetime
```

**Consent Manager Features:**
- `create_consent()` - Create new consent
- `get_consent()` - Retrieve by ID
- `get_patient_consents()` - All consents for patient
- `revoke_consent()` - Revoke with reason
- `check_consent()` - Verify valid consent exists
- `verify_authorization()` - Check user can access PHI
- `get_expiring_consents()` - List expiring soon
- `generate_consent_form()` - Create from template

**Template System:**
```python
# Generate consent form
form = manager.generate_consent_form(
    category=ConsentCategory.TREATMENT,
    patient_data={
        "patient_name": "John Doe",
        "expiration_date": "2025-12-31"
    }
)
```

**Authorization Flow:**
```python
# Before accessing PHI
result = manager.verify_authorization(
    patient_id=patient.id,
    user=current_user,
    consent_types=[ConsentType.TREATMENT]
)

if result["authorized"]:
    # Proceed with PHI access
else:
    # Missing consents: result["missing_consents"]
```

## Example Usage

### Create Consent
```python
consent_id = manager.create_consent(
    patient_id=patient.id,
    consent_type=ConsentType.TREATMENT,
    consented=True,
    obtained_by=user.id,
    consent_form=generated_form,
    expiry_days=365
)
```

### Generate Template
```python
form = manager.generate_consent_form(
    category=ConsentCategory.AGENT_PROCESSING,
    patient_data={
        "patient_name": "John Smith",
        "ai_system_name": "Cortex AI",
        "ai_capabilities": "Diagnosis support, treatment recommendations"
    }
)
```

### Verify Authorization
```python
result = manager.verify_authorization(
    patient_id=patient.id,
    user=current_user,
    consent_types=[ConsentType.TREATMENT, ConsentType.AGENT_PROCESSING]
)

if not result["authorized"]:
    print(f"Missing: {result['missing_consents']}")
```

## Integration Points

**With Audit System:**
```python
# Every consent action logged
log_audit(
    action=AuditAction.CONSENT_GRANTED,
    patient_id=patient.id,
    user_id=user.id,
    details={"consent_type": "treatment"}
)
```

**With PHI Detection:**
```python
# Check consent before processing PHI
if not check_patient_consent(patient.id, ConsentType.AGENT_PROCESSING):
    raise HTTPException(403, "Missing consent for AI processing")
```

**With Encryption:**
```python
# Consent forms encrypted at rest
encrypted = encryption.encrypt(consent_form)
consent.consent_form_encrypted = encrypted["ciphertext"]
```

## Performance Considerations

**Database Indexes:**
- `idx_consent_patient` - Patient ID + consent date
- `idx_consent_type` - Consent type
- `idx_consent_expiry` - Expiry date

**Query Optimization:**
- Active consents filtered in-memory (fast for typical patient counts)
- Expiring consents indexed query
- Patient consent history ordered by date

**Caching Opportunities:**
- Consent status can be cached (5-minute TTL)
- Template forms can be cached
- Authorization results can be cached per user session

## Next Steps: Days 17-18

**Document Management:**
- Encrypted document storage
- Document versioning
- Document access logging
- Multi-format support (PDF, images)
- Retention policies

**Document Features:**
- Upload with consent verification
- Version history tracking
- Access control (patient/user based)
- Secure download
- Automatic retention enforcement

## Files Modified/Created

### Created Files (3):
1. `cortex/consent.py` - Consent management core (700+ lines)
2. `cortex/consent_routes.py` - API endpoints (600+ lines)
3. `tests/test_consent.py` - Test suite (350+ lines)

### Modified Files (1):
1. `cortex/security/rbac.py` - Added consent permissions

## Metrics

**Lines of Code:** ~1,650 lines
**Test Cases:** 30+
**API Endpoints:** 8
**Consent Types:** 6
**Templates:** 4

## HIPAA Compliance Checklist

✅ **Consent Documentation**
- Written consent forms
- Electronic signatures (template support)
- Version control
- Revocation process

✅ **Access Controls**
- Consent verification before data access
- Role-based permissions
- Audit trail for all changes

✅ **Patient Rights**
- Right to grant consent
- Right to revoke consent
- Right to access consent records
- Clear expiration dates

✅ **Data Security**
- Encrypted storage (AES-256-GCM)
- Audit logging
- Access logging

---

Week 3 Days 15-16 complete! Consent management system is fully implemented with comprehensive testing. Ready for document management on Days 17-18.