from fastapi import FastAPI, Query
import uvicorn
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from starlette.responses import JSONResponse
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Host
import logging
from kiteconnect import KiteConnect
from typing import Optional
import argparse
import webbrowser
import asyncio
import threading
import sys

# Load environment variables
load_dotenv()

# Global variables to store authentication details
stored_request_token = None
stored_auth_details = None
stored_redirect_params = None
server_instance = None

# Parse command line arguments
parser = argparse.ArgumentParser(description='Zerodha MCP Server')
parser.add_argument('--api-key', type=str, help='Zerodha API Key')
parser.add_argument('--api-secret', type=str, help='Zerodha API Secret')
parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
parser.add_argument('--mode', type=str, default='development', help='Server mode')
args = parser.parse_args()

session_service_stateful_zerodha_agent = InMemorySessionService()

# Create FastAPI app
app = FastAPI(
    title="Zerodha MCP Server",
    description="A server for Zerodha trading operations using MCP",
    version="1.0.0"
)

API_KEY = os.getenv('ZERODHA_API_KEY') or args.api_key
API_SECRET = os.getenv('ZERODHA_API_SECRET') or args.api_secret
PORT = int(os.getenv('PORT', str(args.port)))
MODE = os.getenv('SERVER_MODE', args.mode)

if not API_KEY or not API_SECRET:
    raise ValueError("ZERODHA_API_KEY and ZERODHA_API_SECRET must be set either in .env file or via command line arguments")

# Initialize KiteConnect with provided credentials
kite = KiteConnect(api_key=API_KEY)

def get_login_url() -> str:
    """Get the login URL for the user. Use this to get the login URL for the user and then redirect the user to the login URL to get the request token.

    Args:
        None

    Returns:
        str: The login URL for the user
    """
    logging.info("Entering get_login_url")
    url = kite.login_url()
    logging.info("Exiting get_login_url")
    return url

def get_stored_auth_details():
    """Get stored authentication details"""
    return stored_auth_details

def get_stored_request_token():
    """Get stored request token"""
    return stored_request_token

def get_stored_redirect_params():
    """Get stored redirect parameters"""
    return stored_redirect_params

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Zerodha MCP Server is running!", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "zerodha-mcp"}

@app.get("/api/info")
async def api_info():
    """API information endpoint"""
    return {
        "service": "Zerodha MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "root": "/",
            "health": "/health",
            "api_info": "/api/info",
            "trade_redirect": "/trade/redirect"
        }
    }

@app.get("/trade/redirect")
async def trade_redirect(
    request_token: str = Query(..., description="Request token from Zerodha login"),
    action: Optional[str] = Query(None, description="Action parameter from Zerodha"),
    type: Optional[str] = Query(None, description="Type parameter from Zerodha"),
    status: Optional[str] = Query(None, description="Status parameter from Zerodha")
):
    """Handle the redirect from Zerodha login and process the request token"""
    global stored_request_token, stored_auth_details, stored_redirect_params, server_instance
    
    try:
        # Log all received parameters
        print("Received parameters:")
        print(f"  - request_token: {request_token}")
        print(f"  - action: {action}")
        print(f"  - type: {type}")
        print(f"  - status: {status}")
        
        # Store redirect parameters
        stored_redirect_params = {
            "action": action,
            "type": type,
            "status": status,
            "request_token": request_token
        }
        
        # Store request token separately
        stored_request_token = request_token
        
        # Check if the status indicates success
        if status and status.lower() != "success":
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": f"Login was not successful. Status: {status}"
                }
            )
        
        # Generate session using the request token
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        print(f"Data received from Kite: {data}")  # Debugging line to check the data structure
        access_token = data["access_token"]
        
        # Set the access token for future API calls
        kite.set_access_token(access_token)
        
        # Store authentication details
        stored_auth_details = {
            "access_token": access_token,
            "user_id": data.get("user_id"),
            "user_name": data.get("user_name"),
            "user_shortname": data.get("user_shortname"),
            "email": data.get("email"),
            "public_token": data.get("public_token"),
            "refresh_token": data.get("refresh_token")
        }
        
        logging.info(f"Successfully authenticated. Access token: {access_token[:10]}...")
        
        print("\n" + "="*50)
        print("🎉 AUTHENTICATION SUCCESSFUL! 🎉")
        print("="*50)
        print(f"User: {data.get('user_name')} ({data.get('user_id')})")
        print(f"Email: {data.get('email')}")
        print(f"Request Token: {request_token}")
        print(f"Access Token: {access_token[:20]}...")
        print("="*50)
        print("THANK YOU! 🙏")
        print("Server will close automatically in 3 seconds...")
        print("="*50)
        
        response_data = {
            "status": "success",
            "message": "Authentication successful! Thank you! Server will close automatically.",
            "redirect_params": stored_redirect_params,
            "kite_data": stored_auth_details
        }

        initial_state = {
            "user_name": stored_auth_details.get('user_name', 'Unknown'),
            "user_id": stored_auth_details.get('user_id', 'Unknown'),
            "access_token": stored_auth_details.get('access_token', 'Not available'),
            "email": stored_auth_details.get('email', 'Not available'),
            "public_token": stored_auth_details.get('public_token', 'Not available'),
            "request_token": stored_request_token,
            "redirect_params": stored_redirect_params
        }

        print("Initial state for session service:", initial_state)
        
        # Schedule server shutdown after sending response
        def shutdown_server():
            import time
            time.sleep(3)  # Wait 3 seconds before shutting down
            print("\nShutting down server... Goodbye! 👋")
            if server_instance:
                server_instance.should_exit = True
            else:
                os._exit(0)
        
        # Start shutdown in background thread
        threading.Thread(target=shutdown_server, daemon=True).start()
        
        return response_data
        
    except Exception as e:
        logging.error(f"Authentication failed: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Authentication failed: {str(e)}",
                "redirect_params": {
                    "action": action,
                    "type": type,
                    "status": status,
                    "request_token": request_token
                }
            }
        )

if __name__ == "__main__":
    # Check if we have valid API credentials before starting
    if API_KEY and API_SECRET:
        # Get login URL and open in browser
        login_url = get_login_url()
        print(f"Opening Zerodha login URL in browser: {login_url}")
        webbrowser.open(login_url)
        print("After logging in, you will be redirected to: http://127.0.0.1:5000/trade/redirect")
        print("The server will automatically close after successful authentication.")
        print("Waiting for authentication...")
    else:
        print("Warning: API_KEY or API_SECRET not set. Login URL will not be opened.")
    
    # Run the server
    try:
        config = uvicorn.Config(
            "main:app",
            host="127.0.0.1",
            port=PORT,
            reload=False,  # Disable reload for clean shutdown
            log_level="info"
        )
        server_instance = uvicorn.Server(config)
        server_instance.run()
    except KeyboardInterrupt:
        print("\nServer interrupted by user")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        # Print stored details if available
        if stored_auth_details:
            print("\n" + "="*50)
            print("STORED AUTHENTICATION DETAILS:")
            print("="*50)
            print(f"Request Token: {stored_request_token}")
            print(f"User ID: {stored_auth_details.get('user_id')}")
            print(f"User Name: {stored_auth_details.get('user_name')}")
            print(f"Email: {stored_auth_details.get('email')}")
            print(f"Access Token: {stored_auth_details.get('access_token')[:20]}..." if stored_auth_details.get('access_token') else "Not available")
            print("="*50)

            initial_state = {
                "user_name": stored_auth_details.get('user_name', 'Unknown'),
                "user_id": stored_auth_details.get('user_id', 'Unknown'),
                "access_token": stored_auth_details.get('access_token', 'Not available'),
                "email": stored_auth_details.get('email', 'Not available'),
                "public_token": stored_auth_details.get('public_token', 'Not available'),
                "request_token": stored_request_token,
                "redirect_params": stored_redirect_params
            }

            print("Initial state for session service:", initial_state)
        
        print("\nServer has shut down. Goodbye! 👋")


