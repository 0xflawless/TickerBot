# Crypto Price Tracker Discord Bot

A Discord bot that tracks cryptocurrency prices from CoinGecko and displays them in real-time through bot nicknames and color-changing roles.

## Features

- Track multiple cryptocurrencies per server
- Auto-updating prices every 5 minutes
- Visual price indicators (green/red roles)
- Persistence across bot restarts
- Rate limit handling
- Multi-server support
- Secure admin-only commands

## Commands

All commands use Discord's slash command system (/).

### Admin Commands (Requires Administrator Permission)
- `/add_token [token_id]` - Start tracking a new cryptocurrency
- `/remove_token [symbol]` - Stop tracking a cryptocurrency
- `/cleanup` - Remove unused price roles
- `/status` - Check bot and API health

### User Commands (Available to Everyone)
- `/list_tokens` - Show all tracked tokens and their prices
- `/price` - Get current prices of tracked tokens

## Setup Instructions

1. **Prerequisites**
   - Python 3.8 or higher
   - A Discord bot token
   - Bot permissions:
     - Send Messages
     - Manage Roles
     - Change Nickname
     - Use Slash Commands
     - Administrator (for admin commands)

2. **Installation**
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/crypto-price-tracker.git
   cd crypto-price-tracker

   # Install requirements
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Copy `.env.example` to `.env`
   - Add your Discord bot token:
     ```
     DISCORD_TOKEN=your_discord_bot_token
     ```

4. **Bot Permissions**
   When inviting the bot to your server, make sure to:
   - Grant Administrator permission for full functionality
   - Or manually set up permissions in Discord:
     1. Create a role for the bot with required permissions
     2. Only give Administrator permission to trusted users who should access admin commands

5. **Running the Bot**
   ```bash
   python bot.py
   ```

## Usage Example

1. Invite the bot to your server with appropriate permissions
2. As a server administrator, use `/add_token bitcoin` to start tracking Bitcoin
3. As a server administrator, use `/add_token ethereum` to add Ethereum tracking
4. Anyone can check prices with `/list_tokens`

## Finding Token IDs

To find the correct token ID for tracking:
1. Visit [CoinGecko](https://www.coingecko.com)
2. Search for your cryptocurrency
3. The token ID is in the URL:
   - Example: `https://www.coingecko.com/en/coins/bitcoin` → token ID is "bitcoin"
   - Example: `https://www.coingecko.com/en/coins/ethereum` → token ID is "ethereum"

## Security Notes

- Admin commands (`/add_token`, `/remove_token`, `/cleanup`, `/status`) are restricted to users with Administrator permission
- Regular users can only use `/list_tokens` and `/price` commands
- The bot will automatically check permissions before executing admin commands
- Make sure to only grant Administrator permission to trusted users

## Troubleshooting

- If admin commands aren't visible, check if you have Administrator permission
- If roles aren't updating, check bot permissions
- If prices aren't updating, use `/status` to check API health (admin only)
- Use `/cleanup` to remove any orphaned roles (admin only)

## Notes

- The bot uses CoinGecko's free API which has rate limits
- Maximum 32 characters for Discord nicknames (prices may be truncated)
- Prices update every 5 minutes to stay within API limits

## Support

If you encounter any issues or need help:
1. Check the logs for error messages
2. Ensure the bot has proper permissions
3. Verify you have Administrator permission for admin commands
4. Verify the token ID exists on CoinGecko
