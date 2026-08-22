# Verify the Data → HTML report
[ReadMe](README.md) • [Release Notes](RELEASE_NOTES.md) • [GNU GPL (license)](LICENSE)

A Gramps tool that runs the built-in **Verify the Data** checks and saves the
result as a self-contained, sortable HTML report in which each item can be
ticked off once you have reviewed it.

## What it does

- Runs the same data checks as Gramps' built-in *Verify the Data* tool.
- Writes a single, standalone `.html` file (CSS and JavaScript embedded).
- The report lets you **sort** by any column, **filter** by severity, **search**,
  **hide reviewed** items, and put a **check mark** next to each item you have
  been through.
- Opens the finished report in your default browser.

## How it works

The tool does **not** copy the checks. It imports the `Verify` class from
Gramps' own `verify` module and calls its `run_the_tool()` through a light
"shim", collecting the results instead of showing them in the usual window.

That means:

- It **follows along automatically** when Gramps improves or adds checks —
  nothing is frozen into a copy.
- **None of Gramps' own files are touched.** The add-on lives entirely in your
  user plugin folder, so it survives Gramps updates.

## Requirements

- Gramps 5.2 or higher.

## Installation

Copy the `VerifyHTML` folder into your Gramps user plugin folder and restart
Gramps:

- **Windows:** `%AppData%\gramps\gramps<ver>\plugins\` (for example `gramps60`)
- **Linux:** `~/.gramps/gramps<ver>/plugins/`
- **macOS:** `~/Library/Application Support/gramps/gramps<ver>/plugins/`

Only these files are needed by the add-on:

```
VerifyHTML/
├── VerifyHTML.gpr.py
├── VerifyHTML.py
├── README.md
└── locale/da/LC_MESSAGES/addon.mo      (Danish translation, optional)
```

The tool appears under **Tools → Analysis and Exploration**.

## Usage

### 1. Set your thresholds (once)

The thresholds — maximum age, young parent, spacing between children, and so on —
are read from the built-in *Verify the Data* tool. Those settings are **only
stored when that tool is actually run.** So:

> Open **Tools → Family Tree Repair → Verify the Data**, set your preferred
> values, and click **Run**. Changing a value and closing the window without
> running does **not** save it.

Once run, your values are remembered and reused every time. You only need to do
this again when you want to change a threshold.

### 2. Generate the report

Run **Verify the Data → HTML report**. It reads your saved thresholds, runs the
checks, asks where to save the `.html` file, and opens it in your browser. The
confirmation dialog reminds you which tool the thresholds came from.

## The report

| Feature | Notes |
| --- | --- |
| Sort | Click any column header; click again to reverse. |
| Filter | *All / Errors only / Warnings only.* |
| Search | Matches name, ID, object type and check text. |
| Hide reviewed | Temporarily removes ticked items from the list. |
| Check mark | Marks an item as reviewed. |
| Save a copy | Downloads a copy with the current check marks baked in. |
| Reset check marks | Clears all marks for this family tree. |

### About saving your progress

Check marks are stored in your browser and are normally kept between visits.
Each item has a stable key (`ID|rule`), so the marks even survive regenerating
the report.

To be completely sure of keeping your progress — or to move it to another
device — use **Save a copy**. The downloaded file has your current check marks
baked in, so they show up wherever the file is opened.

One caveat: when the file is opened as a local file (`file://`) in Chrome,
browser storage is not always kept between sessions. In that case, **Save a
copy** is the safe way to keep your work. Served over `http` (from a website) or
opened in Firefox, the marks persist on their own.

## Language

English is the source language. The report and the tool interface are fully
translatable through a bundled catalog:

```
VerifyHTML/locale/<lang>/LC_MESSAGES/addon.mo
```

A Danish translation is provided. To rebuild it after editing `po/da.po`:

```
msgfmt po/da.po -o locale/da/LC_MESSAGES/addon.mo
```

If no matching `.mo` is found, the tool falls back to English.

## Author

Henning — <contact@myown-project.dk>
Documentation: <https://myown-project.dk/tools/verify-the-data/index.html>
