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
- `/set_interval [seconds]` - Set the price update interval (minimum 60 seconds)

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
   Option 1: Using pip
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/crypto-price-tracker.git
   cd crypto-price-tracker

   # Install requirements
   pip install -r requirements.txt
   ```
   
   Option 2: Using Poetry (Recommended)
   ```bash
   # Install Poetry if you haven't already
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Clone the repository
   git clone https://github.com/yourusername/crypto-price-tracker.git
   cd crypto-price-tracker
   
   # Install dependencies using Poetry
   poetry install
   
   # Run the bot
   poetry run bot
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

## Deployment Options

### Local Hosting
Run the bot locally using the instructions in the Setup section above.

### Railway Deployment (Recommended for 24/7 Uptime)

Railway.app provides an easy way to deploy and host the bot with automatic updates and 24/7 uptime.

1. **Prerequisites**
   - A GitHub account
   - A Railway.app account (sign up at [Railway.app](https://railway.app) using GitHub)

2. **Deployment Steps**
   ```bash
   # 1. Fork this repository to your GitHub account
   # 2. Go to Railway.app and sign in with GitHub
   # 3. Click "New Project"
   # 4. Select "Deploy from GitHub repo"
   # 5. Choose your forked repository
   ```

3. **Environment Setup**
   - In your Railway project, go to the "Variables" tab
   - Add these environment variables:
   ```env
   DISCORD_TOKEN=your_discord_bot_token
   DEBUG=0  # Optional: Set to 1 for debug logging
   ```

4. **Automatic Deployment**
   - Railway will automatically:
     - Detect the Python environment
     - Install dependencies from requirements.txt
     - Start the bot using the Procfile
     - Handle all future updates when you push to GitHub

5. **Monitoring**
   - Use Railway's dashboard to:
     - Monitor bot status
     - View logs
     - Check resource usage
     - Set up alerts

### Railway Features
- 🔄 Automatic deployments
- 📊 Resource monitoring
- 🔍 Live logs
- ⚡ High availability
- 🛡️ SSL/HTTPS enabled
- 🔒 Secure environment variables

### Railway Troubleshooting
- If deployment fails, check:
  1. Procfile exists and contains: `worker: python bot.py`
  2. requirements.txt includes all dependencies
  3. Environment variables are set correctly
- View deployment logs in Railway dashboard for specific errors
