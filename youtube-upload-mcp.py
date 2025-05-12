import os
import json
import tempfile
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta
import requests
import threading
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass
import asyncio

# Allow OAuth to work with HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from mcp.server.fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth_server import OAuthCallbackHandler, start_oauth_server

mcp = FastMCP("youtube-upload", timeout=3600)

PORT = 8080
SCOPES = [
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]
TOKEN_PATH = os.path.join(Path.home(), '.youtube-upload-mcp-token.json')
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'youtube-upload-mcp')

# Read CLIENT_ID and CLIENT_SECRET from environment variables
CLIENT_ID = os.environ.get('YOUTUBE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('YOUTUBE_CLIENT_SECRET')

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)

PrivacyStatus = Literal["private", "public", "unlisted"]

@dataclass
class AuthResponse:
    authenticated: bool
    message: str

@dataclass
class UploadResponse:
    success: bool
    message: str
    video_id: Optional[str] = None
    video_url: Optional[str] = None


def get_youtube_service(credentials):
    """Create a YouTube API service object"""
    return build('youtube', 'v3', credentials=credentials)


@mcp.tool()
async def check_auth_status() -> AuthResponse:
    """Check if the user is authenticated with YouTube"""
    try:
        if not os.path.exists(TOKEN_PATH):
            return AuthResponse(
                authenticated=False,
                message="User is not authenticated with YouTube."
            )
        
        with open(TOKEN_PATH, 'r') as token_file:
            token_data = json.load(token_file)
        
        credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
        
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                with open(TOKEN_PATH, 'w') as token_file:
                    token_file.write(credentials.to_json())
                return AuthResponse(
                    authenticated=True,
                    message="User is authenticated with YouTube and token was refreshed."
                )
            except Exception as e:
                os.remove(TOKEN_PATH)
                return AuthResponse(
                    authenticated=False,
                    message=f"Authentication token expired and could not be refreshed: {str(e)}"
                )
        
        return AuthResponse(
            authenticated=True,
            message="User is authenticated with YouTube."
        )
        
    except Exception as e:
        return AuthResponse(
            authenticated=False,
            message=f"Error checking authentication status: {str(e)}"
        )


@mcp.tool()
async def authenticate() -> Dict[str, Any]:
    """Authenticate with YouTube using OAuth2"""
    try:
        if not CLIENT_ID or not CLIENT_SECRET:
            return {
                "success": False,
                "message": "Missing YouTube API credentials. Please set the YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET environment variables in Claude Desktop config."
            }
            
        OAuthCallbackHandler.authorization_code = None
        OAuthCallbackHandler.state = None
        
        flow = InstalledAppFlow.from_client_config(
            {
                "web": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [f"http://localhost:{PORT}/oauth2callback"]
                }
            },
            SCOPES,
            redirect_uri=f"http://localhost:{PORT}/oauth2callback"
        )
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        print(f"Please authorize this app by visiting this URL: {auth_url}")
        webbrowser.open(auth_url)
        server_thread = threading.Thread(target=start_oauth_server, args=(PORT,))
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for the callback with a timeout
        timeout = 300  # 5 minutes
        start_time = datetime.now()
        
        while server_thread.is_alive():
            if (datetime.now() - start_time).total_seconds() > timeout:
                return {
                    "success": False,
                    "message": "Authentication timed out. Please try again."
                }
            
            if OAuthCallbackHandler.authorization_code and OAuthCallbackHandler.state:
                break
                
            await asyncio.sleep(1)
        
        if not OAuthCallbackHandler.authorization_code:
            return {
                "success": False,
                "message": "Failed to receive authorization code"
            }
        
        callback_url = f"http://localhost:{PORT}/oauth2callback?state={OAuthCallbackHandler.state}&code={OAuthCallbackHandler.authorization_code}"
        flow.fetch_token(authorization_response=callback_url)
        
        credentials = flow.credentials
        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(credentials.to_json())
        
        return {
            "success": True,
            "message": "Authentication successful! You can now upload videos to YouTube."
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Authentication failed: {str(e)}"
        }


async def download_video(url: str) -> Dict[str, Any]:
    """Download a video from a public URL
    
    Args:
        url: URL of the video to download
    """
    try:
        print(f"Downloading video from {url}")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        video_path = os.path.join(TEMP_DIR, f"video_{timestamp}.mp4")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(video_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return {
            "success": True,
            "message": "Video downloaded successfully",
            "path": video_path
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to download video: {str(e)}"
        }

async def upload_to_youtube(
    video_path: str, 
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: PrivacyStatus = "private"
) -> Dict[str, Any]:
    """Upload a video to YouTube
    
    Args:
        video_path: Path to the downloaded video file
        title: Title of the video
        description: Description of the video
        tags: Optional list of video tags
        privacy_status: Privacy status (private/public/unlisted)
    """
    try:
        # Check if the user is authenticated
        if not os.path.exists(TOKEN_PATH):
            return {
                "success": False,
                "message": "User is not authenticated with YouTube. Please authenticate first."
            }
        
        if not os.path.exists(video_path):
            return {
                "success": False,
                "message": f"Video file not found at {video_path}"
            }
        
        with open(TOKEN_PATH, 'r') as token_file:
            token_data = json.load(token_file)
        
        credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
        
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(credentials.to_json())
        
        # Create YouTube API client
        youtube = get_youtube_service(credentials)
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        media = MediaFileUpload(
            video_path,
            mimetype="video/*",
            resumable=True
        )
        print("Uploading video to YouTube...")
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        response = request.execute()
        # os.remove(video_path) # Optional: delete the video file after upload

        return {
            "success": True,
            "message": "Video uploaded successfully!",
            "video_id": response["id"],
            "video_url": f"https://www.youtube.com/watch?v={response['id']}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to upload video: {str(e)}"
        }


@mcp.tool()
async def upload_from_url(
    url: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: PrivacyStatus = "private"
) -> UploadResponse:
    """Download a video from URL and upload it to YouTube
    
    Args:
        url: URL of the video to download
        title: Title of the video
        description: Description of the video
        tags: Optional list of video tags
        privacy_status: Privacy status (private/public/unlisted)
    """
    try:
        if not os.path.exists(TOKEN_PATH):
            return UploadResponse(
                success=False,
                message="User is not authenticated with YouTube. Please authenticate first."
            )
        
        download_result = await download_video(url)
        if not download_result["success"]:
            return UploadResponse(
                success=False,
                message=download_result["message"]
            )
        
        upload_result = await upload_to_youtube(
            download_result["path"],
            title,
            description,
            tags,
            privacy_status
        )
        
        return UploadResponse(
            success=upload_result["success"],
            message=upload_result["message"],
            video_id=upload_result.get("video_id"),
            video_url=upload_result.get("video_url")
        )
        
    except Exception as e:
        return UploadResponse(
            success=False,
            message=f"Failed to process video: {str(e)}"
        )

if __name__ == "__main__":
    mcp.run(transport='stdio')