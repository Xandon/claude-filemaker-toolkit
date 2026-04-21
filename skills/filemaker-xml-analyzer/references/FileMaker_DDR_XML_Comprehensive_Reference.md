# FileMaker Pro DDR XML Format Comprehensive Reference

## Executive Summary

This document provides a thorough research compilation on FileMaker Pro's "Save As XML" (Database Design Report - DDR) XML format. It covers the XML structure, script step encoding, tools for parsing and manipulation, and resources for developers working with FileMaker database metadata.

---

## 1. DDR XML Format Overview

### What is DDR (Database Design Report)?

The **Database Design Report (DDR)** is a comprehensive XML representation of a FileMaker Pro database's structure generated through FileMaker Pro Advanced. It is NOT the database itself (no record data), but rather complete documentation of all structural elements.

#### Accessing DDR Generation
- In FileMaker Pro Advanced: **Tools > Database Design Report**
- Choose **XML format** as the output
- Supported in FileMaker Pro versions 8 and later
- All solution files must be checked during generation

### DDR vs. Save As XML

There are two related but distinct XML outputs:

1. **Database Design Report (DDR) XML**
   - Accessed via Tools > Database Design Report
   - Contains comprehensive structural metadata
   - Most detailed reference format
   - Used by analysis tools like BaseElements

2. **Save a Copy as XML**
   - Menu: File > Save a Copy As
   - Script step availability for automation
   - Similar content to DDR but in different structure
   - **ENCODING NOTE**: Produces UTF-16 format (not UTF-8) - requires conversion for many tools

---

## 2. DDR XML Top-Level Structure

### Root Element

```xml
<FMSaveAsXML version="2.2.2.0" product="FileMaker Pro Advanced" creator="...">
  <!-- Content organized in catalogs -->
</FMSaveAsXML>
```

**Attributes:**
- `version`: XML format version (e.g., 2.2.2.0)
- `product`: FileMaker product name and version
- `creator`: Name of database file

### Main Catalog Sections

The top-level structure contains 10 primary catalogs:

1. **BaseTableCatalog** - Base table definitions (not table occurrences)
2. **RelationshipGraph** - Relationship graph visualization and structure
3. **LayoutCatalog** - Layout definitions with all layout objects
4. **ValueListCatalog** - Value list definitions
5. **ScriptCatalog** - Script definitions with step details
6. **AccountCatalog** - User account definitions
7. **PrivilegesCatalog** - Basic privilege set definitions
8. **ExtendedPrivilegeCatalog** - Extended privilege settings
9. **CustomFunctionCatalog** - Custom function definitions
10. **Options** - File-level options and settings

---

## 3. ScriptCatalog Structure

### Hierarchy

```
ScriptCatalog
  └─ Script (multiple)
      ├─ Name
      ├─ UUID
      ├─ StepList
      │   └─ Step (multiple)
      │       ├─ id (numeric step type identifier)
      │       ├─ name (human-readable step name)
      │       ├─ enable (True/False)
      │       ├─ Options / Calculation / Value elements
      │       └─ Params
      └─ ScriptParameter
```

### Script Element Attributes

- `id`: Unique script identifier (UUID format)
- `name`: Display name of script
- `source`: Indicates if external module

### Step Element Structure

```xml
<Step id="6" name="Go to Layout" enable="True">
  <Calculation/>
  <Value/>
  <Options/>
</Step>
```

**Key Step Attributes:**
- `id`: Numeric identifier mapping to script step type
- `name`: Human-readable step name
- `enable`: Boolean (True/False) - whether step executes
- `Options`: Step-specific configuration parameters
- `Calculation`: CDATA sections for calculation expressions
- `Restore`: Position/size restoration info for certain steps

### StepsForScripts Reference

Some steps contain `<StepsForScripts>` elements that reference other scripts, maintaining cross-references between script calls:

```xml
<StepsForScripts>
  <ScriptReference id="[script-uuid]" name="[script-name]"/>
</StepsForScripts>
```

---

## 4. Script Step IDs and Types

### General Categories

FileMaker organizes script steps into functional categories:

- **Navigation Steps**: Go to Layout, Go to Record, Go to Portal Row, etc.
- **Editing Steps**: Set Field, Find, Replace, etc.
- **Control Steps**: If/Else, Loop, etc.
- **Script Steps**: Perform Script, Exit Script, etc.
- **UI Steps**: Show Dialog, Show Custom Dialog, etc.
- **File Steps**: Open File, Close File, etc.
- **Windows Steps**: New Window, Close Window, etc.
- **Clipboard Steps**: Copy, Cut, Paste, etc.
- **Miscellaneous Steps**: Comment, Pause, Wait, Halt Script, etc.

### Accessing Script Step ID Reference

The complete authoritative list of script step IDs is available at:
- **Official Claris Documentation**: https://help.claris.com/en/pro-help/content/script-steps-reference.html
- **FMWorkmate Reference**: https://fmworkmate.com/script-step-ids.html
- **Version-Specific PDFs**: Available for FileMaker Pro 14, 15, and other versions

**Important**: Script step IDs may vary between FileMaker versions. Always reference documentation for your specific version.

### Example Known Step Types

While the exact complete mapping requires consulting the official reference, common script steps include:
- `id="6"`: Go to Layout
- `id="22"`: Enter Find Mode
- `id="89"`: Comment (# in notation)
- Various numeric IDs for other steps (exact numbers version-dependent)

---

## 5. FieldsForTables Structure

### Hierarchy

```
BaseTableCatalog
  └─ BaseTable
      ├─ Name
      ├─ UUID
      ├─ FieldCatalog
      │   └─ Field (multiple)
      │       ├─ Name
      │       ├─ UUID
      │       ├─ Type (Text, Number, Date, etc.)
      │       ├─ Calculation
      │       ├─ Summary
      │       └─ ValidationScript
      └─ FieldsList (summary of field references)
```

### Field Definition Elements

- **Name**: Field display name
- **Type**: Data type (Text, Number, Date, Time, Timestamp, Container, Calculation, Summary)
- **Options**: Field-specific options (repeating fields, auto-enter settings, etc.)
- **ValidationScript**: Field validation calculation or script reference
- **Comment**: Field documentation/notes
- **UUID**: Unique identifier for field

### Relationships to Tables

Field definitions reference base tables through parent-child XML hierarchy and UUID cross-references.

---

## 6. LayoutCatalog Structure

### Hierarchy

```
LayoutCatalog
  └─ Layout (multiple)
      ├─ Name
      ├─ UUID
      ├─ BaseTable (reference to base table)
      ├─ Objects
      │   └─ Object (multiple layout elements)
      │       ├─ Type (Field, Button, Text, Portal, etc.)
      │       ├─ Name
      │       ├─ Bounds (position/size information)
      │       ├─ Style
      │       └─ Content (field references, calculations, etc.)
      └─ Themes (applied themes/formatting)
```

### Layout Object Attributes

- **Type**: Object type (Field, Button, Portal, WebViewer, etc.)
- **Bounds**: X, Y, width, height coordinates
- **Style**: Font, color, formatting attributes
- **Name**: Object identifier/name
- **Content**: References to fields, values, or calculations

---

## 7. RelationshipGraph Structure

### Hierarchy

```
RelationshipGraph
  ├─ TableOccurrencesList
  │   └─ TableOccurrence (multiple)
  │       ├─ Name
  │       ├─ UUID
  │       ├─ BaseTableRef (reference to base table)
  │       ├─ GraphPosition (x, y coordinates on graph)
  │       └─ Color (visual color on graph)
  └─ RelationshipsList
      └─ Relationship (multiple)
          ├─ Name
          ├─ UUID
          ├─ LeftTableOccurrence
          ├─ RightTableOccurrence
          ├─ JoinType (inner, left, full outer, etc.)
          └─ PredicateList
              └─ Predicate (join condition)
```

### Table Occurrence (TO) Encoding

- **UUID**: Universally unique identifier for portability
- **Version tracking**: Modification history stored within UUID tag
- **Color**: Visual representation on relationship graph
- **Position**: X/Y coordinates showing layout on graph

### Relationship Predicates

Each relationship's join conditions are expressed as:
```xml
<Predicate>
  <LeftFieldRef UUIDRef="[field-uuid]"/>
  <JoinType>eq</JoinType>
  <RightFieldRef UUIDRef="[field-uuid]"/>
</Predicate>
```

---

## 8. ValueListCatalog Structure

### Hierarchy

```
ValueListCatalog
  └─ ValueList (multiple)
      ├─ Name
      ├─ UUID
      ├─ ListElements
      │   └─ ListElement (multiple)
      │       └─ Value
      └─ ListSource (for field-based value lists)
          ├─ TableOccurrence
          ├─ Field
          └─ SortField (optional)
```

### Value List Types

1. **Static Value Lists**: Hard-coded values in `<ListElements>`
2. **Field-Based Value Lists**: Dynamic from table occurrence field reference
3. **Custom Value Lists**: With unique value determination

---

## 9. Script Reference Elements

### ScriptReference Structure

Used throughout DDR for cross-referencing scripts:

```xml
<ScriptReference id="[script-uuid]" name="[script-name]"/>
```

### Where Script References Appear

1. **Perform Script steps**: Reference the called script
2. **Button events**: Reference script to execute
3. **Custom menu items**: Reference associated scripts
4. **Script dependencies**: Track what scripts call what
5. **FileMaker Server schedules**: Reference scripts to execute

### Benefits for Analysis

ScriptReference elements enable:
- Building dependency graphs (which scripts call which)
- Understanding script flow and relationships
- Identifying unused/orphaned scripts
- Change impact analysis

---

## 10. FileMaker Clipboard XML Format (MBS Plugin)

### Clipboard FMObjectList Structure

When you copy FileMaker objects (scripts, script steps, fields, layouts, etc.), they are stored as XML that can be converted to text.

```xml
<fmxmlsnippet type="FMObjectList">
  <Step enable="True" id="[step-id]" name="[step-name]">
    <Calculation>
      <![CDATA[calculation expression here]]>
    </Calculation>
    <Value>[value]</Value>
    <Repetition>[rep-number]</Repetition>
    <Options>
      <Option name="..." value="..."/>
    </Options>
  </Step>
</fmxmlsnippet>
```

### Supported Object Types

Objects that can be copied as XML snippets:
- `Script` - Full script definitions
- `ScriptStep` - Individual script steps
- `Field` - Field definitions
- `Table` - Table definitions
- `ValueList` - Value list definitions
- `Layout` - Layout definitions
- `CustomFunction` - Custom function definitions

### Clipboard to FileMaker Workflow

1. **Copy from FileMaker** → Clipboard contains XML
2. **Extract as Text** → Use Clipboard.GetText or text conversion tools
3. **Edit XML** → Modify step definitions, calculations, etc.
4. **Convert back** → Use Clipboard.SetFileMakerData or tools
5. **Paste to FileMaker** → Rebuilds objects from XML

---

## 11. MBS Plugin Clipboard Functions

### Key Functions for XML Manipulation

#### Clipboard.SetFileMakerData
```
Clipboard.SetFileMakerData(xmlText; type)
```

**Parameters:**
- `xmlText`: Valid FileMaker XML for the object type
- `type`: Object type (ValueList, Script, ScriptStep, Layout, CustomFunction, Table, Field, Layout12)

**Purpose:** Places FileMaker XML on clipboard ready to paste into FileMaker

#### Clipboard.AddText
```
Clipboard.AddText(text)
```

**Purpose:** Adds text to clipboard alongside FileMaker XML

### Clipboard Converter Feature

The MBS SyntaxColoring extension includes an automatic clipboard converter that:
- Converts FileMaker clipboard XML to plain text
- Allows editing in text editors
- Converts back to FileMaker clipboard format
- Preserves XML formatting for round-trip conversion

---

## 12. MBS Plugin Blog Resources

### Key Articles

**"Copy and paste XML in FileMaker"**
- Demonstrates practical workflows for clipboard XML manipulation
- Shows how to edit FileMaker objects as text
- Details the FMObjectList XML structure

**"Use Saxon to query details from FileMaker's Save as XML files"**
- XPath query examples for DDR/Save As XML analysis
- Saxon XML processor for advanced queries
- Integration patterns for automated analysis

**MBS Plugin Version Updates**
- Version 15.4 and later include enhanced clipboard handling
- Progressive improvements in XML conversion accuracy

---

## 13. Python Libraries and Tools for Parsing

### Existing Python Tools

#### FileMaker-DDR-Splitter
- **GitHub**: karstenw/FileMaker-DDR-Splitter
- **Purpose**: Splits FileMaker DDR XML into component files
- **Language**: Python
- **Approach**: Parses XML hierarchy and separates catalog sections

#### migrate-filemaker
- **GitHub**: solutionscay/migrate-filemaker
- **Components**: Includes parse_ddr.py script
- **Purpose**: Parses DDR XML and extracts JSON specifications
- **Useful for**: Migration from FileMaker to other platforms

### Standard Python XML Libraries

For custom DDR parsing projects:

1. **xml.etree.ElementTree**
   - Built-in standard library
   - Good for simple to moderate complexity XML
   - Decent performance
   - DOM-like interface

2. **lxml**
   - Third-party library (faster than ElementTree)
   - XPath support for complex queries
   - Better performance on large files
   - C implementation for speed

3. **xml.dom.minidom**
   - Built-in standard library
   - Full DOM compliance
   - Memory-intensive for large files
   - Good for specific DOM operations

### Recommended Approach

For FileMaker DDR parsing:
- Use `lxml` with XPath queries for analysis
- Use `xml.etree.ElementTree` for basic extraction
- Use `json` library to output structured data
- Consider XSLT (via lxml or Saxon) for complex transformations

---

## 14. BaseElements DDR Analysis

### BaseElements Approach

BaseElements (commercial FileMaker solution) uses:
- **XSLT transformation** to extract data from DDR XML
- **XML catalog import** via FileReference interface
- **Comprehensive analysis** leveraging DDR references

### BaseElements DDR XSLT Library

**GitHub**: GoyaPtyLtd/BaseElements-DDR-XSLT

Contains production XSLT stylesheets for:
- Extracting script information
- Building dependency graphs
- Analyzing layout usage
- Field reference tracking
- Relationship analysis

### Key Advantage Over Newer XML

The DDR format includes **"references"** (places things are used) that are not present in newer Save As XML exports, making DDR particularly valuable for impact analysis.

---

## 15. DDR XML Tools and Utilities

### Commercial Tools

#### 2empowerFM Clipboard Explorer
- **Developer**: Dracoventions
- **Type**: Free FileMaker plugin
- **Features**:
  - Examine clipboard contents
  - Convert FileMaker objects to XML text
  - Save/restore clipboard snippets
  - Visual XML editor for scripts
  - Categorize reusable objects

#### BaseElements
- **Type**: Commercial FileMaker solution
- **Features**:
  - DDR import and analysis
  - Relationship visualization
  - Script dependency tracking
  - Field reference analysis
  - Code change detection

### Open Source Tools

#### SharpFM
- **GitHub**: fuzzzerd/SharpFM
- **Platforms**: Mac, Windows, Linux (cross-platform)
- **Type**: Standalone application
- **Features**:
  - Copy FileMaker objects to XML snippets
  - Convert XML snippets back to FileMaker clipboard format
  - Store/share FileMaker scripts and schema
  - Enable code sharing across machines (RDP, Citrix, plain text)
  - Edit FileMaker code outside FileMaker

#### FmClipTools
- **GitHub**: DanShockley/FileMaker-CRUD-Script
- **Type**: AppleScript (macOS)
- **Features**:
  - Convert FileMaker objects to/from XML
  - Search and replace within clipboard XML
  - Bulk replicate objects
  - AppleScript integration

### Online DDR Readers

**XML DDR Reader Discussion**
- Community forum topic: the.fmsoup.org/t/xml-ddr-reader/1246
- Discussion of tools for analyzing DDR output
- Links to various parsing utilities

---

## 16. Official Documentation References

### Claris/FileMaker DDR XML Grammar Documentation

**Current Versions:**
- [Claris FileMaker Pro 19 Database Design Report XML Output Grammar](https://help.claris.com/archive/fm19/en/pro-db-design-report-xml-grammar/)
- [FileMaker Pro 18 Advanced Database Design Report XML Output Grammar](https://fmhelp.filemaker.com/docs/18/en/ddrxml/)
- [FileMaker Pro 17 Advanced Database Design Report XML Output Grammar](https://fmhelp.filemaker.com/docs/17/en/ddrxml/)

**Archived Versions:**
- FileMaker Pro 16: https://fmhelp.filemaker.com/docs/16/en/ddrxml/
- FileMaker Pro 15: https://help.claris.com/archive/docs/15/en/ddrxml/
- FileMaker Pro 14: https://help.claris.com/archive/docs/14/en/ddrxml/
- FileMaker Pro 13: https://help.claris.com/archive/docs/13/en/fmpa13_ddr_xml_grammar.pdf

### Save As XML Documentation

- [Save a Copy as XML - Claris FileMaker Pro Help](https://help.claris.com/en/pro-help/content/save-a-copy-as-xml.html)
- [Save a Copy as XML - FileMaker Pro 18](https://help.claris.com/archive/help/18/fmp/en/FMP_Help/save-a-copy-as-xml.html)

### Script Steps Reference

- [Script steps reference - Claris FileMaker Pro Help](https://help.claris.com/en/pro-help/content/script-steps-reference.html)
- [Script Step IDs Reference - FMWorkmate](https://fmworkmate.com/script-step-ids.html)

---

## 17. Important Technical Considerations

### UTF-16 vs UTF-8 Encoding

**Critical Issue**: The "Save a Copy as XML" script step produces **UTF-16 format** XML, not UTF-8.

**Implications:**
- Not directly compatible with many XML parsing tools expecting UTF-8
- Requires conversion before processing with standard tools
- XPath queries may fail without encoding conversion
- Text editors may display incorrectly without proper codec

**Solutions:**
- Use iconv or similar tools to convert UTF-16 to UTF-8
- Specify encoding in parsing libraries: `encoding='utf-16'`
- Use Claris's official tools designed for the output format

### Version Compatibility

**Critical**: XML format changes between FileMaker versions.

**Best Practice:**
- Always use same FileMaker version to generate both source and comparison XMLs
- Document which version generated DDR/XML files
- Archive version-specific parsing rules
- Test parsing logic against multiple versions

### File Size Considerations

**For Large Databases:**
- DDR XML files can be very large
- Use streaming XML parsers rather than DOM parsers for huge files
- Consider XSLT processing for transformations
- May cause FileMaker Pro to appear locked during generation

---

## 18. Workflow Examples

### Analyzing Script Structure

1. Generate DDR in XML format from FileMaker Pro Advanced
2. Use Python with lxml to parse ScriptCatalog section
3. Extract all Step elements with attributes
4. Cross-reference script IDs with official documentation
5. Build dependency graph from ScriptReference elements
6. Export analysis to JSON/CSV for reporting

### Extracting Relationship Information

1. Parse RelationshipGraph XML section
2. Build TableOccurrence dictionary (UUID → TO name)
3. Extract relationships with join predicates
4. Map base table UUIDs to names
5. Create relationship diagram representation
6. Identify orphaned or unused table occurrences

### Modifying Scripts via XML

1. Copy script steps from FileMaker (clipboard XML)
2. Convert to text using Clipboard Explorer or MBS plugin
3. Edit Step XML structure (id, options, calculations)
4. Convert back to clipboard XML format
5. Paste modified steps into FileMaker
6. Verify functionality in FileMaker

### Comparing Databases

1. Generate DDR XML from version A
2. Generate DDR XML from version B (same FM version)
3. Parse both files to extract comparable structures
4. Use diff tools to identify schema changes
5. Flag breaking changes or field type modifications
6. Export change report for documentation

---

## 19. Key Resources Summary

### Official Documentation
- Claris FileMaker Help (help.claris.com)
- FileMaker Script Steps Reference
- DDR XML Output Grammar (version-specific)

### Community Resources
- the.fmsoup.org - Independent FileMaker Forum
- FMForums.com - FileMaker Discussions
- FMWorkmate - Script Step ID Reference

### Tools and Libraries
- **MBS Plugin** - Clipboard manipulation with FMObjectList support
- **2empowerFM** - Free Clipboard Explorer plugin
- **SharpFM** - Cross-platform XML conversion tool
- **FmClipTools** - AppleScript for clipboard conversion
- **BaseElements** - Commercial DDR analysis solution
- **lxml (Python)** - Fast XPath-capable XML parsing

### GitHub Projects
- FileMaker-DDR-Splitter (karstenw)
- BaseElements-DDR-XSLT (GoyaPtyLtd)
- SharpFM (fuzzzerd)
- migrate-filemaker (solutionscay)
- FmClipTools (DanShockley)

---

## 20. Next Steps for Implementation

### For Parsing Projects

1. **Determine Target FileMaker Version** - Use appropriate DDR documentation
2. **Handle UTF-16 Encoding** - Convert Save As XML output to UTF-8
3. **Choose Parsing Library** - lxml recommended for large files with XPath
4. **Reference Official DTD** - Consult version-specific grammar documentation
5. **Implement Step ID Mapping** - Create lookup table for script step IDs
6. **Handle CDATA Sections** - Properly parse calculation expressions
7. **Track UUID References** - Build cross-reference maps for lookups
8. **Test Against Multiple Versions** - Verify parser works across FM versions

### For Clipboard XML Projects

1. **Understand FMObjectList Format** - Study example clipboard contents
2. **Use MBS Plugin or Alternatives** - Select appropriate tool for conversion
3. **Round-trip Testing** - Verify copy→edit→paste workflow
4. **Preserve Attributes** - Maintain id, enable, and name attributes
5. **Handle CDATA Content** - Preserve calculation expressions accurately
6. **Document XML Schema** - Create reference for supported elements

---

## Conclusion

FileMaker's DDR XML format provides comprehensive structural metadata for analysis, migration, and development tooling. The format has been evolving across versions, with official documentation available for all modern FileMaker releases. Multiple tools exist for both clipboard XML manipulation and DDR analysis, enabling developers to build sophisticated FileMaker development workflows.

Key considerations include:
- Version-specific XML differences
- UTF-16 encoding issues in Save As XML script step
- Cross-reference and UUID management
- Choice of parsing approach (DOM vs streaming)
- Availability of production tools (BaseElements, MBS, SharpFM)

The research compiled here provides a foundation for understanding and working with FileMaker's XML formats in custom development projects.
