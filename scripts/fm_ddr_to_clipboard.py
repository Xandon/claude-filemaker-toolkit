#!/usr/bin/env python3
"""
FileMaker DDR XML to Clipboard XML Converter

Converts script step XML from FileMaker DDR (Database Design Report) format
to FileMaker clipboard format, which can be pasted via MBS plugin.

The DDR format uses <ParameterValues><Parameter type="..."> structure.
The clipboard format uses step-type-specific child elements.

These are completely different XML schemas for the same data.
"""

import xml.etree.ElementTree as ET
import html as html_mod


def _extract_calc_text(calc_elem):
    """Extract calculation text from DDR's nested Calculation structure.
    DDR: <Calculation datatype="..." position="..."><Calculation><Text>formula</Text></Calculation></Calculation>
    Returns the text content.
    """
    if calc_elem is None:
        return ''
    # Try nested Calculation/Text path
    inner = calc_elem.find('.//Text')
    if inner is not None and inner.text:
        return inner.text
    # Try direct text
    if calc_elem.text:
        return calc_elem.text
    return ''


def _make_cdata_calc(text):
    """Build a clipboard-format <Calculation> element with CDATA."""
    return f'<Calculation><![CDATA[{text}]]></Calculation>'


def _make_calc_elem(tag, text):
    """Build <Tag><Calculation><![CDATA[text]]></Calculation></Tag>"""
    return f'<{tag}><Calculation><![CDATA[{text}]]></Calculation></{tag}>'


def _esc(text):
    """Escape for XML attribute values."""
    return html_mod.escape(str(text), quote=True)


def convert_step(raw_xml):
    """Convert a single DDR step XML to clipboard format.

    Args:
        raw_xml: The raw XML string of a <Step> element from the DDR.

    Returns:
        A clipboard-format XML string for the same step.
    """
    try:
        step = ET.fromstring(raw_xml.strip())
    except ET.ParseError:
        return raw_xml

    step_id = int(step.get('id', '0'))
    step_name = step.get('name', '')
    enabled = step.get('enable', 'True')

    # Get ParameterValues
    pv = step.find('ParameterValues')
    params = list(pv) if pv is not None else []

    # Build clipboard step
    inner_xml = _convert_params(step_id, step_name, params, step)

    if inner_xml:
        return f'<Step enable="{enabled}" id="{step_id}" name="{_esc(step_name)}">\n{inner_xml}\n</Step>'
    else:
        return f'<Step enable="{enabled}" id="{step_id}" name="{_esc(step_name)}"/>'


def _get_param(params, ptype):
    """Find a Parameter element by type attribute."""
    for p in params:
        if p.get('type') == ptype:
            return p
    return None


def _convert_params(step_id, step_name, params, step_elem):
    """Convert DDR ParameterValues to clipboard child elements based on step type."""

    # ── Comment (89) ──────────────────────────────────────────
    if step_id == 89:
        p = _get_param(params, 'Comment')
        if p is not None:
            comment = p.find('Comment')
            if comment is not None:
                val = comment.get('value', '')
                if val:
                    return f'    <Text>{_esc(val)}</Text>'
        return ''

    # ── Set Variable (141) ────────────────────────────────────
    if step_id == 141:
        p = _get_param(params, 'Variable')
        if p is None:
            return ''
        # Value
        value_elem = p.find('value')
        val_text = _extract_calc_text(value_elem.find('Calculation')) if value_elem is not None else ''
        # Repetition
        rep_elem = p.find('repetition')
        rep_text = _extract_calc_text(rep_elem.find('Calculation')) if rep_elem is not None else '1'
        # Name
        name_elem = p.find('Name')
        var_name = name_elem.get('value', '') if name_elem is not None else ''
        lines = []
        lines.append(f'    <Value>\n      {_make_cdata_calc(val_text)}\n    </Value>')
        lines.append(f'    <Repetition>\n      {_make_cdata_calc(rep_text)}\n    </Repetition>')
        lines.append(f'    <Name>{var_name}</Name>')
        return '\n'.join(lines)

    # ── If (68), Else If (125), Exit Loop If (72) ─────────────
    if step_id in (68, 125, 72):
        p = _get_param(params, 'Calculation')
        if p is not None:
            calc = p.find('Calculation')
            text = _extract_calc_text(calc)
            return f'    {_make_cdata_calc(text)}'
        return ''

    # ── Else (69), End If (70), End Loop (73) ─────────────────
    if step_id in (69, 70, 73):
        return ''

    # ── Loop (71) ─────────────────────────────────────────────
    if step_id == 71:
        return '    <FlushType value="Always"/>'

    # ── Set Error Capture (86), Allow User Abort (85) ─────────
    if step_id in (86, 85):
        p = _get_param(params, 'Boolean')
        if p is not None:
            b = p.find('Boolean')
            if b is not None:
                val = b.get('value', 'True')
                return f'    <Set state="{val}"/>'
        return ''

    # ── Exit Script (103) ─────────────────────────────────────
    if step_id == 103:
        p = _get_param(params, 'Calculation')
        if p is not None:
            calc = p.find('Calculation')
            text = _extract_calc_text(calc)
            if text:
                return f'    {_make_cdata_calc(text)}'
        return ''

    # ── Set Field (76) ────────────────────────────────────────
    if step_id == 76:
        lines = []
        # Calculation value
        calc_p = _get_param(params, 'Calculation')
        if calc_p is not None:
            text = _extract_calc_text(calc_p.find('Calculation'))
            lines.append(f'    {_make_cdata_calc(text)}')
        # Field reference
        field_p = _get_param(params, 'FieldReference')
        if field_p is not None:
            fr = field_p.find('FieldReference')
            if fr is not None:
                fid = fr.get('id', '0')
                fname = fr.get('name', '')
                tor = fr.find('TableOccurrenceReference')
                tname = tor.get('name', '') if tor is not None else ''
                lines.append(f'    <Field table="{_esc(tname)}" id="{fid}" name="{_esc(fname)}"/>')
        return '\n'.join(lines)

    # ── Go to Layout (6) ──────────────────────────────────────
    if step_id == 6:
        p = _get_param(params, 'LayoutReferenceContainer')
        if p is not None:
            lrc = p.find('LayoutReferenceContainer')
            if lrc is not None:
                lr = lrc.find('LayoutReference')
                if lr is not None:
                    lid = lr.get('id', '0')
                    lname = lr.get('name', '')
                    lines = []
                    lines.append(f'    <LayoutDestination value="SelectedLayout"/>')
                    lines.append(f'    <Layout id="{lid}" name="{_esc(lname)}"/>')
                    return '\n'.join(lines)
        return '    <LayoutDestination value="CurrentLayout"/>'

    # ── Go to Record/Request/Page (16) ────────────────────────
    if step_id == 16:
        lines = []
        lines.append('    <NoInteract state="True"/>')

        # Direction from Records parameter
        rec_p = _get_param(params, 'Records')
        if rec_p is not None:
            rec = rec_p.find('Records')
            if rec is not None:
                rec_name = rec.get('name', 'First')
                rec_val = rec.get('value', '0')
                if rec_name == 'Next':
                    lines.append('    <Exit state="True"/>')
                    lines.append(f'    <RowPageLocation value="Next"/>')
                elif rec_name == 'Previous':
                    lines.append(f'    <RowPageLocation value="Previous"/>')
                elif rec_name == 'Last':
                    lines.append(f'    <RowPageLocation value="Last"/>')
                else:
                    lines.append(f'    <RowPageLocation value="First"/>')
        else:
            lines.append('    <RowPageLocation value="First"/>')
        return '\n'.join(lines)

    # ── Close Window (121) ────────────────────────────────────
    if step_id == 121:
        p = _get_param(params, 'WindowReference')
        lines = []
        lines.append('    <LimitToWindowsOfCurrentFile state="True"/>')
        if p is not None:
            wr = p.find('WindowReference')
            if wr is not None:
                sel = wr.find('Select')
                if sel is not None:
                    name_el = sel.find('Name')
                    if name_el is not None:
                        calc = name_el.find('Calculation')
                        text = _extract_calc_text(calc)
                        if text:
                            lines.append('    <Window value="ByName"/>')
                            lines.append(f'    {_make_calc_elem("Name", text)}')
                            return '\n'.join(lines)
        lines.append('    <Window value="Current"/>')
        return '\n'.join(lines)

    # ── Show Custom Dialog (87) ───────────────────────────────
    if step_id == 87:
        lines = []
        # Title
        title_p = _get_param(params, 'Title')
        if title_p is not None:
            calc = title_p.find('Calculation')
            text = _extract_calc_text(calc)
            if text:
                lines.append(f'    <Title>\n      {_make_cdata_calc(text)}\n    </Title>')
        # Message
        msg_p = _get_param(params, 'Message')
        if msg_p is not None:
            calc = msg_p.find('Calculation')
            text = _extract_calc_text(calc)
            if text:
                lines.append(f'    <Message>\n      {_make_cdata_calc(text)}\n    </Message>')
        # Buttons
        btn_lines = []
        for btn_type in ('Button1', 'Button2', 'Button3'):
            btn_p = _get_param(params, btn_type)
            if btn_p is not None:
                label = btn_p.get('value', '')
                commit_el = btn_p.find('Boolean')
                commit = commit_el.get('value', 'False') if commit_el is not None else 'False'
                if label:
                    btn_lines.append(f'      <Button CommitState="{commit}">\n        {_make_cdata_calc(label)}\n      </Button>')
                else:
                    btn_lines.append(f'      <Button CommitState="{commit}"/>')
        if btn_lines:
            lines.append('    <Buttons>\n' + '\n'.join(btn_lines) + '\n    </Buttons>')
        # Input fields
        input_p = _get_param(params, 'InputField')
        if input_p is not None:
            # DDR may have multiple InputField parameters
            input_lines = []
            for p in params:
                if p.get('type') == 'InputField':
                    fr = p.find('.//FieldReference')
                    if fr is not None:
                        fid = fr.get('id', '0')
                        fname = fr.get('name', '')
                        tor = fr.find('TableOccurrenceReference')
                        tname = tor.get('name', '') if tor is not None else ''
                        label_calc = p.find('.//Label')
                        label_text = ''
                        if label_calc is not None:
                            lc = label_calc.find('Calculation')
                            label_text = _extract_calc_text(lc)
                        il = f'      <InputField UsePasswordCharacter="False">\n'
                        il += f'        <Field table="{_esc(tname)}" id="{fid}" name="{_esc(fname)}"/>\n'
                        if label_text:
                            il += f'        <Label>\n          {_make_cdata_calc(label_text)}\n        </Label>\n'
                        il += f'      </InputField>'
                        input_lines.append(il)
            if input_lines:
                lines.append('    <InputFields>\n' + '\n'.join(input_lines) + '\n    </InputFields>')
        return '\n'.join(lines)

    # ── Replace Field Contents (91) ───────────────────────────
    if step_id == 91:
        lines = []
        # NoInteract
        no_dialog_p = _get_param(params, 'Boolean')
        no_dialog = 'True'
        if no_dialog_p is not None:
            b = no_dialog_p.find('Boolean')
            if b is not None:
                no_dialog = 'False' if b.get('value') == 'True' else 'True'
        lines.append(f'    <NoInteract state="{no_dialog}"/>')
        # Calculation
        calc_p = _get_param(params, 'Calculation')
        if calc_p is not None:
            text = _extract_calc_text(calc_p.find('Calculation'))
            lines.append('    <With value="Calculation"/>')
            lines.append(f'    {_make_cdata_calc(text)}')
        else:
            lines.append('    <With value="None"/>')
        lines.append('    <SerialNumbers UpdateEntryOptions="False" UseEntryOptions="True"/>')
        # Field reference
        field_p = _get_param(params, 'FieldReference')
        if field_p is not None:
            fr = field_p.find('FieldReference')
            if fr is not None:
                fid = fr.get('id', '0')
                fname = fr.get('name', '')
                tor = fr.find('TableOccurrenceReference')
                tname = tor.get('name', '') if tor is not None else ''
                lines.append(f'    <Field table="{_esc(tname)}" id="{fid}" name="{_esc(fname)}"/>')
        return '\n'.join(lines)

    # ── Go to Related Record (74) ─────────────────────────────
    if step_id == 74:
        p = _get_param(params, 'Related')
        if p is None:
            return ''
        lines = []
        # Options
        opts = p.find('Options')
        match_found = 'False'
        show_related = 'False'
        if opts is not None:
            match_found = opts.get('matchFoundSet', 'False')
            show_related = opts.get('ShowRelated', 'False')

        lines.append(f'    <Option state="False"/>')
        lines.append(f'    <MatchAllRecords state="{match_found}"/>')

        # Window reference
        wr = p.find('WindowReference')
        if wr is not None:
            lines.append('    <ShowInNewWindow state="True"/>')
            lines.append('    <Restore state="True"/>')
            lines.append('    <LayoutDestination value="SelectedLayout"/>')
            # Window name
            name_el = wr.find('Name')
            if name_el is not None:
                calc = name_el.find('Calculation')
                text = _extract_calc_text(calc)
                lines.append(f'    {_make_calc_elem("Name", text)}')
            # Bounds
            bounds = wr.find('Bounds')
            if bounds is not None:
                for dim in ('height', 'width', 'top', 'left'):
                    dim_el = bounds.find(dim)
                    if dim_el is not None:
                        calc = dim_el.find('Calculation')
                        text = _extract_calc_text(calc)
                        tag_map = {'height': 'Height', 'width': 'Width',
                                   'top': 'DistanceFromTop', 'left': 'DistanceFromLeft'}
                        lines.append(f'    {_make_calc_elem(tag_map[dim], text)}')
            # Window style
            style = wr.find('Style')
            if style is not None:
                sname = style.get('name', 'Document')
                sval = style.get('value', '983554')
                lines.append(f'    <NewWndStyles Style="{sname}" Close="Yes" Minimize="Yes" Maximize="Yes" Resize="Yes" Styles="{sval}"/>')
        else:
            lines.append('    <ShowInNewWindow state="False"/>')
            lines.append('    <Restore state="False"/>')
            lines.append('    <LayoutDestination value="CurrentLayout"/>')

        # Table
        tor = p.find('TableOccurrenceReference')
        if tor is not None:
            tid = tor.get('id', '0')
            tname = tor.get('name', '')
            lines.append(f'    <Table id="{tid}" name="{_esc(tname)}"/>')

        # Layout
        lrc = p.find('LayoutReferenceContainer')
        if lrc is not None:
            lr = lrc.find('LayoutReference')
            if lr is not None:
                lid = lr.get('id', '0')
                lname = lr.get('name', '')
                lines.append(f'    <Layout id="{lid}" name="{_esc(lname)}"/>')

        return '\n'.join(lines)

    # ── Import Records (35) ───────────────────────────────────
    if step_id == 35:
        lines = []
        # NoInteract (With dialog boolean)
        for p in params:
            if p.get('type') == 'Boolean':
                b = p.find('Boolean')
                if b is not None:
                    btype = b.get('type', '')
                    if 'dialog' in btype.lower():
                        no_interact = 'True' if b.get('value') == 'False' else 'False'
                        lines.append(f'    <NoInteract state="{no_interact}"/>')
                        lines.append(f'    <Restore state="{no_interact}"/>')
                    elif 'ssl' in btype.lower() or 'verify' in btype.lower():
                        lines.append(f'    <VerifySSLCertificates state="{b.get("value", "False")}"/>')

        # Data source
        ds_p = _get_param(params, 'DataSourceReference')
        if ds_p is not None:
            dsr = ds_p.find('DataSourceReference')
            if dsr is not None:
                file_type = dsr.get('fileType', 'FMPR')
                lines.append(f'    <DataSourceType value="File"/>')
                # Profile (source table)
                imp_p = _get_param(params, 'ImportField')
                if imp_p is not None:
                    imp = imp_p.find('ImportField')
                    if imp is not None:
                        target = imp.find('Target')
                        if target is not None:
                            tor = target.find('TableOccurrenceReference')
                            if tor is not None:
                                tid = tor.get('id', '0')
                                lines.append(f'    <Profile table="{tid}" FieldDelimiter="&#9;" IsPredefined="-1" FieldNameRow="0" DataType="{file_type}"/>')
                # Path
                upl = dsr.find('.//Location')
                if upl is not None and upl.text:
                    lines.append(f'    <UniversalPathList>{_esc(upl.text)}</UniversalPathList>')
                # Import options
                if imp_p is not None:
                    imp = imp_p.find('ImportField')
                    if imp is not None:
                        opts = imp.find('Options')
                        if opts is not None:
                            auto_enter = opts.get('doAutoEntry', 'True')
                            match_names = opts.get('matchFieldNames', 'False')
                            split_rep = opts.get('splitRepetitions', 'False')
                            copy_cont = opts.get('copyContainersAsIs', 'False')
                            lines.append(f'    <ImportOptions CharacterSet="Macintosh" PreserveContainer="{copy_cont}" MatchFieldNames="{match_names}" AutoEnter="{auto_enter}" SplitRepetitions="{split_rep}" method="Add"/>')

        # Target table and field mappings
        imp_p = _get_param(params, 'ImportField')
        if imp_p is not None:
            imp = imp_p.find('ImportField')
            if imp is not None:
                target = imp.find('Target')
                if target is not None:
                    tor = target.find('TableOccurrenceReference')
                    if tor is not None:
                        tid = tor.get('id', '0')
                        tname = tor.get('name', '')
                        lines.append(f'    <Table id="{tid}" name="{_esc(tname)}"/>')
                # Field mappings
                field_container = imp.find('Field')
                if field_container is not None:
                    field_lines = []
                    for m in field_container.findall('Map'):
                        fid = m.get('id', '0')
                        kind = int(m.get('kind', '1'))
                        options = m.get('Options', '0')
                        fr = m.find('FieldReference')
                        if fr is not None:
                            fname = fr.get('name', '')
                            map_val = 'Import' if kind == 0 else 'DoNotImport'
                            field_lines.append(f'      <Field FieldOptions="{options}" map="{map_val}" id="{fid}" name="{_esc(fname)}"/>')
                    if field_lines:
                        lines.append('    <TargetFields>\n' + '\n'.join(field_lines) + '\n    </TargetFields>')

        return '\n'.join(lines)

    # ── Go to Object (145) ────────────────────────────────────
    if step_id == 145:
        p = _get_param(params, 'Object')
        if p is None:
            p = _get_param(params, 'ObjectName')
        lines = []
        if p is not None:
            name_el = p.find('.//Name') or p.find('.//ObjectName')
            if name_el is not None:
                calc = name_el.find('Calculation') if name_el.find('Calculation') is not None else name_el
                text = _extract_calc_text(calc)
                lines.append(f'    <ObjectName>\n      {_make_cdata_calc(text)}\n    </ObjectName>')
            rep_el = p.find('.//repetition') or p.find('.//Repetition')
            if rep_el is not None:
                calc = rep_el.find('Calculation')
                text = _extract_calc_text(calc) or '1'
                lines.append(f'    <Repetition>\n      {_make_cdata_calc(text)}\n    </Repetition>')
            else:
                lines.append(f'    <Repetition>\n      {_make_cdata_calc("1")}\n    </Repetition>')
        else:
            # Try to find calc text directly
            for p2 in params:
                calc = p2.find('.//Calculation')
                if calc is not None:
                    text = _extract_calc_text(calc)
                    if text:
                        lines.append(f'    <ObjectName>\n      {_make_cdata_calc(text)}\n    </ObjectName>')
                        lines.append(f'    <Repetition>\n      {_make_cdata_calc("1")}\n    </Repetition>')
                        break
        return '\n'.join(lines)

    # ── Go to Portal Row (99) ─────────────────────────────────
    if step_id == 99:
        lines = []
        lines.append('    <NoInteract state="False"/>')
        lines.append('    <SelectAll state="True"/>')
        # Row location
        rec_p = _get_param(params, 'Records')
        if rec_p is not None:
            rec = rec_p.find('Records')
            if rec is not None:
                name = rec.get('name', 'First')
                lines.append(f'    <RowPageLocation value="{name}"/>')
            else:
                lines.append('    <RowPageLocation value="First"/>')
        else:
            lines.append('    <RowPageLocation value="First"/>')
        return '\n'.join(lines)

    # ── Freeze Window (79), Refresh Window (80) ───────────────
    if step_id in (79, 80):
        return ''

    # ── Commit Records (75) ───────────────────────────────────
    if step_id == 75:
        lines = []
        lines.append('    <NoInteract state="True"/>')
        p = _get_param(params, 'Boolean')
        if p is not None:
            b = p.find('Boolean')
            if b is not None:
                lines.append(f'    <Option state="{b.get("value", "False")}"/>')
        return '\n'.join(lines)

    # ── New Record (7) ────────────────────────────────────────
    if step_id == 7:
        return ''

    # ── Show All Records (23) ─────────────────────────────────
    if step_id == 23:
        return ''

    # ── Delete All Records (20) ───────────────────────────────
    if step_id == 20:
        lines = []
        p = _get_param(params, 'Boolean')
        if p is not None:
            b = p.find('Boolean')
            if b is not None:
                no_dialog = 'True' if b.get('value') == 'False' else 'False'
                lines.append(f'    <NoInteract state="{no_dialog}"/>')
        else:
            lines.append('    <NoInteract state="True"/>')
        return '\n'.join(lines)

    # ── Perform Script (1) ────────────────────────────────────
    if step_id == 1:
        lines = []
        # Script reference
        list_p = _get_param(params, 'List')
        if list_p is not None:
            sr = list_p.find('.//ScriptReference')
            if sr is not None:
                sid = sr.get('id', '0')
                sname = sr.get('name', '')
                lines.append(f'    <Script id="{sid}" name="{_esc(sname)}"/>')
        # Parameter
        calc_p = _get_param(params, 'Parameter')
        if calc_p is not None:
            calc = calc_p.find('Calculation')
            text = _extract_calc_text(calc)
            if text:
                lines.append(f'    <Parameter>\n      {_make_cdata_calc(text)}\n    </Parameter>')
        return '\n'.join(lines)

    # ── Enter Find Mode (22) ─────────────────────────────────
    if step_id == 22:
        p = _get_param(params, 'Boolean')
        if p is not None:
            b = p.find('Boolean')
            if b is not None:
                return f'    <Pause state="{b.get("value", "False")}"/>'
        return ''

    # ── Perform Find (28) ────────────────────────────────────
    if step_id == 28:
        return ''

    # ── Fallback: return empty (step type not yet mapped) ─────
    return ''


def convert_script_steps(raw_xml_list):
    """Convert a list of DDR step XML strings to clipboard format.

    Args:
        raw_xml_list: List of raw XML strings, one per step.

    Returns:
        Complete clipboard XML string wrapped in fmxmlsnippet.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<fmxmlsnippet type="FMObjectList">']
    for raw in raw_xml_list:
        converted = convert_step(raw)
        # Indent each line of the converted step
        for line in converted.split('\n'):
            lines.append(f'  {line}')
    lines.append('</fmxmlsnippet>')
    return '\n'.join(lines)
