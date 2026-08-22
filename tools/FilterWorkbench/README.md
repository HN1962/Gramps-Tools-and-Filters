# FilterWorkbench (Filterværksted)
[Guide](GUIDE.md) • [ReadMe](README.md) • [GNU GPL (license)](LICENSE)

A Gramps gramplet for building, saving, editing, sharing and **testing** your own
person filters — with reusable *helper filters* as building blocks. It lives in the
**People** view sidebar and keeps its filters completely separate from Gramps' own
filter editor list.

> Danish UI included ("Filterværksted"). Works on Gramps **5.1**, **5.2** and
> **6.0.x**, Windows and Linux.

---

## Why

Gramps' built‑in custom filters are powerful but fiddly to build, and every
experiment ends up in your `custom_filters.xml`. FilterWorkbench gives beginners and
slightly experienced users a friendlier workspace where you can build a filter,
watch the live match count, try it on the person list *without closing the builder*,
and only keep what works — all stored in its own per‑tree file. **Your
`custom_filters.xml` is never touched.**

## Features

- **Main filters + reusable helper filters.** Build a helper once, reference it from
  many main filters.
- **Live match count** while you build.
- **Test as you go** — try the whole filter, a selected helper, or a single selected
  rule directly in the person view (the builder stays open).
- **Apply / Reset** the finished filter to the person list from the gramplet.
- **Applied filters show up in Gramps' own selectors** (GEDCOM export, reports, the
  sidebar) as `wb_<name>` — but only while applied, and only in memory. Reset or close
  and they're gone.
- **Import / Export between family trees**, with a safe additive merge: duplicates are
  skipped, real name‑clashes are renamed, and missing rule add‑ons are flagged before
  you commit.
- **Regular‑expression / case‑sensitive matching** on rules that support it.
- **Favorite rules** — right‑click a rule in the New/Edit picker to pin it under a
  **★ Favorites** group at the very top, so the rules you use most are one click away.
  Favorites are remembered across sessions and across all your trees.
- **Per‑tree JSON storage** — nothing is written to `custom_filters.xml`.

## Install

1. Close your family tree and Gramps.

2. Locate your Gramps user plugin folder:
   - **Windows:** `%APPDATA%\gramps\gramps<XY>\plugins\`
   - **Linux/macOS:** `~/.gramps/gramps<XY>/plugins/`

   where `<XY>` is your version without the dot, e.g. `gramps60` for 6.0,
   `gramps52` for 5.2, or `gramps51` for 5.1.

3. Unzip the download into that folder so you get **one** sub‑folder holding all the
   add‑on's files, with the `locale/` folder kept intact:

   ```
   plugins/FilterWorkbench/
       filterbuildergramplet.gpr.py
       filterbuildergramplet.py
       filterbuilder.py   filterengine.py   filterpanel.py
       ruleeditor.py   operatorwidget.py   filterrefwidget.py
       locale/da/LC_MESSAGES/addon.mo
       README.md   GUIDE.md
   ```

   The sub‑folder name is up to you — Gramps identifies the add‑on by its
   registration, not the folder name. To upgrade later, just replace these files.

4. Restart Gramps, open the **People** view and add the **FilterWorkbench**
   ("Filterværksted") gramplet to the sidebar. If anything went wrong during loading,
   **Help → Plugin Manager** will show the error.

> Your saved filters live separately, in `…/gramps<XY>/filterbuilder/` — not in the
> plugin folder — so replacing or removing the plugin folder never touches them.

## Requirements

- Gramps 5.1, 5.2 or 6.0.x (one code base fits all three), Python 3, GTK 3.
- If you import a filter that references a **rule add‑on** (e.g. a custom rule), install
  that same add‑on in the target Gramps — the import will warn you if it's missing.

## Documentation

See **[GUIDE.md](GUIDE.md)** for the full walkthrough: concepts, building and testing
filters, import/export behaviour, regex/case, and known limitations.

## License

Released under the **GNU General Public License v2.0 or later** (GPL‑2.0‑or‑later),
the same license as Gramps.

## Author

Henning — <contact@myown-project.dk> · <https://myown-project.dk>
