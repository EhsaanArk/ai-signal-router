# User Guide: How to Setup the Telegram Signal Copier

Welcome to the SageMaster Telegram Signal Copier! This guide will show you how to automatically route trading signals from your favorite Telegram channels directly to your SageMaster strategies.

## Step 1: Connect Your Telegram Account

To read signals from your channels, the system needs to connect to your Telegram account.

1. Log in to the **Signal Copier Dashboard**.
2. Navigate to the **Telegram Accounts** tab.
3. Enter your phone number (including the country code, e.g., +1 for US).
4. Click **Send Code**.
5. Open the Telegram app on your phone or computer. You will receive a message from the official "Telegram" account containing a login code.
6. Enter this code into the dashboard.
7. If you have Two-Step Verification enabled, enter your password when prompted.

*Note: Your connection is secure. We use enterprise-grade encryption and never store your messages.*

## Step 2: Create a SageMaster Strategy

Before you can copy signals, you need a strategy to receive them.

1. Go to **Strategies** -> **Create a Strategy**.
2. Under **Trigger Condition**, select **Custom TradingView Alert V2** (recommended for dynamic Stop Loss and Take Profit).
3. Complete the strategy wizard (select your account, pairs, and money management settings).
4. Once created, go to the **Alerts** tab of your new strategy.
5. Copy the **Webhook URL** (it looks like `https://api.sagemaster.io/deals_idea/...`).

## Step 3: Create a Routing Rule

Now, link your Telegram channel to your SageMaster strategy.

1. Go to the **Routing Rules** tab in the Signal Copier dashboard.
2. Click **Create New Rule**.
3. **Select Source**: Choose the Telegram channel you want to copy signals from.
4. **Set Destination**: Paste the **Webhook URL** you copied in Step 2.
5. **Payload Version**: Select V2 (if you selected Custom TradingView Alert V2 in your strategy).
6. Click **Save Rule**.

*Pro Tip: You can create multiple Routing Rules for the same Telegram channel if you want to send the same signal to multiple SageMaster bots! (Subject to your subscription tier limits).*

## Step 4: (Optional) Symbol Mapping & Risk Overrides

Sometimes, signal providers use different names for assets than your broker (e.g., they say "GOLD" but your broker uses "XAUUSD").

1. Click the **Edit** icon next to your new Routing Rule.
2. Under **Symbol Mapping**, enter the provider's symbol (e.g., `GOLD`) and your broker's symbol (e.g., `XAUUSD`).
3. (Pro/Elite Tiers) Under **Risk Overrides**, you can force a specific lot size for this destination, ignoring the signal's suggested risk.
4. Click **Save**.

You are all set! The next time a signal is posted in that channel, the system will automatically parse it and route the order to your SageMaster bot.
