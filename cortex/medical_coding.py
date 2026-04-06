"""
Cortex Medical Coding - ICD-10 and CPT Code Management

This module provides medical coding functionality:
- ICD-10 diagnosis code search
- CPT procedure code search
- Code mapping and validation
- Billing code suggestions
- Code hierarchy navigation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum
import re
import structlog

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_

from cortex.database import get_database_manager, get_db_session
from cortex.models import ICD10Code, CPTCode, CodeMapping

logger = structlog.get_logger()


class CodeType(str, Enum):
    """Medical code types"""
    ICD10 = "icd10"
    CPT = "cpt"


class ICD10Chapter(str, Enum):
    """ICD-10 chapters"""
    INFECTIOUS = "Certain infectious and parasitic diseases"
    NEOPLASMS = "Neoplasms"
    BLOOD = "Diseases of the blood and blood-forming organs"
    ENDOCRINE = "Endocrine, nutritional and metabolic diseases"
    MENTAL = "Mental and behavioral disorders"
    NERVOUS = "Diseases of the nervous system"
    EYE = "Diseases of the eye and adnexa"
    EAR = "Diseases of the ear and mastoid process"
    CIRCULATORY = "Diseases of the circulatory system"
    RESPIRATORY = "Diseases of the respiratory system"
    DIGESTIVE = "Diseases of the digestive system"
    SKIN = "Diseases of the skin and subcutaneous tissue"
    MUSCULOSKELETAL = "Diseases of the musculoskeletal system"
    GENITOURINARY = "Diseases of the genitourinary system"
    PREGNANCY = "Pregnancy, childbirth and the puerperium"
    PERINATAL = "Certain conditions originating in the perinatal period"
    CONGENITAL = "Congenital malformations"
    ABNORMAL = "Symptoms, signs and abnormal clinical findings"
    INJURY = "Injury, poisoning and certain other consequences of external causes"
    EXTERNAL = "External causes of morbidity and mortality"
    HEALTH = "Factors influencing health status"
    SPECIAL = "Codes for special purposes"


class CPTSection(str, Enum):
    """CPT code sections"""
    EVALUATION_MANAGEMENT = "Evaluation and Management"
    ANESTHESIA = "Anesthesia"
    SURGERY = "Surgery"
    RADIOLOGY = "Radiology"
    PATHOLOGY = "Pathology and Laboratory"
    MEDICINE = "Medicine"


class MedicalCoder:
    """
    Medical coding service
    
    Features:
    - Search ICD-10 codes
    - Search CPT codes
    - Validate codes
    - Map ICD-10 to CPT
    - Provide suggestions
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize medical coder"""
        self.db = db_session
    
    def _get_db(self) -> Session:
        """Get database session"""
        if self.db:
            return self.db
        return get_db_session()
    
    # === ICD-10 Methods ===
    
    def search_icd10(
        self,
        query: str,
        limit: int = 50,
        category: Optional[str] = None,
        chapter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search ICD-10 diagnosis codes
        
        Args:
            query: Search query (code or description)
            limit: Maximum results
            category: Filter by category
            chapter: Filter by chapter
            
        Returns:
            List of matching ICD-10 codes
        """
        try:
            db = self._get_db()
            
            # Build query
            q = db.query(ICD10Code)
            
            # Search in code and description
            search_term = f"%{query}%"
            q = q.filter(
                or_(
                    ICD10Code.code.ilike(search_term),
                    ICD10Code.description.ilike(search_term),
                    ICD10Code.synonyms.any(query.lower())
                )
            )
            
            # Filter by category
            if category:
                q = q.filter(ICD10Code.category.ilike(f"%{category}%"))
            
            # Filter by chapter
            if chapter:
                q = q.filter(ICD10Code.chapter.ilike(f"%{chapter}%"))
            
            # Order by billable and relevance
            q = q.order_by(ICD10Code.is_billable.desc())
            
            # Limit results
            q = q.limit(limit)
            
            results = q.all()
            
            return [
                {
                    "code": code.code,
                    "description": code.description,
                    "category": code.category,
                    "chapter": code.chapter,
                    "is_billable": code.is_billable,
                    "synonyms": code.synonyms or []
                }
                for code in results
            ]
            
        except SQLAlchemyError as e:
            logger.error("icd10_search_failed", error=str(e), query=query)
            return []
    
    def get_icd10(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get specific ICD-10 code
        
        Args:
            code: ICD-10 code
            
        Returns:
            Code details or None
        """
        try:
            db = self._get_db()
            
            icd10 = db.query(ICD10Code).filter(
                ICD10Code.code == code.upper()
            ).first()
            
            if not icd10:
                return None
            
            return {
                "code": icd10.code,
                "description": icd10.description,
                "category": icd10.category,
                "chapter": icd10.chapter,
                "is_billable": icd10.is_billable,
                "synonyms": icd10.synonyms or []
            }
            
        except SQLAlchemyError as e:
            logger.error("get_icd10_failed", error=str(e), code=code)
            return None
    
    def validate_icd10(self, code: str) -> bool:
        """
        Validate ICD-10 code format and existence
        
        Args:
            code: ICD-10 code to validate
            
        Returns:
            True if valid
        """
        # Check format (e.g., A00.0, E11.9)
        if not re.match(r'^[A-Z]\d{2}(\.\d{1,4})?$', code.upper()):
            return False
        
        # Check if exists in database
        return self.get_icd10(code) is not None
    
    def get_icd10_hierarchy(self, code: str) -> List[Dict[str, Any]]:
        """
        Get ICD-10 code hierarchy (parent codes)
        
        Args:
            code: ICD-10 code
            
        Returns:
            List of parent codes
        """
        try:
            db = self._get_db()
            
            hierarchy = []
            
            # Get the code itself
            current = self.get_icd10(code)
            if not current:
                return []
            
            hierarchy.append(current)
            
            # Get parent codes (shorter versions)
            parts = code.split('.')
            
            for i in range(len(parts[0]), 0, -1):
                parent_code = code[:i]
                if '.' in code and i == len(parts[0]):
                    # Check without decimal
                    parent = self.get_icd10(parent_code)
                    if parent and parent not in hierarchy:
                        hierarchy.append(parent)
                elif i < len(parts[0]):
                    parent = self.get_icd10(parent_code)
                    if parent and parent not in hierarchy:
                        hierarchy.append(parent)
            
            return hierarchy
            
        except Exception as e:
            logger.error("get_icd10_hierarchy_failed", error=str(e), code=code)
            return []
    
    # === CPT Methods ===
    
    def search_cpt(
        self,
        query: str,
        limit: int = 50,
        section: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search CPT procedure codes
        
        Args:
            query: Search query (code or description)
            limit: Maximum results
            section: Filter by section
            
        Returns:
            List of matching CPT codes
        """
        try:
            db = self._get_db()
            
            q = db.query(CPTCode)
            
            # Search in code and description
            search_term = f"%{query}%"
            q = q.filter(
                or_(
                    CPTCode.code.ilike(search_term),
                    CPTCode.description.ilike(search_term)
                )
            )
            
            # Filter by section
            if section:
                q = q.filter(CPTCode.section.ilike(f"%{section}%"))
            
            # Order by active and RVU
            q = q.order_by(CPTCode.is_active.desc())
            
            # Limit results
            q = q.limit(limit)
            
            results = q.all()
            
            return [
                {
                    "code": code.code,
                    "description": code.description,
                    "category": code.category,
                    "section": code.section,
                    "is_active": code.is_active,
                    "work_rvu": code.work_rvu
                }
                for code in results
            ]
            
        except SQLAlchemyError as e:
            logger.error("cpt_search_failed", error=str(e), query=query)
            return []
    
    def get_cpt(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get specific CPT code
        
        Args:
            code: CPT code
            
        Returns:
            Code details or None
        """
        try:
            db = self._get_db()
            
            cpt = db.query(CPTCode).filter(
                CPTCode.code == code.upper()
            ).first()
            
            if not cpt:
                return None
            
            return {
                "code": cpt.code,
                "description": cpt.description,
                "category": cpt.category,
                "section": cpt.section,
                "is_active": cpt.is_active,
                "work_rvu": cpt.work_rvu
            }
            
        except SQLAlchemyError as e:
            logger.error("get_cpt_failed", error=str(e), code=code)
            return None
    
    def validate_cpt(self, code: str) -> bool:
        """
        Validate CPT code format and existence
        
        Args:
            code: CPT code to validate
            
        Returns:
            True if valid
        """
        # Check format (5 digits or 4 digits + letter)
        if not re.match(r'^\d{5}$|^\d{4}[A-Z]$', code.upper()):
            return False
        
        # Check if exists in database
        return self.get_cpt(code) is not None
    
    # === Code Mapping ===
    
    def map_icd10_to_cpt(
        self,
        icd10_code: str,
        min_confidence: int = 70
    ) -> List[Dict[str, Any]]:
        """
        Get CPT codes commonly used with ICD-10 code
        
        Args:
            icd10_code: ICD-10 diagnosis code
            min_confidence: Minimum mapping confidence (0-100)
            
        Returns:
            List of mapped CPT codes with confidence
        """
        try:
            db = self._get_db()
            
            mappings = db.query(CodeMapping).filter(
                CodeMapping.icd10_code == icd10_code.upper(),
                CodeMapping.mapping_confidence >= min_confidence
            ).order_by(CodeMapping.mapping_confidence.desc()).all()
            
            results = []
            
            for mapping in mappings:
                cpt = db.query(CPTCode).filter(
                    CPTCode.code == mapping.cpt_code
                ).first()
                
                if cpt:
                    results.append({
                        "icd10_code": icd10_code,
                        "cpt_code": cpt.code,
                        "cpt_description": cpt.description,
                        "section": cpt.section,
                        "confidence": mapping.mapping_confidence
                    })
            
            return results
            
        except SQLAlchemyError as e:
            logger.error("map_icd10_to_cpt_failed", error=str(e), icd10_code=icd10_code)
            return []
    
    def map_cpt_to_icd10(
        self,
        cpt_code: str,
        min_confidence: int = 70
    ) -> List[Dict[str, Any]]:
        """
        Get ICD-10 codes commonly used with CPT code
        
        Args:
            cpt_code: CPT procedure code
            min_confidence: Minimum mapping confidence (0-100)
            
        Returns:
            List of mapped ICD-10 codes with confidence
        """
        try:
            db = self._get_db()
            
            mappings = db.query(CodeMapping).filter(
                CodeMapping.cpt_code == cpt_code.upper(),
                CodeMapping.mapping_confidence >= min_confidence
            ).order_by(CodeMapping.mapping_confidence.desc()).all()
            
            results = []
            
            for mapping in mappings:
                icd10 = db.query(ICD10Code).filter(
                    ICD10Code.code == mapping.icd10_code
                ).first()
                
                if icd10:
                    results.append({
                        "cpt_code": cpt_code,
                        "icd10_code": icd10.code,
                        "icd10_description": icd10.description,
                        "category": icd10.category,
                        "confidence": mapping.mapping_confidence
                    })
            
            return results
            
        except SQLAlchemyError as e:
            logger.error("map_cpt_to_icd10_failed", error=str(e), cpt_code=cpt_code)
            return []
    
    def create_mapping(
        self,
        icd10_code: str,
        cpt_code: str,
        confidence: int = 80
    ) -> Optional[UUID]:
        """
        Create ICD-10 to CPT mapping
        
        Args:
            icd10_code: ICD-10 code
            cpt_code: CPT code
            confidence: Mapping confidence (0-100)
            
        Returns:
            Mapping ID or None
        """
        try:
            db = self._get_db()
            
            # Verify both codes exist
            if not self.get_icd10(icd10_code) or not self.get_cpt(cpt_code):
                return None
            
            # Check if mapping exists
            existing = db.query(CodeMapping).filter(
                CodeMapping.icd10_code == icd10_code.upper(),
                CodeMapping.cpt_code == cpt_code.upper()
            ).first()
            
            if existing:
                # Update confidence
                existing.mapping_confidence = confidence
                db.commit()
                return existing.id
            
            # Create new mapping
            mapping = CodeMapping(
                icd10_code=icd10_code.upper(),
                cpt_code=cpt_code.upper(),
                mapping_confidence=confidence
            )
            
            db.add(mapping)
            db.commit()
            db.refresh(mapping)
            
            logger.info(
                "code_mapping_created",
                icd10_code=icd10_code,
                cpt_code=cpt_code,
                confidence=confidence
            )
            
            return mapping.id
            
        except SQLAlchemyError as e:
            logger.error("create_mapping_failed", error=str(e))
            return None
    
    # === Suggestions ===
    
    def suggest_codes(
        self,
        text: str,
        code_type: CodeType = CodeType.ICD10,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Suggest codes based on clinical text
        
        Args:
            text: Clinical text (symptoms, diagnosis, etc.)
            code_type: Type of code to suggest
            limit: Maximum results
            
        Returns:
            List of suggested codes
        """
        # Extract keywords from text
        keywords = self._extract_keywords(text)
        
        # Search for each keyword
        results = []
        seen_codes = set()
        
        for keyword in keywords:
            if code_type == CodeType.ICD10:
                codes = self.search_icd10(keyword, limit=5)
            else:
                codes = self.search_cpt(keyword, limit=5)
            
            for code in codes:
                if code["code"] not in seen_codes:
                    seen_codes.add(code["code"])
                    code["relevance_score"] = self._calculate_relevance(text, code)
                    results.append(code)
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return results[:limit]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract clinical keywords from text"""
        # Common medical terms to look for
        medical_terms = []
        
        # Split text into words
        words = text.lower().split()
        
        # Look for multi-word terms
        for i in range(len(words)):
            # 3-word terms
            if i < len(words) - 2:
                term = " ".join(words[i:i+3])
                if len(term) > 5:
                    medical_terms.append(term)
            
            # 2-word terms
            if i < len(words) - 1:
                term = " ".join(words[i:i+2])
                if len(term) > 4:
                    medical_terms.append(term)
            
            # Single words
            if len(words[i]) > 3:
                medical_terms.append(words[i])
        
        return list(set(medical_terms))
    
    def _calculate_relevance(self, text: str, code: Dict[str, Any]) -> float:
        """Calculate relevance score for code"""
        text_lower = text.lower()
        
        score = 0.0
        
        # Check description match
        if code["description"].lower() in text_lower:
            score += 10.0
        
        # Check code match
        if code["code"].lower() in text_lower:
            score += 5.0
        
        # Check category match
        if "category" in code and code["category"]:
            if code["category"].lower() in text_lower:
                score += 3.0
        
        # Check synonyms
        if "synonyms" in code and code["synonyms"]:
            for synonym in code["synonyms"]:
                if synonym.lower() in text_lower:
                    score += 2.0
        
        return score
    
    # === Statistics ===
    
    def get_code_statistics(self) -> Dict[str, Any]:
        """
        Get code statistics
        
        Returns:
            Statistics about ICD-10 and CPT codes
        """
        try:
            db = self._get_db()
            
            # Count ICD-10 codes
            icd10_count = db.query(ICD10Code).count()
            
            # Count CPT codes
            cpt_count = db.query(CPTCode).count()
            
            # Count mappings
            mapping_count = db.query(CodeMapping).count()
            
            # ICD-10 by chapter
            icd10_by_chapter = {}
            chapters = db.query(
                ICD10Code.chapter,
                db.func.count(ICD10Code.code)
            ).group_by(ICD10Code.chapter).all()
            
            for chapter, count in chapters:
                if chapter:
                    icd10_by_chapter[chapter] = count
            
            # CPT by section
            cpt_by_section = {}
            sections = db.query(
                CPTCode.section,
                db.func.count(CPTCode.code)
            ).group_by(CPTCode.section).all()
            
            for section, count in sections:
                if section:
                    cpt_by_section[section] = count
            
            return {
                "icd10_total": icd10_count,
                "cpt_total": cpt_count,
                "mappings_total": mapping_count,
                "icd10_by_chapter": icd10_by_chapter,
                "cpt_by_section": cpt_by_section
            }
            
        except SQLAlchemyError as e:
            logger.error("get_statistics_failed", error=str(e))
            return {
                "icd10_total": 0,
                "cpt_total": 0,
                "mappings_total": 0,
                "icd10_by_chapter": {},
                "cpt_by_section": {}
            }


# Convenience functions

_coder = None


def get_medical_coder(db_session: Optional[Session] = None) -> MedicalCoder:
    """Get medical coder instance"""
    global _coder
    if db_session:
        return MedicalCoder(db_session)
    if not _coder:
        _coder = MedicalCoder()
    return _coder


def search_icd10(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search ICD-10 codes"""
    return get_medical_coder().search_icd10(query, limit)


def search_cpt(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search CPT codes"""
    return get_medical_coder().search_cpt(query, limit)


def validate_code(code: str, code_type: CodeType) -> bool:
    """Validate medical code"""
    coder = get_medical_coder()
    if code_type == CodeType.ICD10:
        return coder.validate_icd10(code)
    else:
        return coder.validate_cpt(code)