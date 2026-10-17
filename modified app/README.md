# Pixel Pulse desktop application

To add Pixel Pulse to your applications menu and desktop, run this once from this folder:

```bash
bash install_app.sh
```

Then open **Pixel Pulse** from the applications menu or desktop icon. If the desktop asks, right-click the shortcut and choose **Allow Launching**. Keep this project folder in its current location; if you move it, rerun the installer.

Your friend can install the application the same way after extracting the ZIP and installing the dependencies. On first launch, they import their invitation and enter their SDR address.

To launch directly from a terminal:

```bash
bash start.sh
```

This local copy opens User 1's profile. The app asks for your own SDR URI once, starts the radio automatically, and stops it when you close the app. Keep the terminal open while chatting. Close any older copy of the app/radio before starting this one.

## First-time installation

On a compatible Debian/Ubuntu computer, install the dependencies once:

```bash
sudo apt update
sudo apt install gnuradio python3-pyqt5 python3-zmq python3-cryptography python3-numpy python3-yaml python3-pil ffmpeg g++ libiio-utils
```

Then run `bash start.sh`. Missing native and generated radio files are built automatically on first launch. GNU Radio 3.10.9.2 is the tested version. Your SDR must work with GNU Radio's libiio blocks.

## Invite your friend

1. Run `bash start.sh` and choose **☰ → Invite someone…**.
2. Enter your friend's name and save their personal invitation JSON.
3. In another terminal in this folder, run `python3 tools/package_project.py`.
4. Send `dist/Pixel_Pulse_Share.zip` and the invitation JSON privately to your friend.

Your friend extracts the ZIP, installs the dependencies above once, and runs the same command inside the extracted `Pixel_Pulse` folder:

```bash
bash start.sh
```

On first launch they enter their name, import their invitation, and enter their own SDR URI. The app saves their profile as `configs/my_node.json`, builds the radio files if needed, and starts their radio automatically. Every later launch needs only `bash start.sh`.

The local `.coordinator` marker selects User 1's profile. The sharing ZIP excludes this marker, personal profiles, invitations, and history, so your friend gets the invitation screen instead of using your identity. Each invitation is for one person only. Keep the coordinator's database to retain issued-address reservations.

## Chat and connection issues

Both users run `bash start.sh`. Select your peer and send a short text; Delivered confirms that the receiving radio stored the message. Verify a reply before trying attachments.

If the radio fails, the app shows its error and offers Retry or Continue offline. Check power, SDR URI, IIO support and whether another app is already using the device. Details shows the local radio connection. Radio output is saved in `data/<node>/radio.log`. To change the saved URI, close the app and edit `uri` in your configuration (`configs/node_a.json` for User 1 or `configs/my_node.json` for a friend).

The default frequency is 2426500000 Hz. The configured URI is your own SDR's address. Both peers need matching frequency, sample rate, network key and modem settings, but different radio addresses. Keep both radios within range. Adjust the sensing threshold in Details if the channel remains busy at idle.

`run_app.sh` also invokes the automatic launcher. The separate radio launchers are available for manual diagnostics; do not run them alongside the automatic app.

For source changes, `bash setup.sh` rebuilds the radio and runs regression tests. `python3 tools/portable_smoke_test.py` validates the standalone flowgraph. Software checks do not prove over-the-air delivery; the physical link still requires testing with your SDRs.
