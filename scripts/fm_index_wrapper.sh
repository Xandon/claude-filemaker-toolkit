#!/usr/bin/env bash
# fm_index_wrapper.sh — thin wrapper that finds the installed
# filemaker-toolkit plugin's fm_manage.py and indexes a DDR XML in place.
#
# This is the file you drop into a project folder so you can index a
# large DDR from Terminal WITHOUT copying the whole scripts/ directory
# around. Just this one file — everything else stays in the Cowork
# plugin install.
#
# Usage:
#   ./fm_index_wrapper.sh <path/to/file.xml> [--name <solution-name>]
#
# What it does:
#   1. Locates fm_manage.py in your installed filemaker-toolkit plugin
#      (or wherever $FM_MANAGE_PATH points).
#   2. Runs `python3 fm_manage.py index <file.xml>` in the current
#      working directory. Output lands in ./solutions/<name>/ and
#      ./.fm_db_cache/<name>.db, per the normal plugin conventions.
#   3. Runs `python3 fm_manage.py query <name> summary` so you see
#      the counts right after indexing.
#
# Requirements:
#   - python3 (any 3.9+; the plugin is pure standard library, no pip).
#   - filemaker-toolkit installed in Cowork (Customize → Plugins),
#     OR $FM_MANAGE_PATH set to the absolute path of fm_manage.py,
#     OR the plugin scripts placed at ~/.filemaker-toolkit/scripts/.
#
# Environment overrides:
#   FM_MANAGE_PATH     Absolute path to fm_manage.py. Beats auto-detection.
#   FM_PYTHON          Python interpreter to use (default: python3).
#   FM_PROJECT_DIR     Project folder for solutions/ and .fm_db_cache/.
#                      Defaults to the current working directory.

set -euo pipefail

# ─── Args ────────────────────────────────────────────────────────────────
XML_FILE="${1:-}"
if [ -z "$XML_FILE" ] || [ "$XML_FILE" = "--help" ] || [ "$XML_FILE" = "-h" ]; then
    cat <<'USAGE'
Usage: fm_index_wrapper.sh <path/to/file.xml> [--name <solution-name>]

Indexes a FileMaker DDR XML in the current directory using the
installed filemaker-toolkit Cowork plugin. Produces:
  ./solutions/<name>/               (per-solution folder)
  ./.fm_db_cache/<name>.db          (indexed SQLite database)

Overrides:
  FM_MANAGE_PATH   absolute path to fm_manage.py (bypasses auto-detect)
  FM_PYTHON        python interpreter (default: python3)
  FM_PROJECT_DIR   project root (default: current working directory)
USAGE
    exit 2
fi
shift

if [ ! -f "$XML_FILE" ]; then
    echo "Error: '$XML_FILE' does not exist." >&2
    exit 2
fi

# Optional --name flag
NAME_ARGS=()
SOL_NAME_OVERRIDE=""
if [ "${1:-}" = "--name" ] && [ -n "${2:-}" ]; then
    SOL_NAME_OVERRIDE="$2"
    NAME_ARGS=(--name "$2")
    shift 2
fi

# ─── Locate fm_manage.py ─────────────────────────────────────────────────
FM_MANAGE=""

# 1. Explicit env override always wins
if [ -n "${FM_MANAGE_PATH:-}" ] && [ -f "$FM_MANAGE_PATH" ]; then
    FM_MANAGE="$FM_MANAGE_PATH"
fi

# 2. Known Cowork / Claude Desktop install paths on macOS. The plugin
#    install directory contains two UUIDs (session + subsession), so we
#    glob into them. We verify each candidate is actually filemaker-toolkit
#    by grepping for the module docstring — otherwise a same-named script
#    from a different plugin could be picked up.
if [ -z "$FM_MANAGE" ]; then
    SHOPT_RESET=$(shopt -p nullglob)
    shopt -s nullglob
    CANDIDATES=(
        "$HOME/Library/Application Support/Claude/local-agent-mode-sessions"/*/*/rpm/plugin_*/scripts/fm_manage.py
        "$HOME/Library/Application Support/Claude/plugins"/*/scripts/fm_manage.py
        "$HOME/Library/Application Support/Claude/Plugins"/*/scripts/fm_manage.py
        "$HOME/.filemaker-toolkit/scripts/fm_manage.py"
    )
    $SHOPT_RESET
    for candidate in "${CANDIDATES[@]}"; do
        [ -f "$candidate" ] || continue
        # Sanity-check: must be from filemaker-toolkit, not a same-named
        # script that happens to sit somewhere similar.
        if grep -q 'FileMaker Solution Manager' "$candidate" 2>/dev/null; then
            FM_MANAGE="$candidate"
            break
        fi
    done
fi

if [ -z "$FM_MANAGE" ]; then
    cat <<'ERR' >&2
Could not locate fm_manage.py from an installed filemaker-toolkit plugin.

Do one of:
  1) Install the filemaker-toolkit plugin in Cowork
     (Customize → Personal plugins → upload the .zip or .plugin bundle).
  2) Set FM_MANAGE_PATH to the absolute path of fm_manage.py, e.g.
        export FM_MANAGE_PATH=/path/to/scripts/fm_manage.py
     …and re-run this wrapper.
  3) Copy the plugin's scripts/ directory to a stable location and
     symlink or set FM_MANAGE_PATH accordingly, e.g.
        mkdir -p ~/.filemaker-toolkit
        cp -R /path/to/plugin/scripts ~/.filemaker-toolkit/
ERR
    exit 1
fi

PYTHON="${FM_PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: '$PYTHON' not found on PATH. Install Python 3.9+ or set FM_PYTHON." >&2
    exit 1
fi

# Project directory (where solutions/ and .fm_db_cache/ will live).
PROJECT_DIR="${FM_PROJECT_DIR:-$PWD}"

# Compute default solution name (basename minus .xml) for the summary call.
if [ -n "$SOL_NAME_OVERRIDE" ]; then
    SOL_NAME="$SOL_NAME_OVERRIDE"
else
    SOL_NAME="$(basename -- "$XML_FILE")"
    SOL_NAME="${SOL_NAME%.xml}"
    SOL_NAME="${SOL_NAME%.XML}"
fi

echo "Plugin:       $FM_MANAGE"
echo "Python:       $($PYTHON --version 2>&1)"
echo "Project dir:  $PROJECT_DIR"
echo "XML file:     $XML_FILE"
echo "Solution:     $SOL_NAME"
echo ""

# ─── Run index + summary ─────────────────────────────────────────────────
export FM_PROJECT_DIR="$PROJECT_DIR"
"$PYTHON" "$FM_MANAGE" index "$XML_FILE" "${NAME_ARGS[@]}"
echo ""
"$PYTHON" "$FM_MANAGE" query "$SOL_NAME" summary
