# Phone control

Indra runs on your PC. Telegram and WhatsApp carry messages between your phone and that PC. The PC must stay awake, online and running its Indra messaging gateway. These channel connections do not require a public inbound port or Tailscale.

## Create your own Indra Telegram bot

1. Open the verified **@BotFather** account in Telegram and send `/newbot`.
2. Choose the display name **Indra · Origo Labs**, or your own Indra name.
3. Choose an available username ending in `bot`, such as a personal `indra_…_bot` name. Telegram adds `@` when displaying usernames.
4. Copy the bot token into **Indra → Integrations → Telegram → Connect your bot**. Keep the token private; do not paste it into a public chat or screenshot.
5. Enable Telegram, save, and restart the **messaging gateway** from Integrations. Wait for the Telegram card to say **Connected**; an app backend being ready alone does not mean the Telegram adapter is connected.
6. Open your bot’s `https://t.me/your_bot_username` link and press **Start**. Send `/status` as a small connection test.
7. Restrict access to your numeric Telegram user ID, or use Indra’s Pairing flow to approve your own account. Your account’s `@username` is different from its numeric user ID. Do not use `*` to work around an authorization error.

You can change the bot’s display name, description and image through BotFather’s `/mybots` settings. Telegram does not allow changing an existing bot’s username: if an earlier provisioning service created an unwanted username, create a new bot with your chosen Indra username and replace its token in Indra. Do not delete the old bot until your new connection works.

Indra uses your own BotFather bot by default. Optional external quick provisioning appears only when an operator has explicitly configured its service URL; it is not required for manual setup.

## WhatsApp and Indian numbers

1. Open **Indra → Integrations → WhatsApp**.
2. Choose **India (+91)** and enter your 10-digit mobile number, or its complete `+91` form. Spaces, hyphens and Devanagari decimal digits are accepted. The allowlist is stored in canonical international form; duplicate spellings become one identity.
3. For other countries, choose **International** and include the country code.
4. Choose the connection mode, start QR pairing, then open **WhatsApp → Settings → Linked devices → Link a device** on your phone and scan the code shown in Indra.
5. Wait for the linked account, save the setup, and restart the messaging gateway when requested.
6. In bot mode, only approved sender numbers may control Indra. Self-chat mode uses the linked account’s self-chat. An empty allowlist never means unrestricted control.

QR scanning and account confirmation happen on your phone. A bridge process starting is not proof that your phone has finished linking.

## What is available from a phone

Use chat, supported attachments, existing project/Knowledge tools and delegated tasks that your profile allows. `/status` checks the current session and `/stop` cancels work. File access, sandbox limits and human approvals still apply. Phone chat does not grant unrestricted desktop control, turn on the PC, or make a locally hosted model run on the phone itself.

API-backed child agents can work concurrently within the limit in **Auto Routing → Parallel agent work**, provider quotas and cost limits. The built-in local GPU router currently serializes inference to protect model switching and memory. Continuous GPU batching is not enabled by changing the agent limit.

## Troubleshooting

- **Token valid, but no reply:** check the Telegram card’s connection state and gateway diagnostics. Telegram support requires the pinned `python-telegram-bot[webhooks]==22.8` dependency in the product runtime; repeatedly restarting cannot repair a missing adapter package.
- **Gateway running, channel unavailable:** inspect the channel-specific error. Missing adapters now report a failure instead of an endless restart suggestion.
- **Unauthorized:** use numeric Telegram IDs or a reviewed pairing request. A Telegram username is not a phone number or numeric ID.
- **Polling conflict:** do not run two gateways with the same bot token.
- **WhatsApp not receiving:** confirm the phone is actually linked and the allowed number includes its country code.
- **Model loading:** local models load on the PC and may take time on the first request; a connected channel does not verify model inference.

References: [Telegram’s BotFather and bot settings](https://core.telegram.org/bots/features#botfather), [Telegram Bot API](https://core.telegram.org/bots/api), [llama.cpp server concurrency](https://github.com/ggml-org/llama.cpp/tree/master/tools/server).
