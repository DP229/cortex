"""
Cortex Market - Phase 5 Deployment Materials

Market positioning and AI Planning documentation generation:
- AIDL Document Generator for IEC 62304 Annex E
- Market positioning for 2026 regulatory shift
- Bangalore pilot program materials
"""

from cortex.market.aidl_annex_generator import (
    AIDLDocument,
    AIDLGenerator,
    AIDLDocumentExporter,
    AIDLPhase,
    RiskLevel,
    create_aidl_document,
)

from cortex.market.positioning import (
    MarketPositioning,
    BangalorePilotProgram,
    generate_positioning_document,
)

__all__ = [
    # AIDL
    "AIDLDocument",
    "AIDLGenerator",
    "AIDLDocumentExporter",
    "AIDLPhase",
    "RiskLevel",
    "create_aidl_document",
    # Positioning
    "MarketPositioning",
    "BangalorePilotProgram",
    "generate_positioning_document",
]