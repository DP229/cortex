"""
Cortex ReqIF Export - Enterprise Interoperability

Phase 2 Enhancement: Exports tagged requirements to ReqIF format
for integration with enterprise requirements management tools.

ReqIF (Requirements Interchange Format) is an ISO standard
(ISO/IEC 29100) for exchanging requirements data between tools.

Supported Tools:
- IBM DOORS
- PTC Codebeamer
- JAMA Connect
- Siemens Polarion
- SAP Solution Manager

This module provides:
- ReqIF XML generation from tagged requirements
- Requirement hierarchy support
- Attribute mapping for standard compliance
- Type definitions for IEC 62304 / EN 50128
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ReqIF namespace definitions
REQIF_NS = {
    'reqif': 'http://www.omg.org/spec/ReqIF/20110401/reqif.xsd',
    'reqif-common': 'http://www.omg.org/spec/ReqIF/20110401/reqif_common.xsd',
    'reqif-content': 'http://www.omg.org/spec/ReqIF/20110401/reqif_content.xsd',
    'reqif-hardware': 'http://www.omg.org/spec/ReqIF/20110401/reqif_hardware.xsd',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}


@dataclass
class ReqIFAttributeDefinition:
    """Definition of a custom attribute"""
    name: str
    data_type: str  # string, integer, boolean, enumeration, date, real
    description: Optional[str] = None
    default_value: Optional[str] = None
    enumeration_values: Optional[List[str]] = None


class ReqIFExporter:
    """
    Exports Cortex requirements to ReqIF format.
    
    Generates valid ReqIF XML files that can be imported into
    enterprise requirements management tools.
    """
    
    def __init__(
        self,
        tool_name: str = "Cortex Compliance Engine",
        tool_vendor: str = "Cortex",
        tool_version: str = "1.0",
    ):
        self.tool_name = tool_name
        self.tool_vendor = tool_vendor
        self.tool_version = tool_version
        self.attribute_defs: List[ReqIFAttributeDefinition] = []
        self._setup_default_attributes()
    
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
        Export scan results to ReqIF file.
        
        Args:
            scan_results: Output from ComplianceWikiScanner.scan_all()
            output_path: Path to write ReqIF XML file
            spec_object_type_name: Name for the requirement type
            spec_relation_type_name: Name for the traceability relation type
        """
        root = self._create_reqif_header()
        
        # Add core content
        core_content = ET.SubElement(root, 'reqif-content:CORE-CONTENT')
        
        # Create datatype definitions
        datatypes = self._create_datatypes(core_content)
        
        # Create spec relation type
        spec_relation_type = self._create_spec_relation_type(
            core_content, spec_relation_type_name
        )
        
        # Create spec object type (requirement type)
        spec_object_type = self._create_spec_object_type(
            core_content, spec_object_type_name, datatypes
        )
        
        # Create specification (requirement hierarchy)
        spec = self._create_specification(
            core_content, spec_object_type, scan_results
        )
        
        # Create relations between requirements and tests
        self._create_relations(core_content, spec_relation_type, scan_results)
        
        # Write to file
        self._write_xml(root, output_path)
        logger.info(f"Exported ReqIF to {output_path}")
    
    def _create_reqif_header(self) -> ET.Element:
        """Create the ReqIF header structure"""
        # Create root with namespace
        root = ET.Element('ReqIF')
        root.set('xmlns', REQIF_NS['reqif'])
        root.set('xmlns:reqif-common', REQIF_NS['reqif-common'])
        root.set('xmlns:reqif-content', REQIF_NS['reqif-content'])
        root.set('xmlns:xhtml', REQIF_NS['xhtml'])
        
        # THE-HEADER
        header = ET.SubElement(root, 'THE-HEADER')
        
        # CREATION-TIME
        creation_time = ET.SubElement(header, 'CREATION-TIME')
        creation_time.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # REQ-IF-VERSION
        req_if_version = ET.SubElement(header, 'REQ-IF-VERSION')
        req_if_version.text = '1.0'
        
        # TOOL-IDS
        tool_ids = ET.SubElement(header, 'TOOL-IDS')
        
        # SOURCE-TOOL-IDS
        source_tool = ET.SubElement(tool_ids, 'SOURCE-TOOL-ID')
        source_tool.set('TOOL', self.tool_name)
        source_tool.set('VENDOR', self.tool_vendor)
        source_tool.set('VERSION', self.tool_version)
        
        return root
    
    def _create_datatypes(self, parent: ET.Element) -> Dict[str, ET.Element]:
        """Create datatype definitions"""
        datatypes = {}
        datatypes_container = ET.SubElement(parent, 'reqif-content:DATATYPES')
        
        # String datatype
        string_type = ET.SubElement(datatypes_container, 'reqif-common:STRING-DATATYPE')
        dt_id = ET.SubElement(string_type, 'reqif-common:IDENTIFIER')
        dt_id.text = 'STRING'
        dt_long_name = ET.SubElement(string_type, 'reqif-common:LONG-NAME')
        dt_long_name.text = 'String'
        datatypes['string'] = string_type
        
        # Integer datatype
        int_type = ET.SubElement(datatypes_container, 'reqif-common:INTEGER-DATATYPE')
        dt_id = ET.SubElement(int_type, 'reqif-common:IDENTIFIER')
        dt_id.text = 'INTEGER'
        dt_long_name = ET.SubElement(int_type, 'reqif-common:LONG-NAME')
        dt_long_name.text = 'Integer'
        datatypes['integer'] = int_type
        
        # Boolean datatype
        bool_type = ET.SubElement(datatypes_container, 'reqif-common:BOOLEAN-DATATYPE')
        dt_id = ET.SubElement(bool_type, 'reqif-common:IDENTIFIER')
        dt_id.text = 'BOOLEAN'
        dt_long_name = ET.SubElement(bool_type, 'reqif-common:LONG-NAME')
        dt_long_name.text = 'Boolean'
        datatypes['boolean'] = bool_type
        
        # Enumeration datatype for verification method
        enum_type = ET.SubElement(datatypes_container, 'reqif-common:ENUM-DATATYPE')
        dt_id = ET.SubElement(enum_type, 'reqif-common:IDENTIFIER')
        dt_id.text = 'VERIFICATION-METHOD'
        dt_long_name = ET.SubElement(enum_type, 'reqif-common:LONG-NAME')
        dt_long_name.text = 'Verification Method'
        spec_values = ET.SubElement(enum_type, 'reqif-common:SPEC-VALUES')
        for val in ['Inspection', 'Analysis', 'Test', 'Demonstration']:
            spec_val = ET.SubElement(spec_values, 'reqif-common:SPEC-VALUE')
            sv_id = ET.SubElement(spec_val, 'reqif-common:IDENTIFIER')
            sv_id.text = val.upper()
            sv_long_name = ET.SubElement(spec_val, 'reqif-common:LONG-NAME')
            sv_long_name.text = val
        datatypes['enumeration'] = enum_type
        
        return datatypes
    
    def _create_spec_relation_type(
        self,
        parent: ET.Element,
        name: str
    ) -> ET.Element:
        """Create the spec relation type for traceability"""
        spec_types = ET.SubElement(parent, 'reqif-content:SPEC-RELATION-TYPES')
        
        spec_rel_type = ET.SubElement(spec_types, 'reqif-content:SPEC-RELATION-TYPE')
        
        # Identifier
        type_id = ET.SubElement(spec_rel_type, 'reqif-common:IDENTIFIER')
        type_id.text = name.upper().replace(' ', '_')
        
        # Long name
        type_long_name = ET.SubElement(spec_rel_type, 'reqif-common:LONG-NAME')
        type_long_name.text = name
        
        # Last change
        last_change = ET.SubElement(spec_rel_type, 'reqif-common:LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        return spec_rel_type
    
    def _create_spec_object_type(
        self,
        parent: ET.Element,
        name: str,
        datatypes: Dict[str, ET.Element]
    ) -> ET.Element:
        """Create the spec object type (requirement type) with attributes"""
        spec_types = ET.SubElement(parent, 'reqif-content:SPEC-OBJECT-TYPES')
        
        spec_obj_type = ET.SubElement(spec_types, 'reqif-content:SPEC-OBJECT-TYPE')
        
        # Identifier
        type_id = ET.SubElement(spec_obj_type, 'reqif-common:IDENTIFIER')
        type_id.text = name.upper().replace(' ', '_')
        
        # Long name
        type_long_name = ET.SubElement(spec_obj_type, 'reqif-common:LONG-NAME')
        type_long_name.text = name
        
        # Last change
        last_change = ET.SubElement(spec_obj_type, 'reqif-common:LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Attributes
        spec_attribs = ET.SubElement(spec_obj_type, 'reqif-common:SPEC-ATTRIBUTES')
        
        # Add custom attributes
        for attr_def in self.attribute_defs:
            attrib = ET.SubElement(spec_attribs, 'reqif-common:ATTRIBUTE-DEFINITION-STRING')
            
            attr_id = ET.SubElement(attrib, 'reqif-common:IDENTIFIER')
            attr_id.text = attr_def.name.upper().replace('.', '_').replace(' ', '_')
            
            attr_long_name = ET.SubElement(attrib, 'reqif-common:LONG-NAME')
            attr_long_name.text = attr_def.name
            
            attr_type = ET.SubElement(attrib, 'reqif-common:TYPE')
            if attr_def.data_type == 'enumeration':
                type_ref = ET.SubElement(attr_type, 'reqif-common:TYPE')
                type_ref.text = 'VERIFICATION-METHOD'
            else:
                type_ref = ET.SubElement(attr_type, 'reqif-common:TYPE')
                type_ref.text = attr_def.data_type.upper()
        
        return spec_obj_type
    
    def _create_specification(
        self,
        parent: ET.Element,
        spec_object_type: ET.Element,
        scan_results: Dict[str, Any]
    ) -> ET.Element:
        """Create the specification (hierarchy container)"""
        specs = ET.SubElement(parent, 'reqif-content:SPECIFICATIONS')
        
        spec = ET.SubElement(specs, 'reqif-content:SPECIFICATION')
        
        # Identifier
        spec_id = ET.SubElement(spec, 'reqif-common:IDENTIFIER')
        spec_id.text = 'CORTEX_COMPLIANCE_SPEC'
        
        # Long name
        spec_long_name = ET.SubElement(spec, 'reqif-common:LONG-NAME')
        spec_long_name.text = 'Cortex Compliance Requirements'
        
        # Last change
        last_change = ET.SubElement(spec, 'reqif-common:LAST-CHANGE')
        last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Spec object type ref
        obj_type_ref = ET.SubElement(spec, 'reqif-common:TYPE')
        type_ref = ET.SubElement(obj_type_ref, 'reqif-content:SPEC-OBJECT-TYPE-REF')
        type_ref.text = spec_object_type.find('reqif-common:IDENTIFIER').text
        
        # Hierarchy root
        root_hierarchy = ET.SubElement(spec, 'reqif-content:HIERARCHY')
        
        # Object ref (root level - we'll use the first requirement as anchor)
        if scan_results['requirements']:
            first_req = scan_results['requirements'][0]
            obj_ref = ET.SubElement(root_hierarchy, 'reqif-content:OBJECT')
            req_id_ref = ET.SubElement(obj_ref, 'reqif-common:IDENTIFIER-REF')
            req_id_ref.text = first_req['req_id']
        
        # Add all spec objects (requirements)
        self._create_spec_objects(parent, scan_results['requirements'])
        
        return spec
    
    def _create_spec_objects(
        self,
        parent: ET.Element,
        requirements: List[Dict]
    ) -> None:
        """Create spec objects from requirements"""
        spec_objs = ET.SubElement(parent, 'reqif-content:SPEC-OBJECTS')
        
        for req in requirements:
            spec_obj = ET.SubElement(spec_objs, 'reqif-content:SPEC-OBJECT')
            
            # Identifier
            obj_id = ET.SubElement(spec_obj, 'reqif-common:IDENTIFIER')
            obj_id.text = req['req_id']
            
            # Long name (title)
            obj_long_name = ET.SubElement(spec_obj, 'reqif-common:LONG-NAME')
            obj_long_name.text = req['req_id']
            
            # Last change
            last_change = ET.SubElement(spec_obj, 'reqif-common:LAST-CHANGE')
            last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Description (requirement content)
            desc = ET.SubElement(spec_obj, 'reqif-common:DESCRIPTION')
            desc.text = req['content'][:1000] if req['content'] else ''
            
            # Attributes
            attribs = ET.SubElement(spec_obj, 'reqif-common:ATTRIBUTES')
            
            # Requirement type
            attr_type = ET.SubElement(attribs, 'ATTRIBUTE-VALUE-STRING')
            attr_def = ET.SubElement(attr_type, 'ATTRIBUTE-DEFINITION-STRING-REF')
            attr_def.text = 'REQIF_CUSTOMREQUIREMENTTYPE'
            attr_val = ET.SubElement(attr_type, 'reqif-common:THE-VALUE')
            attr_val.text = req.get('type', 'functional')
            
            # Priority
            attr_priority = ET.SubElement(attribs, 'ATTRIBUTE-VALUE-STRING')
            attr_p_def = ET.SubElement(attr_priority, 'ATTRIBUTE-DEFINITION-STRING-REF')
            attr_p_def.text = 'REQIF_CUSTOMPRIORITY'
            attr_p_val = ET.SubElement(attr_priority, 'reqif-common:THE-VALUE')
            attr_p_val.text = req.get('priority', 'shall')
            
            # Safety class
            if req.get('safety_class'):
                attr_sc = ET.SubElement(attribs, 'ATTRIBUTE-VALUE-STRING')
                attr_sc_def = ET.SubElement(attr_sc, 'ATTRIBUTE-DEFINITION-STRING-REF')
                attr_sc_def.text = 'REQIF_CUSTOMSAFETYCLASS'
                attr_sc_val = ET.SubElement(attr_sc, 'reqif-common:THE-VALUE')
                attr_sc_val.text = req['safety_class']
            
            # Source file
            attr_file = ET.SubElement(attribs, 'ATTRIBUTE-VALUE-STRING')
            attr_f_def = ET.SubElement(attr_file, 'ATTRIBUTE-DEFINITION-STRING-REF')
            attr_f_def.text = 'REQIF_CUSTOMSOURCEFILE'
            attr_f_val = ET.SubElement(attr_file, 'reqif-common:THE-VALUE')
            attr_f_val.text = req.get('file_path', '')
    
    def _create_relations(
        self,
        parent: ET.Element,
        spec_relation_type: ET.Element,
        scan_results: Dict[str, Any]
    ) -> None:
        """Create relations between requirements and tests"""
        spec_rels = ET.SubElement(parent, 'reqif-content:SPEC-RELATIONS')
        
        rel_type_id = spec_relation_type.find('reqif-common:IDENTIFIER').text
        
        # Build a map of requirement IDs
        req_ids = {req['req_id'] for req in scan_results['requirements']}
        
        # Add trace links as relations
        for link in scan_results['trace_links']:
            if link['link_type'] == 'verifies':
                spec_rel = ET.SubElement(spec_rels, 'reqif-content:SPEC-RELATION')
                
                # Identifier
                rel_id = ET.SubElement(spec_rel, 'reqif-common:IDENTIFIER')
                rel_id.text = f"REL_{link['source_id']}_{link['target_id']}"
                
                # Long name
                rel_long_name = ET.SubElement(spec_rel, 'reqif-common:LONG-NAME')
                rel_long_name.text = f"{link['source_id']} verifies {link['target_id']}"
                
                # Last change
                last_change = ET.SubElement(spec_rel, 'reqif-common:LAST-CHANGE')
                last_change.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Relation type ref
                rel_type_ref = ET.SubElement(spec_rel, 'reqif-common:TYPE')
                type_ref = ET.SubElement(rel_type_ref, 'reqif-content:SPEC-RELATION-TYPE-REF')
                type_ref.text = rel_type_id
                
                # Source (test)
                source_ref = ET.SubElement(spec_rel, 'reqif-common:SOURCE')
                source_obj = ET.SubElement(source_ref, 'reqif-common:OBJECT-REF')
                source_obj.text = link['source_id']
                
                # Target (requirement)
                target_ref = ET.SubElement(spec_rel, 'reqif-common:TARGET')
                target_obj = ET.SubElement(target_ref, 'reqif-common:OBJECT-REF')
                target_obj.text = link['target_id']
    
    def _write_xml(self, root: ET.Element, output_path: str) -> None:
        """Write XML to file with proper formatting"""
        # Convert to string
        rough_string = ET.tostring(root, encoding='unicode')
        
        # Pretty print with minidom
        reparsed = minidom.parseString(rough_string)
        pretty = reparsed.toprettyxml(indent='  ')
        
        # Remove extra blank lines
        lines = [line for line in pretty.split('\n') if line.strip()]
        pretty = '\n'.join(lines)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(pretty)
    
    def to_string(self, scan_results: Dict[str, Any]) -> str:
        """Export to string instead of file"""
        root = self._create_reqif_header()
        core_content = ET.SubElement(root, 'reqif-content:CORE-CONTENT')
        
        datatypes = self._create_datatypes(core_content)
        spec_relation_type = self._create_spec_relation_type(core_content, "Verifies")
        spec_object_type = self._create_spec_object_type(core_content, "ComplianceRequirement", datatypes)
        spec = self._create_specification(core_content, spec_object_type, scan_results)
        self._create_relations(core_content, spec_relation_type, scan_results)
        
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent='  ')


# === Convenience Functions ===

def export_to_reqif(
    scanner_results: Dict[str, Any],
    output_path: str,
    **kwargs
) -> None:
    """
    Convenience function to export scan results to ReqIF.
    
    Usage:
        scanner = ComplianceWikiScanner(kb)
        results = scanner.scan_all()
        export_to_reqif(results, 'requirements.reqif')
    """
    exporter = ReqIFExporter(**kwargs)
    exporter.export(scanner_results, output_path)


def create_reqif_from_wiki(knowledgebase, output_path: str) -> None:
    """
    Convenience function to scan wiki and export to ReqIF in one call.
    
    Usage:
        create_reqif_from_wiki(kb, 'compliance.requirements.reqif')
    """
    from cortex.compliance_tags import ComplianceWikiScanner
    
    scanner = ComplianceWikiScanner(knowledgebase)
    results = scanner.scan_all()
    export_to_reqif(results, output_path)