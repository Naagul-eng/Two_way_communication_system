# Join Pixel Pulse as Node B

Use the personal invitation JSON sent by Node A. Do not reuse another person's invitation or profile.

1. Clone the `Chatapp` branch, or extract `Pixel_Pulse_Share.zip` and open a terminal inside `Pixel_Pulse`.
2. Install the dependencies in [README.md](README.md#1-get-the-code-and-install-dependencies).
3. Build and test once:

   ```bash
   bash setup.sh
   ```

4. Start chat and radio with one command:

   ```bash
   bash run_node_b.sh
   ```

5. On first launch, enter your name, select your invitation, and enter the URI of your own SDR. Your profile is saved as `configs/my_node.json`, and the radio starts automatically.
6. Send a short text to User 1 and ask for a reply.

For later sessions, run `bash run_node_b.sh` again. Keep the terminal open while chatting. Close the chat window or press Ctrl+C in the terminal to stop the session and its radio.

If the radio cannot connect, check the terminal or `data/my_node/radio.log`. Use Retry after fixing the device connection, or Continue offline to manage contacts and queued messages.

Do not create another coordinator when joining an existing network. See [README.md](README.md) for Node A commands, settings, and troubleshooting.
