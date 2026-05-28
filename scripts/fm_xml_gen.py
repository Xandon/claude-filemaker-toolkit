#!/usr/bin/env python3
"""
FileMaker Script XML Generator

Generates FileMaker script XML that can be pasted via MBS plugin.
Can extract existing scripts as XML, or generate new/modified scripts.

Usage:
    python fm_xml_gen.py extract <db_path> <script_name_or_id>  [--output file.xml]
    python fm_xml_gen.py wrap <steps_xml_file>                   [--output file.xml]
"""

import sys
import sqlite3
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom


def extract_script_xml(db_path, script_name_or_id, output_path=None):
    """Extract a script's steps as clipboard-compatible XML for MBS paste."""
    from fm_ddr_to_clipboard import convert_script_steps
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find script
    try:
        sid = int(script_name_or_id)
        c.execute("SELECT * FROM scripts WHERE script_id=?", (sid,))
    except ValueError:
        c.execute("SELECT * FROM scripts WHERE name=? COLLATE NOCASE", (script_name_or_id,))

    script = c.fetchone()
    if not script:
        c.execute("SELECT * FROM scripts WHERE name LIKE ? COLLATE NOCASE", (f"%{script_name_or_id}%",))
        results = c.fetchall()
        if len(results) == 1:
            script = results[0]
        elif len(results) > 1:
            print(f"Multiple matches:")
            for r in results:
                print(f"  [{r['script_id']}] {r['name']}")
            conn.close()
            return None
        else:
            print(f"Script not found: {script_name_or_id}")
            conn.close()
            return None

    sid = script['script_id']

    # Get all steps
    c.execute("""SELECT step_index, raw_xml FROM script_steps
                 WHERE script_id=? ORDER BY step_index""", (sid,))
    steps = c.fetchall()

    # Convert DDR XML to clipboard format
    raw_list = [step['raw_xml'] for step in steps]
    xml_content = convert_script_steps(raw_list)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"Script XML saved to: {output_path}")
    else:
        print(xml_content)

    conn.close()
    return xml_content


def wrap_steps_xml(steps_xml_path, script_name="Modified Script", script_id="0", output_path=None):
    """Wrap raw step XML in an FMObjectList wrapper for MBS plugin."""
    with open(steps_xml_path, 'r', encoding='utf-8') as f:
        steps_content = f.read()

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<fmxmlsnippet type="FMObjectList">')
    lines.append(f'  <Script id="{script_id}" name="{script_name}">')
    lines.append(f'    <StepList>')
    lines.append(f'      {steps_content}')
    lines.append(f'    </StepList>')
    lines.append(f'  </Script>')
    lines.append('</fmxmlsnippet>')

    xml_content = '\n'.join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"Wrapped XML saved to: {output_path}")
    else:
        print(xml_content)

    return xml_content


def generate_step_xml(step_type, **kwargs):
    """Generate XML for a single FileMaker script step.

    Helper function for programmatically building script steps.
    Returns an XML string for one <Step> element.
    """
    step_templates = {
        'comment': lambda text: f'''<Step index="0" id="89" name="# (comment)" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Comment">
      <Comment value="{_escape(text)}"></Comment>
    </Parameter>
  </ParameterValues>
</Step>''',

        'set_variable': lambda name, value, rep='1': f'''<Step index="0" id="141" name="Set Variable" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Variable">
      <value>
        <Calculation datatype="1" position="1">
          <Calculation><Text><![CDATA[{value}]]></Text></Calculation>
        </Calculation>
      </value>
      <repetition>
        <Calculation datatype="2" position="10">
          <Calculation><Text>{rep}</Text></Calculation>
        </Calculation>
      </repetition>
      <Name value="{_escape(name)}" />
    </Parameter>
  </ParameterValues>
</Step>''',

        'set_field': lambda table, field, value, table_id='0', field_id='0': f'''<Step index="0" id="76" name="Set Field" enable="True">
  <ParameterValues membercount="2">
    <Parameter type="FieldReference">
      <FieldReference id="{field_id}" name="{_escape(field)}">
        <repetition>
          <Calculation datatype="1" position="10"><Calculation><Text>1</Text></Calculation></Calculation>
        </repetition>
        <TableOccurrenceReference id="{table_id}" name="{_escape(table)}" />
      </FieldReference>
    </Parameter>
    <Parameter type="Calculation">
      <Calculation datatype="1" position="0">
        <Calculation><Text><![CDATA[{value}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''',

        'if': lambda condition: f'''<Step index="0" id="68" name="If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text><![CDATA[{condition}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''',

        'else_if': lambda condition: f'''<Step index="0" id="125" name="Else If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text><![CDATA[{condition}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''',

        'else': lambda: '<Step index="0" id="69" name="Else" enable="True"></Step>',
        'end_if': lambda: '<Step index="0" id="70" name="End If" enable="True"></Step>',
        'loop': lambda: '<Step index="0" id="71" name="Loop" enable="True"></Step>',
        'end_loop': lambda: '<Step index="0" id="73" name="End Loop" enable="True"></Step>',

        'exit_loop_if': lambda condition: f'''<Step index="0" id="72" name="Exit Loop If" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="7" position="0">
        <Calculation><Text><![CDATA[{condition}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''',

        'go_to_layout': lambda name, layout_id='0': f'''<Step index="0" id="6" name="Go to Layout" enable="True">
  <ParameterValues membercount="2">
    <Parameter type="LayoutReferenceContainer">
      <LayoutReferenceContainer value="5">
        <LayoutReference id="{layout_id}" name="{_escape(name)}" />
      </LayoutReferenceContainer>
    </Parameter>
    <Parameter type="Animation">
      <Animation name="None" value="0" />
    </Parameter>
  </ParameterValues>
</Step>''',

        'perform_script': lambda name, script_id='0', param='': f'''<Step index="0" id="1" name="Perform Script" enable="True">
  <ParameterValues membercount="2">
    <Parameter type="List">
      <List name="From list" value="0">
        <ScriptReference id="{script_id}" name="{_escape(name)}" />
      </List>
    </Parameter>
    <Parameter type="Parameter">
      <Calculation datatype="1" position="0">
        <Calculation><Text><![CDATA[{param}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''',

        'new_record': lambda: '<Step index="0" id="7" name="New Record/Request" enable="True"></Step>',
        'commit': lambda: '<Step index="0" id="75" name="Commit Records/Requests" enable="True"></Step>',
        'freeze_window': lambda: '<Step index="0" id="79" name="Freeze Window" enable="True"></Step>',
        'refresh_window': lambda: '<Step index="0" id="80" name="Refresh Window" enable="True"></Step>',

        'enter_find_mode': lambda pause='False': f'''<Step index="0" id="22" name="Enter Find Mode" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Boolean">
      <Boolean type="Pause" id="16777216" value="{pause}" />
    </Parameter>
  </ParameterValues>
</Step>''',

        'perform_find': lambda: '<Step index="0" id="28" name="Perform Find" enable="True"></Step>',
        'show_all': lambda: '<Step index="0" id="23" name="Show All Records" enable="True"></Step>',

        # Show Custom Dialog (step id 87). Aliases: 'show_dialog' and 'show_custom_dialog'.
        # title/message are calculation expressions — quote string literals yourself
        # (e.g. '"Navigation Error"'). Defaults to a single OK button.
        'show_dialog': lambda title='', message='', button_ok='OK', button_cancel='':
            (f'''<Step index="0" id="87" name="Show Custom Dialog" enable="True">
  <ParameterValues membercount="{3 if not button_cancel else 4}">
    <Parameter type="Title">
      <Calculation datatype="1" position="0">
        <Calculation><Text><![CDATA[{title}]]></Text></Calculation>
      </Calculation>
    </Parameter>
    <Parameter type="Message">
      <Calculation datatype="1" position="1">
        <Calculation><Text><![CDATA[{message}]]></Text></Calculation>
      </Calculation>
    </Parameter>
    <Parameter type="Button1" value="{_escape(button_ok)}">
      <Boolean type="Commit" value="True" />
    </Parameter>'''
            + (f'''
    <Parameter type="Button2" value="{_escape(button_cancel)}">
      <Boolean type="Commit" value="False" />
    </Parameter>''' if button_cancel else '')
            + '''
  </ParameterValues>
</Step>'''),

        'exit_script': lambda result='': f'''<Step index="0" id="103" name="Exit Script" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Calculation">
      <Calculation datatype="1" position="0">
        <Calculation><Text><![CDATA[{result}]]></Text></Calculation>
      </Calculation>
    </Parameter>
  </ParameterValues>
</Step>''' if result else '<Step index="0" id="103" name="Exit Script" enable="True"></Step>',

        'set_error_capture': lambda on='True': f'''<Step index="0" id="86" name="Set Error Capture" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Boolean">
      <Boolean type="State" id="16777216" value="{on}" />
    </Parameter>
  </ParameterValues>
</Step>''',

        'allow_user_abort': lambda on='False': f'''<Step index="0" id="85" name="Allow User Abort" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Boolean">
      <Boolean type="State" id="16777216" value="{on}" />
    </Parameter>
  </ParameterValues>
</Step>''',

        'go_to_record': lambda target='First': f'''<Step index="0" id="16" name="Go to Record/Request/Page" enable="True">
  <ParameterValues membercount="1">
    <Parameter type="Records">
      <Records name="{target}" value="0" />
    </Parameter>
  </ParameterValues>
</Step>''',
    }

    # Aliases for convenience
    aliases = {
        'show_custom_dialog': 'show_dialog',
        'show_all_records': 'show_all',
        'commit_records': 'commit',
    }
    step_type = aliases.get(step_type, step_type)

    if step_type not in step_templates:
        raise ValueError(f"Unknown step type: {step_type}. Available: {', '.join(step_templates.keys())}")

    template = step_templates[step_type]
    return template(**kwargs)


def _escape(text):
    """Escape XML special characters in attribute values."""
    return (text.replace('&', '&amp;')
                .replace('"', '&quot;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FileMaker Script XML Generator')
    sub = parser.add_subparsers(dest='command')

    ext = sub.add_parser('extract', help='Extract script XML from indexed DB')
    ext.add_argument('db_path', help='Path to indexed .db file')
    ext.add_argument('script', help='Script name or ID')
    ext.add_argument('--output', '-o', help='Output file path')

    wrap = sub.add_parser('wrap', help='Wrap steps XML in FMObjectList')
    wrap.add_argument('steps_file', help='Path to steps XML file')
    wrap.add_argument('--name', default='Modified Script', help='Script name')
    wrap.add_argument('--id', default='0', help='Script ID')
    wrap.add_argument('--output', '-o', help='Output file path')

    args = parser.parse_args()

    if args.command == 'extract':
        extract_script_xml(args.db_path, args.script, args.output)
    elif args.command == 'wrap':
        wrap_steps_xml(args.steps_file, args.name, args.id, args.output)
    else:
        parser.print_help()
