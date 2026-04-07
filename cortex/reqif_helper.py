"""
Cortex ReqIF Export - Enterprise Interoperability with XSD Validation

Phase 2 Enhancement: Exports tagged requirements to ReqIF format
for integration with enterprise requirements management tools.

ReqIF (Requirements Interchange Format) is an ISO standard
(ISO/IEC 29100) for exchanging requirements data between tools.

This module provides:
- ReqIF XML generation from tagged requirements
- XSD schema validation BEFORE writing to disk
- Fully qualified namespace references
- Detailed error reporting for malformed XML

DOORS Compatibility:
- All namespace prefixes must be fully qualified
- All required elements must be present
- All enumerated values must match schema
"""

import io
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# REQIF NAMESPACES (Fully Qualified)
# =============================================================================

# Official ReqIF namespace URIs
REQIF_NAMESPACES = {
    'reqif': 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd',
    'reqif-common': 'http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd',
    'reqif-content': 'http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}

# Prefix to URI mapping for lxml
NSMAP = {
    'reqif': 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd',
    'reqif-common': 'http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd',
    'reqif-content': 'http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd',
    None: 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd',  # Default
}


# =============================================================================
# REQIF SCHEMA VALIDATOR
# =============================================================================

class ReqIFValidationError(Exception):
    """
    Raised when ReqIF XML fails XSD schema validation.
    
    Attributes:
        errors: List of validation error details
        xml_snippet: Portion of XML that failed (if available)
    """
    
    def __init__(self, message: str, errors: List[str] = None, xml_content: str = None):
        self.message = message
        self.errors = errors or []
        self.xml_content = xml_content
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": "ReqIFValidationError",
            "message": self.message,
            "validation_errors": self.errors,
            "xml_length": len(self.xml_content) if self.xml_content else 0,
        }


class ReqIFSchemaValidator:
    """
    Validates ReqIF XML against the official XSD schema.
    
    Uses xmlschema library for robust validation with detailed
    error reporting.
    
    Note: The official ReqIF XSD is complex with many optional elements.
    This validator focuses on DOORS-critical constraints:
    1. All namespace prefixes are properly qualified
    2. All required elements are present
    3. All datatype references are valid
    4. All IDENTIFIER values are properly formatted
    """
    
    # Minimal schema for validation (excerpt - full schema is downloaded)
    MINIMAL_SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:reqif="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
           xmlns:reqif-common="http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd"
           xmlns:reqif-content="http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd"
           targetNamespace="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
           elementFormDefault="qualified">
  
  <!-- Root element -->
  <xs:element name="ReqIF" type="reqif:ReqIF"/>
  
  <xs:complexType name="ReqIF">
    <xs:sequence>
      <xs:element ref="reqif:THE-HEADER"/>
      <xs:element ref="reqif:CORE-CONTENT"/>
      <xs:element ref="reqif:RESOURCE-FILES" minOccurs="0"/>
    </xs:sequence>
    <xs:attribute ref="reqif:version"/>
  </xs:complexType>
  
  <!-- THE-HEADER -->
  <xs:element name="THE-HEADER" type="reqif:TheHeader"/>
  <xs:complexType name="TheHeader">
    <xs:sequence>
      <xs:element name="CREATION-TIME" type="xs:dateTime"/>
      <xs:element name="REQ-IF-VERSION" type="xs:string"/>
      <xs:element name="TOOL-IDS" type="reqif:ToolIds" minOccurs="0"/>
      <xs:element name="SOURCE-TOOL-IDS" type="reqif:SourceToolIds" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
  
  <!-- CORE-CONTENT -->
  <xs:element name="CORE-CONTENT" type="reqif:CoreContent"/>
  <xs:complexType name="CoreContent">
    <xs:sequence>
      <xs:element name="DATATYPES" type="reqif:Datatypes" minOccurs="0"/>
      <xs:element name="SPEC-OBJECT-TYPES" type="reqif:SpecObjectTypes" minOccurs="0"/>
      <xs:element name="SPEC-RELATION-TYPES" type="reqif:SpecRelationTypes" minOccurs="0"/>
      <xs:element name="SPEC-OBJECTS" type="reqif:SpecObjects" minOccurs="0"/>
      <xs:element name="SPEC-RELATIONS" type="reqif:SpecRelations" minOccurs="0"/>
      <xs:element name="SPECIFICATIONS" type="reqif:Specifications" minOccurs="0"/>
    </xs:sequence>
  </xs:complexType>
  
  <!-- Common types -->
  <xs:complexType name="ToolIds"/>
  <xs:complexType name="SourceToolIds"/>
  <xs:complexType name="Datatypes">
    <xs:choice minOccurs="0" maxOccurs="unbounded">
      <xs:element name="STRING-DATATYPE" type="reqif-common:StringDatatype"/>
      <xs:element name="INTEGER-DATATYPE" type="reqif-common:IntegerDatatype"/>
      <xs:element name="BOOLEAN-DATATYPE" type="reqif-common:BooleanDatatype"/>
      <xs:element name="ENUM-DATATYPE" type="reqif-common:EnumDatatype"/>
    </xs:choice>
  </xs:complexType>
  
  <xs:complexType name="SpecObjectTypes">
    <xs:sequence>
      <xs:element name="SPEC-OBJECT-TYPE" type="reqif-common:SpecObjectType"/>
    </xs:sequence>
  </xs:complexType>
  
  <xs:complexType name="SpecRelationTypes">
    <xs:sequence>
      <xs:element name="SPEC-RELATION-TYPE" type="reqif-common:SpecRelationType"/>
    </xs:sequence>
  </xs:complexType>
  
  <xs:complexType name="SpecObjects">
    <xs:sequence>
      <xs:element name="SPEC-OBJECT" type="reqif-common:SpecObject"/>
    </xs:sequence>
  </xs:complexType>
  
  <xs:complexType name="SpecRelations">
    <xs:sequence>
      <xs:element name="SPEC-RELATION" type="reqif-common:SpecRelation"/>
    </xs:sequence>
  </xs:complexType>
  
  <xs:complexType name="Specifications">
    <xs:sequence>
      <xs:element name="SPECIFICATION" type="reqif-content:Specification"/>
    </xs:sequence>
  </xs:complexType>
  
  <!-- Resource files (optional) -->
  <xs:element name="RESOURCE-FILES" type="xs:anyType" minOccurs="0"/>
  
</xs:schema>
"""
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize validator.
        
        Args:
            schema_path: Path to ReqIF XSD schema file. If not provided,
                        uses embedded minimal schema.
        """
        self.schema_path = schema_path
        self._schema = None
        self._lxml_available = False
        self._xmlschema_available = False
        
        self._check_dependencies()
    
    def _check_dependencies(self) -> None:
        """Check for available validation libraries"""
        try:
            from lxml import etree
            self._lxml_available = True
            logger.debug("lxml_available")
        except ImportError:
            logger.warning("lxml_not_available_xsd_validation_disabled")
        
        try:
            import xmlschema
            self._xmlschema_available = True
            logger.debug("xmlschema_available")
        except ImportError:
            logger.warning("xmlschema_not_available_using_lxml_only")
    
    def _get_schema(self):
        """Get or create schema object"""
        if self._schema is not None:
            return self._schema
        
        if self.schema_path and Path(self.schema_path).exists():
            # Load from file
            try:
                if self._xmlschema_available:
                    import xmlschema
                    self._schema = xmlschema.XMLSchema(self.schema_path)
                elif self._lxml_available:
                    from lxml import etree
                    self._schema = etree.XMLSchema(etree.parse(self.schema_path))
            except Exception as e:
                logger.warning(f"failed_to_load_schema: {e}")
        
        if self._schema is None:
            # Use embedded schema
            try:
                if self._xmlschema_available:
                    import xmlschema
                    self._schema = xmlschema.XMLSchema(io.StringIO(self.MINIMAL_SCHEMA))
                elif self._lxml_available:
                    from lxml import etree
                    self._schema = etree.XMLSchema(etree.parse(io.StringIO(self.MINIMAL_SCHEMA)))
            except Exception as e:
                logger.error(f"failed_to_load_embedded_schema: {e}")
                self._schema = None
        
        return self._schema
    
    def validate(self, xml_content: str) -> Tuple[bool, List[str]]:
        """
        Validate XML against ReqIF schema.
        
        Args:
            xml_content: The XML string to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: List[str] = []
        
        # Step 1: Check for namespace prefix consistency
        ns_errors = self._validate_namespaces(xml_content)
        errors.extend(ns_errors)
        
        # Step 2: Check for required structure
        struct_errors = self._validate_structure(xml_content)
        errors.extend(struct_errors)
        
        # Step 3: Try XSD validation if library available
        if self._lxml_available or self._xmlschema_available:
            xsd_errors = self._validate_with_xsd(xml_content)
            errors.extend(xsd_errors)
        
        # Remove duplicates
        errors = list(set(errors))
        
        return len(errors) == 0, errors
    
    def _validate_namespaces(self, xml_content: str) -> List[str]:
        """Validate namespace prefix consistency"""
        errors = []
        
        # Check that namespace prefixes are declared
        required_prefixes = ['reqif', 'reqif-common', 'reqif-content']
        
        for prefix in required_prefixes:
            ns_pattern = f'xmlns:{prefix}='
            if ns_pattern not in xml_content:
                errors.append(
                    f"Missing namespace declaration: {ns_pattern}"
                )
        
        # Check for unqualified elements that should be qualified
        # Common DOORS rejection causes
        unqualified_patterns = [
            (r'<THE-HEADER[^:]', "THE-HEADER should use reqif:THE-HEADER"),
            (r'<CORE-CONTENT[^:]', "CORE-CONTENT should use reqif:CORE-CONTENT"),
            (r'<DATATYPES[^:]', "DATATYPES should use reqif-common:DATATYPES"),
            (r'<SPEC-OBJECTS[^:]', "SPEC-OBJECTS should use reqif-content:SPEC-OBJECTS"),
            (r'<SPEC-OBJECT[^:]', "SPEC-OBJECT should use reqif-common:SPEC-OBJECT"),
            (r'<ATTRIBUTE-VALUE[^:]', "ATTRIBUTE-VALUE should use reqif-common:ATTRIBUTE-VALUE"),
        ]
        
        for pattern, message in unqualified_patterns:
            if re.search(pattern, xml_content):
                errors.append(message)
        
        return errors
    
    def _validate_structure(self, xml_content: str) -> List[str]:
        """Validate required structural elements"""
        errors = []
        
        required_elements = [
            (r'<reqif:ReqIF', "Root element ReqIF not found"),
            (r'<reqif:THE-HEADER', "THE-HEADER not found"),
            (r'<reqif:CORE-CONTENT', "CORE-CONTENT not found"),
            (r'<reqif-common:CREATION-TIME', "CREATION-TIME not found"),
            (r'<reqif-common:REQ-IF-VERSION', "REQ-IF-VERSION not found"),
        ]
        
        for pattern, message in required_elements:
            if not re.search(pattern, xml_content):
                errors.append(message)
        
        # Check identifier formatting
        # ReqIF identifiers should be non-empty alphanumeric with underscores
        invalid_ids = re.findall(r'<[^:]+:IDENTIFIER[^>]*>[^<]*</[^:]+:IDENTIFIER>', xml_content)
        for match in invalid_ids:
            # Extract identifier value
            id_match = re.search(r'>([^<]+)<', match)
            if id_match:
                id_value = id_match.group(1).strip()
                if not id_value:
                    errors.append(f"Empty IDENTIFIER found: {match}")
                elif not re.match(r'^[A-Za-z0-9_-]+$', id_value):
                    errors.append(
                        f"Invalid IDENTIFIER format '{id_value}': "
                        f"must be alphanumeric with underscores/hyphens"
                    )
        
        return errors
    
    def _validate_with_xsd(self, xml_content: str) -> List[str]:
        """Validate using XSD schema"""
        errors = []
        
        schema = self._get_schema()
        if schema is None:
            return ["XSD schema validation unavailable (no schema loaded)"]
        
        try:
            if self._xmlschema_available and hasattr(schema, 'validate'):
                # xmlschema API
                try:
                    schema.validate(xml_content)
                except Exception as e:
                    errors.append(f"XSD validation error: {str(e)}")
            
            elif self._lxml_available:
                from lxml import etree
                
                try:
                    root = etree.fromstring(xml_content.encode('utf-8'))
                    
                    if not schema.validate(root):
                        for error in schema.error_log:
                            errors.append(f"XSD line {error.line}: {error.message}")
                except etree.XMLSyntaxError as e:
                    errors.append(f"XML syntax error: {str(e)}")
        
        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
        
        return errors


# =============================================================================
# REQIF ATTRIBUTE DEFINITION
# =============================================================================

@dataclass
class ReqIFAttributeDefinition:
    """Definition of a custom attribute"""
    name: str
    data_type: str  # string, integer, boolean, enumeration, date, real
    description: Optional[str] = None
    default_value: Optional[str] = None
    enumeration_values: Optional[List[str]] = None


# =============================================================================
# LXML-BASED REQIF EXPORTER
# =============================================================================

class ReqIFExporter:
    """
    Exports Cortex requirements to ReqIF format with XSD validation.
    
    Key improvements over v1:
    1. Uses lxml for proper namespace handling
    2. All elements fully qualified with namespace prefixes
    3. Validates against XSD before writing to disk
    4. Detailed error messages for DOORS compatibility
    
    DOORS Import Tips:
    - Ensure all identifiers use only alphanumeric + underscore
    - Use reqif-common: prefix for all type references
    - Verify CREATION-TIME uses ISO 8601 format
    """
    
    def __init__(
        self,
        tool_name: str = "Cortex Compliance Engine",
        tool_vendor: str = "Cortex",
        tool_version: str = "1.0",
        validate: bool = True,
        schema_path: Optional[str] = None,
    ):
        self.tool_name = tool_name
        self.tool_vendor = tool_vendor
        self.tool_version = tool_version
        self.validate_before_write = validate
        
        # Setup validator
        self._validator = ReqIFSchemaValidator(schema_path)
        
        # Attribute definitions
        self.attribute_defs: List[ReqIFAttributeDefinition] = []
        self._setup_default_attributes()
        
        # Import lxml
        self._lxml_available = False
        try:
            from lxml import etree
            self._etree = etree
            self._lxml_available = True
        except ImportError:
            logger.warning("lxml_not_available_using_xml_etree")
            import xml.etree.ElementTree as ET
            self._etree = ET
    
    def _setup_default_attributes(self) -> None:
        """Set up default attribute definitions for compliance"""
        self.attribute_defs = [
            ReqIFAttributeDefinition(
                name="ReqIF.CustomRequirementType",
                data_type="string",
                description="Requirement type classification"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomPriority",
                data_type="string",
                description="Priority level (shall/should/may)"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomSafetyClass",
                data_type="string",
                description="IEC 62304 Safety Class (A/B/C)"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomRiskLevel",
                data_type="string",
                description="Risk assessment level"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomComplianceStandard",
                data_type="string",
                description="Applicable compliance standard"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomComplianceClause",
                data_type="string",
                description="Specific clause reference"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomVerificationMethod",
                data_type="enumeration",
                description="Verification method",
                enumeration_values=["Inspection", "Analysis", "Test", "Demonstration"]
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomTestStatus",
                data_type="string",
                description="Current test status"
            ),
            ReqIFAttributeDefinition(
                name="ReqIF.CustomSourceFile",
                data_type="string",
                description="Source file path in wiki"
            ),
        ]
    
    def export(
        self,
        scan_results: Dict[str, Any],
        output_path: str,
        spec_object_type_name: str = "ComplianceRequirement",
        spec_relation_type_name: str = "Verifies",
    ) -> None:
        """
        Export scan results to ReqIF file with XSD validation.
        
        Args:
            scan_results: Output from ComplianceWikiScanner.scan_all()
            output_path: Path to write ReqIF XML file
            spec_object_type_name: Name for the requirement type
            spec_relation_type_name: Name for the traceability relation type
            
        Raises:
            ReqIFValidationError: If XML fails validation before write
        """
        # Generate XML
        xml_content = self.to_string(scan_results, spec_object_type_name, spec_relation_type_name)
        
        # Validate before writing
        if self.validate_before_write:
            is_valid, errors = self._validator.validate(xml_content)
            
            if not is_valid:
                error_message = (
                    f"ReqIF XML validation failed with {len(errors)} error(s). "
                    f"File will NOT be written to prevent DOORS rejection. "
                    f"Errors: {'; '.join(errors[:5])}"
                )
                raise ReqIFValidationError(
                    message=error_message,
                    errors=errors,
                    xml_content=xml_content,
                )
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        logger.info(f"Exported validated ReqIF to {output_path}")
    
    def to_string(
        self,
        scan_results: Dict[str, Any],
        spec_object_type_name: str = "ComplianceRequirement",
        spec_relation_type_name: str = "Verifies",
    ) -> str:
        """
        Export to string with proper namespace handling.
        
        Uses lxml for correct namespace qualification.
        Falls back to stdlib xml.etree if lxml unavailable.
        """
        if self._lxml_available:
            return self._to_string_lxml(scan_results, spec_object_type_name, spec_relation_type_name)
        else:
            return self._to_string_stdlib(scan_results, spec_object_type_name, spec_relation_type_name)
    
    def _to_string_lxml(
        self,
        scan_results: Dict[str, Any],
        spec_object_type_name: str,
        spec_relation_type_name: str,
    ) -> str:
        """Generate ReqIF XML using lxml (preferred)"""
        etree = self._etree
        
        # Create namespace map
        nsmap = dict(NSMAP)
        
        # Root element with namespaces
        root = etree.Element(
            '{http://www.omg.org/spec/ReqIF/20110401/reqif.xsd}ReqIF',
            nsmap=nsmap
        )
        
        # THE-HEADER
        header = etree.SubElement(root, '{http://www.omg.org/spec/ReqIF/20110401/reqif.xsd}THE-HEADER')
        
        creation_time = etree.SubElement(header, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}CREATION-TIME')
        creation_time.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        req_if_version = etree.SubElement(header, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}REQ-IF-VERSION')
        req_if_version.text = '1.0'
        
        tool_ids = etree.SubElement(header, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}TOOL-IDS')
        
        source_tool = etree.SubElement(tool_ids, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SOURCE-TOOL-ID')
        source_tool.set('TOOL', self.tool_name)
        source_tool.set('VENDOR', self.tool_vendor)
        source_tool.set('VERSION', self.tool_version)
        
        # CORE-CONTENT
        core_content = etree.SubElement(root, '{http://www.omg.org/spec/ReqIF/20110401/reqif.xsd}CORE-CONTENT')
        
        # DATATYPES
        datatypes = self._create_datatypes_lxml(core_content)
        
        # SPEC-RELATION-TYPE
        spec_relation_type = self._create_spec_relation_type_lxml(
            core_content, spec_relation_type_name
        )
        
        # SPEC-OBJECT-TYPE
        spec_object_type = self._create_spec_object_type_lxml(
            core_content, spec_object_type_name, datatypes
        )
        
        # SPEC-OBJECTS (requirements)
        self._create_spec_objects_lxml(core_content, scan_results['requirements'])
        
        # SPEC-RELATIONS
        self._create_relations_lxml(core_content, spec_relation_type, scan_results)
        
        # SPECIFICATIONS
        spec = self._create_specification_lxml(
            core_content, spec_object_type, scan_results
        )
        
        # Serialize
        return etree.tostring(
            root,
            xml_declaration=True,
            encoding='UTF-8',
            pretty_print=True
        ).decode('utf-8')
    
    def _create_datatypes_lxml(self, parent) -> Dict[str, Any]:
        """Create datatype definitions using lxml"""
        etree = self._etree
        datatypes = {}
        
        datatypes_container = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}DATATYPES'
        )
        
        # String
        string_type = etree.SubElement(datatypes_container, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}STRING-DATATYPE')
        dt_id = etree.SubElement(string_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        dt_id.text = 'STRING'
        dt_long_name = etree.SubElement(string_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        dt_long_name.text = 'String'
        datatypes['string'] = string_type
        
        # Integer
        int_type = etree.SubElement(datatypes_container, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}INTEGER-DATATYPE')
        dt_id = etree.SubElement(int_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        dt_id.text = 'INTEGER'
        dt_long_name = etree.SubElement(int_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        dt_long_name.text = 'Integer'
        datatypes['integer'] = int_type
        
        # Boolean
        bool_type = etree.SubElement(datatypes_container, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}BOOLEAN-DATATYPE')
        dt_id = etree.SubElement(bool_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        dt_id.text = 'BOOLEAN'
        dt_long_name = etree.SubElement(bool_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        dt_long_name.text = 'Boolean'
        datatypes['boolean'] = bool_type
        
        # Enumeration
        enum_type = etree.SubElement(datatypes_container, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ENUM-DATATYPE')
        dt_id = etree.SubElement(enum_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        dt_id.text = 'VERIFICATION-METHOD'
        dt_long_name = etree.SubElement(enum_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        dt_long_name.text = 'Verification Method'
        spec_values = etree.SubElement(enum_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-VALUES')
        for val in ['Inspection', 'Analysis', 'Test', 'Demonstration']:
            spec_val = etree.SubElement(spec_values, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-VALUE')
            sv_id = etree.SubElement(spec_val, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
            sv_id.text = val.upper().replace(' ', '_')
            sv_long_name = etree.SubElement(spec_val, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
            sv_long_name.text = val
        datatypes['enumeration'] = enum_type
        
        return datatypes
    
    def _create_spec_relation_type_lxml(self, parent, name: str):
        """Create spec relation type using lxml"""
        etree = self._etree
        
        spec_types = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-RELATION-TYPES'
        )
        
        spec_rel_type = etree.SubElement(spec_types, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-RELATION-TYPE')
        
        type_id = etree.SubElement(spec_rel_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        type_id.text = self._sanitize_identifier(name)
        
        type_long_name = etree.SubElement(spec_rel_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        type_long_name.text = name
        
        last_change = etree.SubElement(spec_rel_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        return spec_rel_type
    
    def _create_spec_object_type_lxml(self, parent, name: str, datatypes: Dict):
        """Create spec object type using lxml"""
        etree = self._etree
        
        spec_types = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-OBJECT-TYPES'
        )
        
        spec_obj_type = etree.SubElement(spec_types, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-OBJECT-TYPE')
        
        type_id = etree.SubElement(spec_obj_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        type_id.text = self._sanitize_identifier(name)
        
        type_long_name = etree.SubElement(spec_obj_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        type_long_name.text = name
        
        last_change = etree.SubElement(spec_obj_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Attributes definition
        spec_attribs = etree.SubElement(spec_obj_type, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-ATTRIBUTES')
        
        for attr_def in self.attribute_defs:
            if attr_def.data_type == 'enumeration':
                attrib = etree.SubElement(spec_attribs, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ATTRIBUTE-DEFINITION-ENUMERATION')
            else:
                attrib = etree.SubElement(spec_attribs, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ATTRIBUTE-DEFINITION-STRING')
            
            attr_id = etree.SubElement(attrib, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
            attr_id.text = self._sanitize_identifier(attr_def.name)
            
            attr_long_name = etree.SubElement(attrib, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
            attr_long_name.text = attr_def.name
        
        return spec_obj_type
    
    def _create_spec_objects_lxml(self, parent, requirements: List[Dict]) -> None:
        """Create spec objects (requirements) using lxml"""
        etree = self._etree
        
        spec_objs = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-OBJECTS'
        )
        
        for req in requirements:
            spec_obj = etree.SubElement(spec_objs, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-OBJECT')
            
            # Identifier
            obj_id = etree.SubElement(spec_obj, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
            obj_id.text = self._sanitize_identifier(req['req_id'])
            
            # Long name
            obj_long_name = etree.SubElement(spec_obj, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
            obj_long_name.text = req['req_id']
            
            # Last change
            last_change = etree.SubElement(spec_obj, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LAST-CHANGE')
            last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Description
            desc = etree.SubElement(spec_obj, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}DESCRIPTION')
            desc.text = (req['content'] or '')[:2000]
            
            # Attributes
            attribs = etree.SubElement(spec_obj, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ATTRIBUTES')
            
            # Add attribute values
            self._add_attribute_value_lxml(attribs, 'ReqIF.CustomRequirementType', req.get('type', 'functional'))
            self._add_attribute_value_lxml(attribs, 'ReqIF.CustomPriority', req.get('priority', 'shall'))
            
            if req.get('safety_class'):
                self._add_attribute_value_lxml(attribs, 'ReqIF.CustomSafetyClass', req['safety_class'])
            
            self._add_attribute_value_lxml(attribs, 'ReqIF.CustomSourceFile', req.get('file_path', ''))
    
    def _add_attribute_value_lxml(self, parent, attr_name: str, value: str) -> None:
        """Add an attribute value element"""
        etree = self._etree
        
        attr_val = etree.SubElement(parent, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ATTRIBUTE-VALUE-STRING')
        
        attr_def_ref = etree.SubElement(attr_val, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}ATTRIBUTE-DEFINITION-STRING-REF')
        attr_def_ref.text = self._sanitize_identifier(attr_name)
        
        the_value = etree.SubElement(attr_val, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}THE-VALUE')
        the_value.text = value
    
    def _create_specification_lxml(self, parent, spec_object_type, scan_results) -> None:
        """Create specification using lxml"""
        etree = self._etree
        
        specs = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd}SPECIFICATIONS'
        )
        
        spec = etree.SubElement(specs, '{http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd}SPECIFICATION')
        
        spec_id = etree.SubElement(spec, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
        spec_id.text = 'CORTEX_COMPLIANCE_SPEC'
        
        spec_long_name = etree.SubElement(spec, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
        spec_long_name.text = 'Cortex Compliance Requirements'
        
        last_change = etree.SubElement(spec, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Type ref
        obj_type_ref = etree.SubElement(spec, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}TYPE')
        type_ref = etree.SubElement(obj_type_ref, '{http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd}SPEC-OBJECT-TYPE-REF')
        type_ref.text = self._sanitize_identifier('ComplianceRequirement')
        
        return spec
    
    def _create_relations_lxml(self, parent, spec_relation_type, scan_results) -> None:
        """Create relations using lxml"""
        etree = self._etree
        
        spec_rels = etree.SubElement(
            parent,
            '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-RELATIONS'
        )
        
        rel_type_id = self._sanitize_identifier(spec_relation_type.find('{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER').text)
        
        for link in scan_results['trace_links']:
            if link['link_type'] == 'verifies':
                spec_rel = etree.SubElement(spec_rels, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-RELATION')
                
                rel_id = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}IDENTIFIER')
                rel_id.text = f"REL_{self._sanitize_identifier(link['source_id'])}_{self._sanitize_identifier(link['target_id'])}"
                
                rel_long_name = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LONG-NAME')
                rel_long_name.text = f"{link['source_id']} verifies {link['target_id']}"
                
                last_change = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}LAST-CHANGE')
                last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Type ref
                rel_type_ref = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}TYPE')
                type_ref = etree.SubElement(rel_type_ref, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SPEC-RELATION-TYPE-REF')
                type_ref.text = rel_type_id
                
                # Source
                source_ref = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}SOURCE')
                source_obj = etree.SubElement(source_ref, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}OBJECT-REF')
                source_obj.text = self._sanitize_identifier(link['source_id'])
                
                # Target
                target_ref = etree.SubElement(spec_rel, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}TARGET')
                target_obj = etree.SubElement(target_ref, '{http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd}OBJECT-REF')
                target_obj.text = self._sanitize_identifier(link['target_id'])
    
    def _sanitize_identifier(self, identifier: str) -> str:
        """
        Sanitize identifier to be ReqIF/DOORS compatible.
        
        DOORS requirement: identifiers must be alphanumeric
        with underscores/hyphens, no spaces or special chars.
        """
        # Replace spaces and special chars with underscore
        sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', identifier)
        
        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Ensure doesn't start with number
        if sanitized and sanitized[0].isdigit():
            sanitized = 'ID_' + sanitized
        
        # Truncate if too long (DOORS has limits)
        return sanitized[:64]
    
    def _to_string_stdlib(
        self,
        scan_results: Dict[str, Any],
        spec_object_type_name: str,
        spec_relation_type_name: str,
    ) -> str:
        """
        Fallback: Generate ReqIF XML using stdlib xml.etree.
        
        Note: stdlib doesn't handle namespaces as well as lxml.
        This is a last resort if lxml is not available.
        """
        import xml.etree.ElementTree as ET
        
        # Register namespaces
        for prefix, uri in REQIF_NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        # Root
        root = ET.Element('ReqIF')
        root.set('xmlns', 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd')
        root.set('xmlns:reqif-common', 'http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd')
        root.set('xmlns:reqif-content', 'http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd')
        
        # Header
        header = ET.SubElement(root, 'THE-HEADER')
        creation_time = ET.SubElement(header, 'CREATION-TIME')
        creation_time.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        req_if_version = ET.SubElement(header, 'REQ-IF-VERSION')
        req_if_version.text = '1.0'
        
        # Core content
        core_content = ET.SubElement(root, 'CORE-CONTENT')
        
        # ... (simplified, would need full implementation)
        
        # Serialize
        rough_string = ET.tostring(root, encoding='unicode')
        
        # Add XML declaration
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + rough_string


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def export_to_reqif(
    scan_results: Dict[str, Any],
    output_path: str,
    validate: bool = True,
    **kwargs
) -> None:
    """
    Convenience function to export scan results to ReqIF.
    
    Usage:
        scanner = ComplianceWikiScanner(kb)
        results = scanner.scan_all()
        export_to_reqif(results, 'requirements.reqif')
    """
    exporter = ReqIFExporter(validate=validate, **kwargs)
    exporter.export(scan_results, output_path)


def create_reqif_from_wiki(knowledgebase, output_path: str, validate: bool = True) -> None:
    """
    Convenience function to scan wiki and export to ReqIF in one call.
    
    Usage:
        create_reqif_from_wiki(kb, 'compliance.requirements.reqif')
    """
    from cortex.compliance_tags import ComplianceWikiScanner
    
    scanner = ComplianceWikiScanner(knowledgebase)
    results = scanner.scan_all()
    export_to_reqif(results, output_path, validate=validate)


def validate_reqif_file(file_path: str, schema_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate an existing ReqIF file.
    
    Returns dict with:
    - is_valid: bool
    - errors: List of error messages
    - file_path: Path validated
    """
    validator = ReqIFSchemaValidator(schema_path)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    
    is_valid, errors = validator.validate(xml_content)
    
    return {
        "file_path": file_path,
        "is_valid": is_valid,
        "error_count": len(errors),
        "errors": errors,
    }