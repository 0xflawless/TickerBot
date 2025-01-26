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
We welcome contributions that improve the bot's functionality and reliability. However, as this is a commercial product:

1. Please contact us before starting work on significant changes
2. All contributions must be reviewed and approved by our team
3. Contributors agree to transfer ownership of their code to our organization
4. We may decline contributions that don't align with our product vision

To contribute:
1. Open an issue describing your proposed change
2. Wait for approval from our team
3. Fork the repository and create your changes
4. Submit a pull request referencing the issue

## License
© 2024 [@L3VEL7](https://github.com/L3VEL7/). All rights reserved.

This software is provided under a proprietary license. Usage is subject to the following restrictions:

1. **Usage Restrictions**
   - Personal use is permitted (single instance for personal Discord servers)
   - Project/Business use requires explicit written permission
   - Commercial use requires explicit written permission
   - No redistribution without authorization
   - No creation of derivative works without approval

2. **Permissions**
   - Private installation and use
   - Code viewing for security auditing
   - Bug reporting and fixes

3. **Personal Use**
   - You may run one instance for your personal Discord server
   - You may not use this bot for:
     - Commercial projects or businesses
     - Public bot services
     - Multiple instance deployments without permission

4. **Requirements**
   - Maintain all copyright notices
   - Include original license text

For licensing inquiries or permissions beyond these restrictions, please contact: timm@servicedao.com
