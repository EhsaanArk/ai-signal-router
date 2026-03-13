# Customer Support Playbook

## 1. Overview
This playbook provides customer support agents with the knowledge required to troubleshoot issues related to the SageMaster Telegram Signal Copier.

## 2. Common Issues & Troubleshooting

### Issue 1: "I can't connect my Telegram account"
**Symptoms**: User does not receive the login code, or the dashboard shows an error after entering the code.
**Troubleshooting Steps**:
1. Verify the user is entering their phone number with the correct country code (e.g., +1 for US, +44 for UK).
2. Ask the user to check their Telegram app on their phone or desktop. The code is sent as a message from the official "Telegram" service account, *not* via SMS.
3. If the user has Two-Step Verification (2FA) enabled on Telegram, ensure they are entering their cloud password when prompted.

### Issue 2: "My signals aren't copying to SageMaster"
**Symptoms**: A signal is posted in the channel, but no trade appears in the user's broker account.
**Troubleshooting Steps**:
1. **Check Connection**: Verify the user's Telegram session is still active in the dashboard.
2. **Check Channel Config**: Ensure the specific channel is toggled "ON" in the dashboard.
3. **Check Logs**: Navigate to the user's Signal Logs in the admin panel.
    - If the signal is marked `ignored`, the AI determined it wasn't a valid trading signal.
    - If the signal is marked `failed`, check the error message. It may be a malformed webhook URL or a SageMaster API error.
4. **Check Webhook URL**: Ensure the user pasted the correct URL from their SageMaster strategy (`https://api.sagemaster.io/deals_idea/...`).

### Issue 3: "The trade opened with the wrong symbol"
**Symptoms**: The signal said "GOLD" but the trade failed to route because the broker expects "XAUUSD".
**Troubleshooting Steps**:
1. Explain the Symbol Mapping feature to the user.
2. Guide them to the channel configuration page and instruct them to add a mapping: Provider Symbol = `GOLD`, Broker Symbol = `XAUUSD`.

## 3. Escalation Path
If an issue cannot be resolved using the steps above, escalate to the Engineering team via Jira. Include the following information:
- User Email
- Telegram Channel ID/Name
- Timestamp of the missed/failed signal
- The raw text of the signal (if available)
