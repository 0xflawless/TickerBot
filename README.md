# Crypto Price Tracker Bot

A Discord bot that tracks cryptocurrency prices and displays them in real-time with trend indicators.

## Features
- Real-time price updates from CoinGecko
- Price trend indicators (↗️, ↘️, ➡️)
- 24-hour price change percentage
- Multiple bot support for tracking different tokens
- Configurable update intervals
- Admin commands for easy setup

## Setup

### Prerequisites
- Python 3.8 or higher
- pip or Poetry for dependency management
- Discord bot token(s)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/crypto-price-tracker
cd crypto-price-tracker
```

2. Install dependencies:
```bash
# Using pip
pip install -r requirements.txt

# Or using Poetry
poetry install
```

3. Create environment files for each bot instance:

For first bot (bot1.env):
```env
DISCORD_TOKEN=your_first_bot_token
DEBUG=0
```

For second bot (bot2.env):
```env
DISCORD_TOKEN=your_second_bot_token
DEBUG=0
```

### Bot Setup

1. Create bot applications in [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application"
   - Go to "Bot" section
   - Enable necessary Intents (Message Content, Server Members)
   - Copy the token for each bot

2. Invite bots to your server using OAuth2 URL:
   - Required permissions: Send Messages, Change Nickname
   - Bot permission: Administrator (for admin commands)

## Running the Bot

### Running Single Instance
```bash
# Linux/Mac
python bot.py

# Windows
python bot.py
```

### Running Multiple Instances
```bash
# Linux/Mac
env $(cat bot1.env) python bot.py
env $(cat bot2.env) python bot.py

# Windows (using cmd files)
cmd1.bat
cmd2.bat
```

## Usage

### Initial Setup
1. Use `/sync` to sync commands (admin only)
2. Use `/setup` to configure channels
3. Follow the setup guide in your config channel

### Available Commands
- `/add_token [token_id]` - Add token to track
- `/remove_token [symbol]` - Remove tracked token
- `/list_tokens` - Show tracked tokens
- `/set_interval [seconds]` - Set update frequency
- `/get_interval` - Show current update interval
- `/status` - Check bot status
- `/force_update` - Force immediate update
- `/sync` - Sync slash commands

### Example
1. Add Bitcoin tracking:
```
/add_token bitcoin
```

2. Set 5-minute update interval:
```
/set_interval 300
```

## Display Format
- Nickname: `BTC: $50000 ↗`
- Status: `Watching 24h: BTC +5.2%`

## Multiple Bot Setup
To track multiple tokens with separate bots:
1. Create multiple bot applications in Discord Developer Portal
2. Create separate .env files for each bot
3. Run multiple instances of the bot with different tokens
4. Each bot can track different tokens independently

## Troubleshooting
- If commands don't appear, use `/sync`
- Check logs for errors (enable DEBUG=1 for detailed logs)
- Ensure bot has proper permissions in server
- Verify CoinGecko API status with `/status`

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
