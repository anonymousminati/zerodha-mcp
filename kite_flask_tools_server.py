from kiteconnect import KiteConnect
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import datetime

# Load environment variables from a .env file
load_dotenv()

# --- Configuration & Initialization ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = os.getenv('ZERODHA_API_KEY')
API_SECRET = os.getenv("ZERODHA_API_SECRET")

# This global variable will hold the single, authenticated KiteConnect instance.
# In a production multi-user app, this would be replaced with a robust session management system.
global_kite = None

app = Flask(__name__)

# --- Authentication Helpers & Endpoints ---

def check_authentication():
    """
    Internal helper to verify if the user is authenticated.
    
    This function checks for the existence of a global KiteConnect instance and
    whether an access token has been set for it. It's used as a preliminary
    check in most API endpoints.

    Returns:
        tuple: A tuple containing (is_authenticated, error_response, http_status_code).
               If authenticated, returns (True, None, None).
               If not, returns (False, json_error_response, 401).
    """
    if not global_kite or not global_kite.access_token:
        error_msg = "Not authenticated. Please login first."
        logging.warning(error_msg)
        return False, jsonify({"status": "error", "message": error_msg}), 401
    return True, None, None

@app.route("/api/auth/check", methods=["GET"])
def check_auth_endpoint() -> dict:
    """
    Endpoint to check if the current session is authenticated.

    This is a public-facing endpoint for a client to quickly verify if its
    session on the server is still considered valid.

    Returns:
        dict: A JSON object with the authentication status.
              - Success: {"status": "success", "message": "Session is authenticated."}
              - Failure: {"status": "error", "message": "Not authenticated. Please login first."}
    """
    authenticated, error_response, _ = check_authentication()
    if not authenticated:
        return error_response
    return jsonify({"status": "success", "message": "Session is authenticated."})

@app.route("/login", methods=["GET"])
def login() -> dict:
    """
    Generates the Zerodha login URL for the user to initiate authentication.

    This is the first step in the authentication flow. The client calls this
    endpoint to get the unique URL where the user must be redirected to log in
    with their Zerodha credentials.

    Returns:
        dict: A JSON object containing the login URL or an error.
              - Success: {"status": "success", "login_url": "https://kite.trade/connect/login?v=3&api_key=..."}
              - Failure: {"status": "error", "message": "API Key not configured."}
    """
    global global_kite
    if not API_KEY:
        logging.error("ZERODHA_API_KEY not found in .env file.")
        return jsonify({"status": "error", "message": "API Key not configured."}), 500

    try:
        global_kite = KiteConnect(api_key=API_KEY)
        login_url = global_kite.login_url()
        logging.info("Login URL generated.")
        return jsonify({"status": "success", "login_url": login_url})
    except Exception as e:
        logging.error(f"Error generating login URL: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/trade/redirect", methods=["GET"])
def trade_redirect() -> dict:
    """
    Callback endpoint for Zerodha to redirect to after successful login.

    After the user authenticates on the Zerodha page, Zerodha redirects them
    to this endpoint, providing a `request_token` in the query parameters.
    This token is then exchanged for a full-fledged `access_token`.

    Returns:
        dict: A JSON object indicating the result of the session generation.
              - Success: {"status": "success", "message": "Authentication successful!", "data": {...session_data...}}
              - Failure: {"status": "error", "message": "Authentication failed: ..."}
    """
    global global_kite
    request_token = request.args.get("request_token")

    if not request_token:
        return jsonify({"status": "error", "message": "No request_token found in callback."}), 400
    if not global_kite:
        return jsonify({"status": "error", "message": "KiteConnect instance not initialized."}), 500

    try:
        session_data = global_kite.generate_session(request_token, api_secret=API_SECRET)
        global_kite.set_access_token(session_data["access_token"])
        logging.info("Authentication successful. Session generated.")
        return jsonify({
            "status": "success",
            "message": "Authentication successful!",
            "data": session_data
        })
    except Exception as e:
        logging.error(f"Session generation failed: {e}")
        return jsonify({"status": "error", "message": f"Authentication failed: {e}"}), 500

@app.route("/api/auth/token/set", methods=["POST"])
def set_access_token() -> dict:
    """
    Manually sets the access token for the KiteConnect instance.

    This is useful for re-initializing a session without the full login flow,
    for instance, if the client has a previously stored valid access token.

    Request Body (JSON):
        {"access_token": "your_token"}

    Returns:
        dict: A JSON object confirming the action.
    """
    global global_kite
    params = request.get_json()
    if not params or "access_token" not in params:
        return jsonify({"status": "error", "message": "Missing 'access_token' in request body."}), 400

    try:
        # Initialize kite if it doesn't exist
        if not global_kite:
            global_kite = KiteConnect(api_key=API_KEY)
            
        global_kite.set_access_token(params["access_token"])
        logging.info("Access token has been set manually.")
        return jsonify({"status": "success", "message": "Access token set successfully."})
    except Exception as e:
        logging.error(f"Failed to set access token: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/auth/token/renew", methods=["POST"])
def renew_access_token() -> dict:
    """
    Renews an access token using a refresh token.

    This allows for extending a session's life without requiring the user to log in again.

    Request Body (JSON):
        {"refresh_token": "your_refresh_token"}

    Returns:
        dict: A JSON object with the new session data.
    """
    global global_kite
    params = request.get_json()
    if not params or "refresh_token" not in params:
        return jsonify({"status": "error", "message": "Missing 'refresh_token' in request body."}), 400

    if not global_kite:
        return jsonify({"status": "error", "message": "KiteConnect instance not initialized."}), 500

    try:
        session_data = global_kite.renew_access_token(params["refresh_token"], api_secret=API_SECRET)
        global_kite.set_access_token(session_data["access_token"])
        logging.info("Access token renewed successfully.")
        return jsonify({"status": "success", "data": session_data})
    except Exception as e:
        logging.error(f"Failed to renew access token: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Core Trading & Data Endpoints ---

@app.route("/api/user/profile", methods=["GET"])
def get_profile() -> dict:
    """
    Fetches the user's complete profile information.

    Returns:
        dict: A JSON object containing the profile data or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        return jsonify({"status": "success", "data": global_kite.profile()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/user/margins", methods=["GET"])
def get_margins() -> dict:
    """
    Fetches account balance and cash margin details.

    Query Parameters:
        segment (str, optional): The trading segment ('equity' or 'commodity'). 
                                 If not provided, margins for all segments are returned.

    Returns:
        dict: A JSON object containing margin data or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        segment = request.args.get("segment")
        return jsonify({"status": "success", "data": global_kite.margins(segment=segment)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portfolio/holdings", methods=["GET"])
def get_holdings() -> dict:
    """
    Fetches the list of all instruments held by the user in their portfolio.

    Returns:
        dict: A JSON object containing a list of holdings or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        return jsonify({"status": "success", "data": global_kite.holdings()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portfolio/positions", methods=["GET"])
def get_positions() -> dict:
    """
    Fetches the list of all open positions for the current day.

    Returns:
        dict: A JSON object containing net and day-wise positions or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        return jsonify({"status": "success", "data": global_kite.positions()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portfolio/positions/convert", methods=["PUT"])
def convert_position() -> dict:
    """
    Converts an open position from one product type to another (e.g., MIS to CNC).

    Request Body (JSON):
        A dictionary with parameters like 'exchange', 'tradingsymbol', 'transaction_type',
        'position_type', 'quantity', 'old_product', 'new_product'.

    Returns:
        dict: A JSON object confirming the action's success or failure.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    params = request.get_json()
    if not params:
        return jsonify({"status": "error", "message": "Request body cannot be empty."}), 400
    try:
        result = global_kite.convert_position(**params)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/orders/place", methods=["POST"])
def place_order() -> dict:
    """
    Places a new order.

    Request Body (JSON):
        A dictionary containing all necessary order parameters as defined in the
        Kite Connect documentation (e.g., 'variety', 'tradingsymbol', 'quantity', etc.).

    Returns:
        dict: A JSON object with the newly placed order's ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    params = request.get_json()
    if not params:
        return jsonify({"status": "error", "message": "Request body cannot be empty."}), 400
    try:
        order_id = global_kite.place_order(**params)
        return jsonify({"status": "success", "data": {"order_id": order_id}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/orders/modify", methods=["PUT"])
def modify_order() -> dict:
    """
    Modifies an open, pending order.

    Request Body (JSON):
        A dictionary containing the 'variety', 'order_id', and other parameters
        to be modified (e.g., 'quantity', 'price').

    Returns:
        dict: A JSON object with the modified order's ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    params = request.get_json()
    if not params:
        return jsonify({"status": "error", "message": "Request body cannot be empty."}), 400
    try:
        order_id = global_kite.modify_order(**params)
        return jsonify({"status": "success", "data": {"order_id": order_id}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/orders/cancel/<variety>/<order_id>", methods=["DELETE"])
def cancel_order(variety: str, order_id: str) -> dict:
    """
    Cancels an open, pending order.

    URL Parameters:
        variety (str): The variety of the order (e.g., 'regular', 'amo').
        order_id (str): The ID of the order to be cancelled.

    Query Parameters:
        parent_order_id (str, optional): The parent order ID for bracket/cover orders.

    Returns:
        dict: A JSON object with the cancelled order's ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        parent_order_id = request.args.get("parent_order_id")
        cancelled_id = global_kite.cancel_order(variety, order_id, parent_order_id)
        return jsonify({"status": "success", "data": {"order_id": cancelled_id}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/orders/exit/<variety>/<order_id>", methods=["DELETE"])
def exit_order(variety: str, order_id: str) -> dict:
    """
    Exits a Cover Order (CO). This is an alias for cancel_order.

    URL Parameters:
        variety (str): The variety of the order, typically 'co'.
        order_id (str): The ID of the order to be exited.

    Query Parameters:
        parent_order_id (str, optional): The parent order ID.

    Returns:
        dict: A JSON object with the exited order's ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        parent_order_id = request.args.get("parent_order_id")
        exited_id = global_kite.exit_order(variety, order_id, parent_order_id)
        return jsonify({"status": "success", "data": {"order_id": exited_id}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/trades", methods=["GET"])
def get_trades() -> dict:
    """
    Fetches the list of all trades executed on the current day.

    Returns:
        dict: A JSON object containing a list of trade data or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        return jsonify({"status": "success", "data": global_kite.trades()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/gtt/place", methods=["POST"])
def place_gtt() -> dict:
    """
    Places a Good 'Til Triggered (GTT) order.

    Request Body (JSON):
        A dictionary containing all necessary GTT parameters as defined in the
        Kite Connect documentation (e.g., 'trigger_type', 'tradingsymbol', 'trigger_values', 'orders').

    Returns:
        dict: A JSON object with the GTT trigger ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    params = request.get_json()
    if not params:
        return jsonify({"status": "error", "message": "Request body cannot be empty."}), 400
    try:
        result = global_kite.place_gtt(**params)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/gtt/delete/<int:trigger_id>", methods=["DELETE"])
def delete_gtt(trigger_id: int) -> dict:
    """
    Deletes an active GTT order.

    URL Parameters:
        trigger_id (int): The ID of the GTT to be deleted.

    Returns:
        dict: A JSON object with the deleted GTT's trigger ID or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    try:
        result = global_kite.delete_gtt(trigger_id)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/market/historical", methods=["POST"])
def get_historical_data() -> dict:
    """
    Fetches historical candle data for a given instrument.

    Request Body (JSON):
        A dictionary with parameters: 'instrument_token', 'from_date', 'to_date',
        'interval'. 'from_date' and 'to_date' can be 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'.

    Returns:
        dict: A JSON object containing a list of candle data or an error.
    """
    authenticated, err, code = check_authentication()
    if not authenticated: return err, code
    params = request.get_json()
    if not params:
        return jsonify({"status": "error", "message": "Request body cannot be empty."}), 400
    try:
        # Convert date strings to datetime objects
        for date_field in ["from_date", "to_date"]:
            if date_field in params:
                try:
                    params[date_field] = datetime.datetime.strptime(params[date_field], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    params[date_field] = datetime.datetime.strptime(params[date_field], "%Y-%m-%d").date()
        
        result = global_kite.historical_data(**params)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Main Execution ---
if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        print("FATAL: ZERODHA_API_KEY and ZERODHA_API_SECRET must be set in your .env file.")
        exit(1)

    print("Starting Kite Connect Flask Server...")
    print("1. Ensure this server is running.")
    print("2. Use the 'kite_flask.py' client to interact with this server.")
    print(f"3. To start, the client will call the /login endpoint to get a URL.")
    app.run(port=5000, debug=True)
