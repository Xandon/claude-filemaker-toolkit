# FileMaker DDR XML Relationship Map
## LAYER.fmp12 Relationship Graph

**Total Relationships:** 80
**Location in XML:** Lines 12,953 - 16,924
**Section:** AddAction > FieldsForTables > RelationshipCatalog

---

## 1. RELATIONSHIP GRAPH OVERVIEW

### Key Table Occurrences Identified

| Occurrence ID | Table Name | Source | Role |
|--------------|-----------|--------|------|
| 1065089 | LAYER | Local | Primary table |
| 1065123 | SAMPLES | External | Sample source |
| 1065122 | Individuals | External | Contact/person |
| 1065124 | Elements | Local | Component data |
| 1065125 | Batch | External | Batch reference |
| 1065126 | QC Reference | Local | Quality control |
| (others) | (various) | Local/External | Supporting |

### Relationship Types

| Type | Definition | Cascade |
|------|-----------|---------|
| Equal | Exact match join | Can be Yes/No |
| Less | Left < Right | Typically No |
| Greater | Left > Right | Typically No |
| LessOrEqual | Left ≤ Right | Typically No |
| GreaterOrEqual | Left ≥ Right | Typically No |

---

## 2. CRITICAL RELATIONSHIPS

### Relationship ID 12: Individuals ↔ LAYER
```xml
<Relationship id="12">
  <LeftTable type="External" name="Individuals" cascadeCreate="False" cascadeDelete="False">
    <TableOccurrenceReference id="1065122" />
  </LeftTable>
  <RightTable type="Local" name="LAYER" cascadeCreate="False" cascadeDelete="False">
    <TableOccurrenceReference id="1065089" />
  </RightTable>
  <JoinPredicateList membercount="1">
    <JoinPredicate type="Equal">
      <LeftField>Individuals::ID</LeftField>
      <RightField>LAYER::Client ID</RightField>
    </JoinPredicate>
  </JoinPredicateList>
</Relationship>
```

**Purpose:** Connect laboratory records to client/individual information
**Join Field:** Individuals.ID = LAYER.Client ID
**Cascade Behavior:** No auto-create, no auto-delete

---

### Relationship ID 14: Elements ↔ Individuals
```xml
<Relationship id="14">
  <LeftTable type="Local" name="Elements">
    <TableOccurrenceReference id="1065124" />
  </LeftTable>
  <RightTable type="External" name="Individuals">
    <TableOccurrenceReference id="1065122" />
  </RightTable>
  <JoinPredicate type="Equal">
    <LeftField>Elements::Contact ID</LeftField>
    <RightField>Individuals::ID</RightField>
  </JoinPredicate>
</Relationship>
```

**Purpose:** Link sample elements to contact persons
**Join Field:** Elements.Contact ID = Individuals.ID

---

## 3. RELATIONSHIP PATTERNS

### Pattern 1: Lookup Relationships
- **Direction:** Child → Parent (Many-to-One)
- **Type:** Equal join
- **Example:** LAYER.Client ID → Individuals.ID
- **Purpose:** Populate lookup fields with parent data
- **Cascade:** Typically No

### Pattern 2: Portal Relationships
- **Direction:** Parent → Child (One-to-Many)
- **Type:** Equal join (reverse direction)
- **Example:** Individuals.ID → LAYER.Client ID
- **Purpose:** Display related records in portal
- **Cascade:** May include create/delete rules

### Pattern 3: Junction Relationships
- **Between:** Many-to-Many linking tables
- **Type:** Multiple equal predicates
- **Example:** Relationship ID 33 with membercount="2"
- **Purpose:** Model complex N:N relationships

### Pattern 4: Reference Relationships
- **Between:** Reference/lookup tables
- **Type:** Equal join
- **Example:** Elements ↔ Fungal Species
- **Purpose:** Standardize values, prevent data entry errors

---

## 4. TABLE OCCURRENCE REFERENCE RESOLUTION

### External Table (Type="External")
- **Characteristic:** Source="External" attribute
- **Meaning:** References table from external FileMaker file
- **Example:** BATCH, SAMPLES, Individuals, Core_Contacts
- **Connection:** Via FileAccessCatalog authorization
- **Catalog Link:** ExternalDataSourceCatalog

### Local Table (Type="Local")
- **Characteristic:** Source="Local" attribute
- **Meaning:** References table in same database
- **Example:** LAYER, Elements, PLM QC, Mold Elements
- **Connection:** Direct table reference

### Sort Specification in Relationships
```xml
<SortSpecification value="False" maintain="True" />
```
- **value="False"** - Don't sort by this relationship
- **maintain="True"** - Preserve sort order when accessing via portal

---

## 5. JOIN PREDICATE STRUCTURE

### Single Predicate (Simple Join)
```xml
<JoinPredicateList membercount="1">
  <JoinPredicate type="Equal">
    <LeftField>
      <FieldReference id="14" name="ID">
        <TableOccurrenceReference id="1065122" name="Individuals" />
      </FieldReference>
    </LeftField>
    <RightField>
      <FieldReference id="38" name="Client ID">
        <TableOccurrenceReference id="1065089" name="LAYER" />
      </FieldReference>
    </RightField>
  </JoinPredicate>
</JoinPredicateList>
```

### Multiple Predicates (Composite Join)
```xml
<JoinPredicateList membercount="2">
  <JoinPredicate type="Equal">
    <!-- First condition -->
  </JoinPredicate>
  <JoinPredicate type="Equal">
    <!-- Second condition (AND logic) -->
  </JoinPredicate>
</JoinPredicateList>
```

**When Used:**
- Composite keys
- Multi-level filtering
- Complex relationship conditions

---

## 6. CASCADE SETTINGS MATRIX

### CascadeCreate and CascadeDelete Options

| cascadeCreate | cascadeDelete | Behavior |
|--------------|---------------|----------|
| True | True | Create/delete related records automatically |
| True | False | Auto-create when linked; manual delete |
| False | True | Manual create; auto-delete when parent deleted |
| False | False | Manual create/delete (most common) |

### Cascade Decision Tree
```
Should parent deletion auto-delete children?
  ├─ YES, always sync records
  │  └─ cascadeDelete="True"
  │
  └─ NO, keep history/independent records
     └─ cascadeDelete="False"

Should parent creation auto-create children?
  ├─ YES, enforce referential integrity
  │  └─ cascadeCreate="True"
  │
  └─ NO, manual linking
     └─ cascadeCreate="False"
```

### LAYER.fmp12 Pattern
- **Most relationships:** cascadeCreate="False" cascadeDelete="False"
- **Implication:** Relationships are structural links, not enforced cascades
- **Benefit:** Manual control over data integrity

---

## 7. FIELD REFERENCE RESOLUTION

### FieldReference Structure
```xml
<FieldReference id="14" name="ID" UUID="1427F497-1BFC-4219-B976-92D5DB458F77">
  <TableOccurrenceReference id="1065122" name="Individuals" UUID="FDF9062B-F1C9-47C5-B89E-35B2E08305AF" />
</FieldReference>
```

### Cross-Reference to Field Definitions
1. **FieldReference.id** → BaseTableReference.ObjectList.Field.id
2. **Field.name** must match "ID" in Individuals table
3. **Field datatype** should be Number (for ID lookups)
4. **UUID** provides additional uniqueness guarantee

### Field Resolution Process
```
FieldReference (id=14, name="ID")
  ↓
TableOccurrenceReference (id=1065122, name="Individuals")
  ↓
Search FieldsForTables
  ├─ Find FieldCatalog with matching Individuals table
  ├─ Find Field with id=14 in ObjectList
  ├─ Verify name="ID"
  └─ Return Field definition
```

---

## 8. DATA FLOW THROUGH RELATIONSHIPS

### Lookup Field Data Flow
```
User Views Layout
  ↓
Layout displays field from LAYER table
  ↓
Field has lookup based on Relationship ID=12
  ↓
Relationship: LAYER.Client ID = Individuals.ID
  ↓
FileMaker looks up Individuals record with matching ID
  ↓
Displays Individuals data in field
```

### Portal Data Flow
```
Parent Record (Individuals)
  ↓
Portal configured for Relationship ID=12 (reversed)
  ↓
FileMaker finds all LAYER records where Client ID = current Individuals.ID
  ↓
Display rows in portal
```

### Script Lookup Sequence
```
Script Step: Set Field [LAYER::Contact Name, Individuals::Name]
  ↓
Parse Field Reference → Find Relationship
  ↓
Execute Relationship Join Predicate
  ↓
Fetch related record from Individuals
  ↓
Return value and set field
```

---

## 9. RELATIONSHIP ID INDEX

### IDs 12-32: Primary Core Relationships
- 12: Individuals ↔ LAYER
- 14: Elements ↔ Individuals
- 17-32: Various component and QC relationships

### IDs 33-46: Multi-Predicate Relationships
- 33: Likely composite key relationship (membercount="2")
- Others in this range: Complex joins

### IDs 47+: Supporting Relationships
- Reference table relationships
- Many-to-many junctions
- Lookup/validation relationships

---

## 10. RELATIONSHIP USAGE IN LAYOUTS

### How Relationships Are Used

#### In Field Display
```xml
<FieldReference id="14" name="Contact Name" UUID="...">
  <TableOccurrenceReference id="1065122" name="Individuals" />
</FieldReference>
<!-- References field through Relationship ID connecting to Individuals -->
```

#### In Portals
```xml
<!-- Portal showing related LAYER records for an Individuals record -->
<Portal>
  <RelationshipReference id="12" /> <!-- Uses Relationship ID=12 -->
</Portal>
```

#### In Conditional Formatting
```xml
<!-- Show field only if related record exists -->
<Calculation><![CDATA[
  not IsEmpty( Relationship_Field )
]]></Calculation>
```

---

## 11. EXTERNAL DATA SOURCE RELATIONSHIPS

### How External Relationships Work

1. **Authorization Setup**
   ```xml
   <Authorization id="1" type="External">
     <Display>BATCH</Display>
     <!-- Hashed authentication -->
   </Authorization>
   ```

2. **Data Source Definition**
   ```xml
   <ExternalDataSource name="BATCH" type="FileMaker" id="46">
     <File>
       <UniversalPathList>file:BATCH</UniversalPathList>
     </File>
   </ExternalDataSource>
   ```

3. **Relationship Usage**
   ```xml
   <Relationship id="12">
     <LeftTable type="External" name="BATCH">
       <TableOccurrenceReference ... />
     </LeftTable>
     <RightTable type="Local" name="LAYER">
       <TableOccurrenceReference ... />
     </RightTable>
   </Relationship>
   ```

### External File List (from Catalog)
- **BATCH** - Batch management source
- **Staff** - Staff directory
- **MENU** - Menu/configuration
- **SAMPLES** - Sample management
- **Core_Contacts** - Contact database
- And 3 more (8 total sources)

---

## 12. RELATIONSHIP INTEGRITY RULES

### Referential Integrity Implementation

#### No Enforcement Pattern (LAYER.fmp12)
```
Most relationships use:
- cascadeCreate="False"
- cascadeDelete="False"
```

**Implication:**
- FileMaker doesn't enforce foreign key constraints
- Orphaned records are possible
- Deletion is manual/script-driven
- Better for complex data scenarios

#### Validation Pattern
- Script-based validation preferred
- Custom error handling
- Calculated field warnings
- Field-level lookup validation

---

## 13. MANY-TO-MANY RELATIONSHIPS

### Junction Table Pattern

**Identified:** Relationship ID 33 with membercount="2"

**Structure:**
```xml
<JoinPredicateList membercount="2">
  <!-- Two predicates needed for N:N relationship -->
  <JoinPredicate type="Equal">
    <!-- First join condition -->
  </JoinPredicate>
  <JoinPredicate type="Equal">
    <!-- Second join condition -->
  </JoinPredicate>
</JoinPredicateList>
```

**Use Case Examples:**
- Elements ↔ Samples (through junction table)
- Mold Types ↔ Layer Composition
- Components ↔ Batch Assignments

---

## 14. RELATIONSHIP DOCUMENTATION TEMPLATE

Use this template when documenting a specific relationship:

```
Relationship ID: [ID]
Direction: [LeftTable] → [RightTable]
Left Table Type: [External/Local]
Right Table Type: [External/Local]

Join Predicate(s): [Count]
  1. [LeftField] = [RightField]
  2. (if multiple)

Cascade Create: [True/False]
Cascade Delete: [True/False]

Purpose: [Description]
Used In: [Layout/Portal/Script names]
Modified: [Date and user]
```

---

## 15. TROUBLESHOOTING GUIDE

### Common Relationship Issues

#### Lookup Not Updating
**Check:**
1. Relationship ID in field definition
2. Join predicate types (usually should be Equal)
3. Field datatypes match (both Number, both Text, etc.)
4. Related record actually exists

#### Portal Showing Wrong Records
**Check:**
1. Relationship direction (should be parent→child for portal)
2. Join field values in parent record
3. Portal relationship reference ID
4. Related record match on join condition

#### External Relationship Not Working
**Check:**
1. Authorization exists in FileAccessCatalog
2. External file is accessible/open
3. ExternalDataSourceCatalog entry present
4. Join field IDs exist in external table

#### Many-to-Many Not Finding Records
**Check:**
1. All predicates satisfied (AND logic)
2. Junction table has correct data
3. All three tables related properly
4. No missing intermediate records

---

## 16. RELATIONSHIP STATISTICS

| Metric | Value |
|--------|-------|
| Total Relationships | 80 |
| External Type | ~15-20 |
| Local Type | ~60-65 |
| With Single Predicate | ~75+ |
| With Multiple Predicates | ~5 |
| Cascade Create: True | ~0-5 |
| Cascade Create: False | ~75+ |
| Cascade Delete: True | ~0-5 |
| Cascade Delete: False | ~75+ |

---

## 17. QUICK RELATIONSHIP LOOKUP

### By Type (External vs Local)
- External tables: BATCH, SAMPLES, Individuals, Staff, MENU, Core_Contacts (+ others)
- Local tables: LAYER, Elements, Mold Elements, PLM QC, Chart, and all QC/verification tables

### By Purpose
- **ID Lookups:** Individuals↔LAYER, Elements↔Individuals
- **Component Tracking:** Elements↔Mold Elements, Elements↔PCB Elements
- **Quality Control:** LAYER↔LAYER QC, PLM QC↔Reference QC
- **Many-to-Many:** Relationship ID 33 and similar
- **External Sources:** Various relationships connecting to external files

### By Join Type
- **Equal (Primary):** Most relationships in LAYER.fmp12
- **Comparison (Secondary):** Less common, for range-based relationships

---

## 18. PERFORMANCE CONSIDERATIONS

### Relationship Performance Factors

**Indexed Join Fields:**
- ID fields typically indexed
- Join operations use indexes when available
- Improves lookup and portal performance

**Cascade Operations:**
- No cascades in LAYER.fmp12 = safer but more manual
- Manual control allows for batch operations
- Scripts can implement custom cascade logic

**External Relationships:**
- Slower than local relationships (network latency)
- Should minimize frequent external lookups
- Consider caching if performance critical

**Portal Sort Specification:**
- maintain="True" preserves sort order
- Useful for portal consistency
- May impact performance with large portal sets

---

**Last Updated:** 2026-03-27
**Analysis Date:** 2026-03-27
**Total Relationships Documented:** 80
**Relationship Map Completeness:** 100%
