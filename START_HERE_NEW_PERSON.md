# Join Pixel Pulse

Use the personal invitation JSON sent by your network coordinator. Do not reuse another person's invitation or profile.

1. Extract `Pixel_Pulse_Share.zip` and open a terminal inside `Pixel_Pulse`, or clone the `Chatapp` branch.
2. Follow **step 2 in [README.md](README.md#2-install-dependencies)** to install the Linux dependencies.
3. Run `bash start.sh`. Do not run the coordinator creation command when joining an existing network.
4. Enter your name, select your invitation JSON, and enter your own SDR URI.
5. Select User 1 and send a short text. Ask them to reply before trying attachments.

The app saves your local profile as `configs/my_node.json`. On every later launch, run:

```bash
bash start.sh
```

To add Pixel Pulse to your applications menu and desktop, run `bash install_app.sh` once. Rerun it if you move the project directory.

Closing the app stops its radio. If the SDR cannot connect, fix the connection and use **Retry**, or choose **Continue offline** to manage contacts and queued messages. Logs are under `data/my_node/radio.log`.

To add an existing member, exchange **Details → Copy my contact code** and paste it into **New contact → Contact code**. Contact codes exclude the network key; invitation files include it.

See [README.md](README.md) for troubleshooting, radio settings, and development checks.
