#!/usr/bin/env python3
"""
FileMaker Relationship Graph Visualizer

Generate an interactive, self-contained HTML visualization of FileMaker table
occurrences and their relationships from an indexed DDR SQLite database.

Uses the ACTUAL coordinates from FileMaker's relationship graph so the layout
matches what the developer sees in FileMaker Pro. Table occurrences are rendered
as rectangular boxes colored by base table, connected by relationship lines
showing key field names.

Usage:
    python fm_graph.py <db_path> --output graph.html [--focus "TableName"] [--depth 2]
"""

import sys
import sqlite3
import json
import argparse
from pathlib import Path
from collections import defaultdict, deque


def get_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_table_occurrences(conn):
    c = conn.cursor()
    c.execute("""
        SELECT to_id, name, base_table_id, base_table_name, view, height,
               coord_top, coord_left, coord_bottom, coord_right,
               color_r, color_g, color_b
        FROM table_occurrences ORDER BY name
    """)
    return {row['to_id']: dict(row) for row in c.fetchall()}


def fetch_relationships(conn):
    c = conn.cursor()
    c.execute("""
        SELECT id, rel_id, left_table, left_table_id, left_field,
               right_table, right_table_id, right_field, join_type
        FROM relationships ORDER BY left_table, right_table
    """)
    return [dict(row) for row in c.fetchall()]


def fetch_fields_for_table(conn, base_table_name):
    c = conn.cursor()
    c.execute("""SELECT name, fieldtype, datatype FROM fields
                 WHERE table_name=? ORDER BY name""",
              (base_table_name,))
    return [dict(row) for row in c.fetchall()]


def fetch_layouts_for_to(conn, to_name):
    c = conn.cursor()
    c.execute("SELECT layout_id, name FROM layouts WHERE table_occurrence=? ORDER BY name",
              (to_name,))
    return [dict(row) for row in c.fetchall()]


def get_connected_tos(tos, relationships, focus_name, depth):
    adj = defaultdict(set)
    for rel in relationships:
        adj[rel['left_table']].add(rel['right_table'])
        adj[rel['right_table']].add(rel['left_table'])
    connected = set()
    visited = set()
    queue = deque([(focus_name, 0)])
    while queue:
        name, d = queue.popleft()
        if name in visited:
            continue
        visited.add(name)
        connected.add(name)
        if d < depth:
            for nb in adj.get(name, []):
                if nb not in visited:
                    queue.append((nb, d + 1))
    return {tid for tid, to in tos.items() if to['name'] in connected}


# ── Color palette for base tables ──
PALETTE = [
    '#5B8BD6','#D4845A','#6EAF4D','#C9A832','#9B7BCC','#4BA89E','#D65D5D',
    '#7CAA5C','#5A9BD6','#D17A4A','#3AA8D1','#6EBB6E','#B880CC','#D99440',
    '#5DC4C4','#CC6666','#A060B8','#8EBC5E','#40B8CC','#CC5080',
    '#4E9E80','#D48A2A','#4A9ED6','#9848A0','#70C070','#D06848',
    '#6080CC','#B86E3A','#50B088','#C0A030','#8870C0','#3898B0',
]

# Field type abbreviation for badges
def _type_badge(fieldtype, datatype):
    if fieldtype == 'Summary':
        return 'SUM'
    if fieldtype == 'Calculated':
        return 'CALC'
    dt = (datatype or '').lower()
    if dt == 'text': return 'TEXT'
    if dt == 'number': return 'NUM'
    if dt == 'date': return 'DATE'
    if dt == 'time': return 'TIME'
    if dt == 'timestamp': return 'TS'
    if dt == 'binary': return 'BIN'
    return ''


def generate_html(db_path, output_path, focus_to=None, focus_depth=2):
    conn = get_conn(db_path)
    tos = fetch_table_occurrences(conn)
    relationships = fetch_relationships(conn)
    to_rels_map = defaultdict(list)
    for rel in relationships:
        to_rels_map[rel['left_table']].append(rel)
        to_rels_map[rel['right_table']].append(rel)

    filtered_ids = set(tos.keys())
    if focus_to:
        filtered_ids = get_connected_tos(tos, relationships, focus_to, focus_depth)

    # Assign colors by base table
    base_tables = sorted(set(to['base_table_name'] for to in tos.values()))
    bt_color = {bt: PALETTE[i % len(PALETTE)] for i, bt in enumerate(base_tables)}

    # Cache fields per base table to avoid re-fetching
    _field_cache = {}
    def get_fields(bt_name):
        if bt_name not in _field_cache:
            _field_cache[bt_name] = fetch_fields_for_table(conn, bt_name)
        return _field_cache[bt_name]

    nodes = []
    node_idx = {}
    for to_id in filtered_ids:
        to = tos[to_id]
        rels = to_rels_map.get(to['name'], [])
        node_idx[to_id] = len(nodes)
        fields = get_fields(to['base_table_name'])
        layouts = fetch_layouts_for_to(conn, to['name'])
        color = bt_color.get(to['base_table_name'], '#888')
        nodes.append({
            'id': to_id, 'name': to['name'],
            'bt': to['base_table_name'], 'view': to['view'] or 'Collapse',
            'x': to['coord_left'] or 0, 'y': to['coord_top'] or 0,
            'w': max((to['coord_right'] or 0) - (to['coord_left'] or 0), 120),
            'h': max((to['coord_bottom'] or 0) - (to['coord_top'] or 0), 40),
            'c': color,
            'rc': len(rels),
            'f': [[f['name'], _type_badge(f.get('fieldtype',''), f.get('datatype',''))]
                  for f in fields[:30]],
            'fc': len(fields),
            'lc': len(layouts),
            'ln': [l['name'] for l in layouts[:10]],
        })

    edges = []
    seen = set()
    for rel in relationships:
        lid = rid = None
        for tid, to in tos.items():
            if to['name'] == rel['left_table']:
                lid = tid
            if to['name'] == rel['right_table']:
                rid = tid
        if lid and rid and lid in filtered_ids and rid in filtered_ids:
            if rel['id'] not in seen:
                seen.add(rel['id'])
                edges.append({
                    's': node_idx[lid], 't': node_idx[rid],
                    'lf': rel['left_field'], 'rf': rel['right_field'],
                    'lt': rel['left_table'], 'rt': rel['right_table'],
                    'jt': rel['join_type'] or 'Equal',
                })

    base_table_count = len(base_tables)
    orphans = sum(1 for to in tos.values() if not to_rels_map.get(to['name']))
    stats = {
        'to': len(filtered_ids), 'rel': len(edges),
        'bt': base_table_count, 'orph': orphans,
    }
    conn.close()

    html = _build_html(nodes, edges, stats, bt_color)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Graph written to {output_path}")
    print(f"  Nodes: {len(nodes)} / {len(tos)}  Edges: {len(edges)} / {len(relationships)}")


def _build_html(nodes, edges, stats, bt_color):
    nj = json.dumps(nodes, separators=(',',':'))
    ej = json.dumps(edges, separators=(',',':'))
    sj = json.dumps(stats)
    bj = json.dumps(bt_color)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FileMaker Relationship Graph</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#141622;color:#c8cad0;height:100vh;display:flex;flex-direction:column;overflow:hidden}}
::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-track{{background:#191b2a}}
::-webkit-scrollbar-thumb{{background:#2d3048;border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:#3d4068}}

/* ── Top Bar ── */
.topbar{{background:#191b2a;border-bottom:1px solid rgba(255,255,255,0.06);
  padding:0 20px;height:48px;display:flex;align-items:center;gap:20px;flex-shrink:0;z-index:20}}
.logo{{font-size:14px;font-weight:700;color:#e0e2e8;letter-spacing:-0.3px}}
.logo span{{color:#5b8bd6;margin-left:2px}}
.nav{{display:flex;gap:0}}
.nav a{{padding:12px 16px;font-size:12px;color:#6b6f82;text-decoration:none;
  border-bottom:2px solid transparent;transition:color .15s}}
.nav a.active{{color:#e0e2e8;border-bottom-color:#5b8bd6}}
.nav a:hover{{color:#a0a4b8}}
.search-box{{flex:1;max-width:320px;margin-left:auto;position:relative}}
.search-box input{{width:100%;padding:7px 12px 7px 32px;background:#10121e;border:1px solid rgba(255,255,255,0.08);
  border-radius:6px;color:#c8cad0;font-size:12px;outline:none;transition:border-color .15s}}
.search-box input:focus{{border-color:rgba(91,139,214,0.5)}}
.search-box svg{{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:#4a4d60}}
.stats-row{{display:flex;gap:16px;align-items:center}}
.stat{{text-align:center}}
.stat b{{font-size:13px;color:#8b9cf6;display:block;font-weight:600}}
.stat small{{font-size:9px;color:#4a4d60;text-transform:uppercase;letter-spacing:.6px}}

/* ── Main Layout ── */
.main{{flex:1;display:flex;overflow:hidden;position:relative}}
canvas{{flex:1;background:#141622;cursor:grab}}canvas:active{{cursor:grabbing}}

/* ── Right Panel (Inspector) ── */
.inspector{{width:320px;background:#191b2a;border-left:1px solid rgba(255,255,255,0.06);
  display:flex;flex-direction:column;flex-shrink:0;transition:width .2s ease;overflow:hidden}}
.inspector.collapsed{{width:0;border:none}}
.insp-header{{padding:14px 16px 10px;border-bottom:1px solid rgba(255,255,255,0.06);
  display:flex;align-items:center;gap:10px}}
.insp-icon{{width:32px;height:32px;border-radius:6px;display:flex;align-items:center;
  justify-content:center;font-size:14px;flex-shrink:0}}
.insp-title{{font-size:13px;font-weight:600;color:#e0e2e8}}
.insp-sub{{font-size:10px;color:#4a4d60;text-transform:uppercase;letter-spacing:.5px;margin-top:1px}}
.insp-close{{margin-left:auto;cursor:pointer;color:#4a4d60;font-size:16px;padding:4px}}
.insp-close:hover{{color:#e0e2e8}}
.insp-body{{flex:1;overflow-y:auto;padding:12px 16px}}
.insp-empty{{color:#3a3d50;text-align:center;padding:60px 16px;line-height:1.6;font-size:12px}}
.insp-desc{{font-size:12px;color:#8b8fa4;line-height:1.5;margin-bottom:16px}}
.insp-stats{{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}}
.insp-stat{{background:#10121e;border-radius:6px;padding:8px 12px;flex:1;min-width:80px}}
.insp-stat b{{font-size:14px;color:#e0e2e8;display:block}}
.insp-stat small{{font-size:9px;color:#4a4d60;text-transform:uppercase;letter-spacing:.4px}}
.insp-section{{margin-bottom:16px}}
.insp-section-title{{font-size:10px;font-weight:600;color:#5b6080;text-transform:uppercase;
  letter-spacing:.6px;margin-bottom:8px}}
.rel-item{{padding:8px 10px;background:#10121e;border-radius:5px;margin-bottom:4px;
  cursor:pointer;border-left:3px solid #3a3d50;transition:background .1s}}
.rel-item:hover{{background:#1a1d30;border-left-color:#5b8bd6}}
.rel-fld{{font-family:'JetBrains Mono','Fira Code',Menlo,monospace;font-size:11px;color:#8bb4f6}}
.rel-arr{{color:#4a4d60;margin:0 4px;font-size:12px}}
.rel-tables{{font-size:10px;color:#4a4d60;margin-top:2px}}
.tag{{display:inline-block;padding:2px 8px;background:#1a1d30;border-radius:4px;
  font-size:10px;margin:2px 2px 0 0;color:#8b8fa4;border:1px solid rgba(255,255,255,0.04)}}
.tag.key{{background:rgba(91,139,214,0.12);color:#8bb4f6;border-color:rgba(91,139,214,0.2)}}

/* ── Left Sidebar (Legend) ── */
.sidebar{{width:220px;background:#191b2a;border-right:1px solid rgba(255,255,255,0.06);
  display:flex;flex-direction:column;flex-shrink:0;transition:width .2s ease;overflow:hidden}}
.sidebar.collapsed{{width:0;border:none}}
.sb-header{{padding:14px 16px;border-bottom:1px solid rgba(255,255,255,0.06)}}
.sb-title{{font-size:11px;font-weight:600;color:#5b6080;text-transform:uppercase;letter-spacing:.6px}}
.sb-body{{flex:1;overflow-y:auto;padding:8px 12px}}
.bt-row{{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px;
  cursor:pointer;transition:background .1s;margin-bottom:1px}}
.bt-row:hover{{background:rgba(255,255,255,0.03)}}
.bt-row.active{{background:rgba(91,139,214,0.1)}}
.bt-dot{{width:8px;height:8px;border-radius:2px;flex-shrink:0}}
.bt-name{{font-size:11px;color:#8b8fa4;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bt-cnt{{font-size:10px;color:#3a3d50;flex-shrink:0}}

/* ── Bottom Toolbar ── */
.toolbar{{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);
  background:rgba(25,27,42,0.95);border:1px solid rgba(255,255,255,0.08);
  border-radius:8px;padding:6px 10px;display:flex;align-items:center;gap:6px;
  backdrop-filter:blur(12px);z-index:10}}
.tb-btn{{padding:5px 12px;background:transparent;border:1px solid rgba(255,255,255,0.06);
  border-radius:5px;color:#6b6f82;cursor:pointer;font-size:11px;
  font-family:inherit;transition:all .1s;white-space:nowrap;user-select:none}}
.tb-btn:hover{{background:rgba(255,255,255,0.04);color:#a0a4b8}}
.tb-btn.on{{background:rgba(91,139,214,0.15);border-color:rgba(91,139,214,0.3);color:#8bb4f6}}
.tb-sep{{width:1px;height:20px;background:rgba(255,255,255,0.06)}}
.tb-zoom{{font-size:11px;color:#6b6f82;min-width:48px;text-align:center;user-select:none}}

/* ── Minimap ── */
.minimap{{position:absolute;bottom:16px;right:332px;width:180px;height:120px;
  background:rgba(20,22,34,0.92);border:1px solid rgba(255,255,255,0.08);
  border-radius:6px;overflow:hidden;cursor:crosshair;z-index:10;
  backdrop-filter:blur(8px)}}
.minimap canvas{{width:100%;height:100%}}
</style>
</head>
<body>

<!-- Top Bar -->
<div class="topbar">
  <div class="logo">FileMaker<span>Graph</span></div>
  <div class="nav">
    <a class="active" href="#">Graph</a>
    <a href="#" id="navSchemas">Schemas</a>
    <a href="#" id="navRelations">Relations</a>
  </div>
  <div class="search-box">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="q" placeholder="Search tables..." autocomplete="off">
  </div>
  <div class="stats-row">
    <div class="stat"><b id="s0">0</b><small>TOs</small></div>
    <div class="stat"><b id="s1">0</b><small>Rels</small></div>
    <div class="stat"><b id="s2">0</b><small>Tables</small></div>
  </div>
</div>

<!-- Main Area -->
<div class="main">
  <!-- Left Sidebar -->
  <div class="sidebar" id="sidebar">
    <div class="sb-header"><span class="sb-title">Base Tables</span></div>
    <div class="sb-body" id="legend"></div>
  </div>

  <!-- Canvas -->
  <canvas id="cv"></canvas>

  <!-- Bottom Toolbar -->
  <div class="toolbar">
    <button class="tb-btn" id="bFit" title="Fit all nodes">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
      &nbsp;Fit
    </button>
    <div class="tb-sep"></div>
    <button class="tb-btn" id="bZmOut">-</button>
    <span class="tb-zoom" id="zoomPct">100%</span>
    <button class="tb-btn" id="bZmIn">+</button>
    <div class="tb-sep"></div>
    <button class="tb-btn on" id="bLbl">Labels</button>
    <button class="tb-btn" id="bFld">Fields</button>
    <button class="tb-btn on" id="bRel">Key Fields</button>
    <button class="tb-btn on" id="bOrph">Orphans</button>
    <div class="tb-sep"></div>
    <button class="tb-btn" id="bSB">Sidebar</button>
  </div>

  <!-- Minimap -->
  <div class="minimap" id="mmW"><canvas id="mm"></canvas></div>

  <!-- Right Inspector -->
  <div class="inspector" id="inspector">
    <div class="insp-header">
      <div class="insp-icon" id="inspIcon" style="background:#1a1d30;color:#5b6080">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <div>
        <div class="insp-title" id="inspTitle">TO Inspector</div>
        <div class="insp-sub" id="inspSub">Select a table occurrence</div>
      </div>
      <span class="insp-close" id="inspClose">&times;</span>
    </div>
    <div class="insp-body" id="inspBody">
      <div class="insp-empty">Click a table occurrence or<br>relationship to inspect it</div>
    </div>
  </div>
</div>

<script>
const N={nj};
const E={ej};
const S={sj};
const BTC={bj};

document.getElementById('s0').textContent=S.to;
document.getElementById('s1').textContent=S.rel;
document.getElementById('s2').textContent=S.bt;

// ── Badge colors ──
const BC={{TEXT:'#3aa8d1',NUM:'#d4845a',DATE:'#6eaf4d',TIME:'#9b7bcc',TS:'#c9a832',
  BIN:'#cc6666',CALC:'#5b8bd6',SUM:'#d65d5d'}};

// ── State ──
let px=0,py=0,sc=1,selN=null,selE=null,drag=false,qry='';
let showLbl=true,showFld=false,showOrph=true,showRel=true;
let hlN=new Set(),lm={{x:0,y:0}},filterBT=null;
const cv=document.getElementById('cv'),c=cv.getContext('2d');

// ── Graph bounds ──
let gxMin=1e9,gyMin=1e9,gxMax=-1e9,gyMax=-1e9;
N.forEach(n=>{{gxMin=Math.min(gxMin,n.x);gyMin=Math.min(gyMin,n.y);
  gxMax=Math.max(gxMax,n.x+n.w);gyMax=Math.max(gyMax,n.y+n.h)}});
const gW=gxMax-gxMin+300,gH=gyMax-gyMin+300;
N.forEach(n=>{{n.x-=gxMin-150;n.y-=gyMin-150}});

// ── Build legend sidebar ──
(function(){{
  const counts={{}};
  N.forEach(n=>{{counts[n.bt]=(counts[n.bt]||0)+1}});
  const sorted=Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  let h='';
  sorted.forEach(([bt,cnt])=>{{
    const col=BTC[bt]||'#888';
    const short=bt.replace(/__/g,' ').replace(/_/g,' ');
    h+='<div class="bt-row" data-bt="'+bt+'" title="'+bt+'">'+
       '<div class="bt-dot" style="background:'+col+'"></div>'+
       '<span class="bt-name">'+short+'</span>'+
       '<span class="bt-cnt">'+cnt+'</span></div>';
  }});
  document.getElementById('legend').innerHTML=h;
  document.querySelectorAll('.bt-row').forEach(el=>{{
    el.addEventListener('click',function(){{
      const bt=this.dataset.bt;
      if(filterBT===bt){{filterBT=null;document.querySelectorAll('.bt-row').forEach(r=>r.classList.remove('active'))}}
      else{{filterBT=bt;document.querySelectorAll('.bt-row').forEach(r=>r.classList.toggle('active',r.dataset.bt===bt))}}
      draw();
    }});
  }});
}})();

function resize(){{cv.width=cv.offsetWidth;cv.height=cv.offsetHeight;draw()}}
window.addEventListener('resize',resize);

function vis(n){{
  if(!showOrph&&n.rc===0)return false;
  if(filterBT&&n.bt!==filterBT)return false;
  if(qry&&!n.name.toLowerCase().includes(qry)&&!n.bt.toLowerCase().includes(qry))return false;
  return true;
}}
function tw(sx,sy){{return[(sx-px)/sc,(sy-py)/sc]}}

// ── Color helpers ──
function hex2rgb(h){{const r=parseInt(h.slice(1,3),16),g=parseInt(h.slice(3,5),16),b=parseInt(h.slice(5,7),16);return[r,g,b]}}
function darken(hex,f){{const[r,g,b]=hex2rgb(hex);return'rgb('+Math.round(r*f)+','+Math.round(g*f)+','+Math.round(b*f)+')'}}
function lighten(hex,f){{const[r,g,b]=hex2rgb(hex);return'rgb('+Math.min(255,Math.round(r+(255-r)*f))+','+Math.min(255,Math.round(g+(255-g)*f))+','+Math.min(255,Math.round(b+(255-b)*f))+')'}}
function alpha(hex,a){{const[r,g,b]=hex2rgb(hex);return'rgba('+r+','+g+','+b+','+a+')'}}

function clipPt(bx,by,bw,bh,tx,ty){{
  const cx=bx+bw/2,cy=by+bh/2,dx=tx-cx,dy=ty-cy;
  if(dx===0&&dy===0)return[cx,cy];
  const sx=dx!==0?(dx>0?(bx+bw-cx):(bx-cx))/dx:1e9;
  const sy=dy!==0?(dy>0?(by+bh-cy):(by-cy))/dy:1e9;
  const s=Math.min(sx,sy);
  return[cx+dx*s,cy+dy*s];
}}

// ── Rounded rect helper ──
function rRect(x,y,w,h,r){{
  c.beginPath();
  c.moveTo(x+r,y);c.lineTo(x+w-r,y);c.arcTo(x+w,y,x+w,y+r,r);
  c.lineTo(x+w,y+h-r);c.arcTo(x+w,y+h,x+w-r,y+h,r);
  c.lineTo(x+r,y+h);c.arcTo(x,y+h,x,y+h-r,r);
  c.lineTo(x,y+r);c.arcTo(x,y,x+r,y,r);
  c.closePath();
}}

// ── Drawing ──
function draw(){{
  const dpr=1;
  c.fillStyle='#141622';c.fillRect(0,0,cv.width,cv.height);
  c.save();c.translate(px,py);c.scale(sc,sc);

  // Subtle grid dots
  if(sc<0.12){{
    c.fillStyle='rgba(40,43,65,0.4)';
    const step=500;
    for(let x=0;x<gW;x+=step)for(let y=0;y<gH;y+=step)c.fillRect(x,y,2/sc,2/sc);
  }}

  const R=6/sc; // corner radius

  // ── Relationship lines ──
  E.forEach((e,i)=>{{
    const s=N[e.s],t=N[e.t];
    if(!vis(s)||!vis(t))return;

    const p1=clipPt(s.x,s.y,s.w,s.h,t.x+t.w/2,t.y+t.h/2);
    const p2=clipPt(t.x,t.y,t.w,t.h,s.x+s.w/2,s.y+s.h/2);

    const isSel=selE===i;
    const isHl=hlN.size>0&&hlN.has(e.s)&&hlN.has(e.t);

    // Line
    c.beginPath();c.moveTo(p1[0],p1[1]);c.lineTo(p2[0],p2[1]);
    if(isSel){{c.strokeStyle='#5b8bd6';c.lineWidth=2.5/sc}}
    else if(isHl){{c.strokeStyle='rgba(91,139,214,0.55)';c.lineWidth=1.8/sc}}
    else{{c.strokeStyle='rgba(60,65,100,'+(sc>0.2?0.25:0.12)+')';c.lineWidth=1/sc}}
    c.stroke();

    // Endpoint dots
    if(sc>0.15){{
      const dotR=2.5/sc;
      const col=isSel?'#5b8bd6':isHl?'rgba(91,139,214,0.5)':'rgba(60,65,100,0.3)';
      c.fillStyle=col;
      c.beginPath();c.arc(p1[0],p1[1],dotR,0,Math.PI*2);c.fill();
      c.beginPath();c.arc(p2[0],p2[1],dotR,0,Math.PI*2);c.fill();
    }}

    // Field labels on lines
    if(showRel&&sc>0.45&&(isSel||isHl||sc>0.8)){{
      const mx=(p1[0]+p2[0])/2,my=(p1[1]+p2[1])/2;
      const fs=9/sc;
      c.font='500 '+fs+'px "JetBrains Mono","Fira Code",Menlo,monospace';
      const sym=e.jt==='Equal'?'=':e.jt==='NotEqual'?'\\u2260':e.jt==='CartesianProduct'?'\\u00D7':e.jt==='LessOrEqual'?'\\u2264':'\\u2265';
      const lbl=e.lf+' '+sym+' '+e.rf;
      const tw2=c.measureText(lbl).width;
      // Background pill
      rRect(mx-tw2/2-5/sc,my-fs/2-3/sc,tw2+10/sc,fs+6/sc,3/sc);
      c.fillStyle='rgba(20,22,34,0.92)';c.fill();
      c.strokeStyle='rgba(255,255,255,0.06)';c.lineWidth=0.5/sc;c.stroke();
      c.fillStyle=isSel||isHl?'#8bb4f6':'rgba(100,110,150,0.7)';
      c.textAlign='center';c.textBaseline='middle';
      c.fillText(lbl,mx,my);
    }}
  }});

  // ── Table Occurrence cards ──
  N.forEach((n,i)=>{{
    if(!vis(n))return;

    const isSel=selN===i;
    const isHl=hlN.has(i);
    const isQ=qry&&n.name.toLowerCase().includes(qry);
    const col=n.c;

    // ── Ultra far: colored dot ──
    if(sc<0.06){{
      c.fillStyle=isHl?lighten(col,0.3):col;
      c.fillRect(n.x+n.w*0.2,n.y+n.h*0.2,n.w*0.6,n.h*0.6);
      return;
    }}

    // ── Far: colored rect with subtle border ──
    if(sc<0.15){{
      rRect(n.x,n.y,n.w,n.h,2/sc);
      c.fillStyle=isHl||isQ?lighten(col,0.1):darken(col,0.6);c.fill();
      c.strokeStyle=isQ?'#ffd54f':isSel?'#5b8bd6':isHl?lighten(col,0.3):'rgba(255,255,255,0.05)';
      c.lineWidth=(isSel||isQ?2:0.7)/sc;c.stroke();
      return;
    }}

    // ── Medium / Close: Full Stitch-style card ──
    const hdrH=26/sc;

    // Shadow for selected
    if(isSel){{
      c.shadowColor='rgba(91,139,214,0.3)';c.shadowBlur=20/sc;
      c.shadowOffsetX=0;c.shadowOffsetY=4/sc;
    }}

    // Card body
    rRect(n.x,n.y,n.w,n.h,R);
    c.fillStyle='#1e2035';c.fill();

    // Reset shadow
    c.shadowColor='transparent';c.shadowBlur=0;c.shadowOffsetX=0;c.shadowOffsetY=0;

    // Header bar with base-table color
    c.save();
    rRect(n.x,n.y,n.w,n.h,R);
    c.clip();
    c.fillStyle=isSel?lighten(col,0.1):isHl?lighten(col,0.05):col;
    c.fillRect(n.x,n.y,n.w,hdrH);
    // Subtle gradient on header
    const hg=c.createLinearGradient(n.x,n.y,n.x,n.y+hdrH);
    hg.addColorStop(0,'rgba(255,255,255,0.08)');hg.addColorStop(1,'rgba(0,0,0,0.08)');
    c.fillStyle=hg;c.fillRect(n.x,n.y,n.w,hdrH);
    c.restore();

    // Card border
    rRect(n.x,n.y,n.w,n.h,R);
    c.strokeStyle=isQ?'#ffd54f':isSel?'rgba(91,139,214,0.6)':isHl?alpha(col,0.4):'rgba(255,255,255,0.06)';
    c.lineWidth=(isSel||isQ?2:0.8)/sc;c.stroke();

    // TO name in header
    if(showLbl||isSel||isQ||sc>0.18){{
      const fs=Math.min(12,Math.max(9,11))/sc;
      c.font='600 '+fs+'px Inter,-apple-system,sans-serif';
      c.fillStyle='#fff';c.textAlign='left';c.textBaseline='middle';
      let lbl=n.name;
      const mxW=n.w-12/sc;
      while(c.measureText(lbl).width>mxW&&lbl.length>3)lbl=lbl.slice(0,-1);
      if(lbl!==n.name)lbl+='\\u2026';
      c.fillText(lbl,n.x+8/sc,n.y+hdrH/2);
    }}

    // Base table subtitle
    if(sc>0.35&&n.bt!==n.name){{
      const fs2=9/sc;
      c.font='400 '+fs2+'px Inter,-apple-system,sans-serif';
      c.fillStyle='rgba(200,202,210,0.45)';
      c.textBaseline='top';c.textAlign='left';
      let sub=n.bt.replace(/__/g,' \\u203a ');
      const mxW2=n.w-12/sc;
      while(c.measureText(sub).width>mxW2&&sub.length>3)sub=sub.slice(0,-1);
      c.fillText(sub,n.x+8/sc,n.y+hdrH+5/sc);
    }}

    // ── Field list (Stitch-style with type badges) ──
    if(showFld&&n.f.length>0&&sc>0.4){{
      const ffs=9/sc;
      const badgeFs=7.5/sc;
      const rowH=ffs+7/sc;
      const startY=n.y+hdrH+(n.bt!==n.name?ffs+10/sc:6/sc);
      const maxLn=Math.floor((n.y+n.h-startY-4/sc)/rowH);

      for(let fi=0;fi<Math.min(n.f.length,Math.max(0,maxLn));fi++){{
        const[fn,ft]=n.f[fi];
        const ry=startY+fi*rowH;
        const isKey=fn.startsWith('_')||fn.startsWith('__');

        // Alternating row bg
        if(fi%2===0){{
          c.fillStyle='rgba(255,255,255,0.015)';
          c.fillRect(n.x+1/sc,ry-1/sc,n.w-2/sc,rowH);
        }}

        // Field icon dot
        const dotCol=isKey?'#5b8bd6':'rgba(100,110,150,0.4)';
        c.fillStyle=dotCol;
        c.beginPath();c.arc(n.x+12/sc,ry+ffs/2+1/sc,2/sc,0,Math.PI*2);c.fill();

        // Field name
        c.font='400 '+ffs+'px "JetBrains Mono","Fira Code",Menlo,monospace';
        c.fillStyle=isKey?'rgba(139,180,246,0.8)':'rgba(200,202,210,0.55)';
        c.textAlign='left';c.textBaseline='top';
        let txt=fn;
        const badgeW=ft?(c.font=badgeFs+'px Inter,sans-serif',c.measureText(ft).width+8/sc):0;
        c.font='400 '+ffs+'px "JetBrains Mono","Fira Code",Menlo,monospace';
        const mxW3=n.w-24/sc-badgeW;
        while(c.measureText(txt).width>mxW3&&txt.length>3)txt=txt.slice(0,-1);
        if(txt!==fn)txt+='\\u2026';
        c.fillText(txt,n.x+18/sc,ry);

        // Type badge
        if(ft&&sc>0.5){{
          c.font='600 '+badgeFs+'px Inter,sans-serif';
          const tw3=c.measureText(ft).width;
          const bx=n.x+n.w-tw3-12/sc;
          const by2=ry-0.5/sc;
          const bw=tw3+6/sc;
          const bh=badgeFs+4/sc;
          const badgeCol=BC[ft]||'#6b6f82';
          rRect(bx,by2,bw,bh,2/sc);
          c.fillStyle=alpha(badgeCol,0.15);c.fill();
          c.fillStyle=badgeCol;
          c.textAlign='center';c.textBaseline='top';
          c.fillText(ft,bx+bw/2,by2+2/sc);
        }}
      }}
      if(n.f.length>maxLn&&maxLn>0){{
        const ry=startY+maxLn*rowH;
        c.font='400 '+(ffs*0.9)+'px Inter,sans-serif';
        c.fillStyle='rgba(100,110,150,0.4)';c.textAlign='left';c.textBaseline='top';
        c.fillText('+'+(n.fc-Math.min(n.f.length,maxLn))+' more fields',n.x+18/sc,ry);
      }}
    }}
  }});

  c.restore();
  drawMM();
  document.getElementById('zoomPct').textContent=Math.round(sc*100)+'%';
}}

// ── Minimap ──
const mmC=document.getElementById('mm'),mmX=mmC.getContext('2d');
function drawMM(){{
  const w=mmC.width=mmC.offsetWidth,h=mmC.height=mmC.offsetHeight;
  if(!w||!h)return;
  mmX.fillStyle='#10121e';mmX.fillRect(0,0,w,h);
  const s=Math.min(w/gW,h/gH)*0.9;
  const ox=(w-gW*s)/2,oy=(h-gH*s)/2;
  N.forEach(n=>{{
    if(!vis(n))return;
    mmX.fillStyle=hlN.has(N.indexOf(n))?lighten(n.c,0.3):n.c;
    mmX.fillRect(ox+n.x*s,oy+n.y*s,Math.max(2,n.w*s),Math.max(1,n.h*s));
  }});
  const vx=(-px/sc)*s+ox,vy=(-py/sc)*s+oy,vw=(cv.width/sc)*s,vh=(cv.height/sc)*s;
  mmX.strokeStyle='rgba(91,139,214,0.6)';mmX.lineWidth=1.5;
  mmX.strokeRect(vx,vy,vw,vh);
}}

document.getElementById('mmW').addEventListener('mousedown',function(ev){{
  const r=mmC.getBoundingClientRect();
  const w=mmC.offsetWidth,h=mmC.offsetHeight;
  const s=Math.min(w/gW,h/gH)*0.9;
  const ox=(w-gW*s)/2,oy=(h-gH*s)/2;
  const mx2=(ev.clientX-r.left-ox)/s,my2=(ev.clientY-r.top-oy)/s;
  px=-mx2*sc+cv.width/2;py=-my2*sc+cv.height/2;draw();
}});

// ── Hit testing ──
function hitN(wx,wy){{for(let i=N.length-1;i>=0;i--){{const n=N[i];if(!vis(n))continue;
  if(wx>=n.x&&wx<=n.x+n.w&&wy>=n.y&&wy<=n.y+n.h)return i}}return null}}
function hitE(wx,wy){{let best=null,bd=10/sc;
  E.forEach((e,i)=>{{const s2=N[e.s],t2=N[e.t];if(!vis(s2)||!vis(t2))return;
    const d=dSeg(wx,wy,s2.x+s2.w/2,s2.y+s2.h/2,t2.x+t2.w/2,t2.y+t2.h/2);
    if(d<bd){{bd=d;best=i}}}});return best}}
function dSeg(px2,py2,x1,y1,x2,y2){{const dx=x2-x1,dy=y2-y1,l2=dx*dx+dy*dy;
  if(l2===0)return Math.hypot(px2-x1,py2-y1);
  let t=((px2-x1)*dx+(py2-y1)*dy)/l2;t=Math.max(0,Math.min(1,t));
  return Math.hypot(px2-(x1+t*dx),py2-(y1+t*dy))}}

// ── Mouse events ──
cv.addEventListener('mousedown',ev=>{{
  const[wx,wy]=tw(ev.offsetX,ev.offsetY);
  const ni=hitN(wx,wy);
  if(ni!==null){{selN=ni;selE=null;hlConn(ni);showND(ni)}}
  else{{const ei=hitE(wx,wy);
    if(ei!==null){{selE=ei;selN=null;hlN.clear();hlN.add(E[ei].s);hlN.add(E[ei].t);showED(ei)}}
    else{{drag=true;selN=null;selE=null;hlN.clear();
      document.getElementById('inspBody').innerHTML='<div class="insp-empty">Click a table occurrence or<br>relationship to inspect it</div>';
      document.getElementById('inspTitle').textContent='TO Inspector';
      document.getElementById('inspSub').textContent='Select a table occurrence';
      document.getElementById('inspIcon').style.background='#1a1d30';
      document.getElementById('inspIcon').style.color='#5b6080';
    }}
  }}
  lm={{x:ev.clientX,y:ev.clientY}};draw()
}});
cv.addEventListener('mousemove',ev=>{{
  const dx=ev.clientX-lm.x,dy=ev.clientY-lm.y;lm={{x:ev.clientX,y:ev.clientY}};
  if(drag){{px+=dx;py+=dy;draw()}}
}});
cv.addEventListener('mouseup',()=>drag=false);
cv.addEventListener('mouseleave',()=>drag=false);
cv.addEventListener('wheel',ev=>{{
  ev.preventDefault();
  const[wx,wy]=tw(ev.offsetX,ev.offsetY);
  const f=ev.deltaY<0?1.12:0.89;
  const ns=Math.max(0.015,Math.min(10,sc*f));
  px=ev.offsetX-wx*ns;py=ev.offsetY-wy*ns;sc=ns;draw()
}},{{passive:false}});

cv.addEventListener('dblclick',ev=>{{
  const[wx,wy]=tw(ev.offsetX,ev.offsetY);
  const ni=hitN(wx,wy);
  if(ni!==null){{const n=N[ni];sc=Math.min(2,cv.width/(n.w*5));
    px=cv.width/2-(n.x+n.w/2)*sc;py=cv.height/2-(n.y+n.h/2)*sc;
    selN=ni;selE=null;hlConn(ni);showND(ni);draw()}}
}});

function hlConn(i){{hlN.clear();hlN.add(i);
  E.forEach(e=>{{if(e.s===i||e.t===i){{hlN.add(e.s);hlN.add(e.t)}}
  }})}}

// ── Inspector panel ──
function esc(s){{return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}}
function showND(i){{
  const n=N[i];const rels=E.filter(e=>e.s===i||e.t===i);
  document.getElementById('inspTitle').textContent=n.name;
  document.getElementById('inspSub').textContent='TABLE OCCURRENCE';
  document.getElementById('inspIcon').style.background=alpha(n.c,0.15);
  document.getElementById('inspIcon').style.color=n.c;
  document.getElementById('inspIcon').innerHTML='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>';

  let h='<div class="insp-desc">Base table: <strong style="color:#e0e2e8">'+esc(n.bt)+'</strong><br>'+
    'View: '+esc(n.view)+'</div>';
  h+='<div class="insp-stats">';
  h+='<div class="insp-stat"><b>'+n.fc+'</b><small>Fields</small></div>';
  h+='<div class="insp-stat"><b>'+n.rc+'</b><small>Rels</small></div>';
  h+='<div class="insp-stat"><b>'+n.lc+'</b><small>Layouts</small></div>';
  h+='</div>';

  if(rels.length){{
    h+='<div class="insp-section"><div class="insp-section-title">Relationships ('+rels.length+')</div>';
    rels.forEach(r=>{{
      const other=r.s===i?r.rt:r.lt;
      const sym=r.jt==='Equal'?'=':r.jt==='NotEqual'?'\\u2260':r.jt==='CartesianProduct'?'\\u00D7':r.jt==='LessOrEqual'?'\\u2264':'\\u2265';
      h+='<div class="rel-item" onclick="goTO(\\''+esc(other)+'\\')">'+
        '<span class="rel-fld">'+esc(r.lf)+'</span><span class="rel-arr">'+sym+'</span><span class="rel-fld">'+esc(r.rf)+'</span>'+
        '<div class="rel-tables">'+esc(r.lt)+' \\u2194 '+esc(r.rt)+'</div></div>';
    }});h+='</div>';
  }}
  if(n.ln.length){{
    h+='<div class="insp-section"><div class="insp-section-title">Layouts</div>';
    n.ln.forEach(l=>{{h+='<span class="tag">'+esc(l)+'</span>'}});h+='</div>';
  }}
  if(n.f.length){{
    h+='<div class="insp-section"><div class="insp-section-title">Fields ('+n.fc+')</div>';
    n.f.forEach(f=>{{
      const isK=f[0].startsWith('_');
      const badge=f[1]?'<span style="float:right;font-size:9px;padding:1px 5px;border-radius:3px;'+
        'background:'+alpha(BC[f[1]]||'#6b6f82',0.15)+';color:'+(BC[f[1]]||'#6b6f82')+'">'+f[1]+'</span>':'';
      h+='<span class="tag'+(isK?' key':'')+'">'+badge+(isK?'\\uD83D\\uDD11 ':'')+esc(f[0])+'</span>';
    }});
    if(n.fc>n.f.length)h+='<span class="tag">+'+(n.fc-n.f.length)+' more</span>';
    h+='</div>';
  }}
  document.getElementById('inspBody').innerHTML=h;
}}
function showED(i){{
  const e=E[i];
  const sym=e.jt==='Equal'?'=':e.jt==='NotEqual'?'\\u2260':e.jt==='CartesianProduct'?'\\u00D7':e.jt==='LessOrEqual'?'\\u2264':'\\u2265';
  document.getElementById('inspTitle').textContent='Relationship';
  document.getElementById('inspSub').textContent=e.jt.toUpperCase()+' JOIN';
  document.getElementById('inspIcon').style.background='rgba(91,139,214,0.15)';
  document.getElementById('inspIcon').style.color='#5b8bd6';
  document.getElementById('inspIcon').innerHTML='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';

  let h='<div style="padding:16px;background:#10121e;border-radius:6px;margin-bottom:16px;'+
    'font-family:JetBrains Mono,Fira Code,Menlo,monospace;font-size:12px;line-height:2">'+
    '<span style="color:#8bb4f6">'+esc(e.lt)+'</span>.<span style="color:#e0e2e8">'+esc(e.lf)+'</span><br>'+
    '<span style="color:#4a4d60;font-size:16px">&nbsp; '+sym+' </span><br>'+
    '<span style="color:#8bb4f6">'+esc(e.rt)+'</span>.<span style="color:#e0e2e8">'+esc(e.rf)+'</span></div>'+
    '<div style="display:flex;gap:6px">'+
    '<button class="tb-btn" onclick="goTO(\\''+esc(e.lt)+'\\')">\\u2192 '+esc(e.lt)+'</button>'+
    '<button class="tb-btn" onclick="goTO(\\''+esc(e.rt)+'\\')">\\u2192 '+esc(e.rt)+'</button></div>';
  document.getElementById('inspBody').innerHTML=h;
}}
function goTO(name){{
  const i=N.findIndex(n=>n.name===name);if(i<0)return;
  const n=N[i];sc=Math.min(1.5,cv.width/(n.w*6));
  px=cv.width/2-(n.x+n.w/2)*sc;py=cv.height/2-(n.y+n.h/2)*sc;
  selN=i;selE=null;hlConn(i);showND(i);draw();
}}

// ── Toolbar ──
function tog(id,get,set){{document.getElementById(id).addEventListener('click',function(){{
  set(!get());this.classList.toggle('on');draw()}})}}
tog('bLbl',()=>showLbl,v=>showLbl=v);
tog('bFld',()=>showFld,v=>showFld=v);
tog('bOrph',()=>showOrph,v=>showOrph=v);
tog('bRel',()=>showRel,v=>showRel=v);

function fitAll(){{sc=Math.min(cv.width/gW,cv.height/gH)*0.95;
  px=(cv.width-gW*sc)/2;py=(cv.height-gH*sc)/2;draw()}}
document.getElementById('bFit').addEventListener('click',fitAll);

document.getElementById('bZmIn').addEventListener('click',()=>{{
  sc=Math.min(10,sc*1.25);draw()}});
document.getElementById('bZmOut').addEventListener('click',()=>{{
  sc=Math.max(0.015,sc/1.25);draw()}});

document.getElementById('bSB').addEventListener('click',function(){{
  document.getElementById('sidebar').classList.toggle('collapsed');
  this.classList.toggle('on');
  setTimeout(resize,220);
}});
document.getElementById('inspClose').addEventListener('click',()=>{{
  document.getElementById('inspector').classList.toggle('collapsed');
  setTimeout(resize,220);
}});

document.getElementById('q').addEventListener('input',function(){{qry=this.value.toLowerCase().trim();draw()}});

document.addEventListener('keydown',e=>{{
  if(e.target.tagName==='INPUT')return;
  if(e.key==='Escape'){{selN=null;selE=null;hlN.clear();draw()}}
  if(e.key==='+'||e.key==='='){{sc=Math.min(10,sc*1.2);draw()}}
  if(e.key==='-'){{sc=Math.max(0.015,sc/1.2);draw()}}
  if(e.key==='f'||e.key==='F'){{document.getElementById('q').focus();e.preventDefault()}}
}});

// ── Init ──
resize();fitAll();
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='FileMaker Relationship Graph Visualizer')
    parser.add_argument('db_path', help='Path to indexed SQLite database')
    parser.add_argument('--output', '-o', default='fm_graph.html', help='Output HTML file')
    parser.add_argument('--focus', default=None, help='Focus on a specific TO name')
    parser.add_argument('--depth', type=int, default=2, help='Relationship depth for focus mode')
    args = parser.parse_args()
    if not Path(args.db_path).exists():
        print(f"Error: Database not found: {args.db_path}")
        sys.exit(1)
    generate_html(args.db_path, args.output, args.focus, args.depth)


if __name__ == '__main__':
    main()
