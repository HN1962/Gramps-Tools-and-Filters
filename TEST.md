## How to test the filters and tools

The safest way to test one of these projects is to install it in your Gramps
user plugin folder. This does not modify the Gramps program files.

1. Close Gramps.

2. Extract the downloaded ZIP archive.

3. Copy or extract the project folder into your Gramps user plugin folder.
   Keep the complete folder structure unchanged, including any `locale` folder
   included with the project.

   The user plugin folder is normally located here:

   - **Windows:** `%AppData%\gramps\gramps<version>\plugins\`
   - **Linux:** `~/.gramps/gramps<version>/plugins/`
   - **macOS:** `~/Library/Application Support/gramps/gramps<version>/plugins/`

   Replace `<version>` with the Gramps version folder used on your system.

4. Start Gramps again.

5. Check that the installed filter, rule, gramplet or tool is available where
   described in the project documentation.

If the project does not appear or fails to load, check **Help → Plugin Manager**
for an error message.

### Removing the test version

1. Close Gramps.
2. Delete the project folder that you added to the Gramps user plugin folder.
3. Start Gramps again.

Because the project was installed only in the user plugin folder, removing that
folder removes the test installation without changing the original Gramps
program files.

[← Back to README](README.md)