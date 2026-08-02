# -*- coding: utf-8 -*-
#
# VerifyHTML - a Gramps tool
#
# Runs the built-in "Verify the Data" checks and saves the result as a
# sortable HTML report in which each item can be ticked off once reviewed.
#
# Design principle
# ----------------
# This tool does NOT copy the checks. It imports the class from the built-in
# verify module and calls its run_the_tool() through a light "shim". The
# report therefore follows along automatically whenever Gramps improves or
# adds checks, and none of Gramps' own files are touched.
#
# The thresholds (maximum age, young father, ...) are read from the settings
# you last saved in the built-in "Verify the Data" tool. Those settings are
# only stored when you actually RUN that tool (it saves the options at the
# end of a run), so run "Verify the Data" once with your preferred values
# before running this report.
#
# ---------------------------------------------------------------------------

import os
import json
import datetime
import webbrowser

from gi.repository import Gtk

# --- Translation ------------------------------------------------------------
# English is the source language. A bundled locale/<lang>/LC_MESSAGES/addon.mo
# (e.g. Danish) is picked up automatically via get_addon_translator().
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except (ValueError, AttributeError):
    _trans = glocale.translation
_ = _trans.gettext

# --- Gramps base classes ----------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.dialog import OkDialog, ErrorDialog

# --- Reuse of the built-in Verify tool --------------------------------------
# These names have been stable across Gramps 5.x and 6.x.
from gramps.plugins.tool.verify import Verify, VerifyOptions, Rule


# Default thresholds - only used as a fallback if your own saved settings
# cannot be read (for example on a brand-new family tree).
_DEFAULTS = {
    "oldage": 90, "hwdif": 30, "cspace": 8, "cbspan": 25,
    "yngmar": 17, "oldmar": 50, "oldmom": 48, "yngmom": 17,
    "yngdad": 18, "olddad": 65, "wedder": 3, "mxchildmom": 12,
    "mxchilddad": 15, "lngwdw": 30, "oldunm": 99,
    "estimate_age": 0, "invdate": 1,
}


# ===========================================================================
#
# Tool options (we keep none of our own - we borrow Verify's saved ones)
#
# ===========================================================================
class VerifyHTMLOptions(tool.ToolOptions):
    """Empty options. Thresholds come from the built-in Verify tool."""

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
        self.options_dict = {}
        self.options_help = {}


# ===========================================================================
#
# The tool itself
#
# ===========================================================================
class VerifyHTMLTool(tool.Tool):
    """Run the built-in data checks and save them as a sortable HTML report."""

    def __init__(self, dbstate, user, options_class, name, callback=None):
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.dbstate = dbstate
        self.user = user
        self.uistate = getattr(user, "uistate", None)
        self.db = dbstate.db

        parent = self.uistate.window if self.uistate else None

        # 1) Read the thresholds you last saved in "Verify the Data"
        options_dict = self._load_saved_thresholds()

        # 2) Run the built-in checks (headless, no window)
        try:
            results = self._run_checks(options_dict)
        except Exception as err:  # pragma: no cover - defensive
            ErrorDialog(
                _("Could not run the verification"),
                str(err),
                parent=parent,
            )
            return

        # 3) Build the HTML report
        html_text = self._build_html(results)

        # 4) Save via a file dialog and open in the browser
        self._save_and_open(html_text, len(results), parent)

    # ----------------------------------------------------------------- step 1
    def _load_saved_thresholds(self):
        """Read the settings saved by the built-in Verify tool."""
        options_dict = dict(_DEFAULTS)
        try:
            saved = VerifyOptions("verify")
            saved.load_previous_values()
            source = getattr(saved, "options_dict", {}) or {}
            for key in _DEFAULTS:
                if key in source:
                    options_dict[key] = source[key]
        except Exception:
            pass  # fall back to _DEFAULTS
        return options_dict

    # ----------------------------------------------------------------- step 2
    def _run_checks(self, options_dict):
        """
        Run the verify module's own run_the_tool() headlessly.

        We create a Verify object WITHOUT calling its __init__ (which would
        otherwise open the dialog) and give it just the attributes that
        run_the_tool() touches. All rules and the whole traversal therefore
        come from Gramps itself - we merely collect the results.
        """
        runner = Verify.__new__(Verify)
        runner.db = self.db
        runner.v_r = None

        class _Shim:
            pass

        handler = _Shim()
        handler.options_dict = options_dict
        opts = _Shim()
        opts.handler = handler
        runner.options = opts

        collected = []
        runner.add_results = collected.append          # collects (7-tuple)
        runner.set_total = lambda total: None          # no progress bar
        runner.update = lambda *a, **k: None

        runner.run_the_tool(cli=True)                  # cli=True -> no GUI call
        return collected

    # ----------------------------------------------------------------- step 3
    def _build_html(self, results):
        """Build the rows and insert them into the HTML template."""
        rows = []
        for item in results:
            # report_itself() -> (msg, gramps_id, name, type, rule_id, severity, handle)
            msg, gid, name, the_type, rule_id, severity, _handle = item
            sev = "error" if severity == Rule.ERROR else "warning"
            if the_type == "Person":
                obj = _("Person")
            elif the_type == "Family":
                obj = _("Family")
            else:
                obj = str(the_type)
            rows.append({
                "sev": sev,
                "msg": msg or "",
                "obj": obj,
                "gid": gid or "",
                "name": name or "",
                "key": "%s|%s" % (gid, rule_id),
            })

        n_err = sum(1 for r in rows if r["sev"] == "error")
        n_warn = len(rows) - n_err
        tree_name = self.db.get_dbname() or _("Untitled")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        lang = (getattr(glocale, "lang", None) or "en")[:2]

        # All user-visible strings, routed through _() so a Danish .mo
        # translates the whole report.
        labels = {
            "doc_title": _("Data verification"),
            "h1": _("Data verification"),
            "tree_label": _("Family tree"),
            "generated": _("generated"),
            "total": _("items in total"),
            "errors": _("errors"),
            "warnings": _("warnings"),
            "reviewed": _("reviewed"),
            "f_all": _("All"),
            "f_err": _("Errors only"),
            "f_warn": _("Warnings only"),
            "search": _("Search name, ID or check\u2026"),
            "hide": _("Hide reviewed"),
            "reset": _("Reset check marks"),
            "savecopy": _("Save a copy"),
            "c_severity": _("Severity"),
            "c_check": _("Check"),
            "c_object": _("Object"),
            "c_id": _("ID"),
            "c_name": _("Name"),
            "chip_error": _("Error"),
            "chip_warning": _("Warning"),
            "empty": _("No items match the filter."),
            "confirm_reset": _("Remove all check marks for this family tree?"),
            "footer": _(
                "Check marks are stored in your browser and are normally kept "
                "between visits (each item has a stable key, so they survive "
                "even if the report is regenerated). To be completely sure of "
                "keeping your progress - or to move it to another device - click "
                "\u201cSave a copy\u201d: the downloaded file has your current "
                "check marks baked in. When the file is opened locally in Chrome, "
                "browser storage is not always kept between sessions, so saving a "
                "copy is the safe option; served over http or opened in Firefox "
                "it persists on its own."
            ),
        }

        data_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
        # strings JavaScript needs at runtime
        js_labels = json.dumps(
            {k: labels[k] for k in ("chip_error", "chip_warning",
                                    "empty", "confirm_reset")},
            ensure_ascii=False,
        ).replace("</", "<\\/")

        html_text = _HTML_TEMPLATE
        # static (server-rendered) replacements
        repl = {
            "__LANG__": lang,
            "__TREE__": _html_escape(tree_name),
            "__STAMP__": _html_escape(stamp),
            "__TOTAL__": str(len(rows)),
            "__ERR__": str(n_err),
            "__WARN__": str(n_warn),
            "__TREEKEY__": _js_string(tree_name),
            "__DATA__": data_json,
            "__JSLABELS__": js_labels,
            "__L_DOCTITLE__": _html_escape(labels["doc_title"]),
            "__L_H1__": _html_escape(labels["h1"]),
            "__L_TREE__": _html_escape(labels["tree_label"]),
            "__L_GENERATED__": _html_escape(labels["generated"]),
            "__L_TOTAL__": _html_escape(labels["total"]),
            "__L_ERRORS__": _html_escape(labels["errors"]),
            "__L_WARNINGS__": _html_escape(labels["warnings"]),
            "__L_REVIEWED__": _html_escape(labels["reviewed"]),
            "__L_FALL__": _html_escape(labels["f_all"]),
            "__L_FERR__": _html_escape(labels["f_err"]),
            "__L_FWARN__": _html_escape(labels["f_warn"]),
            "__L_SEARCH__": _html_escape(labels["search"]),
            "__L_HIDE__": _html_escape(labels["hide"]),
            "__L_RESET__": _html_escape(labels["reset"]),
            "__L_SAVECOPY__": _html_escape(labels["savecopy"]),
            "__L_CSEV__": _html_escape(labels["c_severity"]),
            "__L_CCHECK__": _html_escape(labels["c_check"]),
            "__L_COBJ__": _html_escape(labels["c_object"]),
            "__L_CID__": _html_escape(labels["c_id"]),
            "__L_CNAME__": _html_escape(labels["c_name"]),
            "__L_FOOTER__": _html_escape(labels["footer"]),
        }
        for token, value in repl.items():
            html_text = html_text.replace(token, value)
        return html_text

    # ----------------------------------------------------------------- step 4
    def _save_and_open(self, html_text, count, parent):
        """Ask the user for a location, write the file and open it."""
        tree_name = self.db.get_dbname() or "tree"
        safe = "".join(
            c if (c.isalnum() or c in " -_") else "_" for c in tree_name
        ).strip().replace(" ", "_") or "tree"
        suggested = "verification_%s.html" % safe

        dialog = Gtk.FileChooserDialog(
            title=_("Save HTML report"),
            transient_for=parent,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            _("_Cancel"), Gtk.ResponseType.CANCEL,
            _("_Save"), Gtk.ResponseType.ACCEPT,
        )
        try:
            dialog.set_do_overwrite_confirmation(True)
        except Exception:
            pass
        dialog.set_current_name(suggested)
        try:
            dialog.set_current_folder(os.path.expanduser("~"))
        except Exception:
            pass
        flt = Gtk.FileFilter()
        flt.set_name("HTML")
        flt.add_pattern("*.html")
        dialog.add_filter(flt)

        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()

        if not path:
            return
        if not path.lower().endswith(".html"):
            path += ".html"

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html_text)
        except Exception as err:
            ErrorDialog(_("Could not save the file"), str(err), parent=parent)
            return

        # open in the default browser
        try:
            os.startfile(path)          # Windows
        except AttributeError:
            try:
                webbrowser.open("file://" + path)
            except Exception:
                pass

        OkDialog(
            _("Report saved"),
            _("%(n)d items written to:\n%(p)s\n\n"
              "Thresholds were taken from the last run of the built-in "
              "\"Verify the Data\" tool.") % {"n": count, "p": path},
            parent=parent,
        )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _html_escape(text):
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _js_string(text):
    """Safe JS string body (without the surrounding quotes)."""
    return (json.dumps(str(text), ensure_ascii=False)[1:-1]
            .replace("</", "<\\/"))


# ===========================================================================
#
# The HTML template (self-contained file - CSS + JS embedded)
#
# ===========================================================================
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__L_DOCTITLE__ - __TREE__</title>
<style>
  :root{
    --bg:#f7f5f1; --card:#ffffff; --ink:#28292b; --muted:#6b6f76;
    --line:#e3ddd2; --accent:#3f6f7a;
    --err-bg:#f7e7e4; --err-ink:#a4402f; --err-bar:#c4553d;
    --warn-bg:#f6efdd; --warn-ink:#8a6a1f; --warn-bar:#c8a34a;
    --done:#eef1ee;
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    padding:24px;
  }
  .wrap{max-width:1040px; margin:0 auto}
  header{margin-bottom:18px}
  h1{font-size:24px; margin:0 0 4px; font-weight:600; letter-spacing:.2px}
  .sub{color:var(--muted); font-size:14px}
  .pills{display:flex; flex-wrap:wrap; gap:10px; margin:16px 0}
  .pill{
    background:var(--card); border:1px solid var(--line); border-radius:999px;
    padding:6px 14px; font-size:14px; display:flex; gap:8px; align-items:center
  }
  .pill b{font-weight:600}
  .dot{width:9px; height:9px; border-radius:50%}
  .dot.err{background:var(--err-bar)} .dot.warn{background:var(--warn-bar)}
  .dot.done{background:var(--accent)}
  .toolbar{
    display:flex; flex-wrap:wrap; gap:10px; align-items:center;
    background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:12px; margin-bottom:14px
  }
  .seg{display:inline-flex; border:1px solid var(--line); border-radius:9px; overflow:hidden}
  .seg button{
    border:0; background:var(--card); color:var(--ink); padding:7px 14px;
    font-size:14px; cursor:pointer
  }
  .seg button+button{border-left:1px solid var(--line)}
  .seg button.on{background:var(--accent); color:#fff}
  input[type=search]{
    flex:1; min-width:160px; border:1px solid var(--line); border-radius:9px;
    padding:8px 12px; font-size:14px; background:var(--card); color:var(--ink)
  }
  label.check{display:flex; gap:7px; align-items:center; font-size:14px; color:var(--muted); cursor:pointer}
  .btn{
    border:1px solid var(--line); background:var(--card); color:var(--ink);
    border-radius:9px; padding:7px 12px; font-size:14px; cursor:pointer
  }
  .btn:hover{border-color:var(--accent); color:var(--accent)}
  .tablecard{background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden}
  .scroll{overflow-x:auto}
  table{border-collapse:collapse; width:100%; font-size:15px}
  thead th{
    position:sticky; top:0; background:#efeae1; text-align:left;
    padding:11px 14px; font-weight:600; font-size:13px; color:#55585d;
    border-bottom:1px solid var(--line); white-space:nowrap; cursor:pointer;
    user-select:none
  }
  thead th.nosort{cursor:default}
  th .arrow{color:var(--accent); font-size:11px; margin-left:4px}
  tbody td{padding:10px 14px; border-bottom:1px solid var(--line); vertical-align:top}
  tbody tr:last-child td{border-bottom:0}
  tbody tr:hover{background:#faf8f4}
  tr.done{background:var(--done)} tr.done td{color:var(--muted)}
  tr.done .msg{text-decoration:line-through}
  td.c-done{text-align:center; width:44px}
  td.c-done input{width:18px; height:18px; cursor:pointer}
  .chip{display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap}
  .chip.error{background:var(--err-bg); color:var(--err-ink)}
  .chip.warning{background:var(--warn-bg); color:var(--warn-ink)}
  tr.error td:first-child{box-shadow:inset 3px 0 0 var(--err-bar)}
  tr.warning td:first-child{box-shadow:inset 3px 0 0 var(--warn-bar)}
  .gid{font-variant-numeric:tabular-nums; color:var(--muted); white-space:nowrap}
  .empty{padding:34px; text-align:center; color:var(--muted)}
  footer{color:var(--muted); font-size:12.5px; margin-top:16px; line-height:1.6}
  @media (max-width:560px){
    body{padding:14px} h1{font-size:20px} table{font-size:14px}
    thead th,tbody td{padding:9px 10px}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>__L_H1__</h1>
    <div class="sub">__L_TREE__: <b>__TREE__</b> &nbsp;&middot;&nbsp; __L_GENERATED__ __STAMP__</div>
    <div class="pills">
      <span class="pill"><b id="p-total">__TOTAL__</b> __L_TOTAL__</span>
      <span class="pill"><span class="dot err"></span><b>__ERR__</b> __L_ERRORS__</span>
      <span class="pill"><span class="dot warn"></span><b>__WARN__</b> __L_WARNINGS__</span>
      <span class="pill"><span class="dot done"></span><b id="p-done">0</b> __L_REVIEWED__</span>
    </div>
  </header>

  <div class="toolbar">
    <div class="seg" id="segsev">
      <button data-sev="all" class="on">__L_FALL__</button>
      <button data-sev="error">__L_FERR__</button>
      <button data-sev="warning">__L_FWARN__</button>
    </div>
    <input type="search" id="q" placeholder="__L_SEARCH__">
    <label class="check"><input type="checkbox" id="hide"> __L_HIDE__</label>
    <button class="btn" id="savecopy">__L_SAVECOPY__</button>
    <button class="btn" id="reset">__L_RESET__</button>
  </div>

  <div class="tablecard">
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th class="nosort">&#10003;</th>
            <th data-col="sev">__L_CSEV__<span class="arrow"></span></th>
            <th data-col="msg">__L_CCHECK__<span class="arrow"></span></th>
            <th data-col="obj">__L_COBJ__<span class="arrow"></span></th>
            <th data-col="gid">__L_CID__<span class="arrow"></span></th>
            <th data-col="name">__L_CNAME__<span class="arrow"></span></th>
          </tr>
        </thead>
        <tbody id="body"></tbody>
      </table>
    </div>
    <div class="empty" id="empty" style="display:none"></div>
  </div>

  <footer>__L_FOOTER__</footer>
</div>

<script id="precheck">window.PRECHECKED = [];</script>
<script>
const DATA = __DATA__;
const LABELS = __JSLABELS__;
const NS = "vh:" + "__TREEKEY__" + ":";

let state = { sev:"all", q:"", hide:false, col:"sev", dir:1 };
const SEVRANK = { error:0, warning:1 };

/* Check marks baked into a saved copy (used when the browser has no
   explicit local decision for an item). */
const _pre = new Set(Array.isArray(window.PRECHECKED) ? window.PRECHECKED : []);
/* Fallback stores if localStorage is blocked (e.g. Chrome on file://). */
const _memYes = new Set();
const _memNo  = new Set();

/* ---- persistence (fail-safe) ---- */
function isDone(key){
  try {
    const v = localStorage.getItem(NS+key);
    if(v === "1") return true;
    if(v === "0") return false;
    return _pre.has(key);          /* no local decision -> baked-in state */
  } catch(e){
    if(_memYes.has(key)) return true;
    if(_memNo.has(key)) return false;
    return _pre.has(key);
  }
}
function setDone(key,val){
  try {
    localStorage.setItem(NS+key, val ? "1" : "0");
  } catch(e){
    if(val){ _memYes.add(key); _memNo.delete(key); }
    else   { _memNo.add(key);  _memYes.delete(key); }
  }
}

/* ---- counters ---- */
function updateDone(){
  let n = 0;
  for(const r of DATA){ if(isDone(r.key)) n++; }
  document.getElementById("p-done").textContent = n;
}

/* ---- filter + sort + draw ---- */
function render(){
  const q = state.q.trim().toLowerCase();
  let rows = DATA.filter(r=>{
    if(state.sev!=="all" && r.sev!==state.sev) return false;
    if(state.hide && isDone(r.key)) return false;
    if(q){
      const hay = (r.msg+" "+r.name+" "+r.gid+" "+r.obj).toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });

  const col = state.col, dir = state.dir;
  rows.sort((a,b)=>{
    let x,y;
    if(col==="sev"){ x=SEVRANK[a.sev]; y=SEVRANK[b.sev]; }
    else { x=(a[col]||"").toLowerCase(); y=(b[col]||"").toLowerCase(); }
    if(x<y) return -1*dir;
    if(x>y) return 1*dir;
    return (a.gid||"").localeCompare(b.gid||"");
  });

  const body = document.getElementById("body");
  body.textContent = "";
  const frag = document.createDocumentFragment();

  for(const r of rows){
    const done = isDone(r.key);
    const tr = document.createElement("tr");
    tr.className = r.sev + (done ? " done" : "");

    const tdC = document.createElement("td");
    tdC.className = "c-done";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.checked = done;
    cb.addEventListener("change", ()=>{
      setDone(r.key, cb.checked);
      updateDone();
      if(state.hide) render(); else tr.className = r.sev + (cb.checked?" done":"");
    });
    tdC.appendChild(cb); tr.appendChild(tdC);

    const tdS = document.createElement("td");
    const chip = document.createElement("span");
    chip.className = "chip " + r.sev;
    chip.textContent = r.sev==="error" ? LABELS.chip_error : LABELS.chip_warning;
    tdS.appendChild(chip); tr.appendChild(tdS);

    const tdM = document.createElement("td");
    tdM.className = "msg"; tdM.textContent = r.msg; tr.appendChild(tdM);

    const tdO = document.createElement("td");
    tdO.textContent = r.obj; tr.appendChild(tdO);

    const tdG = document.createElement("td");
    tdG.className = "gid"; tdG.textContent = r.gid; tr.appendChild(tdG);

    const tdN = document.createElement("td");
    tdN.textContent = r.name; tr.appendChild(tdN);

    frag.appendChild(tr);
  }
  body.appendChild(frag);

  const empty = document.getElementById("empty");
  empty.textContent = LABELS.empty;
  empty.style.display = rows.length ? "none" : "block";
  paintArrows();
}

function paintArrows(){
  document.querySelectorAll("thead th[data-col]").forEach(th=>{
    const a = th.querySelector(".arrow");
    if(th.dataset.col===state.col) a.textContent = state.dir>0 ? "\u25B2" : "\u25BC";
    else a.textContent = "";
  });
}

/* ---- events ---- */
document.getElementById("segsev").addEventListener("click", e=>{
  const b = e.target.closest("button"); if(!b) return;
  state.sev = b.dataset.sev;
  document.querySelectorAll("#segsev button").forEach(x=>x.classList.toggle("on", x===b));
  render();
});
document.getElementById("q").addEventListener("input", e=>{
  state.q = e.target.value; render();
});
document.getElementById("hide").addEventListener("change", e=>{
  state.hide = e.target.checked; render();
});
document.getElementById("reset").addEventListener("click", ()=>{
  if(!confirm(LABELS.confirm_reset)) return;
  for(const r of DATA) setDone(r.key, false);
  updateDone(); render();
});
document.getElementById("savecopy").addEventListener("click", ()=>{
  /* Bake the current check marks into a standalone downloadable copy. */
  const done = DATA.filter(r=>isDone(r.key)).map(r=>r.key);
  document.getElementById("precheck").textContent =
    "window.PRECHECKED = " + JSON.stringify(done) + ";";
  const copy = "<!DOCTYPE html>\n" + document.documentElement.outerHTML;
  const blob = new Blob([copy], {type:"text/html;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (document.title || "verification") + ".html";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
});
document.querySelectorAll("thead th[data-col]").forEach(th=>{
  th.addEventListener("click", ()=>{
    const col = th.dataset.col;
    if(state.col===col) state.dir *= -1;
    else { state.col = col; state.dir = 1; }
    render();
  });
});

updateDone();
render();
</script>
</body>
</html>
"""
