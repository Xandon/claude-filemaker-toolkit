# FileMaker Pro Script Step Types - Quick Index

Quick reference table of all 72 step types extracted from FileMaker Pro DDR.

| ID | Step Name | Parameters | Parameter Types |
|----|-----------|-----------|-----------------|
| 1 | Perform Script | 2 | List, Parameter |
| 6 | Go to Layout | 2 | LayoutReferenceContainer, Animation |
| 7 | New Record/Request | 0 | None |
| 8 | Duplicate Record/Request | 0 | None |
| 9 | Delete Record/Request | 1 | Boolean |
| 10 | Delete All Records | 1 | Boolean |
| 16 | Go to Record/Request/Page | 1 | Records |
| 17 | Go to Field | 2 | Boolean, FieldReference |
| 22 | Enter Find Mode | 1 | Boolean |
| 23 | Show All Records | 0 | None |
| 25 | Omit Record | 0 | None |
| 27 | Show Omitted Only | 0 | None |
| 28 | Perform Find | 0 | None |
| 29 | Show/Hide Toolbars | 3 | Boolean, Boolean, List |
| 31 | Adjust Window | 1 | List |
| 33 | Open File | 2 | Boolean, DataSourceReference |
| 35 | Import Records | 4 | Boolean, Boolean, DataSourceReference, ImportField |
| 36 | Export Records | 3 | Boolean, Boolean, Export |
| 39 | Sort Records | 3 | Boolean, Restore, SortSpecification |
| 41 | Enter Preview Mode | 1 | Boolean |
| 42 | Print Setup | 3 | Restore, Boolean, PageSetup |
| 43 | Print | 4 | Boolean, Restore, Print, PageSetup |
| 44 | Exit Application | 0 | None |
| 47 | Copy | 2 | Boolean, FieldReference |
| 48 | Paste | 3 | Boolean, Boolean, FieldReference |
| 55 | Enter Browse Mode | 1 | Boolean |
| 57 | Send Event | 1 | None |
| 61 | Insert Text | 3 | Boolean, Target, Text |
| 62 | Pause/Resume Script | 1 | Options |
| 63 | Send Mail | 1 | Email |
| 68 | If | 1 | Calculation |
| 69 | Else | 0 | None |
| 70 | End If | 0 | None |
| 71 | Loop | 1 | List |
| 72 | Exit Loop If | 1 | Calculation |
| 73 | End Loop | 0 | None |
| 74 | Go to Related Record | 1 | Related |
| 75 | Commit Records/Requests | 3 | Boolean, Boolean, Boolean |
| 76 | Set Field | 2 | FieldReference, Calculation |
| 79 | Freeze Window | 0 | None |
| 80 | Refresh Window | 2 | Boolean, Boolean |
| 83 | Change Password | 3 | Old, New, Boolean |
| 85 | Allow User Abort | 1 | Boolean |
| 86 | Set Error Capture | 1 | Boolean |
| 87 | Show Custom Dialog | 4 | Message, Button1, Button2, Button3 |
| 89 | # (comment) | 1 | Comment |
| 90 | Halt Script | 0 | None |
| 91 | Replace Field Contents | 3 | Boolean, FieldReference, replace |
| 93 | Beep | 0 | None |
| 99 | Go to Portal Row | 2 | Boolean, Portal |
| 102 | Flush Cache to Disk | 0 | None |
| 103 | Exit Script | 0 | None |
| 104 | Delete Portal Row | 1 | Boolean |
| 111 | Open URL | 3 | Boolean, Boolean, URL |
| 119 | Move/Resize Window | 1 | WindowReference |
| 121 | Close Window | 1 | WindowReference |
| 122 | New Window | 1 | WindowReference |
| 123 | Select Window | 1 | WindowReference |
| 125 | Else If | 1 | Calculation |
| 126 | Constrain Found Set | 2 | FindRequest, Boolean |
| 127 | Extend Found Set | 1 | FindRequest |
| 132 | Export Field Contents | 2 | Boolean, UniversalPathList |
| 134 | Add Account | 4 | Name, Password, PrivilegeSetReference, Boolean |
| 135 | Delete Account | 1 | Calculation |
| 138 | Re-Login | 3 | Boolean, Name, Password |
| 141 | Set Variable | 1 | Variable |
| 143 | Save Records as Excel | 5 | Restore, Boolean, UniversalPathList, Options, Boolean |
| 144 | Save Records as PDF | 6 | Restore, Boolean, Boolean, UniversalPathList, Options, Bo... |
| 145 | Go to Object | 1 | Object |
| 146 | Set Web Viewer | 2 | Calculation, action |
| 167 | Refresh Object | 1 | Object |
| 180 | Refresh Portal | 1 | Object |


## Step Type Categories


### Navigation
- **Go to Layout** (ID: 6)
- **Go to Record/Request/Page** (ID: 16)
- **Go to Field** (ID: 17)
- **Go to Related Record** (ID: 74)
- **Go to Object** (ID: 145)
- **Go to Portal Row** (ID: 99)

### Finding & Sorting
- **Enter Find Mode** (ID: 22)
- **Perform Find** (ID: 28)
- **Show All Records** (ID: 23)
- **Omit Record** (ID: 25)
- **Show Omitted Only** (ID: 27)
- **Sort Records** (ID: 39)
- **Constrain Found Set** (ID: 126)
- **Extend Found Set** (ID: 127)

### Field Operations
- **Set Field** (ID: 76)
- **Insert Text** (ID: 61)
- **Replace Field Contents** (ID: 91)
- **Export Field Contents** (ID: 132)

### Record Operations
- **New Record/Request** (ID: 7)
- **Duplicate Record/Request** (ID: 8)
- **Delete Record/Request** (ID: 9)
- **Delete All Records** (ID: 10)
- **Commit Records/Requests** (ID: 75)

### Variables & Control
- **Set Variable** (ID: 141)
- **If** (ID: 68)
- **Else If** (ID: 125)
- **Else** (ID: 69)
- **End If** (ID: 70)
- **Loop** (ID: 71)
- **Exit Loop If** (ID: 72)
- **End Loop** (ID: 73)

### Script Control
- **Perform Script** (ID: 1)
- **Pause/Resume Script** (ID: 62)
- **Allow User Abort** (ID: 85)
- **Set Error Capture** (ID: 86)
- **Halt Script** (ID: 90)
- **Exit Script** (ID: 103)
- **# (comment)** (ID: 89)

### User Interface
- **Show Custom Dialog** (ID: 87)
- **Adjust Window** (ID: 31)
- **Close Window** (ID: 121)
- **New Window** (ID: 122)
- **Select Window** (ID: 123)
- **Move/Resize Window** (ID: 119)
- **Show/Hide Toolbars** (ID: 29)
- **Freeze Window** (ID: 79)
- **Refresh Window** (ID: 80)
- **Refresh Object** (ID: 167)
- **Refresh Portal** (ID: 180)

### File & Database
- **Open File** (ID: 33)
- **Import Records** (ID: 35)
- **Export Records** (ID: 36)
- **Save Records as Excel** (ID: 143)
- **Save Records as PDF** (ID: 144)
- **Flush Cache to Disk** (ID: 102)

### Window & Application
- **Enter Preview Mode** (ID: 41)
- **Enter Browse Mode** (ID: 55)
- **Print Setup** (ID: 42)
- **Print** (ID: 43)
- **Exit Application** (ID: 44)

### Miscellaneous
- **Copy** (ID: 47)
- **Paste** (ID: 48)
- **Send Event** (ID: 57)
- **Send Mail** (ID: 63)
- **Change Password** (ID: 83)
- **Beep** (ID: 93)
- **Open URL** (ID: 111)
- **Delete Portal Row** (ID: 104)
- **Add Account** (ID: 134)
- **Delete Account** (ID: 135)
- **Re-Login** (ID: 138)
- **Set Web Viewer** (ID: 146)
