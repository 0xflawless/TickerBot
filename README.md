# Crypto Price Tracker Bot

A Discord bot that tracks cryptocurrency prices and displays them in real-time with trend indicators.

## Features
- Real-time price updates from CoinGecko
- Price trend indicators (📈, 📉, ➡️)
- 24-hour price change percentage
- Multiple bot support for tracking different tokens
- Configurable update intervals
- Admin commands for easy setup

## Deployment on Railway.app

### Prerequisites
- GitHub account
- Railway.app account (can sign up with GitHub)
- Discord bot token

### Setup Steps

1. **Create a Discord Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a "New Application"
   - Go to "Bot" section
   - Click "Add Bot"
   - Enable necessary intents:
     - Message Content Intent
     - Server Members Intent
   - Copy the bot token

2. **Deploy to Railway**
   - Fork this repository to your GitHub
   - Go to [Railway.app](https://railway.app)
   - Click "Start a New Project"
   - Select "Deploy from GitHub repo"
   - Choose your forked repository
   - Add environment variable:
     - Key: `DISCORD_TOKEN`
     - Value: Your Discord bot token
   - Railway will automatically deploy your bot

3. **Invite Bot to Server**
   - Go back to Discord Developer Portal
   - Select your application
   - Go to "OAuth2" → "URL Generator"
   - Select scopes:
     - `bot`
     - `applications.commands`
   - Select bot permissions:
     - `Change Nickname` (to update its own nickname)
     - `Send Messages` (to respond to commands)
     - `Use Slash Commands`
   - Copy and open the generated URL
   - Choose your server and authorize the bot

### Multiple Bot Setup on Railway
To track multiple tokens:
1. Create additional bot applications in Discord Developer Portal
2. Fork the repository again with a different name
3. Create a new Railway project for each bot
4. Add the new bot token as environment variable
5. Deploy and invite each bot to your server

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

### Display Format
- Nickname: `BTC: $50000 📈`
- Status: `Watching 24h: BTC +5.2%`

## Troubleshooting

### Railway Specific
- Check "Deployments" tab for build/runtime errors
- View logs in the "Deployments" section
- Ensure environment variables are set correctly
- Check if the service is running (green status)

### General
- If commands don't appear, use `/sync`
- Check logs for errors (enable DEBUG=1 for detailed logs)
- Ensure bot has proper permissions in server
- Verify CoinGecko API status with `/status`

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
