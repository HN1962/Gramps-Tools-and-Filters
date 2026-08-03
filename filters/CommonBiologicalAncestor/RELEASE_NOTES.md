# Common Biological Ancestor — a Gramps filter rule

Initial public release.

## Added

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
- Optional Danish translation supplied as `addon.mo`.

## Compatibility

- Gramps 5.2 or higher.
- Tested with Gramps 6.0.8 on Windows 11 and Zorin OS 18.1 Core
- macOS not tested

## License

This modified version remains under the GNU General Public License, version 2 or, at your option, any later version. See [LICENSE](LICENSE).

## Project website

[myown-project.dk](https://myown-project.dk/)
