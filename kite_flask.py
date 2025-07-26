import requests
import webbrowser
import logging
import json

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BASE_API_URL = "http://127.0.0.1:5000"

# --- Core API Communication ---
def call_api(endpoint: str, method: str = "GET", params: dict = None, json_data: dict = None) -> dict:
    """
    Generic function to call any API endpoint of the Flask server.

    This is the central communication hub for the client. It handles constructing
    the full URL, making the HTTP request, and processing the response.

    Args:
        endpoint (str): The specific API path (e.g., "/login", "/api/user/profile").
        method (str): The HTTP method to use ("GET", "POST", "PUT", "DELETE").
        params (dict, optional): A dictionary of query parameters for GET requests.
        json_data (dict, optional): A dictionary to be sent as the JSON body for
                                    POST, PUT, or DELETE requests.

    Returns:
        dict: The JSON response from the server as a dictionary. In case of an
              error, it returns a dictionary with "status": "error" and a "message".
    """
    url = f"{BASE_API_URL}{endpoint}"
    logging.info(f"Calling: {method} {url}")
    try:
        response = requests.request(method, url, params=params, json=json_data, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.ConnectionError as e:
        msg = f"Connection Error: Could not connect to the server at {url}. Is it running?"
        logging.error(msg)
        return {"status": "error", "message": msg}
    except requests.exceptions.HTTPError as e:
        msg = f"HTTP Error: {e.response.status_code} for {url}. Response: {e.response.text}"
        logging.error(msg)
        try:
            return e.response.json()
        except json.JSONDecodeError:
            return {"status": "error", "message": msg}
    except requests.exceptions.RequestException as e:
        msg = f"Request failed: {e}"
        logging.error(msg)
        return {"status": "error", "message": msg}

# --- Authentication Functions ---
def initiate_login_flow() -> dict:
    """
    Starts the login process by getting a login URL from the server and opening it.
    This is the primary method to begin an authenticated session.

    Returns:
        dict: The JSON response from the server.
            - Success: `{'status': 'success', 'login_url': '...'}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    response = call_api("/login")
    if response.get("status") == "success" and response.get("login_url"):
        webbrowser.open(response["login_url"])
        print("Login URL opened in browser. Please authenticate and then run other functions.")
    else:
        print(f"Failed to get login URL: {response.get('message')}")
    return response

def check_authentication_status() -> dict:
    """
    Checks if the server session is currently authenticated.

    Returns:
        dict: A JSON object confirming the authentication status.
            - Success: `{'status': 'success', 'message': 'Session is authenticated.'}`
            - Failure: `{'status': 'error', 'message': 'Not authenticated. Please login first.'}`
    """
    return call_api("/api/auth/check")

def set_access_token(access_token: str) -> dict:
    """
    Manually sets the access token on the server. Useful for session resumption.

    Args:
        access_token (str): A valid Kite Connect access token.

    Returns:
        dict: The JSON response from the server.
            - Success: `{'status': 'success', 'message': 'Access token set successfully.'}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/auth/token/set", method="POST", json_data={"access_token": access_token})

def renew_access_token(refresh_token: str) -> dict:
    """
    Renews the access token on the server using a refresh token.

    Args:
        refresh_token (str): A valid Kite Connect refresh token.

    Returns:
        dict: The JSON response from the server, containing new token data.
            - Success: `{'status': 'success', 'data': {'access_token': '...', 'refresh_token': '...'}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/auth/token/renew", method="POST", json_data={"refresh_token": refresh_token})

# --- User Data Functions ---
def get_profile() -> dict:
    """
    Fetches the complete user profile from the server.

    Returns:
        dict: A JSON object containing the user's profile data.
            - Success: `{'status': 'success', 'data': {'user_id': '...', 'user_name': '...', ...}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/user/profile")

def get_margins(segment: str = None) -> dict:
    """
    Fetches account margins from the server.

    Args:
        segment (str, optional): The segment to fetch margins for ('equity' or 'commodity'). 
                                 Defaults to all segments.

    Returns:
        dict: A JSON object containing the margin data.
            - Success: `{'status': 'success', 'data': {'equity': {...}, 'commodity': {...}}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    params = {"segment": segment} if segment else None
    return call_api("/api/user/margins", params=params)

# --- Portfolio Functions ---
def get_holdings() -> dict:
    """
    Fetches all portfolio holdings from the server.

    Returns:
        dict: A JSON object containing a list of holdings.
            - Success: `{'status': 'success', 'data': [{'tradingsymbol': '...', 'quantity': ..., ...}]}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/portfolio/holdings")

def get_positions() -> dict:
    """
    Fetches all current day positions from the server.

    Returns:
        dict: A JSON object containing position data.
            - Success: `{'status': 'success', 'data': {'net': [...], 'day': [...]}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/portfolio/positions")

def convert_position(**kwargs) -> dict:
    """
    Converts a position's product type (e.g., MIS to CNC).

    Args:
        **kwargs: Keyword arguments corresponding to the Kite Connect `convert_position` method.

    Returns:
        dict: The JSON response from the server.
            - Success: `{'status': 'success', 'data': True}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/portfolio/positions/convert", method="PUT", json_data=kwargs)

# --- Order and Trade Functions ---
def place_order(**kwargs) -> dict:
    """
    Places an order through the server.

    Args:
        **kwargs: Keyword arguments corresponding to the Kite Connect `place_order` method.

    Returns:
        dict: The JSON response from the server, containing the order ID.
            - Success: `{'status': 'success', 'data': {'order_id': '...'}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/orders/place", method="POST", json_data=kwargs)

def modify_order(**kwargs) -> dict:
    """
    Modifies a pending order through the server.

    Args:
        **kwargs: Keyword arguments corresponding to the Kite Connect `modify_order` method.

    Returns:
        dict: The JSON response from the server, containing the order ID.
            - Success: `{'status': 'success', 'data': {'order_id': '...'}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/orders/modify", method="PUT", json_data=kwargs)

def cancel_order(variety: str, order_id: str, parent_order_id: str = None) -> dict:
    """
    Cancels a pending order through the server.

    Args:
        variety (str): The variety of the order (e.g., 'regular').
        order_id (str): The ID of the order to cancel.
        parent_order_id (str, optional): The parent order ID if it's a bracket/cover order.

    Returns:
        dict: The JSON response from the server, containing the order ID.
            - Success: `{'status': 'success', 'data': {'order_id': '...'}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    params = {"parent_order_id": parent_order_id} if parent_order_id else None
    return call_api(f"/api/orders/cancel/{variety}/{order_id}", method="DELETE", params=params)

def exit_order(variety: str, order_id: str, parent_order_id: str = None) -> dict:
    """
    Exits a Cover Order (CO) through the server.

    Args:
        variety (str): The variety of the order, typically 'co'.
        order_id (str): The ID of the order to exit.
        parent_order_id (str, optional): The parent order ID.

    Returns:
        dict: The JSON response from the server, containing the order ID.
            - Success: `{'status': 'success', 'data': {'order_id': '...'}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    params = {"parent_order_id": parent_order_id} if parent_order_id else None
    return call_api(f"/api/orders/exit/{variety}/{order_id}", method="DELETE", params=params)

def get_trades() -> dict:
    """
    Fetches all trades for the day from the server.

    Returns:
        dict: A JSON object containing a list of trades.
            - Success: `{'status': 'success', 'data': [{'trade_id': '...', 'order_id': '...', ...}]}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/trades")

# --- GTT Functions ---
def place_gtt(**kwargs) -> dict:
    """
    Places a Good 'Til Triggered (GTT) order through the server.

    Args:
        **kwargs: Keyword arguments corresponding to the Kite Connect `place_gtt` method.

    Returns:
        dict: The JSON response from the server, containing the trigger ID.
            - Success: `{'status': 'success', 'data': {'trigger_id': ...}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/gtt/place", method="POST", json_data=kwargs)

def delete_gtt(trigger_id: int) -> dict:
    """
    Deletes a GTT order through the server.

    Args:
        trigger_id (int): The ID of the GTT to delete.

    Returns:
        dict: The JSON response from the server, containing the trigger ID.
            - Success: `{'status': 'success', 'data': {'trigger_id': ...}}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api(f"/api/gtt/delete/{trigger_id}", method="DELETE")

# --- Market Data Functions ---
def get_historical_data(**kwargs) -> dict:
    """
    Fetches historical data from the server.

    Args:
        **kwargs: Keyword arguments corresponding to the Kite Connect `historical_data` method.

    Returns:
        dict: A JSON object containing a list of historical candle data.
            - Success: `{'status': 'success', 'data': [{'date': '...', 'open': ..., 'high': ..., ...}]}`
            - Failure: `{'status': 'error', 'message': '...'}`
    """
    return call_api("/api/market/historical", method="POST", json_data=kwargs)


# --- Example Usage ---
if __name__ == "__main__":
    # This block demonstrates how to use the client functions.
    # It follows the standard workflow: Login -> Check Status -> Make API Calls.
    print("--- Kite Connect Client ---")
    print("This script provides functions to interact with your local Kite Flask server.")
    
    # Step 1: Login. This is typically done only once per session.
    # Uncomment the line below to start the browser-based login process.
    initiate_login_flow()
    
    # After logging in via the browser, the server will have an active session.
    # You must press Enter in the console to proceed with the script.
    input("\nPress Enter to continue after you have authenticated in the browser...")

    # Step 2: Check if the authentication was successful.
    print("\n--- Checking Authentication Status ---")
    status = check_authentication_status()
    print(json.dumps(status, indent=2))

    # Step 3: If authenticated, proceed to make other API calls.
    if status.get("status") == "success":
        print("\n--- Fetching Profile ---")
        profile = get_profile()
        print(json.dumps(profile, indent=2))

        # --- Live Order Placement Examples (USE WITH CAUTION) ---
        # NOTE: The following examples will place LIVE orders.
        #       Modify the tradingsymbol, price, and quantity as needed.
        
        # --- Example 1: Place a LIMIT Buy Order ---
        print("\n--- Placing a LIMIT Buy Order (CAUTION: LIVE) ---")
        try:
            limit_order_response = place_order(
                tradingsymbol="INFY",       # The stock symbol
                exchange="NSE",             # The exchange (e.g., NSE, BSE)
                transaction_type="BUY",     # "BUY" or "SELL"
                quantity=1,                 # The number of shares
                product="CNC",              # "CNC" (long-term), "MIS" (intraday), "NRML" (futures/options)
                order_type="LIMIT",         # "LIMIT", "MARKET", "SL", "SL-M"
                price=1500.00,              # The price for a LIMIT order
                variety="regular"           # "regular", "amo", "co", "bo"
            )
            print(json.dumps(limit_order_response, indent=2))
        except Exception as e:
            print(f"Error placing LIMIT order: {e}")

        # --- Example 2: Place a MARKET Sell Order ---
        print("\n--- Placing a MARKET Sell Order (CAUTION: LIVE) ---")
        try:
            market_order_response = place_order(
                tradingsymbol="RELIANCE",
                exchange="NSE",
                transaction_type="SELL",
                quantity=1,
                product="MIS",
                order_type="MARKET",
                variety="regular"
            )
            print(json.dumps(market_order_response, indent=2))
        except Exception as e:
            print(f"Error placing MARKET order: {e}")
            
        # --- Example 3: Place a single-leg GTT Buy Order ---
        # This order will be placed when the price of SBIN drops to 800 or below.
        print("\n--- Placing a GTT Buy Order (CAUTION: LIVE) ---")
        try:
            # For a GTT, you need the last traded price to set a valid trigger.
            # In a real application, you would fetch this dynamically.
            # We will use a placeholder value here.
            last_price = 850.00 
            
            gtt_response = place_gtt(
                trigger_type="single",      # "single" or "two-leg" (for OCO)
                tradingsymbol="SBIN",
                exchange="NSE",
                trigger_values=[800.00],    # The price at which the order should be triggered
                last_price=last_price,      # The last traded price of the instrument
                orders=[{                  # A list of orders to be placed when triggered
                    "transaction_type": "BUY",
                    "quantity": 5,
                    "product": "CNC",
                    "order_type": "LIMIT",
                    "price": 800.00         # The limit price of the order to be placed
                }]
            )
            print(json.dumps(gtt_response, indent=2))
        except Exception as e:
            print(f"Error placing GTT order: {e}")

    else:
        print("\nAuthentication check failed. Please run initiate_login_flow() and try again.")
