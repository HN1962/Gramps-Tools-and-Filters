# A named place and its sub-places — a Gramps filter rule V1.0.0

A custom **Places** filter rule for [Gramps](https://gramps-project.org/) that
matches the named place itself plus **every place enclosed by it** — all the way
down the place hierarchy.

## Why?

Gramps already ships a place rule, **"IsEnclosedBy"**, but it selects by **Gramps
ID**. IDs change on backend upgrade, backup import and version switches, which
makes ID-based filters brittle. This rule does the same job **by place name**,
which is self-documenting and stable. If several places share a name, **all** of
them are used as targets.

It is the Places-view companion to the person rule *"People with an event in a
place or its sub-places"*: same name-based, transitive enclosure, but here the
result is the matching **places** themselves rather than people.

## Requirements

- Gramps 5.1, 5.2 or 6.x. The rule file works on all of them (the rule method
  was renamed between the major versions, and this addon defines both names).

## Installation

1. Locate your Gramps user plugin folder:
   - **Windows:** `%APPDATA%\gramps\gramps<XY>\plugins\`
   - **Linux/macOS:** `~/.gramps/gramps<XY>/plugins/`

   where `<XY>` is your version without the dot, e.g. `gramps60`, `gramps52` or
   `gramps51`.

2. Create a subfolder there, e.g. `PlaceInNamedPlaceEnclosed`, and copy in:
   - `placeinnamedplaceenclosed.py`
   - `placeinnamedplaceenclosed.gpr.py`
   - the `locale/` folder (for the Danish translation)

3. Restart Gramps. Any load error shows in **Help → Plugin Manager**.

## Usage

1. In the **Places** view, open the place filter editor (the filter gramplet /
   **Edit → Place Filter Editor**).
2. Add a new filter, click **Add** to add a rule, and under **General filters**
   choose **"Places within a named place or its sub-places"**.
3. Fill in the fields:
   - **Place name** — the name (or full title) of the place, e.g. `Langeland`.
     All places with that name are matched, and the place itself as well as
     everything below it counts.
   - **Use regular expressions** (checkbox) — leave unticked for an exact,
     case-insensitive name match (the default). Tick it to treat the place-name
     field as a regular expression, e.g. `Bagen.*`, `^Skåne$`, or `Skåne|Fyn`.
4. Click **OK**.

The result is every place that is, or lies within, the named place — handy for
scoping a jurisdiction, then reusing the filter in reports or exports.

### Exact vs. regular-expression name matching

By default the place name is matched **exactly** (ignoring upper/lower case).
Ticking **Use regular expressions** switches the place-name field to a regular
expression, searched anywhere in the name/title:

- `Langeland` (unticked) — only places named exactly *Langeland*.
- `Lange.*` (ticked) — *Langeland*, *Langeskov*, …
- `^Langeland$` (ticked) — exactly *Langeland*.
- `Skåne|Fyn` (ticked) — places named *Skåne* or *Fyn*.

**This differs from the usual Gramps behaviour.** Gramps' standard rules that
offer a "Use regular expressions" checkbox treat the **unticked** field as a
*substring* (contains) match. This rule instead treats the unticked field as an
**exact**, whole-name (case-insensitive) match. In both, **ticked** = a regular
expression — so the only difference from the usual behaviour is the unticked
default: exact here, contains elsewhere.

Note: in regex mode the pattern is also tested against each place's full title,
so an unanchored pattern can match via the title too; anchor with `^…$` for the
name field only.

## How matching works

The rule resolves the typed name to every place whose name/title matches, then a
place is selected if it **is** one of those targets or lies **within** one
(tested with Gramps' own `located_in`, so the "enclosed by" semantics are
identical to the built-in rule). Place hierarchies are shallow, so this is cheap
even on large trees.

## License

GNU General Public License, version 2 or later — same as Gramps.

## Translations (i18n)

Ships with a Danish translation. Layout:

```
<addon folder>/
  *.py  *.gpr.py
  po/template.pot   po/da.po
  locale/da/LC_MESSAGES/addon.mo
```

Gramps loads `locale/<lang>/LC_MESSAGES/addon.mo` automatically for that
language. To add a language, copy `po/template.pot` to `po/<lang>.po`, translate
each `msgstr`, compile to `locale/<lang>/LC_MESSAGES/addon.mo`
(`msgfmt po/<lang>.po -o locale/<lang>/LC_MESSAGES/addon.mo`), and restart.

Only strings unique to this addon are translated here. Standard Gramps terms —
the **General filters** category name and the **Use regular expressions**
checkbox — come from Gramps' own translations automatically.
