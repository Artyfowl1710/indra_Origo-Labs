# Telegram and WhatsApp


## Telegram: your own bot

1. Open Telegram and find the verified `@BotFather` account.
2. Send `/newbot`, choose a display name such as Indra and a unique username ending in `bot`.
3. Copy the bot token into Indra → Integrations → Telegram → manual/own-bot setup. Never paste it into GitHub, screenshots or shared chat.
4. Open your bot from the BotFather link and send `/start`. Configure the allowed user/chat identity through the setup flow. Your `@username` is a handle; numeric user/chat IDs are separate identifiers. Avoid adding the `@` twice.
5. Enable Telegram, start/restart the messaging gateway and run the integration test. Send `/status` from the allowed account and check that it replies. `/help` lists the commands supported by your running build; `/stop` cancels active work.

You do not need the author's bot or any hosted bot service. Creating your own bot gives you ownership of its name/token. A historical bot username is not changed merely by changing its display name.

## WhatsApp self-chat

Use the WhatsApp integration's **Self-chat** mode if you want to operate Indra through messages to yourself. Pair the QR code using WhatsApp → Linked devices. The bridge needs Node, included in the release. Use international E.164 format for number-based configuration: an Indian mobile number has country code `+91` followed by its ten-digit national number. Do not publish your phone number or pairing/session files.

Check the configured activation/prefix behavior before using self-chat for ordinary notes. Only invoke the agent with the activation form shown by your setup; otherwise pause/disable the integration or stop the gateway while saving private notes. Do not assume every self-message is ignored. Bot mode and self-chat are different setups. If you unlink the device on your phone, reset the local pairing through the integration and pair again rather than reusing a stale session.

## Gateway troubleshooting

"Gateway not started" means credentials alone are insufficient: enable the channel and start/restart the gateway. Check local logs for an authentication failure or another process polling the same Telegram bot. Check allowlists if outbound tests work but inbound commands do not. Do not run multiple gateway processes for the same account. Keep the PC awake; phone control cannot use a workstation that is powered off.

## Private dashboard sharing

The optional native Phone Setup uses private Tailscale connectivity plus workstation authentication. This is separate from Telegram/WhatsApp bots. Do not open a public unauthenticated port. The user needs to configure their own network and phone; the release includes no pre-paired device.
