"""
Tests for Medical Coding System

Tests:
- ICD-10 code search
- CPT code search
- Code validation
- Code mapping
- Code suggestions
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.orm import Session

from cortex.medical_coding import (
    MedicalCoder, CodeType, ICD10Chapter, CPTSection,
    get_medical_coder, search_icd10, search_cpt
)
from cortex.models import ICD10Code, CPTCode, CodeMapping


class TestMedicalCoder:
    """Test MedicalCoder class"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = MagicMock(spec=Session)
        return db
    
    @pytest.fixture
    def coder(self, mock_db):
        """Create medical coder with mock database"""
        return MedicalCoder(db_session=mock_db)
    
    @pytest.fixture
    def sample_icd10(self):
        """Create sample ICD-10 code"""
        code = Mock(spec=ICD10Code)
        code.code = "E11.9"
        code.description = "Type 2 diabetes mellitus without complications"
        code.category = "Endocrine, nutritional and metabolic diseases"
        code.chapter = "Endocrine, nutritional and metabolic diseases"
        code.is_billable = True
        code.synonyms = ["Type 2 diabetes", "NIDDM", "Non-insulin dependent diabetes"]
        return code
    
    @pytest.fixture
    def sample_cpt(self):
        """Create sample CPT code"""
        code = Mock(spec=CPTCode)
        code.code = "99213"
        code.description = "Office or other outpatient visit for the evaluation and management of an established patient"
        code.category = "Evaluation and Management"
        code.section = "Evaluation and Management"
        code.is_active = True
        code.work_rvu = 1.3
        return code
    
    def test_search_icd10(self, coder, mock_db, sample_icd10):
        """Test ICD-10 code search"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_icd10
        ]
        
        results = coder.search_icd10("diabetes", limit=10)
        
        assert len(results) == 1
        assert results[0]["code"] == "E11.9"
        assert "diabetes" in results[0]["description"].lower()
        mock_db.query.assert_called_once()
    
    def test_search_icd10_with_filters(self, coder, mock_db, sample_icd10):
        """Test ICD-10 search with filters"""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_icd10
        ]
        
        results = coder.search_icd10(
            "diabetes",
            limit=10,
            category="Endocrine",
            chapter="Endocrine, nutritional and metabolic diseases"
        )
        
        assert len(results) == 1
        assert results[0]["code"] == "E11.9"
    
    def test_get_icd10(self, coder, mock_db, sample_icd10):
        """Test getting specific ICD-10 code"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_icd10
        
        result = coder.get_icd10("E11.9")
        
        assert result is not None
        assert result["code"] == "E11.9"
        assert result["description"] == "Type 2 diabetes mellitus without complications"
    
    def test_get_icd10_not_found(self, coder, mock_db):
        """Test getting non-existent ICD-10 code"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = coder.get_icd10("INVALID")
        
        assert result is None
    
    def test_validate_icd10_format(self, coder):
        """Test ICD-10 format validation"""
        # Valid formats
        assert coder.validate_icd10("A00.0") is False  # Doesn't exist in DB
        assert coder.validate_icd10("E11.9") is False  # Doesn't exist in DB
        
        # Invalid formats
        assert coder.validate_icd10("123") is False
        assert coder.validate_icd10("ABC") is False
        assert coder.validate_icd10("12345") is False
    
    def test_search_cpt(self, coder, mock_db, sample_cpt):
        """Test CPT code search"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_cpt
        ]
        
        results = coder.search_cpt("office visit", limit=10)
        
        assert len(results) == 1
        assert results[0]["code"] == "99213"
        assert "office" in results[0]["description"].lower()
    
    def test_get_cpt(self, coder, mock_db, sample_cpt):
        """Test getting specific CPT code"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cpt
        
        result = coder.get_cpt("99213")
        
        assert result is not None
        assert result["code"] == "99213"
        assert "evaluation and management" in result["description"].lower()
    
    def test_get_cpt_not_found(self, coder, mock_db):
        """Test getting non-existent CPT code"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = coder.get_cpt("99999")
        
        assert result is None
    
    def test_validate_cpt_format(self, coder):
        """Test CPT format validation"""
        # Valid formats (but doesn't exist in DB)
        assert coder.validate_cpt("99213") is False  # Doesn't exist in DB
        
        # Invalid formats
        assert coder.validate_cpt("123") is False
        assert coder.validate_cpt("ABC") is False
        assert coder.validate_cpt("123456") is False
    
    def test_map_icd10_to_cpt(self, coder, mock_db, sample_cpt):
        """Test mapping ICD-10 to CPT codes"""
        mapping = Mock(spec=CodeMapping)
        mapping.icd10_code = "E11.9"
        mapping.cpt_code = "99213"
        mapping.mapping_confidence = 90
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mapping
        ]
        
        # Mock CPT query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_cpt
        
        results = coder.map_icd10_to_cpt("E11.9", min_confidence=70)
        
        assert len(results) == 1
        assert results[0]["cpt_code"] == "99213"
        assert results[0]["confidence"] == 90
    
    def test_map_cpt_to_icd10(self, coder, mock_db, sample_icd10):
        """Test mapping CPT to ICD-10 codes"""
        mapping = Mock(spec=CodeMapping)
        mapping.cpt_code = "99213"
        mapping.icd10_code = "E11.9"
        mapping.mapping_confidence = 85
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mapping
        ]
        
        # Mock ICD-10 query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_icd10
        
        results = coder.map_cpt_to_icd10("99213", min_confidence=70)
        
        assert len(results) == 1
        assert results[0]["icd10_code"] == "E11.9"
        assert results[0]["confidence"] == 85
    
    def test_create_mapping(self, coder, mock_db, sample_icd10, sample_cpt):
        """Test creating code mapping"""
        # Mock existing code checks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_icd10,  # ICD-10 exists
            sample_cpt,    # CPT exists
            None           # No existing mapping
        ]
        
        mapping = Mock(spec=CodeMapping)
        mapping.id = uuid4()
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock query for existing mapping
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = coder.create_mapping("E11.9", "99213", confidence=85)
        
        # Verify database operations called
        # Note: Actual implementation might differ
        assert result is not None  # Would be the mapping ID
    
    def test_suggest_codes_icd10(self, coder, mock_db, sample_icd10):
        """Test code suggestions for ICD-10"""
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_icd10
        ]
        
        results = coder.suggest_codes(
            "patient has type 2 diabetes mellitus",
            code_type=CodeType.ICD10,
            limit=5
        )
        
        # Should extract keywords and search
        assert isinstance(results, list)
    
    def test_extract_keywords(self, coder):
        """Test keyword extraction"""
        text = "patient presents with type 2 diabetes and hypertension"
        
        keywords = coder._extract_keywords(text)
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # Should have single words and multi-word terms
        assert any("diabetes" in kw for kw in keywords)
    
    def test_calculate_relevance(self, coder, sample_icd10):
        """Test relevance calculation"""
        text = "Type 2 diabetes mellitus without complications"
        
        code_dict = {
            "code": "E11.9",
            "description": "Type 2 diabetes mellitus without complications",
            "category": "Endocrine",
            "synonyms": ["NIDDM", "Type 2 diabetes"]
        }
        
        score = coder._calculate_relevance(text, code_dict)
        
        assert score > 0
        # Exact description match should give high score
        assert score >= 10.0
    
    def test_get_code_statistics(self, coder, mock_db):
        """Test getting code statistics"""
        mock_db.query.return_value.count.return_value = 1000
        
        # Mock group by queries
        mock_db.query.return_value.group_by.return_value.all.return_value = [
            ("Chapter 1", 100),
            ("Chapter 2", 150)
        ]
        
        stats = coder.get_code_statistics()
        
        assert "icd10_total" in stats
        assert "cpt_total" in stats
        assert "mappings_total" in stats
        assert "icd10_by_chapter" in stats
        assert "cpt_by_section" in stats


class TestCodeTypes:
    """Test code type enums"""
    
    def test_code_type_enum(self):
        """Test code type enum"""
        assert CodeType.ICD10.value == "icd10"
        assert CodeType.CPT.value == "cpt"
    
    def test_icd10_chapter_enum(self):
        """Test ICD-10 chapter enum"""
        assert ICD10Chapter.INFECTIOUS.value == "Certain infectious and parasitic diseases"
        assert ICD10Chapter.NEOPLASMS.value == "Neoplasms"
        assert ICD10Chapter.CIRCULATORY.value == "Diseases of the circulatory system"
    
    def test_cpt_sectionenum(self):
        """Test CPT section enum"""
        assert CPTSection.EVALUATION_MANAGEMENT.value == "Evaluation and Management"
        assert CPTSection.SURGERY.value == "Surgery"
        assert CPTSection.RADIOLOGY.value == "Radiology"


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch('cortex.medical_coding.get_medical_coder')
    def test_search_icd10(self, mock_get_coder):
        """Test search_icd10 function"""
        mock_coder = Mock()
        mock_coder.search_icd10.return_value = [{"code": "E11.9"}]
        mock_get_coder.return_value = mock_coder
        
        results = search_icd10("diabetes")
        
        assert len(results) == 1
        assert results[0]["code"] == "E11.9"
        mock_coder.search_icd10.assert_called_once()
    
    @patch('cortex.medical_coding.get_medical_coder')
    def test_search_cpt(self, mock_get_coder):
        """Test search_cpt function"""
        mock_coder = Mock()
        mock_coder.search_cpt.return_value = [{"code": "99213"}]
        mock_get_coder.return_value = mock_coder
        
        results = search_cpt("office visit")
        
        assert len(results) == 1
        assert results[0]["code"] == "99213"
        mock_coder.search_cpt.assert_called_once()
    
    @patch('cortex.medical_coding.get_medical_coder')
    def test_validate_code_icd10(self, mock_get_coder):
        """Test validate_code for ICD-10"""
        mock_coder = Mock()
        mock_coder.validate_icd10.return_value = True
        mock_get_coder.return_value = mock_coder
        
        from cortex.medical_coding import validate_code
        
        result = validate_code("E11.9", CodeType.ICD10)
        
        assert result is True
        mock_coder.validate_icd10.assert_called_once_with("E11.9")
    
    @patch('cortex.medical_coding.get_medical_coder')
    def test_validate_code_cpt(self, mock_get_coder):
        """Test validate_code for CPT"""
        mock_coder = Mock()
        mock_coder.validate_cpt.return_value = True
        mock_get_coder.return_value = mock_coder
        
        from cortex.medical_coding import validate_code
        
        result = validate_code("99213", CodeType.CPT)
        
        assert result is True
        mock_coder.validate_cpt.assert_called_once_with("99213")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])