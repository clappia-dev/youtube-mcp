# YouTube Upload MCP Server (Python)

A Model Context Protocol (MCP) server implemented in Python that allows Claude Desktop to download videos from temporary URLs and upload them to YouTube.

## Features

- OAuth2 authentication with YouTube
- Check YouTube Authentication Status
- Download videos from public URLs
- Upload videos to YouTube

## Prerequisites

- Python 3.7+
- YouTube API credentials (OAuth 2.0 Client ID and Client Secret)
- Claude Desktop
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Installation

1. Clone or download this repository
2. Install dependencies:

```bash
uv venv
source .venv/bin/activate # Update the cmd as per your shell
uv sync
```

3. Register a new project in the [Google Cloud Console](https://console.cloud.google.com/)
4. Enable the YouTube Data API v3
5. Create OAuth 2.0 credentials (Web application type)
   - Set the authorized redirect URI to `http://localhost:8080/oauth2callback`

## Adding to Claude Desktop

Edit your Claude Desktop configuration file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the following configuration:

```json
{
  "mcpServers": {
    "youtube-upload": {
      "command": "uv",
      "args": [
        "--directory",
        "/folder/containing/youtube-upload-mcp",
        "run",
        "youtube-upload-mcp.py"
      ]
    }
  }
}
```

Replace `/folder/containing/youtube-upload-mcp` with the actual path of the cloned repository.

## How It Works

### Authentication Flow

When you authenticate with YouTube:

1. The MCP server generates an OAuth authorization URL
2. It starts a local web server on port 8080 to handle the callback
3. It opens a browser window where you can sign in to Google and authorize the application
4. After authorization, Google redirects to your local server with the auth code
5. The server exchanges the code for access and refresh tokens
6. Tokens are saved locally for future use

### Tool Functions

The server provides the following tools:

1. **check_auth_status**: Checks if you're authenticated with YouTube
2. **authenticate**: Authenticates with YouTube using OAuth2
3. **upload_to_youtube**: Download a video from a public URL and uploads a video to YouTube

## Using the MCP Server with Claude

After configuring Claude Desktop, restart the application. You can then use the following commands with Claude:

1. **Check authentication status**:
   Ask Claude to check if you're authenticated with YouTube.

2. **Authenticate with YouTube**:
   Ask Claude to authenticate with YouTube, and enter your Google credentials when prompted

3. **Upload a video to YouTube**:
   Ask Claude to download any video from internet and upload it to YouTube.

## Example Prompts

```
Can you check if I'm authenticated with YouTube?
```

```
Please authenticate with YouTube.
```

```
Please download and upload this video to YouTube:
- URL: [VIDEO_URL]
- Title: My Test Video
- Description: This is a test video uploaded via MCP server
- Tags: test, mcp, claude
- Privacy: private
```

## Security Notes

- Your OAuth credentials are sensitive information. Do not share them with others.
- Tokens are stored locally in your home directory.
- The server only works on your local machine.

## Troubleshooting

- If authentication fails, make sure your OAuth credentials are correct and properly configured in the Google Cloud Console.
- If video download fails, ensure the URL is publicly accessible.
- If upload fails, check your YouTube account status and quota limits.