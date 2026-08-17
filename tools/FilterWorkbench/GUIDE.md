# FilterWorkbench — Guide

*A Gramps gramplet for building, saving, editing, sharing and testing your own person
filters. Danish name: **Filterværksted**.*

This guide covers what FilterWorkbench is, how it stores things, and how to use every
part of it. For a quick summary and install steps, see [README.md](README.md).

---

## 1. What it is

FilterWorkbench is a floating **gramplet** that you add to the **People** view sidebar.
From there you can:

- build your own **main filters** out of rules,
- reuse **helper filters** as building blocks,
- **test** a filter (or one helper, or one rule) live on the person list,
- **apply** a finished filter to the person list, and
- **import/export** filters between family trees.

It is meant for beginners and slightly experienced users who understand the three ways
rules can be combined (all / any / exactly one), and who want a friendlier place to
experiment than Gramps' built‑in filter editor.

## 2. How it stores filters (and why that matters)

FilterWorkbench keeps its filters in **its own file, one per family tree**, named after
the tree's internal database id. It has two sections:

- **main** — your main filters (the ones you apply, save and share), and
- **temp** — reusable **helper filters**.

**It never writes to Gramps' `custom_filters.xml`.** FilterWorkbench filters are
completely separate from Gramps' own custom filters, so experimenting here can't clutter
or corrupt your Gramps filter list.

References between filters are stored as stable ids and resolved to run‑time names only
when a filter is actually applied — so renaming a helper never breaks a main filter that
uses it.

## 3. Concepts

- **Rule** — the smallest piece, e.g. *"has a name matching…"* or *"is a descendant
  of…"*. FilterWorkbench uses the same rule catalogue as Gramps, including any rule
  add‑ons you have installed.
- **Helper filter** — a small, named, reusable filter you build once and reference from
  one or more main filters. Helper filters are building blocks; they are created and
  edited *inside* the builder (there is deliberately no standalone "new helper" button).
  If you want a filter available on its own elsewhere, make it a **main** filter instead.
- **Main filter** — a filter you name, save, apply and share. A main filter can contain
  plain rules and/or references to helper filters.
- **Combine mode (operator)** — how a filter's rules are combined: match **all** of
  them, match **any** of them, or match **exactly one**. There is also an **invert**
  option ("show the opposite result").

## 4. The build window

Open it from the gramplet with **New** (blank) or **Edit** (the selected main filter).

At the top a short note reminds you what the window does. Below that:

- **Name / comment** for the filter.
- **Rule list** — two columns, *Filter* and *Description*. The Description column shows
  the comment of a referenced helper filter, so you can see at a glance what a reference
  does. You can drag the *Filter* column wider; its width is remembered.
- **New / Edit / Remove** rules, and **Test selected rule** — run just the highlighted
  rule on the person list to see what it alone matches.
- **Combine mode** and the **"show the opposite result"** (invert) checkbox.
- A **helper‑filter list** underneath, with its own **New / Edit / Remove** and
  **Test selected filter** (runs just the highlighted helper on the person list).
- **Test filter** — run the whole filter you're building on the person list, **without
  closing the builder**, so you can keep tweaking.
- **Reset view** — clear the test and show everyone again.
- **Save** — the only action that writes to disk.

### Live match count

While you build, FilterWorkbench shows how many people the current filter matches, and
updates it as you edit. One special case: a rule that depends on the **active person**
can't be counted from the floating window (Gramps only knows the active person in the
person view itself), so its count is shown blank rather than a misleading `0` — the
filter still applies correctly. If you want a dependable "proband" anchor, use Gramps'
built‑in **Home Person** rule instead.

## 5. Testing vs. applying

- **Testing** (from the build window) previews a filter/helper/rule on the person list
  while you work. It's transient.
- **Applying** (from the gramplet, **Apply filter**) pushes a saved main filter to the
  person list until you press **Reset** (or close Gramps).

While a filter is applied — or while you're testing one — it also appears in Gramps'
other person selectors (GEDCOM export's *Person Filter*, reports, the sidebar) under the
readable name **`wb_<name>`**. This is convenient: you can apply a filter here and then
pick it straight from the GEDCOM export dialog. It lives only in memory; **Reset** or
closing removes it, and it is never written to `custom_filters.xml`.

> Note the distinction: applied filters appear in Gramps' filter **selection lists** as
> `wb_<name>`, but they never appear in Gramps' own filter **editor** (the custom‑filter
> builder), because FilterWorkbench never writes there.

## 6. The gramplet

The gramplet is your home base in the People view sidebar:

- **Saved filters** dropdown — your main filters for this tree.
- **Apply** (eye) / **Reset** (house) — apply the selected filter to the person list, or
  show everyone again.
- **New / Edit / Delete** — manage main filters. Deleting a filter that is currently
  applied automatically resets the view.
- **Import / Export** — move filters between trees (see below).
- A short feature list you can read at a glance.

## 7. Import / Export between trees

**Export** writes all of this tree's filters to a file. **Import** *adds* filters from
another tree's file — it never replaces what you already have. The merge is careful:

- A filter whose **content already exists** here (regardless of its name) is treated as a
  true duplicate and **skipped**; references are pointed at your local copy. Re‑importing
  the same file therefore adds nothing (it's idempotent).
- A filter that **shares a name with a *different* local filter** is added under a new
  name (`Name (2)`, `Name (3)`, …), and the importing filter is rewired to that new
  copy. Your local filters are never changed.
- Everything else is added under its own name.

The import dialog summarises what was added, skipped and renamed. If an imported filter
references a **rule add‑on** that isn't installed in this Gramps, the dialog **warns you
before you confirm** — the filter still imports, but it will only work once you install
the matching rule add‑on.

## 8. Regular expressions and case

Rules that support it (the ones with a *Use regular expressions* option in the rule
editor) can match by regex, and optionally **case‑sensitively**. Tick *Use regular
expressions* to treat the value as a regex; the *Case sensitive* option becomes available
when regex is on. These settings are saved with the rule and re‑applied whenever the
filter runs, on both Gramps 5.2 and 6.0.

## 9. Notes & known limitations

- **Wayland (Linux):** the compositor controls window *placement*, so FilterWorkbench
  can't guarantee it reopens in the same spot; window *size* is restored. X11 behaves as
  expected. Not critical.
- **Active‑person rule:** its live count is shown blank (see §4); it still applies. Use
  **Home Person** for a deterministic anchor.
- **Helper filters** are created/edited only from inside the builder, by design.

## 10. Uninstall

Close Gramps and delete the add‑on's folder from your user *plugins* directory (see the
README for the path). Your family‑tree data is untouched. FilterWorkbench's own per‑tree
filter files live separately, in `…/gramps<XY>/filterbuilder/`, and can be removed too if
you wish.

## 11. Translations

The interface ships with a Danish translation ("Filterværksted"). A few strings shared
with Gramps' own rule editor follow Gramps' built‑in translation, so they appear in your
language if Gramps itself is translated there.

## License & author

Released under the **GNU General Public License v2.0 or later** (GPL‑2.0‑or‑later), the
same license as Gramps.

Henning — <contact@myown-project.dk> · <https://myown-project.dk>
