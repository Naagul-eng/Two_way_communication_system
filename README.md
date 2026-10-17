# Pixel Pulse — Two-Way SDR Chat

Pixel Pulse is a Linux desktop chat application for text and attachments over software-defined radios. It starts its GNU Radio transceiver automatically and stops it when the window closes. The radio uses QPSK, CSMA/CA, acknowledgements, retries, Reed–Solomon error correction, and an NLMS equalizer.

The application is maintained on the **`Chatapp`** branch of **`Two_way_communication_system`**. Run all commands below from the repository root, where `start.sh` is located.

## 1. Get the application

For a new copy:

```bash
git clone --branch Chatapp https://github.com/Naagul-eng/Two_way_communication_system.git
cd Two_way_communication_system
```

For an existing checkout, check your work before switching branches:

```bash
git status
git switch Chatapp
```

The application files now live directly in this directory. Older instructions that refer to a `modified app` subdirectory no longer apply. If you installed a desktop shortcut before this reorganization, rerun `bash install_app.sh` from this directory.

## 2. Install dependencies

Use a Debian/Ubuntu Linux desktop with Python 3, GNU Radio with IIO/PlutoSDR blocks, and a compatible SDR on each participant's computer. GNU Radio **3.10.9.2** is the version previously tested for this project. A compiler builds the native equalizer locally.

```bash
sudo apt update
sudo apt install git gnuradio python3-pyqt5 python3-zmq python3-cryptography python3-numpy python3-yaml python3-pil ffmpeg g++ libiio-utils
```

Use the system Python (`/usr/bin/python3`) so the GNU Radio and PyQt packages installed by `apt` are available. If a virtual environment is active, deactivate it before continuing.

Check the Python dependencies:

```bash
python3 -c 'import PyQt5, zmq, cryptography, numpy, yaml, PIL; from gnuradio import gr, iio; print("Dependencies OK")'
```

## 3. Set up the first user (coordinator)

Do this **once for a new radio network**, on one computer only:

```bash
python3 tools/create_coordinator.py --name "User 1" --uri "ip:192.168.1.10"
bash start.sh
```

Replace the URI with the address of **your own SDR**. The setup command creates `configs/node_a.json` with a new random network key and a local `.coordinator` marker. On first launch, confirm your SDR URI when prompted. The radio and desktop app then start together.

If this checkout already has your coordinator profile, skip the creation command and run `bash run_node_a_chat.sh`. The creation command refuses to overwrite an existing profile or coordinator history. Keep `data/node_a/` to retain messages and issued-address reservations.

After the initial setup, launch with:

```bash
bash start.sh
```

Keep the terminal open while chatting. Close older app/radio instances before launching another copy. Closing the application stops its radio.

## 4. Invite a second user

On the coordinator's computer:

1. Open the app and select **☰ → Invite someone…**.
2. Enter the person's name and save the personal invitation JSON, preferably under `Invitations/`.
3. Build a clean sharing ZIP:

   ```bash
   python3 tools/package_project.py
   ```

4. Send `dist/Pixel_Pulse_Share.zip` and that person's invitation privately to them. Each invitation is for one person and contains the network key.

On the second user's computer:

1. Extract the ZIP and open a terminal inside the extracted `Pixel_Pulse` directory. Alternatively, clone the `Chatapp` branch as described above.
2. Install the dependencies in step 2.
3. Run `bash start.sh`. **Do not create another coordinator profile.**
4. Enter your name, import the invitation issued to you, and enter your own SDR URI.
5. Select User 1 and send a short text. User 1 should reply to verify both directions before sending attachments.

The friend's profile is saved locally as `configs/my_node.json`. Future launches need only `bash start.sh`. To add another existing member, exchange **Details → Copy my contact code** and paste it into **New contact → Contact code**.

## 5. Install the desktop shortcut (optional)

After configuring your profile:

```bash
bash install_app.sh
```

Open **Pixel Pulse** from your applications menu or desktop. If your desktop asks, right-click the shortcut and choose **Allow Launching**. Keep this directory in its installed location; rerun the installer after moving it. The installer creates shortcuts for your current Linux user.

## Radio settings and troubleshooting

Local settings are in `configs/node_a.json` for the coordinator and `configs/my_node.json` for an invited user. Close the app before editing them.

| Setting / symptom | What to check |
| --- | --- |
| SDR URI | `uri` must point to the SDR connected to this computer, for example `ip:192.168.1.10`. |
| Frequency and sample rate | Defaults are `2426500000` Hz and `2400000` samples/s. Both peers need matching frequency, sample rate, network key, and modem settings, with different node addresses. |
| Radio fails to connect | Check SDR power, connectivity, IIO support, and that no other app owns the device. Use **Retry** after fixing the issue. |
| Continue offline | Opens the interface for contacts and queued messages. It does not transmit until the radio reconnects. |
| Messages stay queued | Check the radio connection in **Details**, the peer's running app, matching settings, and radio range. |
| Channel stays busy at idle | Review the sensing threshold in **Details** and check interference. |
| Delivered | The receiving radio stored the message. Confirm a reply to test the return link. |
| Build/import error | Check the dependency command above and use the system Python. Run `bash setup.sh` to rebuild. |

Radio output is written to `data/<node>/radio.log`. To check IIO connectivity directly, use your actual URI:

```bash
iio_info -u ip:192.168.1.10
```

`configs/node_a.example.json` is a public reference. Its all-zero example key is for software tests and the standalone demo flowgraph; `create_coordinator.py` generates a different key for your network. The application selects your local runtime profile when starting the radio.

## Development and verification

Rebuild the native equalizer, refresh the embedded flowgraph sources, compile the radio, and run the regression suite:

```bash
bash setup.sh
```

After the initial build, run just the tests with:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

Validate that the maintained GRC compiles and passes radio tests outside this checkout:

```bash
python3 tools/portable_smoke_test.py
```

These checks cover software behavior and simulated PHY/MAC paths. A two-radio hardware test is still needed to verify over-the-air communication.

The normal launcher owns the radio process. For manual diagnostics, close the normal app first, then use `bash run_radio.sh configs/my_node.json` or `bash run_node_a_radio.sh`.

`tools/build_flowgraph.py` optionally converts the original `Working1.0.grc`, which is not required to build this branch. To regenerate from a separately supplied original, run `python3 tools/build_flowgraph.py --source /path/to/Working1.0.grc`, then `bash setup.sh`.

## Repository layout

```text
Two_way_communication_system/
├── README.md                     # Installation, operation, and development
├── START_HERE_NEW_PERSON.md       # Short guide for invited users
├── start.sh                      # Build missing assets and launch app + radio
├── setup.sh                      # Rebuild radio assets and run tests
├── install_app.sh                # Install per-user desktop shortcuts
├── configs/
│   └── node_a.example.json       # Public defaults; local profiles are ignored
├── sdrchat/                       # Desktop UI, protocol, MAC, and radio modules
│   └── native/nlms.cpp           # Native equalizer source
├── flowgraphs/
│   ├── Working1.0_csma.grc       # Maintained transceiver
│   └── legacy/                   # Original transmitter/receiver references
├── assets/                       # App icon
├── tests/                        # Software regression tests
└── tools/                        # Setup, packaging, and flowgraph utilities
```

Git excludes local profiles, `.coordinator`, `data/`, `Invitations/`, invitation exports, logs, generated radio Python, native binaries, desktop shortcuts, and `dist/`. The sharing ZIP also excludes personal profiles, keys, invitations, and history. During this cleanup, the older databases from the former repository root were preserved locally under `data/previous-root/`; the application's active history stays in `data/node_a/` and `data/my_node/`.

Personal files tracked by earlier commits remain in the repository's existing history; this cleanup stops tracking them in the current branch without rewriting that history.

## Save and publish changes to Chatapp

Review the diff before committing. Keep personal files out of staged changes:

```bash
git status
git diff
git add -A
git diff --cached --stat
git commit -m "Organize chat application and document setup"
git push origin Chatapp
```
