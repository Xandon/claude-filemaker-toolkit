# FileMaker Pro Script Step Types Reference

## Overview

This document catalogs all 72 unique script step types found in the FileMaker Pro DDR XML export.

**Source:** LAYER.xml (StepsForScripts section, lines 696732-954065)
**Extracted:** All unique step id + name combinations
**Total Step Types:** 72

## Table of Contents

1. [Critical Step Types](#critical-step-types)
2. [All Step Types](#all-step-types-reference)
3. [Parameter Type Reference](#parameter-type-reference)
4. [Notes on Parameter Encoding](#notes-on-parameter-encoding)

## Critical Step Types

The following step types are most commonly used in script development and receive detailed documentation:

### Set Variable (ID: 141)

**Purpose:** Stores a value in a variable with optional scope modifiers

**Parameter Encoding:**
- Parameter 1: `Variable` - Contains variable name and value assignment
  - `Name` attribute: Variable name (e.g., `$BatchID`, `$$GlobalVar`)
  - `value` element: Calculation expression defining the variable value
  - `repetition` element: Optional repetition index

**Example XML Structure:**
```xml
<Step id="141" name="Set Variable" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Variable">
      <value>
        <Calculation datatype="1" position="1">
          <Calculation>
            <Text>Get(scriptParameter)</Text>
          </Calculation>
        </Calculation>
      </value>
      <Name value="$BatchID" />
    </Parameter>
  </ParameterValues>
</Step>
```

### Set Field (ID: 76)

**Purpose:** Sets a field value to a calculated result

**Parameter Encoding:**
- Parameter 1: `FieldReference` - Specifies the target field
  - `id`, `name`, `UUID`: Identify the field
  - `TableOccurrenceReference`: Points to the table occurrence
  - `repetition` element: Optional field repetition index
- Parameter 2: `Calculation` - The value to set

**Example XML Structure:**
```xml
<Step id="76" name="Set Field" enable="True">
  <ParameterValues membercount="2">
    <Parameter type="FieldReference">
      <FieldReference id="4" name="Batch ID" UUID="...">
        <repetition>
          <Calculation datatype="1" position="10">
            <Calculation><Text>1</Text></Calculation>
          </Calculation>
        </repetition>
        <TableOccurrenceReference id="1065089" name="LAYER" UUID="..." />
      </FieldReference>
    </Parameter>
    <Parameter type="Calculation">
      <Calculation datatype="1" position="0">
        <Calculation><Text>BATCH::Global Batch ID</Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>
```

### If/Else If/Else/End If Control Flow

**If (ID: 68)** - Evaluates a condition and branches execution
- Parameter: `Calculation` containing boolean expression
- Datatype: "7" (Boolean)

**Else If (ID: 125)** - Additional condition within If block
- Parameter: `Calculation` containing boolean expression
- Must appear between If and End If

**Else (ID: 69)** - Default branch when all If/Else If conditions are false
- No parameters

**End If (ID: 70)** - Marks the end of If block
- No parameters

**Example If/Else If/Else Structure:**
```xml
<Step id="68" name="If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text>$chart_type="plotly"</Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>
<!-- script steps when condition is true -->
<Step id="125" name="Else If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text>$type="alternative"</Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>
<Step id="69" name="Else" enable="True" />
<Step id="70" name="End If" enable="True" />
```

### Loop/Exit Loop If/End Loop Control Flow

**Loop (ID: 71)** - Begins a loop block
- No parameters

**Exit Loop If (ID: 72)** - Conditional loop exit
- Parameter: `Calculation` containing boolean condition
- When condition is true, loop exits

**End Loop (ID: 73)** - Marks the end of loop block
- No parameters

**Example Loop Structure:**
```xml
<Step id="71" name="Loop" enable="True" />
<!-- loop body -->
<Step id="72" name="Exit Loop If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text>$counter >= 100</Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>
<Step id="73" name="End Loop" enable="True" />
```

### Perform Script (ID: 1)

**Purpose:** Calls another script

**Parameter Encoding:**
- Parameter 1: `ScriptReferenceContainer` - Target script reference
- Parameter 2: `Calculation` - Optional parameter to pass to script (accessed via Get(scriptParameter))

### Go to Layout (ID: 6)

**Purpose:** Navigates to a specific layout

**Parameter Encoding:**
- Parameter 1: `LayoutReferenceContainer` - Target layout reference
  - Contains `LayoutReference` with id, name, UUID
- Parameter 2: `Animation` - Transition animation (e.g., "None", value="0")

### Perform Find (ID: 28)

**Purpose:** Executes the find request(s) set up by preceding Enter Find Mode and Set Field steps
- No parameters required

### Enter Find Mode (ID: 22)

**Purpose:** Enters find mode

**Parameter Encoding:**
- Parameter 1: `Boolean` - Pause option (type="Pause")

### Show Custom Dialog (ID: 87)

**Purpose:** Displays a custom dialog box

**Parameter Encoding:**
- Parameter types: `Title`, `Message`, `Button1`, `Button2`, `Button3`
- Each parameter is a `Calculation` containing text/formula
- Button parameters are optional; defined buttons appear in dialog

### Exit Script (ID: 103)

**Purpose:** Ends script execution and optionally returns a value

**Parameter Encoding:**
- Optional Parameter 1: `Calculation` - Return value for the script
- If no parameter, script exits with empty result

### Go to Record/Request/Page (ID: 16)

**Purpose:** Navigate to a specific record

**Parameter Encoding:**
- Parameter 1: `Target` - One of: First, Last, Next, Previous, ByRecordNumber
- Parameter 2: `Calculation` - Record number (when ByRecordNumber is used)

### Sort Records (ID: 39)

**Purpose:** Sorts the found set

**Parameter Encoding:**
- Parameter 1: `SortSpecification` - Contains sort fields and order
  - Includes field references and sort direction (ascending/descending)
- Parameter 2: `Records` - Record scope (All, FoundSet, etc.)

### Commit Records/Requests (ID: 75)

**Purpose:** Commits (saves) pending record changes

**Parameter Encoding:**
- Parameter 1: `Calculation` - Records to commit scope
- Parameter 2: `Boolean` - Skip validation option

### Set Error Capture (ID: 86)

**Purpose:** Enables or disables script error suppression

**Parameter Encoding:**
- Parameter 1: `Boolean` - true to enable capture, false to disable
- When enabled, Get(LastError) contains the error code

---

## All Step Types Reference

### Complete List of 72 Step Types

**Flush Cache to Disk** (ID: 102)
- Parameters: None

**Exit Script** (ID: 103)
- Parameters: Calculation

**Delete Portal Row** (ID: 104)
- Parameters: Boolean

**Delete All Records** (ID: 10)
- Parameters: Boolean

**Open URL** (ID: 111)
- Parameters: Boolean, URL

**Move/Resize Window** (ID: 119)
- Parameters: WindowReference

**Close Window** (ID: 121)
- Parameters: WindowReference

**New Window** (ID: 122)
- Parameters: WindowReference

**Select Window** (ID: 123)
- Parameters: WindowReference

**Else If** (ID: 125)
- Parameters: Calculation

**Constrain Found Set** (ID: 126)
- Parameters: Boolean, FindRequest

**Extend Found Set** (ID: 127)
- Parameters: FindRequest

**Export Field Contents** (ID: 132)
- Parameters: Boolean, UniversalPathList

**Add Account** (ID: 134)
- Parameters: Boolean, Name, Password, PrivilegeSetReference

**Delete Account** (ID: 135)
- Parameters: Calculation

**Re-Login** (ID: 138)
- Parameters: Boolean, Name, Password

**Set Variable** (ID: 141)
- Parameters: Variable

**Save Records as Excel** (ID: 143)
- Parameters: Boolean, Options, Restore, UniversalPathList

**Save Records as PDF** (ID: 144)
- Parameters: Boolean, Options, Restore, UniversalPathList

**Go to Object** (ID: 145)
- Parameters: Object

**Set Web Viewer** (ID: 146)
- Parameters: Calculation, action

**Refresh Object** (ID: 167)
- Parameters: Object

**Go to Record/Request/Page** (ID: 16)
- Parameters: Records

**Go to Field** (ID: 17)
- Parameters: Boolean, FieldReference

**Refresh Portal** (ID: 180)
- Parameters: Object

**Perform Script** (ID: 1)
- Parameters: List, Parameter

**Enter Find Mode** (ID: 22)
- Parameters: Boolean

**Show All Records** (ID: 23)
- Parameters: None

**Omit Record** (ID: 25)
- Parameters: None

**Show Omitted Only** (ID: 27)
- Parameters: None

**Perform Find** (ID: 28)
- Parameters: FindRequest

**Show/Hide Toolbars** (ID: 29)
- Parameters: Boolean, List

**Adjust Window** (ID: 31)
- Parameters: List

**Open File** (ID: 33)
- Parameters: Boolean, DataSourceReference

**Import Records** (ID: 35)
- Parameters: Boolean, DataSourceReference, ImportField

**Export Records** (ID: 36)
- Parameters: Boolean, Export

**Sort Records** (ID: 39)
- Parameters: Boolean, Restore, SortSpecification

**Enter Preview Mode** (ID: 41)
- Parameters: Boolean

**Print Setup** (ID: 42)
- Parameters: Boolean, PageSetup, Restore

**Print** (ID: 43)
- Parameters: Boolean, PageSetup, Print, Restore

**Exit Application** (ID: 44)
- Parameters: None

**Copy** (ID: 47)
- Parameters: Boolean, FieldReference

**Paste** (ID: 48)
- Parameters: Boolean, FieldReference

**Enter Browse Mode** (ID: 55)
- Parameters: Boolean

**Send Event** (ID: 57)
- Parameters: None

**Insert Text** (ID: 61)
- Parameters: Boolean, Target, Text

**Pause/Resume Script** (ID: 62)
- Parameters: Options

**Send Mail** (ID: 63)
- Parameters: Email

**If** (ID: 68)
- Parameters: Calculation

**Else** (ID: 69)
- Parameters: None

**Go to Layout** (ID: 6)
- Parameters: Animation, LayoutReferenceContainer

**End If** (ID: 70)
- Parameters: None

**Loop** (ID: 71)
- Parameters: List

**Exit Loop If** (ID: 72)
- Parameters: Calculation

**End Loop** (ID: 73)
- Parameters: None

**Go to Related Record** (ID: 74)
- Parameters: Related

**Commit Records/Requests** (ID: 75)
- Parameters: Boolean

**Set Field** (ID: 76)
- Parameters: Calculation, FieldReference

**Freeze Window** (ID: 79)
- Parameters: None

**New Record/Request** (ID: 7)
- Parameters: None

**Refresh Window** (ID: 80)
- Parameters: Boolean

**Change Password** (ID: 83)
- Parameters: Boolean, New, Old

**Allow User Abort** (ID: 85)
- Parameters: Boolean

**Set Error Capture** (ID: 86)
- Parameters: Boolean

**Show Custom Dialog** (ID: 87)
- Parameters: Button1, Button2, Button3, Field1, Field2, Message, Title

**# (comment)** (ID: 89)
- Parameters: Comment

**Duplicate Record/Request** (ID: 8)
- Parameters: None

**Halt Script** (ID: 90)
- Parameters: None

**Replace Field Contents** (ID: 91)
- Parameters: Boolean, FieldReference, replace

**Beep** (ID: 93)
- Parameters: None

**Go to Portal Row** (ID: 99)
- Parameters: Boolean, Portal

**Delete Record/Request** (ID: 9)
- Parameters: Boolean


---

## Parameter Type Reference

FileMaker DDR XML uses the following parameter types to encode script step arguments:

### Variable
Script or global variable definition with name and value

---

## Notes on Parameter Encoding

### Calculation Elements
Calculation parameters use a standardized structure:
```xml
<Calculation datatype="TYPE" position="INDEX">
  <Calculation>
    <Text><![CDATA[expression or value]]></Text>
  </Calculation>
</Calculation>
```

**Datatype Values:**
- `0`: Unknown/Mixed type
- `1`: Text/String
- `2`: Number
- `4`: Date
- `5`: Time
- `6`: Timestamp
- `7`: Boolean

### Field References
Field references include:
- `id`: Unique field identifier
- `name`: Field name as shown in field picker
- `UUID`: Globally unique identifier
- `TableOccurrenceReference`: Links field to its table/TO
- `repetition`: Optional element for repeated field indices

### Layout References
Layout references in containers:
```xml
<LayoutReferenceContainer value="COUNT">
  <LayoutReference id="ID" name="NAME" UUID="UUID" />
</LayoutReferenceContainer>
```

### Variable Encoding
Variables are encoded as:
- `$name`: Local variable (script scope)
- `$$name`: Global variable (file scope)
- Name attribute stores the variable identifier
- value element stores the expression to assign

### Options Attribute
The `Options` attribute on Step elements is a bitmask encoding step-specific flags:
- Common values: 0 (default), 16384, 32768, 16777216, -2147483648
- Specific meaning depends on the step type
- Use in conjunction with step documentation

---

## Data Extraction Methodology

This reference was generated by:
1. Converting LAYER.xml from UTF-16 to UTF-8 encoding
2. Extracting the StepsForScripts XML section (lines 696732-954065)
3. Parsing all Step elements and cataloging unique id + name combinations
4. Collecting 1-3 complete examples for each step type
5. Analyzing parameter types and encoding patterns
6. Documenting parameter structure and datatype mappings

**Total Records Analyzed:**
- Unique Step Types: 72
- Total Step Instances: 435 (membercount in StepsForScripts)
- Unique Parameter Types: 42

