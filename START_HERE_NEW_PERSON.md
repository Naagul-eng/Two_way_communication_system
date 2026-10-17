# Join Pixel Pulse as Node B

Use the personal invitation JSON sent by Node A. Do not reuse another person's invitation or profile.

1. Clone the `Chatapp` branch, or extract `Pixel_Pulse_Share.zip` and open a terminal inside `Pixel_Pulse`.
2. Install the dependencies in [README.md](README.md#1-get-the-code-and-install-dependencies).
3. Build and test once:

   ```bash
   bash setup.sh
   ```

4. In terminal 1, open the chat window:

   ```bash
   bash run_node_b_chat.sh
   ```

5. Enter your name, select your invitation, and enter the URI of your own SDR. Your profile is saved as `configs/my_node.json`.
6. In terminal 2, opened in the same project directory, start the radio:

   ```bash
   bash run_node_b_radio.sh
   ```

7. Send a short text to User 1 and ask for a reply.

For later sessions, run the same two Node B commands. Closing the chat window leaves the radio running; press Ctrl+C in the radio terminal to stop it. Keep both terminals open while chatting.

Do not create another coordinator when joining an existing network. See [README.md](README.md) for Node A commands, settings, and troubleshooting.
