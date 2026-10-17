# Join Pixel Pulse

1. Extract `Pixel_Pulse_Share.zip` and open a terminal inside `Pixel_Pulse`.
2. Install the dependencies listed in README.md once.
3. Run `bash install_app.sh` once, then open **Pixel Pulse** from your applications menu.
4. Enter your name and select the personal invitation JSON from User 1.
5. Enter your own SDR URI when prompted. Your profile is saved as `configs/my_node.json`.
6. The app and radio start together. Select User 1 to send a message.

On every later launch, open **Pixel Pulse** from your applications menu or desktop icon. Alternatively, run:

```bash
bash start.sh
```

Close the app to stop its radio. If the device cannot connect, use Retry after resolving the connection, or Continue offline to manage contacts and queued messages.

Do not reuse another person's invitation or profile. To add an existing member, exchange **Details → Copy my contact code** and paste it in **New contact → Contact code**. Contact cards exclude the network key; invitations contain it and should be shared privately with their intended recipient.
