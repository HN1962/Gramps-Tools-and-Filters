# Non-birth child — a Gramps review rule

A custom filter rule for [Gramps](https://gramps-project.org/) that matches
people who are recorded as a child with a relationship to a parent **other than
"Birth"** — adopted, foster, step, sponsored, none, unknown or a custom type.

## Why?

This rule is a review/QA companion to the **Common Biological Ancestor** rule.
That rule decides who is a blood relative purely from the **child relationship
type** (Birth vs. Adopted / Foster / …) recorded on each child. It can therefore
only be as accurate as those labels.

The catch: in Gramps the **default** relationship for a new child is **"Birth"**.
An adopted or foster child whose relationship type was never changed silently
looks biological, and will be treated as a blood relative.

Run this rule to list everyone marked as a non-birth child, so you can confirm
the labels are complete and correct — and, by knowing your own tree, spot anyone
who *should* be on the list but isn't (because they were left at the default).

## Requirements

- Gramps 5.x or 6.x. The rule file works on both.

## Installation

1. Locate your Gramps user plugin folder:
   - **Windows:** `%APPDATA%\gramps\gramps<XY>\plugins\`
   - **Linux/macOS:** `~/.gramps/gramps<XY>/plugins/`

   where `<XY>` is your version without the dot, e.g. `gramps60` or `gramps52`.

2. Create a subfolder, e.g. `NonBirthChildRelation`, and copy both files into it:
   - `hasnonbirthchildrelation.py`
   - `hasnonbirthchildrelation.gpr.py`

3. Open `hasnonbirthchildrelation.gpr.py` and set `gramps_target_version` to
   **your** Gramps version, `major.minor` (see **Help → About**). If it does not
   match, Gramps will refuse to load the rule.

4. Restart Gramps. Any load error is shown in **Help → Plugin Manager**.

## Usage

1. In a person view, open **Edit → Person Filter Editor**.
2. Add a filter and click **Add** to add a rule.
3. Under **Family filters**, choose **"People recorded as a non-birth child"**.
4. Open the **Child relationship type** drop-down and pick one:
   - **(any non-birth)** — the first entry — matches *all* non-birth
     relationships at once (adopted, foster, step, sponsored, none, unknown).
   - Or pick a **single type** (Adopted, Foster, Stepchild, …) to narrow the
     list.
5. Click **OK**. Optionally tick **"Return values that do not match the filter
   rule"** to invert it.

The match fires if the person has **any** parent family in which their
relationship to the father **or** the mother qualifies.

## Notes

- A person appearing in both a birth family and an adoptive family will match
  (their adoptive relationship qualifies), which is exactly what you want when
  reviewing.
- **(any non-birth)** deliberately also surfaces `None` and `Unknown`
  relationships, since those are gaps worth reviewing too. Pick a specific type
  if you want a narrower list.
- The drop-down is supplied through the Gramps filter editor's supported
  custom-widget hook (a `(label, factory)` tuple in the rule's `labels`). It
  stores the language-neutral English keyword, so a saved filter keeps working
  even if you switch interface language.

## License

GNU General Public License, version 2 or later — same as Gramps.

## Catching the opposite case (children wrongly left at "Birth")

This rule lists children marked as *non-birth*. It cannot find the reverse — a
child that *should* be non-birth but was left at the default "Birth" — because
in the data such a child looks fully biological, so no filter can detect it with
certainty.

Gramps' built-in **Verify the Data** tool (**Tools → Utilities → Verify the
Data**) is the practical safety net. It flags birth relationships that are
biologically *implausible*: a parent too young or too old at the child's birth,
a parent not yet born, or a parent already dead. Those are exactly the cases
where a "Birth" tag is suspect, so you can review each one and re-tag it if
needed. Note this only catches implausible cases — an adopted child whose
adoptive parents are a plausible age will not be flagged.

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
