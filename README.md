# Pixel Pulse — Two-Way SDR Chat

Pixel Pulse exchanges text and attachments between SDR nodes using GNU Radio and a PyQt5 chat window. Run everything from a terminal with the Bash scripts below. Use one terminal on each computer: a single node command starts both the chat window and its radio.

Use the **`Chatapp`** branch of `Two_way_communication_system`. All commands below run from the repository root, where `setup.sh` is located.

## 1. Get the code and install dependencies

For a new copy:

```bash
git clone --branch Chatapp https://github.com/Naagul-eng/Two_way_communication_system.git
cd Two_way_communication_system
```

Use Debian/Ubuntu Linux, the system Python (`/usr/bin/python3`), and a compatible SDR with GNU Radio IIO/PlutoSDR support on each computer. GNU Radio 3.10.9.2 is the tested version. Deactivate any virtual environment before continuing.

```bash
sudo apt update
sudo apt install git gnuradio python3-pyqt5 python3-zmq python3-cryptography python3-numpy python3-yaml python3-pil ffmpeg g++ libiio-utils
```

## 2. Build and test once on each computer

```bash
bash setup.sh
```

This builds the native equalizer, updates the embedded radio sources, compiles the GNU Radio flowgraph, and runs the regression tests. Run it again after changing radio source code. It does not start the chat window or transmit.

The application files live directly in this repository. Commands in older instructions that refer to a `modified app` subdirectory should now be run here.

## 3. Run Node A (first user / coordinator)

If `configs/node_a.json` already exists, keep it and skip profile creation. For a new network only, create the coordinator once:

```bash
python3 tools/create_coordinator.py --name "User 1" --uri "ip:192.168.1.10"
```

Replace the URI with the address of **Node A's own SDR**. This creates a local profile with a new random network key and refuses to overwrite an existing identity or coordinator history.

Start chat and radio together with one command:

```bash
bash run_node_a.sh
```

Confirm the SDR URI if prompted. The radio starts after profile setup, and the chat window shows Connected when the radio service is available. Keep this terminal open while chatting. Close the chat window or press **Ctrl+C in this terminal** to stop both the chat session and its radio.

## 4. Invite Node B (second user)

In Node A's chat window:

1. Select **☰ → Invite someone…**.
2. Enter the person's name and save their personal invitation JSON under `Invitations/`.
3. Send that invitation privately to the person. Each invitation assigns one person's address and includes the network key.

Node B can clone the same branch, or you can create a clean source ZIP:

```bash
python3 tools/package_project.py
```

Send `dist/Pixel_Pulse_Share.zip` and the invitation. The ZIP excludes local profiles, keys, invitations, histories, and compiled binaries.

## 5. Run Node B (invited user)

On the second computer, clone the repository or extract the ZIP and enter its `Pixel_Pulse` directory. Install dependencies and run `bash setup.sh` as described above. Do not create another coordinator for the same network.

Start chat and radio together:

```bash
bash run_node_b.sh
```

On first launch, enter your name, import your personal invitation, and confirm **Node B's own SDR URI**. This saves `configs/my_node.json`, then starts the radio automatically.

Select User 1 and send a short text. Ask Node A to reply to confirm both directions before sending attachments. Close the chat window or press **Ctrl+C in this terminal** to stop the session and radio.

For later sessions, run the same single Node A or Node B command; setup and invitation import are only needed initially or after relevant changes.

## Command reference

| Command | Purpose |
| --- | --- |
| `bash setup.sh` | Build the radio and run software tests. |
| `bash run_node_a.sh` | Start Node A's chat and radio with `configs/node_a.json`. |
| `bash run_node_b.sh` | Start Node B's chat and radio; import an invitation on first launch. |
| `bash run_app.sh --config configs/custom.json` | Start chat and radio with another local profile. |
| `python3 tools/package_project.py` | Build the clean sharing ZIP. |

The older `run_node_a_chat.sh` and `run_node_b_chat.sh` commands also launch both chat and radio. Each physical node needs a different invitation/address. Run one session per node.

The `run_node_a_radio.sh`, `run_node_b_radio.sh`, and `run_radio.sh` scripts remain available for radio-only diagnostics. Close the combined session before using them so two processes do not compete for the same SDR.

## Settings and troubleshooting

Close the chat window to stop its radio before editing local profiles. Node A uses `configs/node_a.json`; Node B uses `configs/my_node.json`.

| Symptom / setting | Action |
| --- | --- |
| `Run bash setup.sh first` | Build the generated radio files with `bash setup.sh`. |
| Missing Python module | Install the dependencies above and use the system Python. |
| Radio cannot connect | Check SDR power, the local `uri`, IIO support, and whether another process owns the device. Errors appear in the launch terminal and `data/<node>/radio.log`. Use **Retry** after fixing the connection, or **Continue offline** to manage contacts and queued messages. |
| Chat stays Offline | Check the launch terminal or `data/<node>/radio.log`, then resolve the SDR connection and use Retry. |
| Queued messages | Check both radios are running, the devices are in range, and both profiles have matching radio settings and network key. |
| Channel busy at idle | Review the sensing threshold in Details and check interference. |
| Delivered | The receiving radio stored the message. Confirm a reply to test the return link. |

Default frequency: **2426500000 Hz**. Default sample rate: **2400000 samples/s**. Peers need matching frequency, sample rate, modem settings, and network key, with different node addresses. `uri` is the address of the SDR attached to this computer.

Check your SDR connection using its actual URI:

```bash
iio_info -u ip:192.168.1.10
```

To add another existing member, exchange **Details → Copy my contact code** and paste it into **New contact → Contact code**. Contact codes exclude the network key; invitations include it.

## Software checks

After building, run the regression suite or the isolated flowgraph check:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
python3 tools/portable_smoke_test.py
```

These checks exercise software behavior and simulated PHY/MAC paths. Verify over-the-air delivery separately with your two SDRs.

The maintained flowgraph is `flowgraphs/Working1.0_csma.grc`. Original transmitter/receiver references are under `flowgraphs/legacy/`. The optional conversion tool takes an explicit original file: `python3 tools/build_flowgraph.py --source /path/to/Working1.0.grc`.

## Source and local data

- `sdrchat/`: chat interface, protocol, MAC, and radio code.
- `configs/node_a.example.json`: public example defaults used by tests and the standalone demo flowgraph. Its all-zero key is a test value; create a real coordinator profile with the command above.
- `tests/` and `tools/`: regression tests, profile creation, packaging, and flowgraph tools.
- `data/node_a/` and `data/my_node/`: local chat/radio history. Keep the coordinator history to retain issued-address reservations.
- `data/previous-root/`: older local databases preserved during repository cleanup.

Local profiles, history, invitation exports, generated radio files, native binaries, and release ZIPs are ignored by Git. Personal files from earlier commits remain in the existing Git history; the current branch stops tracking them without rewriting history.

## Commit and publish changes

```bash
git status
git diff
git add -A
git diff --cached --stat
git commit -m "Describe your changes"
git push origin Chatapp
```
