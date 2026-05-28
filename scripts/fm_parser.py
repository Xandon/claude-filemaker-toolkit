#!/usr/bin/env python3
"""
FileMaker DDR XML Parser - Core Indexing Engine

Parses FileMaker "Save As XML" (DDR) exports and indexes them into SQLite
for fast querying. Handles UTF-16 encoding and 100MB+ files efficiently
using iterative SAX-like parsing.

Usage:
    python fm_parser.py index <xml_file> [--db <output.db>]
    python fm_parser.py info <db_file>
"""

import sys
import os
import re
import sqlite3
import codecs
import xml.etree.ElementTree as ET
from io import StringIO
import argparse
import json
import time


def create_db(db_path):
    """Create the SQLite database with all required tables."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY,
        filename TEXT,
        filepath TEXT,
        uuid TEXT,
        fm_version TEXT,
        locale TEXT,
        indexed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS tables_def (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        table_id INTEGER,
        name TEXT,
        uuid TEXT,
        field_count INTEGER,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS fields (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        table_id INTEGER,
        table_name TEXT,
        field_id INTEGER,
        name TEXT,
        fieldtype TEXT,
        datatype TEXT,
        comment TEXT,
        uuid TEXT,
        is_global INTEGER DEFAULT 0,
        max_repetitions INTEGER DEFAULT 1,
        auto_enter_type TEXT,
        validation_type TEXT,
        calculation_text TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        script_id INTEGER,
        name TEXT,
        uuid TEXT,
        is_folder INTEGER DEFAULT 0,
        is_separator INTEGER DEFAULT 0,
        is_hidden INTEGER DEFAULT 0,
        run_with_full_access INTEGER DEFAULT 0,
        step_count INTEGER DEFAULT 0,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS script_steps (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        script_id INTEGER,
        script_name TEXT,
        step_index INTEGER,
        step_type_id INTEGER,
        step_name TEXT,
        enabled INTEGER DEFAULT 1,
        raw_xml TEXT,
        human_readable TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS layouts (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        layout_id INTEGER,
        name TEXT,
        uuid TEXT,
        table_occurrence TEXT,
        table_occurrence_id INTEGER,
        width INTEGER,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        rel_id INTEGER,
        uuid TEXT,
        left_table TEXT,
        left_table_id INTEGER,
        right_table TEXT,
        right_table_id INTEGER,
        join_type TEXT,
        left_field TEXT,
        right_field TEXT,
        cascade_create INTEGER DEFAULT 0,
        cascade_delete INTEGER DEFAULT 0,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS value_lists (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        vl_id INTEGER,
        name TEXT,
        uuid TEXT,
        source_type TEXT,
        values_text TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS script_references (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        source_type TEXT,
        source_id INTEGER,
        source_name TEXT,
        target_script_id INTEGER,
        target_script_name TEXT,
        target_script_uuid TEXT,
        context TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS field_references (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        source_type TEXT,
        source_id INTEGER,
        source_name TEXT,
        field_id INTEGER,
        field_name TEXT,
        table_occurrence TEXT,
        table_occurrence_id INTEGER,
        context TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS layout_references (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        source_type TEXT,
        source_id INTEGER,
        source_name TEXT,
        layout_id INTEGER,
        layout_name TEXT,
        layout_uuid TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS external_data_sources (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        eds_id INTEGER,
        name TEXT,
        source_type TEXT,
        path TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS custom_functions (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        cf_id INTEGER,
        name TEXT,
        uuid TEXT,
        display TEXT,
        param_count INTEGER DEFAULT 0,
        parameters TEXT,
        calculation_text TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE TABLE IF NOT EXISTS cf_references (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        cf_id INTEGER,
        cf_name TEXT,
        script_id INTEGER,
        script_name TEXT,
        step_index INTEGER,
        context TEXT,
        FOREIGN KEY(file_id) REFERENCES files(id)
    );

    CREATE INDEX IF NOT EXISTS idx_scripts_name ON scripts(name);
    CREATE INDEX IF NOT EXISTS idx_cf_refs_cf ON cf_references(cf_name);
    CREATE INDEX IF NOT EXISTS idx_cf_refs_script ON cf_references(script_id);
    CREATE INDEX IF NOT EXISTS idx_cf_name ON custom_functions(name);
    CREATE INDEX IF NOT EXISTS idx_scripts_id ON scripts(script_id);
    CREATE INDEX IF NOT EXISTS idx_script_steps_script ON script_steps(script_id);
    CREATE INDEX IF NOT EXISTS idx_fields_name ON fields(name);
    CREATE INDEX IF NOT EXISTS idx_fields_table ON fields(table_name);
    CREATE INDEX IF NOT EXISTS idx_layouts_name ON layouts(name);
    CREATE INDEX IF NOT EXISTS idx_script_refs_target ON script_references(target_script_id);
    CREATE INDEX IF NOT EXISTS idx_script_refs_source ON script_references(source_id);
    CREATE INDEX IF NOT EXISTS idx_field_refs_field ON field_references(field_name);
    CREATE INDEX IF NOT EXISTS idx_layout_refs_layout ON layout_references(layout_id);
    """)
    conn.commit()
    return conn


def read_fm_xml(filepath):
    """Read a FileMaker XML file, handling UTF-16 encoding."""
    # Try UTF-16 first (standard FM export), fall back to UTF-8
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(4)
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff') or (len(raw) >= 4 and raw[1] == 0):
            with codecs.open(filepath, 'r', 'utf-16') as f:
                return f.read()
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        with codecs.open(filepath, 'r', 'utf-16') as f:
            return f.read()


def _sanitize_xml_content(content):
    """Remove control characters that are invalid in XML 1.0.
    XML 1.0 allows: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]"""
    import re
    # Match control chars except tab (0x9), newline (0xA), carriage return (0xD)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)


def parse_xml_streaming(filepath):
    """Parse FM XML file and return the root element.
    For very large files, we use iterparse patterns."""
    content = read_fm_xml(filepath)
    # Remove any BOM
    if content and content[0] == '\ufeff':
        content = content[1:]
    # Strip invalid XML 1.0 control characters (common in FM exports)
    content = _sanitize_xml_content(content)
    return ET.fromstring(content)


def translate_step_to_human(step_elem, step_name, step_id):
    """Translate a script step XML element to human-readable FileMaker notation."""
    enabled = step_elem.get('enable', 'True') == 'True'
    prefix = "" if enabled else "// [DISABLED] "

    params = step_elem.find('.//ParameterValues')

    # Comment
    if step_id == 89:
        comment = ""
        cp = step_elem.find('.//Comment')
        if cp is not None:
            comment = cp.get('value', cp.text or '')
        return f"{prefix}# {comment}"

    # Set Variable
    if step_id == 141:
        var_name = ""
        var_value = ""
        var_param = step_elem.find('.//Parameter[@type="Variable"]')
        if var_param is not None:
            name_elem = var_param.find('Name')
            if name_elem is not None:
                var_name = name_elem.get('value', '')
            calc = var_param.find('.//Calculation/Calculation/Text')
            if calc is None:
                calc = var_param.find('.//Calculation//Text')
            if calc is not None:
                var_value = (calc.text or '').strip()
        rep = ""
        rep_elem = step_elem.find('.//repetition//Text')
        if rep_elem is not None and rep_elem.text and rep_elem.text.strip() != '1':
            rep = f"[{rep_elem.text.strip()}]"
        return f"{prefix}Set Variable [ {var_name}{rep} ; Value: {var_value} ]"

    # Set Field
    if step_id == 76:
        field_name = ""
        table_name = ""
        calc_value = ""
        fr = step_elem.find('.//Parameter[@type="FieldReference"]//FieldReference')
        if fr is not None:
            field_name = fr.get('name', '')
            to = fr.find('TableOccurrenceReference')
            if to is not None:
                table_name = to.get('name', '')
        calc_p = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        if calc_p is not None:
            calc_value = (calc_p.text or '').strip()
        full_field = f"{table_name}::{field_name}" if table_name else field_name
        return f"{prefix}Set Field [ {full_field} ; {calc_value} ]"

    # If
    if step_id == 68:
        calc = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        cond = (calc.text or '').strip() if calc is not None else ""
        return f"{prefix}If [ {cond} ]"

    # Else If
    if step_id == 125:
        calc = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        cond = (calc.text or '').strip() if calc is not None else ""
        return f"{prefix}Else If [ {cond} ]"

    # Else
    if step_id == 69:
        return f"{prefix}Else"

    # End If
    if step_id == 70:
        return f"{prefix}End If"

    # Loop
    if step_id == 71:
        return f"{prefix}Loop"

    # Exit Loop If
    if step_id == 72:
        calc = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        cond = (calc.text or '').strip() if calc is not None else ""
        return f"{prefix}Exit Loop If [ {cond} ]"

    # End Loop
    if step_id == 73:
        return f"{prefix}End Loop"

    # Perform Script
    if step_id == 1:
        script_ref = step_elem.find('.//ScriptReference')
        script_name_val = script_ref.get('name', '') if script_ref is not None else ""
        param_calc = step_elem.find('.//Parameter[@type="Parameter"]//Text')
        if param_calc is None:
            # Try alternate location
            params_all = step_elem.findall('.//Parameter')
            for p in params_all:
                if p.get('type') not in ('List', 'ScriptReferenceContainer'):
                    t = p.find('.//Text')
                    if t is not None:
                        param_calc = t
                        break
        param_val = (param_calc.text or '').strip() if param_calc is not None else ""
        if param_val:
            return f'{prefix}Perform Script [ "{script_name_val}" ; Parameter: {param_val} ]'
        return f'{prefix}Perform Script [ "{script_name_val}" ]'

    # Go to Layout
    if step_id == 6:
        lr = step_elem.find('.//LayoutReference')
        layout_name = lr.get('name', '') if lr is not None else "original layout"
        return f'{prefix}Go to Layout [ "{layout_name}" ]'

    # Go to Record/Request/Page
    if step_id == 16:
        rec = step_elem.find('.//Parameter[@type="Records"]')
        target = "unknown"
        if rec is not None:
            rec_elem = rec.find('Records')
            if rec_elem is not None:
                target = rec_elem.get('value', rec_elem.get('name', 'unknown'))
        return f"{prefix}Go to Record/Request/Page [ {target} ]"

    # Enter Find Mode
    if step_id == 22:
        pause = "False"
        bp = step_elem.find('.//Boolean[@type="Pause"]')
        if bp is not None:
            pause = bp.get('value', 'False')
        return f"{prefix}Enter Find Mode [ Pause: {pause} ]"

    # Perform Find
    if step_id == 28:
        return f"{prefix}Perform Find []"

    # Show All Records
    if step_id == 23:
        return f"{prefix}Show All Records"

    # New Record/Request
    if step_id == 7:
        return f"{prefix}New Record/Request"

    # Delete Record/Request
    if step_id == 9:
        no_dialog = ""
        bp = step_elem.find('.//Boolean')
        if bp is not None and bp.get('value') == 'True':
            no_dialog = " [ With dialog: Off ]"
        return f"{prefix}Delete Record/Request{no_dialog}"

    # Commit Records
    if step_id == 75:
        skip = ""
        bp = step_elem.find('.//Boolean')
        if bp is not None:
            skip = " [ Skip data entry validation ; No dialog ]"
        return f"{prefix}Commit Records/Requests{skip}"

    # Sort Records
    if step_id == 39:
        restore = step_elem.find('.//Parameter[@type="Restore"]')
        if restore is not None:
            return f"{prefix}Sort Records [ Restore ; No dialog ]"
        return f"{prefix}Sort Records []"

    # Enter Browse Mode
    if step_id == 55:
        return f"{prefix}Enter Browse Mode []"

    # Enter Preview Mode
    if step_id == 41:
        return f"{prefix}Enter Preview Mode []"

    # Freeze Window
    if step_id == 79:
        return f"{prefix}Freeze Window"

    # Refresh Window
    if step_id == 80:
        return f"{prefix}Refresh Window"

    # Set Error Capture
    if step_id == 86:
        val = "On"
        bp = step_elem.find('.//Boolean')
        if bp is not None:
            val = "On" if bp.get('value') == 'True' else "Off"
        return f"{prefix}Set Error Capture [ {val} ]"

    # Allow User Abort
    if step_id == 85:
        val = "On"
        bp = step_elem.find('.//Boolean')
        if bp is not None:
            val = "On" if bp.get('value') == 'True' else "Off"
        return f"{prefix}Allow User Abort [ {val} ]"

    # Exit Script
    if step_id == 103:
        calc = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        if calc is not None and calc.text:
            return f"{prefix}Exit Script [ Result: {calc.text.strip()} ]"
        return f"{prefix}Exit Script []"

    # Halt Script
    if step_id == 90:
        return f"{prefix}Halt Script"

    # Show Custom Dialog
    if step_id == 87:
        title = ""
        message = ""
        tp = step_elem.find('.//Parameter[@type="Title"]//Text')
        if tp is not None:
            title = (tp.text or '').strip()
        mp = step_elem.find('.//Parameter[@type="Message"]//Text')
        if mp is not None:
            message = (mp.text or '').strip()
        return f'{prefix}Show Custom Dialog [ "{title}" ; "{message}" ]'

    # Open URL
    if step_id == 111:
        url = step_elem.find('.//Parameter[@type="URL"]//Text')
        url_val = (url.text or '').strip() if url is not None else ""
        return f'{prefix}Open URL [ {url_val} ]'

    # Go to Related Record
    if step_id == 74:
        rel = step_elem.find('.//RelatedRecordParameters')
        if rel is not None:
            to_ref = rel.find('.//TableOccurrenceReference')
            layout_ref = rel.find('.//LayoutReference')
            to_name = to_ref.get('name', '') if to_ref is not None else ''
            lay_name = layout_ref.get('name', '') if layout_ref is not None else ''
            return f'{prefix}Go to Related Record [ From table: "{to_name}" ; Using layout: "{lay_name}" ]'
        return f"{prefix}Go to Related Record []"

    # Save Records as PDF
    if step_id == 144:
        path = step_elem.find('.//UniversalPathList')
        path_val = (path.text or '').strip() if path is not None else ""
        return f'{prefix}Save Records as PDF [ "{path_val}" ]'

    # Save Records as Excel
    if step_id == 143:
        path = step_elem.find('.//UniversalPathList')
        path_val = (path.text or '').strip() if path is not None else ""
        return f'{prefix}Save Records as Excel [ "{path_val}" ]'

    # Print
    if step_id == 43:
        return f"{prefix}Print [ ]"

    # Print Setup
    if step_id == 42:
        return f"{prefix}Print Setup [ ]"

    # Send Mail
    if step_id == 63:
        return f"{prefix}Send Mail [ ]"

    # Close Window
    if step_id == 121:
        return f"{prefix}Close Window [ ]"

    # New Window
    if step_id == 122:
        name = step_elem.find('.//WindowReference//Calculation//Text')
        name_val = (name.text or '').strip() if name is not None else ""
        return f'{prefix}New Window [ Name: "{name_val}" ]'

    # Select Window
    if step_id == 123:
        name = step_elem.find('.//WindowReference//Calculation//Text')
        name_val = (name.text or '').strip() if name is not None else ""
        return f'{prefix}Select Window [ Name: "{name_val}" ]'

    # Adjust Window
    if step_id == 31:
        opt = step_elem.find('.//Parameter[@type="List"]//List')
        val = opt.get('name', 'Resize to Fit') if opt is not None else ""
        return f"{prefix}Adjust Window [ {val} ]"

    # Go to Field
    if step_id == 17:
        fr = step_elem.find('.//FieldReference')
        if fr is not None:
            fname = fr.get('name', '')
            to = fr.find('TableOccurrenceReference')
            tname = to.get('name', '') if to is not None else ''
            full = f"{tname}::{fname}" if tname else fname
            return f"{prefix}Go to Field [ {full} ]"
        return f"{prefix}Go to Field []"

    # Go to Portal Row
    if step_id == 99:
        return f"{prefix}Go to Portal Row [ ]"

    # Omit Record
    if step_id == 25:
        return f"{prefix}Omit Record"

    # Show Omitted Only
    if step_id == 27:
        return f"{prefix}Show Omitted Only"

    # Go to Object
    if step_id == 145:
        obj = step_elem.find('.//Parameter[@type="Object"]//Calculation//Text')
        obj_val = (obj.text or '').strip() if obj is not None else ""
        return f'{prefix}Go to Object [ Object Name: "{obj_val}" ]'

    # Set Web Viewer
    if step_id == 146:
        url = step_elem.find('.//Parameter[@type="Calculation"]//Text')
        url_val = (url.text or '').strip() if url is not None else ""
        return f'{prefix}Set Web Viewer [ URL: {url_val} ]'

    # Import Records
    if step_id == 35:
        return f"{prefix}Import Records [ ]"

    # Export Records
    if step_id == 36:
        return f"{prefix}Export Records [ ]"

    # Replace Field Contents
    if step_id == 91:
        fr = step_elem.find('.//FieldReference')
        fname = fr.get('name', '') if fr is not None else ''
        return f"{prefix}Replace Field Contents [ {fname} ]"

    # Delete Portal Row
    if step_id == 104:
        return f"{prefix}Delete Portal Row [ ]"

    # Constrain Found Set
    if step_id == 126:
        return f"{prefix}Constrain Found Set [ ]"

    # Extend Found Set
    if step_id == 127:
        return f"{prefix}Extend Found Set [ ]"

    # Pause/Resume Script
    if step_id == 62:
        dur = step_elem.find('.//Duration//Text')
        if dur is not None and dur.text:
            return f"{prefix}Pause/Resume Script [ Duration: {dur.text.strip()} ]"
        return f"{prefix}Pause/Resume Script [ Indefinitely ]"

    # Insert Text
    if step_id == 61:
        text = step_elem.find('.//Parameter[@type="Text"]//Text')
        text_val = (text.text or '').strip() if text is not None else ""
        return f'{prefix}Insert Text [ "{text_val}" ]'

    # Flush Cache to Disk
    if step_id == 102:
        return f"{prefix}Flush Cache to Disk"

    # Beep
    if step_id == 93:
        return f"{prefix}Beep"

    # Export Field Contents
    if step_id == 132:
        return f"{prefix}Export Field Contents [ ]"

    # Duplicate Record
    if step_id == 8:
        return f"{prefix}Duplicate Record/Request"

    # Delete All Records
    if step_id == 10:
        return f"{prefix}Delete All Records [ No dialog ]"

    # Refresh Object
    if step_id == 167:
        obj = step_elem.find('.//Parameter[@type="Object"]//Calculation//Text')
        obj_val = (obj.text or '').strip() if obj is not None else ""
        return f'{prefix}Refresh Object [ "{obj_val}" ]'

    # Refresh Portal
    if step_id == 180:
        obj = step_elem.find('.//Parameter[@type="Object"]//Calculation//Text')
        obj_val = (obj.text or '').strip() if obj is not None else ""
        return f'{prefix}Refresh Portal [ "{obj_val}" ]'

    # Move/Resize Window
    if step_id == 119:
        return f"{prefix}Move/Resize Window [ ]"

    # Open File
    if step_id == 33:
        ds = step_elem.find('.//DataSourceReference')
        name_val = ds.get('name', '') if ds is not None else ''
        return f'{prefix}Open File [ "{name_val}" ]'

    # Add Account
    if step_id == 134:
        return f"{prefix}Add Account [ ]"

    # Delete Account
    if step_id == 135:
        return f"{prefix}Delete Account [ ]"

    # Re-Login
    if step_id == 138:
        return f"{prefix}Re-Login [ ]"

    # Change Password
    if step_id == 83:
        return f"{prefix}Change Password [ ]"

    # Copy
    if step_id == 47:
        return f"{prefix}Copy [ ]"

    # Paste
    if step_id == 48:
        return f"{prefix}Paste [ ]"

    # Send Event
    if step_id == 57:
        return f"{prefix}Send Event [ ]"

    # Exit Application
    if step_id == 44:
        return f"{prefix}Exit Application"

    # Show/Hide Toolbars
    if step_id == 29:
        return f"{prefix}Show/Hide Toolbars [ ]"

    # Fallback
    return f"{prefix}{step_name} [ ... ]"


def index_file(xml_path, db_path):
    """Index a FileMaker XML file into the SQLite database."""
    print(f"Reading {xml_path}...")
    start = time.time()

    root = parse_xml_streaming(xml_path)

    print(f"  Parsed XML in {time.time()-start:.1f}s")

    conn = create_db(db_path)
    c = conn.cursor()

    # File info
    fm_file = root.get('File', os.path.basename(xml_path))
    fm_uuid = root.get('UUID', '')
    fm_version = root.get('Source', '')
    fm_locale = root.get('locale', '')

    c.execute("INSERT INTO files (filename, filepath, uuid, fm_version, locale, indexed_at) VALUES (?,?,?,?,?,datetime('now'))",
              (fm_file, xml_path, fm_uuid, fm_version, fm_locale))
    file_id = c.lastrowid

    structure = root.find('Structure')
    if structure is None:
        print("ERROR: No <Structure> element found")
        conn.close()
        return

    # Process all AddAction sections
    for add_action in structure.findall('AddAction'):
        # --- Tables and Fields ---
        for fft in add_action.findall('.//FieldsForTables'):
            for fc in fft.findall('FieldCatalog'):
                bt = fc.find('BaseTableReference')
                if bt is None:
                    continue
                table_name = bt.get('name', '')
                table_id_val = int(bt.get('id', 0))
                table_uuid = bt.get('UUID', '')

                obj_list = fc.find('ObjectList')
                field_count = int(obj_list.get('membercount', 0)) if obj_list is not None else 0

                c.execute("INSERT INTO tables_def (file_id, table_id, name, uuid, field_count) VALUES (?,?,?,?,?)",
                          (file_id, table_id_val, table_name, table_uuid, field_count))

                if obj_list is not None:
                    for field in obj_list.findall('Field'):
                        fid = int(field.get('id', 0))
                        fname = field.get('name', '')
                        ftype = field.get('fieldtype', '')
                        dtype = field.get('datatype', '')
                        fcomment = field.get('comment', '')
                        fuuid = ''
                        uuid_elem = field.find('UUID')
                        if uuid_elem is not None and uuid_elem.text:
                            fuuid = uuid_elem.text.strip()

                        is_global = 0
                        storage = field.find('Storage')
                        if storage is not None:
                            is_global = 1 if storage.get('global') == 'True' else 0
                            max_rep = int(storage.get('maxRepetitions', 1))
                        else:
                            max_rep = 1

                        auto_enter = ''
                        ae = field.find('AutoEnter')
                        if ae is not None:
                            auto_enter = ae.get('type', '')

                        validation = ''
                        val = field.find('Validation')
                        if val is not None:
                            validation = val.get('type', '')

                        calc_text = ''
                        calc = field.find('.//Calculation/Text')
                        if calc is not None and calc.text:
                            calc_text = calc.text.strip()

                        c.execute("""INSERT INTO fields
                            (file_id, table_id, table_name, field_id, name, fieldtype, datatype,
                             comment, uuid, is_global, max_repetitions, auto_enter_type,
                             validation_type, calculation_text)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (file_id, table_id_val, table_name, fid, fname, ftype, dtype,
                             fcomment, fuuid, is_global, max_rep, auto_enter, validation, calc_text))

        # --- Value Lists ---
        for vlc in add_action.findall('.//ValueListCatalog'):
            for vl in vlc.findall('.//ValueList'):
                vl_id = int(vl.get('id', 0))
                vl_name = vl.get('name', '')
                vl_uuid = ''
                uuid_elem = vl.find('UUID')
                if uuid_elem is not None and uuid_elem.text:
                    vl_uuid = uuid_elem.text.strip()
                c.execute("INSERT INTO value_lists (file_id, vl_id, name, uuid) VALUES (?,?,?,?)",
                          (file_id, vl_id, vl_name, vl_uuid))

        # --- Relationships ---
        for rc in add_action.findall('.//RelationshipCatalog'):
            for rel in rc.findall('.//Relationship'):
                rid = int(rel.get('id', 0))
                ruuid = ''
                uuid_elem = rel.find('UUID')
                if uuid_elem is not None and uuid_elem.text:
                    ruuid = uuid_elem.text.strip()

                lt = rel.find('LeftTable')
                rt = rel.find('RightTable')

                lt_name = lt_id = rt_name = rt_id = ''
                cascade_c = cascade_d = 0

                if lt is not None:
                    lto = lt.find('TableOccurrenceReference')
                    if lto is not None:
                        lt_name = lto.get('name', '')
                        lt_id = int(lto.get('id', 0))

                if rt is not None:
                    rto = rt.find('TableOccurrenceReference')
                    if rto is not None:
                        rt_name = rto.get('name', '')
                        rt_id = int(rto.get('id', 0))
                    cascade_c = 1 if rt.get('cascadeCreate') == 'True' else 0
                    cascade_d = 1 if rt.get('cascadeDelete') == 'True' else 0

                jp = rel.find('.//JoinPredicateList/JoinPredicate')
                join_type = jp.get('type', '') if jp is not None else ''

                lf_name = rf_name = ''
                if jp is not None:
                    lf = jp.find('.//LeftField//FieldReference')
                    rf = jp.find('.//RightField//FieldReference')
                    if lf is not None:
                        lf_name = lf.get('name', '')
                    if rf is not None:
                        rf_name = rf.get('name', '')

                c.execute("""INSERT INTO relationships
                    (file_id, rel_id, uuid, left_table, left_table_id, right_table, right_table_id,
                     join_type, left_field, right_field, cascade_create, cascade_delete)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (file_id, rid, ruuid, lt_name, lt_id, rt_name, rt_id,
                     join_type, lf_name, rf_name, cascade_c, cascade_d))

        # --- Scripts (catalog) ---
        for sc in add_action.findall('.//ScriptCatalog'):
            for script in sc.findall('Script'):
                sid = int(script.get('id', 0))
                sname = script.get('name', '')
                is_folder = 1 if script.get('isFolder') else 0
                is_sep = 1 if script.get('isSeparatorItem') else 0

                suuid = ''
                uuid_elem = script.find('UUID')
                if uuid_elem is not None and uuid_elem.text:
                    suuid = uuid_elem.text.strip()

                is_hidden = 0
                run_full = 0
                opts = script.find('Options')
                if opts is not None:
                    is_hidden = 1 if opts.get('hidden') == 'True' else 0
                    run_full = 1 if opts.get('runwithfullaccess') == 'True' else 0

                c.execute("""INSERT INTO scripts
                    (file_id, script_id, name, uuid, is_folder, is_separator, is_hidden, run_with_full_access)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (file_id, sid, sname, suuid, is_folder, is_sep, is_hidden, run_full))

        # --- Layouts ---
        for lc in add_action.findall('.//LayoutCatalog'):
            for layout in lc.findall('Layout'):
                lid = int(layout.get('id', 0))
                lname = layout.get('name', '')
                lwidth = int(layout.get('width', 0)) if layout.get('width') else 0

                luuid = ''
                uuid_elem = layout.find('UUID')
                if uuid_elem is not None and uuid_elem.text:
                    luuid = uuid_elem.text.strip()

                to_name = ''
                to_id = 0
                to_ref = layout.find('TableOccurrenceReference')
                if to_ref is not None:
                    to_name = to_ref.get('name', '')
                    to_id = int(to_ref.get('id', 0))

                c.execute("""INSERT INTO layouts
                    (file_id, layout_id, name, uuid, table_occurrence, table_occurrence_id, width)
                    VALUES (?,?,?,?,?,?,?)""",
                    (file_id, lid, lname, luuid, to_name, to_id, lwidth))

                # Extract script references from layout buttons
                for sr in layout.findall('.//ScriptReference'):
                    sr_id = int(sr.get('id', 0))
                    sr_name = sr.get('name', '')
                    sr_uuid = sr.get('UUID', '')
                    c.execute("""INSERT INTO script_references
                        (file_id, source_type, source_id, source_name, target_script_id,
                         target_script_name, target_script_uuid, context)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (file_id, 'layout', lid, lname, sr_id, sr_name, sr_uuid, 'button/trigger'))

                # Extract field references from layout
                for fr in layout.findall('.//FieldReference'):
                    frid = int(fr.get('id', 0))
                    frname = fr.get('name', '')
                    to = fr.find('TableOccurrenceReference')
                    toname = to.get('name', '') if to is not None else ''
                    toid = int(to.get('id', 0)) if to is not None else 0
                    c.execute("""INSERT INTO field_references
                        (file_id, source_type, source_id, source_name, field_id, field_name,
                         table_occurrence, table_occurrence_id, context)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (file_id, 'layout', lid, lname, frid, frname, toname, toid, 'layout_field'))

        # --- External Data Sources ---
        for edsc in add_action.findall('.//ExternalDataSourceCatalog'):
            for eds in edsc.findall('ExternalDataSource'):
                eid = int(eds.get('id', 0))
                ename = eds.get('name', '')
                etype = eds.get('type', '')
                epath = ''
                upl = eds.find('.//UniversalPathList')
                if upl is not None and upl.text:
                    epath = upl.text.strip()
                c.execute("INSERT INTO external_data_sources (file_id, eds_id, name, source_type, path) VALUES (?,?,?,?,?)",
                          (file_id, eid, ename, etype, epath))

        # --- Custom Functions ---
        cf_names = []  # collect for cross-referencing in script steps
        # FM exports use either CustomFunctionCatalog or CustomFunctionsCatalog
        cf_catalogs = add_action.findall('.//CustomFunctionCatalog')
        if not cf_catalogs:
            cf_catalogs = add_action.findall('.//CustomFunctionsCatalog')
        for cfc in cf_catalogs:
            for cf in cfc.findall('.//CustomFunction'):
                cfid = int(cf.get('id', 0))
                cfname = cf.get('name', '')
                cfuuid = ''
                uuid_elem = cf.find('UUID')
                if uuid_elem is not None and uuid_elem.text:
                    cfuuid = uuid_elem.text.strip()
                # Display signature (e.g., "DeclareVariables ( ParameterString )")
                cfdisplay = ''
                disp_elem = cf.find('Display')
                if disp_elem is not None and disp_elem.text:
                    cfdisplay = disp_elem.text.strip()
                # Parameters from ObjectList
                param_names = []
                obj_list = cf.find('ObjectList')
                if obj_list is not None:
                    for param in obj_list.findall('Parameter'):
                        pname = param.get('name', '')
                        if pname:
                            param_names.append(pname)
                cfparams = ', '.join(param_names)
                param_count = len(param_names)
                # Calculation text (DDR may not include this)
                cfcalc = ''
                calc_elem = cf.find('.//Calculation/Text')
                if calc_elem is not None and calc_elem.text:
                    cfcalc = calc_elem.text.strip()
                c.execute("""INSERT INTO custom_functions
                    (file_id, cf_id, name, uuid, display, param_count, parameters, calculation_text)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (file_id, cfid, cfname, cfuuid, cfdisplay, param_count, cfparams, cfcalc))
                cf_names.append((cfid, cfname))

        # --- Script Steps ---
        for sfs in add_action.findall('.//StepsForScripts'):
            for script_block in sfs.findall('Script'):
                sref = script_block.find('ScriptReference')
                if sref is None:
                    continue
                sid = int(sref.get('id', 0))
                sname = sref.get('name', '')

                obj_list = script_block.find('ObjectList')
                step_count = int(obj_list.get('membercount', 0)) if obj_list is not None else 0

                # Update script record with step count
                c.execute("UPDATE scripts SET step_count=? WHERE file_id=? AND script_id=?",
                          (step_count, file_id, sid))

                if obj_list is None:
                    continue

                for step in obj_list.findall('Step'):
                    step_idx = int(step.get('index', 0))
                    step_type_id = int(step.get('id', 0))
                    step_name_val = step.get('name', '')
                    step_enabled = 1 if step.get('enable', 'True') == 'True' else 0

                    # Store raw XML
                    raw_xml = ET.tostring(step, encoding='unicode')

                    # Generate human-readable translation
                    human = translate_step_to_human(step, step_name_val, step_type_id)

                    c.execute("""INSERT INTO script_steps
                        (file_id, script_id, script_name, step_index, step_type_id, step_name,
                         enabled, raw_xml, human_readable)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (file_id, sid, sname, step_idx, step_type_id, step_name_val,
                         step_enabled, raw_xml, human))

                    # Extract script references from Perform Script steps
                    for sr in step.findall('.//ScriptReference'):
                        sr_id_val = int(sr.get('id', 0))
                        sr_name_val = sr.get('name', '')
                        sr_uuid_val = sr.get('UUID', '')
                        c.execute("""INSERT INTO script_references
                            (file_id, source_type, source_id, source_name, target_script_id,
                             target_script_name, target_script_uuid, context)
                            VALUES (?,?,?,?,?,?,?,?)""",
                            (file_id, 'script', sid, sname, sr_id_val, sr_name_val, sr_uuid_val, 'perform_script'))

                    # Extract layout references from Go to Layout steps
                    for lr in step.findall('.//LayoutReference'):
                        lr_id = int(lr.get('id', 0))
                        lr_name = lr.get('name', '')
                        lr_uuid = lr.get('UUID', '')
                        c.execute("""INSERT INTO layout_references
                            (file_id, source_type, source_id, source_name, layout_id, layout_name, layout_uuid)
                            VALUES (?,?,?,?,?,?,?)""",
                            (file_id, 'script', sid, sname, lr_id, lr_name, lr_uuid))

                    # Extract field references from Set Field and other steps
                    for fr in step.findall('.//FieldReference'):
                        frid = int(fr.get('id', 0))
                        frname = fr.get('name', '')
                        to = fr.find('TableOccurrenceReference')
                        toname = to.get('name', '') if to is not None else ''
                        toid = int(to.get('id', 0)) if to is not None else 0
                        c.execute("""INSERT INTO field_references
                            (file_id, source_type, source_id, source_name, field_id, field_name,
                             table_occurrence, table_occurrence_id, context)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (file_id, 'script', sid, sname, frid, frname, toname, toid, 'script_step'))

    # --- Cross-reference custom functions in script steps ---
    if cf_names:
        import re as _re
        # Build a regex pattern matching any CF name as a word boundary
        # Sort by length descending so longer names match first
        sorted_cfs = sorted(cf_names, key=lambda x: len(x[1]), reverse=True)
        cf_pattern = _re.compile(
            r'\b(' + '|'.join(_re.escape(name) for _, name in sorted_cfs) + r')\b'
        )
        cf_id_map = {name: cfid for cfid, name in cf_names}

        # Scan all script step calculations for CF references
        rows = c.execute("""SELECT file_id, script_id, script_name, step_index, raw_xml
                           FROM script_steps WHERE file_id=?""", (file_id,)).fetchall()
        cf_ref_set = set()  # deduplicate (cf_name, script_id, step_index)
        for row in rows:
            raw = row[4] if row[4] else ''
            # Extract text inside <Calculation><Text>...</Text></Calculation> and other text nodes
            matches = cf_pattern.findall(raw)
            for cf_match in matches:
                key = (cf_match, row[1], row[3])
                if key not in cf_ref_set:
                    cf_ref_set.add(key)
                    # Extract a snippet of context (the human-readable step would be ideal)
                    c.execute("""INSERT INTO cf_references
                        (file_id, cf_id, cf_name, script_id, script_name, step_index, context)
                        VALUES (?,?,?,?,?,?,?)""",
                        (file_id, cf_id_map[cf_match], cf_match, row[1], row[2], row[3], 'calculation'))

    conn.commit()

    # Print summary
    c.execute("SELECT COUNT(*) FROM custom_functions WHERE file_id=?", (file_id,))
    cf_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cf_references WHERE file_id=?", (file_id,))
    cf_ref_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tables_def WHERE file_id=?", (file_id,))
    table_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM fields WHERE file_id=?", (file_id,))
    field_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM scripts WHERE file_id=?", (file_id,))
    script_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM script_steps WHERE file_id=?", (file_id,))
    step_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM layouts WHERE file_id=?", (file_id,))
    layout_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM relationships WHERE file_id=?", (file_id,))
    rel_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM script_references WHERE file_id=?", (file_id,))
    ref_count = c.fetchone()[0]

    elapsed = time.time() - start
    print(f"\nIndexed {fm_file} in {elapsed:.1f}s:")
    print(f"  Tables:        {table_count}")
    print(f"  Fields:        {field_count}")
    print(f"  Scripts:       {script_count}")
    print(f"  Script Steps:  {step_count}")
    print(f"  Layouts:       {layout_count}")
    print(f"  Relationships: {rel_count}")
    print(f"  Cross-refs:    {ref_count}")
    print(f"  Custom Funcs:  {cf_count}")
    print(f"  CF References: {cf_ref_count}")
    print(f"\nDatabase saved to: {db_path}")

    conn.close()
    return db_path


def show_info(db_path):
    """Show summary info about an indexed database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    for row in c.execute("SELECT filename, fm_version, locale, indexed_at FROM files"):
        print(f"File: {row[0]}  |  FM Version: {row[1]}  |  Locale: {row[2]}  |  Indexed: {row[3]}")

    c.execute("SELECT COUNT(*) FROM tables_def")
    print(f"\nTables: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM fields")
    print(f"Fields: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM scripts WHERE is_separator=0 AND is_folder=0")
    print(f"Scripts: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM script_steps")
    print(f"Script Steps: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM layouts")
    print(f"Layouts: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM relationships")
    print(f"Relationships: {c.fetchone()[0]}")

    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FileMaker DDR XML Parser')
    sub = parser.add_subparsers(dest='command')

    idx = sub.add_parser('index', help='Index an XML file')
    idx.add_argument('xml_file', help='Path to FM XML file')
    idx.add_argument('--db', default=None, help='Output database path')

    info = sub.add_parser('info', help='Show database info')
    info.add_argument('db_file', help='Path to database')

    args = parser.parse_args()

    if args.command == 'index':
        db = args.db or args.xml_file.rsplit('.', 1)[0] + '.db'
        index_file(args.xml_file, db)
    elif args.command == 'info':
        show_info(args.db_file)
    else:
        parser.print_help()
