# FileMaker Pro DDR XML Structure Map
## LAYER.fmp12 Database

**File:** LAYER.fmp12 (UTF-16 encoded)
**Total Lines:** 966,969
**Version:** FMSaveAsXML 2.2.2.0 (FM21.1.3)
**UUID:** 4F56F7B7-B65A-4C4B-BE57-FBEEA4CC1168
**Locale:** English

---

## 1. TOP-LEVEL STRUCTURE OVERVIEW

The document contains a single `<Structure>` root element with `membercount="2"`, containing two main actions:

| Section | Type | Line Start | Line End | Member Count |
|---------|------|-----------|----------|--------------|
| AddAction (primary) | Structure | 4 | 954,066 | 21 members |
| ModifyAction | Structure | 954,067 | 966,953 | 2 members |

---

## 2. AddAction SECTION (Lines 4-954,066)

### Subsections within AddAction:

| Subsection | Purpose | Line | Member Count |
|-----------|---------|------|--------------|
| BaseDirectoryCatalog | Base directory configuration | ~5 | 1 |
| FileAccessCatalog | File access/authorization settings | ~13 | 11 authorizations |
| ExternalDataSourceCatalog | External data source definitions | ~98 | 8 sources |
| CustomMenuCatalog | Custom menu definitions | ~600+ | Multiple menus |
| FieldsForTables | All table and field definitions | **1,615** | **18 tables** |
| OptionsForValueLists | Value list options | ~15,350 | 59 value lists |
| RelationshipCatalog | Relationship definitions | 12,953 | 80 relationships |
| ScriptCatalog | Script catalog | **16,925** | **574 scripts** |
| ThemeCatalog | Theme definitions | **19,799** | **5 themes** |
| LayoutCatalog #1 | Layout definitions (primary) | **33,127** | **303 layouts** |
| StepsForScripts | Script step definitions | **696,732** | **435 script definitions** |

---

## 3. FieldsForTables SECTION (AddAction: Lines 1,615-16,924)

### 3.1 Table Summary
18 base tables with complete field definitions:

| Table Name | ID | Field Count | Notes |
|-----------|----|----|-------|
| LAYER | 129 | 193 | Primary table |
| DEFAULTS | 130 | 12 | Default values |
| Elements | 133 | 129 | Element data |
| PLM QC | 134 | 62 | Quality control |
| LAYER Description | 135 | 1 | Lookup/reference |
| Mold Elements | 136 | 78 | Mold component data |
| Mold Layers | 137 | 154 | Mold layer data |
| Fungal Species | 138 | 4 | Species reference |
| Mold Elements Particulate | 139 | 78 | Particulate data |
| Mold Types Entries | 140 | 2 | Type reference |
| Recovered Library | 141 | 1 | Library reference |
| Chart | 142 | 17 | Chart data |
| PCB Types | 143 | 3 | PCB type reference |
| PCB Elements | 144 | 6 | PCB elements |
| Reference QC | 145 | 15 | Reference QC data |
| LAYER QC | 146 | 197 | QC details |
| Verification | 147 | 27 | Verification data |
| PLM QC OIL | 148 | 9 | Oil QC data |

**Total Fields Across All Tables:** ~1,000+ fields

### 3.2 Field Structure Example
Each field definition includes:
- Field ID, name, fieldtype (Normal/Summary/Calculation), datatype
- UUID with modification tracking
- AutoEnter settings
- Validation rules (OnlyDuringDataEntry, unique, existing, notEmpty)
- Storage settings (index, global flag, maxRepetitions)
- Language references

### 3.3 Also Contains:
- **OptionsForValueLists** (~15,350): 59 value list definitions
- **RelationshipCatalog** (12,953-16,924): 80 relationship definitions

---

## 4. RelationshipCatalog SECTION (Lines 12,953-16,924)

### 4.1 Relationship Structure
80 total relationships, each containing:
- Relationship ID and UUID
- LeftTable and RightTable definitions with:
  - TableOccurrenceReference (id, name, UUID)
  - cascadeCreate and cascadeDelete flags
  - SortSpecification settings
- JoinPredicateList with equal/less/greater/etc. join types

### 4.2 Relationship Details
Relationships link tables via join predicates. Example structure:

```xml
<Relationship id="12">
  <LeftTable cascadeCreate="False" cascadeDelete="False" type="External">
    <TableOccurrenceReference id="1065122" name="Individuals" />
  </LeftTable>
  <RightTable cascadeCreate="False" cascadeDelete="False" type="Local">
    <TableOccurrenceReference id="1065089" name="LAYER" />
  </RightTable>
  <JoinPredicateList membercount="1">
    <JoinPredicate type="Equal">
      <LeftField>...Individuals::ID...</LeftField>
      <RightField>...LAYER::Client ID...</RightField>
    </JoinPredicate>
  </JoinPredicateList>
</Relationship>
```

### 4.3 Key Relationships Identified
- Individuals ↔ LAYER (Client lookup)
- Elements ↔ Individuals (Contact reference)
- Multiple self-joins and cross-table relationships
- Both Local and External table types

---

## 5. ScriptCatalog SECTION (Lines 16,925-19,798)

### 5.1 Summary Statistics
- **Total Script Entries:** 574
- **Standalone Scripts:** 574
- **Script Folders:** 0
- **Separators:** Multiple (marked with isSeparatorItem="True")

### 5.2 Script Naming Conventions
Scripts organized into functional groups:

#### Lab Work Scripts
- "Start Lab Work"
- "Start Lab Work Point Count"
- "Start ASB-07 Lab Work Point Count"
- "Start Lab Work Mold"

#### Navigation Scripts
- "Main Menu"
- "Find"
- "Open Batch COC"
- "LINK"

#### Analysis Scripts
- "Today Analyzed"
- "Today Review"
- "Clear search fields"

#### Chart/Reporting Scripts
- "Google Charts" (folder structure)
- "SetUpChart (type)"
- "sh_Chart_Gather_Data plotlygraph"
- "sh_Chart_Gather_plotly - Air Fungal Spores"

#### Other Scripts
- "TestSave to temp folder"
- "Show Hints - Tutorial"

### 5.3 Script Structure
Each script element contains:
```xml
<Script id="ID" name="ScriptName" [isSeparatorItem="True"] [isFolder="True"]>
  <UUID modifications="COUNT" ...>UUID</UUID>
  <Options hidden="True|False" access="ReadWrite" runwithfullaccess="False" />
  <TagList></TagList>
</Script>
```

---

## 6. ThemeCatalog SECTION (Lines 19,799-33,126)

### 6.1 Theme Summary
- **Total Themes:** 5
- Purpose: Define visual styling/appearance for layouts

### 6.2 Theme Elements
Themes likely contain:
- CSS styling definitions
- Color schemes
- Font specifications
- Border/margin settings

---

## 7. LayoutCatalog #1 SECTION (Lines 33,127-696,731)

### 7.1 Summary
- **Total Layouts:** 303
- **Size:** ~663,600 lines
- This is the primary layout definition section

### 7.2 Layout Structure Example
```xml
<Layout id="1" name="Data Entry" width="1359">
  <TableOccurrenceReference id="1065089" name="LAYER" />
  <LayoutThemeReference></LayoutThemeReference>
  <PartsList membercount="1">
    <Part type="Body" kind="4" size="849" ...>
      <ObjectList membercount="206">
        <!-- Layout objects (fields, buttons, text, etc.) -->
      </ObjectList>
    </Part>
  </PartsList>
</Layout>
```

### 7.3 Layout Objects Found

#### Object Types:
- **Text** - Static text labels
- **Rectangle** - Graphical rectangles
- **Edit Box** - Data entry fields
- **Button** - Action buttons
- **Grouped Button** - Buttons with grouped content

#### Button with Script Trigger Structure:
```xml
<LayoutObject type="Grouped Button" id="ID" kind="8">
  <UUID>UUID</UUID>
  <Bounds top="Y1" left="X1" bottom="Y2" right="X2" />
  <GroupedButton>
    <action>
      <Options>4</Options>
      <ScriptReference id="99" name="Today Analyzed" UUID="UUID" />
    </action>
    <ObjectList membercount="1">
      <!-- nested objects -->
    </ObjectList>
  </GroupedButton>
</LayoutObject>
```

#### Field Reference Structure:
```xml
<Field>
  <FieldReference id="91" name="LAB ID Calc" repetition="1" UUID="UUID">
    <TableOccurrenceReference id="1065089" name="LAYER" UUID="UUID" />
  </FieldReference>
  <Options>32</Options>
  <Display Style="0" show="1" />
  <Usage inputMode="0" type="0" />
</Field>
```

### 7.4 Layout Object Properties
Each layout object includes:
- **hash** - Unique object identifier hash
- **id** - Object ID
- **type** - Object type (Text, Button, Rectangle, etc.)
- **name** - Object name
- **kind** - Object kind subtype
- **UUID** - Universally unique identifier
- **Bounds** - top, left, bottom, right coordinates
- **Options** - Display and behavior options
- **TabOrder** - Tab navigation order
- **LocalCSS** - Styling (colors, borders, fonts, alignment, etc.)

### 7.5 Sample Layout Names
- "Data Entry"
- "Organics PBC DE"
- Analysis/QC layouts
- Reference/lookup layouts
- Report layouts

---

## 8. StepsForScripts SECTION (Lines 696,732-954,066)

### 8.1 Summary
- **Total Script Definitions:** 435
- **Purpose:** Contains the actual step-by-step script logic

### 8.2 Script Step Structure

Each script's steps are defined as:
```xml
<Script>
  <ScriptReference id="428" name="Start Lab Work" UUID="UUID" />
  <ObjectList membercount="5">
    <Step hash="HASH" index="0" id="6" name="Go to Layout" enable="True">
      <UUID>UUID</UUID>
      <OwnerID></OwnerID>
      <Options>10</Options>
      <ParameterValues membercount="2">
        <Parameter type="LayoutReferenceContainer">
          <LayoutReferenceContainer value="5">
            <LayoutReference id="1" name="Data Entry" UUID="UUID" />
          </LayoutReferenceContainer>
        </Parameter>
        <Parameter type="Animation">
          <Animation name="None" value="0" />
        </Parameter>
      </ParameterValues>
    </Step>
    <!-- Additional steps... -->
  </ObjectList>
</Script>
```

### 8.3 Common Step Types Identified
- **Go to Layout** - Navigate to specified layout with optional animation
- **Enter Find Mode** - Enter find/search mode
- **Set Field** - Set field value with calculation/expression
- **Perform Find** - Execute find operation
- **Select Window** - Switch to window

### 8.4 Step Parameters
Steps can contain:
- **LayoutReferenceContainer** - Target layout reference
- **Animation** - Transition animation settings
- **Boolean** - True/false flags
- **FieldReference** - Target field with table occurrence
- **Calculation** - Calculation expressions (embedded CDATA)
- **WindowReference** - Window selection parameters

### 8.5 Script Step References
Each step links back to:
- Script definitions (via ScriptReference with id, name, UUID)
- Layout references (via LayoutReference)
- Field references (with table occurrence context)

---

## 9. ModifyAction SECTION (Lines 954,067-966,953)

### 9.1 Structure
Contains modifications to base definitions:

| Subsection | Line | Member Count | Purpose |
|-----------|------|--------------|---------|
| FieldsForTables | 954,068 | 421 | Modified field definitions |
| LayoutCatalog #2 | 960,233 | 190 | Additional/modified layouts |

### 9.2 FieldsForTables (ModifyAction)
- **421 field entries** (vs. 18 tables in AddAction)
- Represents field modifications/overrides
- Likely includes calculated fields, summary fields, or user-specific modifications

### 9.3 LayoutCatalog #2 (ModifyAction)
- **190 layouts** (vs. 303 in AddAction)
- Represents layout overrides or user-specific layout modifications
- Maintains same structure as primary LayoutCatalog

---

## 10. ENCODING AND METADATA

### 10.1 File Encoding
- Original: UTF-16 (with BOM)
- Converted: UTF-8 for analysis
- Conversion command: `iconv -f UTF-16 -t UTF-8`

### 10.2 Modification Tracking
All major elements include:
```xml
<UUID modifications="COUNT" userName="Frogx" accountName="admin"
       timestamp="YYYY-MM-DDTHH:MM:SS">UUID-GUID</UUID>
```

### 10.3 Creation Tracking
Elements include CreationTimestamp and CreationAccountName:
- User: "admin" (most common)
- User: "Frogx" (active developer)
- Timestamps span from 2016 to 2026

---

## 11. RELATIONSHIPS AND REFERENCES

### 11.1 Reference Architecture

**Layout Objects → Scripts**
- GroupedButton.action → ScriptReference (id, name, UUID)
- ScriptTrigger elements reference scripts (id, action, browseMode)

**Layouts → Fields**
- EditBox/Field → FieldReference (id, name, UUID)
- FieldReference → TableOccurrenceReference (context)

**Layouts → Tables**
- LayoutHeader → TableOccurrenceReference (defines layout's base table)

**Scripts → Layouts/Fields**
- Step definitions reference LayoutReference and FieldReference elements
- Maintains table context through TableOccurrenceReference

**Tables → Fields**
- FieldCatalog contains ObjectList of Field definitions
- Each Field has id, name, datatype, fieldtype

### 11.2 Cross-References Summary
- **374 total TableOccurrenceReferences** across layouts
- **Multiple script triggers per layout** (OnObjectModify, OnObjectEnter, etc.)
- **Cascading relationships** with create/delete rules defined

---

## 12. SUMMARY STATISTICS

| Element Type | Count | Notes |
|-------------|-------|-------|
| Base Tables | 18 | Primary table definitions |
| Total Fields | ~1,000+ | Across all tables |
| Relationships | 80 | Table joins and connections |
| Scripts | 574 | Named scripts + separators |
| Themes | 5 | Visual style definitions |
| Layouts (AddAction) | 303 | Primary layouts |
| Layouts (ModifyAction) | 190 | Override layouts |
| Layout Objects | 10,000+ | Estimated (buttons, fields, text, etc.) |
| Script Steps | 435 | Individual script definitions |
| Authorizations | 11 | File access permissions |
| External Data Sources | 8 | Connected databases |
| Custom Menus | Multiple | File, Edit, Tools, etc. |

---

## 13. KEY DATA FLOW PATTERNS

### 13.1 Typical User Action Flow
1. **User clicks Button on Layout** (GroupedButton with ScriptReference)
2. **Script executes** (Script steps from StepsForScripts)
3. **Step navigates Layout** (Go to Layout step references LayoutCatalog)
4. **Layout displays Fields** (EditBox objects reference FieldCatalog)
5. **Fields linked to Tables** (FieldReference → TableOccurrenceReference → BaseTableReference)

### 13.2 Data Relationship Flow
```
BaseTableReference (abstract table)
    ↓
FieldCatalog (field definitions)
    ↓
TableOccurrenceReference (instance in relationship graph)
    ↓
FieldReference in Layout (specific field on layout)
    ↓
Relationship (joins to other tables)
```

### 13.3 Script Execution Context
```
ScriptReference (script name/id)
    ↓
StepsForScripts (step definitions)
    ↓
Step Parameters (calculations, field refs, layout refs)
    ↓
Execution in TableOccurrenceReference context
```

---

## 14. NOTES AND OBSERVATIONS

### 14.1 Database Purpose
- **Laboratory/Testing Management System**
- Focused on quality control (QC tables and layouts)
- Mold/fungal analysis (Mold Elements, Mold Types, Fungal Species)
- PCB/electronics testing (PCB Types, PCB Elements)
- Sample batching and tracking (BATCH, SAMPLES references)

### 14.2 Complexity Indicators
- 303 layouts suggests complex user interface
- 574 scripts indicates significant business logic
- 80 relationships shows complex data model
- Multiple external data sources (8 connections)
- Authorization system with 11 accounts suggests multi-user environment

### 14.3 Modification Patterns
- Most recent modifications: 2026-03-06 (script catalog)
- Most active user: "Frogx" (developer)
- Heavy use of timestamps for audit trail
- Field modifications tracked through UUID counts

### 14.4 Design Patterns Observed
- **Modular scripts** - Many script names suggest reusable functions (sh_ prefixes)
- **Layered architecture** - AddAction (primary) + ModifyAction (overrides)
- **Theme support** - 5 themes for flexible UI
- **Multi-user security** - Authorization catalog with account-level access
- **External integration** - Multiple external data source connections

---

## 15. FILE NAVIGATION QUICK REFERENCE

### Jump to Major Sections
- Line 4: AddAction begins
- Line 1,615: FieldsForTables (18 tables, ~1,000+ fields)
- Line 12,953: RelationshipCatalog (80 relationships)
- Line 16,925: ScriptCatalog (574 scripts)
- Line 19,799: ThemeCatalog (5 themes)
- Line 33,127: LayoutCatalog #1 (303 layouts)
- Line 696,732: StepsForScripts (435 script definitions)
- Line 954,067: ModifyAction begins
- Line 954,068: FieldsForTables ModifyAction (421 fields)
- Line 960,233: LayoutCatalog #2 (190 layouts)
- Line 966,954: Structure closes

---

**Document Generated:** 2026-03-27
**Source File:** /sessions/great-adoring-einstein/mnt/XML/LAYER.xml
**Analysis Tool:** Python 3 XML parsing with ripgrep pattern matching
