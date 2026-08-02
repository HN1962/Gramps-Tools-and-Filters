# Common Biological Ancestor — a Gramps filter rule

A custom filter rule for [Gramps](https://gramps-project.org/) that matches
people who share a **biological** ancestor with a chosen person.

## Why?

Gramps ships with the rule **"People with a common ancestor with `<person>`"**.
When it walks up the family tree it follows *every* parent link, regardless of
whether a child is a birth, adopted, foster or step child. As a result, adopted
and foster children are treated as blood relatives of their adoptive/foster
family's ancestors.

This rule does the same job, but follows a parent link **only when the child's
relationship to that parent is "Birth"**. Adopted, foster, step and sponsored
children are therefore included only if they are *also* recorded as a birth
child in a biological family. A child that appears solely in an adoptive or
foster family is given no ancestors beyond itself and will not match through
that family.

## Requirements

- Gramps 5.x or 6.x. The rule file works on both (the rule method was renamed
  between the two major versions, and this addon defines both names).

## Installation

1. Locate your Gramps user plugin folder:
   - **Windows:** `%APPDATA%\gramps\gramps<XY>\plugins\`
   - **Linux/macOS:** `~/.gramps/gramps<XY>/plugins/`

   where `<XY>` is your version without the dot, e.g. `gramps60` for 6.0 or
   `gramps52` for 5.2.

2. Create a subfolder there, for example `CommonBiologicalAncestor`, and copy
   both files into it:
   - `hascommonbiologicalancestor.py`
   - `hascommonbiologicalancestor.gpr.py`

3. Open `hascommonbiologicalancestor.gpr.py` and set `gramps_target_version`
   to **your** Gramps version, `major.minor` (see **Help → About**), e.g.
   `"6.0"` or `"5.2"`. If this does not match, Gramps will refuse to load the
   rule.

4. Restart Gramps. If anything went wrong during loading, **Help → Plugin
   Manager** will show the error.

## Usage

1. In any person view, open **Edit → Person Filter Editor**.
2. Add a new filter (or edit an existing one) and click **Add** to add a rule.
3. Under the **Ancestral filters** category, choose
   **"People with a common biological ancestor with `<person>`"**.
4. Enter the reference person's **Gramps ID** and click **OK**.
5. Optionally tick **"Return values that do not match the filter rule"** to get
   the complement.

The rule can be combined with other rules exactly like the built-in one, and
the resulting filter can be used for reports, exports and tags.

## Important: relationship types must be correct

The rule relies entirely on the **child reference relationship type** (Birth /
Adopted / Foster / …) recorded on each child, for both the father and the
mother side. If an adopted or foster child is left with the default "Birth"
relationship, it will still be counted as biological. It is worth checking that
these relationship types are set correctly on the relevant families.
For this purpose I have created a new filter that can help with this. It is called NonBirthChildRelation and can be found here ....

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

Only strings unique to this addon are translated here; standard Gramps terms
(category names, "ID:", the relationship-type names in the drop-down, etc.)
come from Gramps' own translations automatically.
