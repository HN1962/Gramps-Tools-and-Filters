# Non-birth child — a Gramps review rule

Initial public release.

## Added

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
- Optional Danish translation supplied as `addon.mo`.

## Compatibility

- Gramps 5.2 or higher.
- Tested with Gramps 6.0.8 on Windows 11 and Zorin OS 18.1 Core
- macOS not tested

## License

This modified version remains under the GNU General Public License, version 2 or, at your option, any later version. See [LICENSE](LICENSE).

## Project website

[myown-project.dk](https://myown-project.dk/)
