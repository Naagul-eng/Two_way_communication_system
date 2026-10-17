# Pixel Pulse

The maintained desktop application is in [modified app](<modified app/README.md>).

On Linux, open a terminal in that folder and install the dependencies listed in its README. Run:

```bash
bash install_app.sh
```

Then open **Pixel Pulse** from your applications menu. You can also run `bash start.sh` directly; the radio starts with the app and stops when it closes.

For the first user/coordinator, run `bash start.sh configs/node_a.json`. Existing local coordinator installations use their `.coordinator` marker. Friends import their personal invitation on first launch.

Only source, documentation, configuration and tests belong in the repository. Generated radio files and the native library are rebuilt automatically by `start.sh`. User histories, invitations, local profiles, shortcuts and release ZIPs are ignored. Create a sharing ZIP when needed with `python3 tools/package_project.py` inside the application folder.
