# Event in Place (or sub-place) — a Gramps filter rule V1.0.0
[ReadMe](README.md) • [GNU GPL (license)](LICENSE)

A custom filter rule for [Gramps](https://gramps-project.org/) that matches
people who have an **event whose place lies within a named place** — including
everything enclosed by it, all the way down the place hierarchy.

## Why?

Filtering people by jurisdiction (parish / county / province / state / country)
normally needs a **three-filter chain across namespaces** in Gramps:

1. a place filter **"IsEnclosedBy"** (only editable in the Places view),
2. an event filter **"MatchesPlaceFilter"** (only in the Events view),
3. a person filter **"MatchesEventFilter"** (in the People view).

This rule collapses that chain into **one person rule**: the place enclosure is
done *inside* the rule, so you don't have to build a place filter and an event
filter first. Pick it in the People view (or in FilterWorkbench) and you are
done.

It matches by **place name**, not by Gramps ID. IDs change on backend upgrade,
backup import and version switches, which makes ID-based filters brittle; names
are self-documenting. If several places share a name (e.g. two "Skåne"), **all**
of them are used as targets, so the filter simply works.

## What it does NOT do

It solves the **simple case**: "people with an (optionally typed) event inside a
jurisdiction." It does **not** do event-quality composition — e.g. "events with
a missing date or source *within* a jurisdiction." That is genuine event-filter
territory and still needs Gramps' Events view.

## Requirements

- Gramps 5.1, 5.2 or 6.x. The rule file works on all of them (the rule method
  was renamed between the major versions, and this addon defines both names).

## Installation

1. Locate your Gramps user plugin folder:
   - **Windows:** `%APPDATA%\gramps\gramps<XY>\plugins\`
   - **Linux/macOS:** `~/.gramps/gramps<XY>/plugins/`

   where `<XY>` is your version without the dot, e.g. `gramps60` for 6.0,
   `gramps52` for 5.2 or `gramps51` for 5.1.

2. Create a subfolder there, for example `HasEventInPlaceEnclosed`, and copy the
   files into it:
   - `haseventinplaceenclosed.py`
   - `haseventinplaceenclosed.gpr.py`
   - the `locale/` folder (for the Danish translation)

3. Restart Gramps. If anything went wrong during loading, **Help → Plugin
   Manager** will show the error.

## Usage

1. In any person view, open **Edit → Person Filter Editor**.
2. Add a new filter (or edit an existing one) and click **Add** to add a rule.
3. Under the **Event filters** category, choose
   **"People with an event in a place or its sub-places"**.
4. Fill in the fields:
   - **Place name** — the name (or full title) of the place, e.g. `København`.
     All places with that name are matched, and the place itself as well as
     everything below it counts.
   - **Event type** — leave blank to match events of any type, or pick a type
     (e.g. Birth, Death) from the drop-down to match only that type.
   - **Use regular expressions** (checkbox) — leave unticked for an exact,
     case-insensitive name match (the default). Tick it to treat the place-name
     field as a regular expression instead, e.g. `Bagen.*` (starts with),
     `^Skåne$` (exactly Skåne), or `Skåne|Fyn` (either).
5. Click **OK**.

### Exact vs. regular-expression name matching

By default the place name is matched **exactly** (ignoring upper/lower case).
Ticking **Use regular expressions** switches the place-name field to a regular
expression, searched anywhere in the name/title:

- `Bagenkop` (unticked) — matches only places named exactly *Bagenkop*.
- `Bagen.*` (ticked) — matches *Bagenkop*, *Bagenkobbel*, …
- `^Bagenkop$` (ticked) — exactly *Bagenkop*, same as unticked.
- `Skåne|Fyn` (ticked) — places named *Skåne* or *Fyn*.

Note: in regex mode the pattern is also tested against each place's full title
(e.g. *"Bagenkop, Langeland, …"*), so an unanchored pattern like `Bagenkop` can
match via the title too; anchor with `^…$` if you want the name field only.

**This differs from the usual Gramps behaviour.** Gramps' standard rules that
offer a "Use regular expressions" checkbox treat the **unticked** field as a
*substring* (contains) match. This rule instead treats the unticked field as an
**exact**, whole-name (case-insensitive) match. In both, **ticked** = a regular
expression — so the only difference from the usual behaviour is the unticked
default: exact here, contains elsewhere.

The rule can be combined with other rules exactly like a built-in one, and the
resulting filter can be used for reports, exports and tags. It also appears in
FilterWorkbench's rule picker automatically.

## How matching works

For each of the person's events, the rule looks at the event's place and matches
when that place **is** the named place or lies **within** it (transitively up the
place hierarchy). The named place itself always counts, so a person with an event
recorded directly at the named place matches. The enclosure test is Gramps' own
`located_in`, so the "enclosed by" semantics are identical to the built-in place
rule. Place hierarchies are shallow (a few levels), so this is cheap even on large
trees.

## License

GNU General Public License, version 2 or later — same as Gramps.

## Translations (i18n)

This addon ships with a Danish translation and is ready for more languages.
Layout:

```
<addon folder>/
  *.py  *.gpr.py
  po/
    template.pot          # all translatable strings (source)
    da.po                 # Danish translation (source)
  locale/
    da/LC_MESSAGES/addon.mo   # compiled Danish catalog (used at runtime)
```

Gramps loads `locale/<lang>/LC_MESSAGES/addon.mo` automatically when the
interface is set to that language, and falls back to English otherwise. The
`.mo` filename must be exactly `addon.mo`.

To add another language, e.g. German:

1. Copy `po/template.pot` to `po/de.po` and translate each `msgstr`.
2. Compile it to `locale/de/LC_MESSAGES/addon.mo`. With GNU gettext:
   `msgfmt po/de.po -o locale/de/LC_MESSAGES/addon.mo`
   (or use the Python `polib` package: `pofile('po/de.po').save_as_mofile(...)`).
3. Restart Gramps.

Only strings unique to this addon are translated here. Standard Gramps terms —
the **Event type** drop-down and the **Event filters** category name — come from
Gramps' own translations automatically, so the rule editor renders the correct
widgets in every language.
