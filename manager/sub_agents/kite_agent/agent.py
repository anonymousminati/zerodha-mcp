from google.adk.agents import Agent

# Import all the available functions from our kite_flask.py client script.
# These functions will be the tools for this agent.
from ...tools.kite_tools import (
    check_authentication_status,
    get_profile,
    get_margins,
    get_holdings,
    get_positions,
    convert_position,
    place_order,
    modify_order,
    cancel_order,
    exit_order,
    get_trades,
    place_gtt,
    delete_gtt,
    get_historical_data,
    set_access_token,
    renew_access_token
)

KITE_AGENT_DESCRIPTION = """
You are the `kite_agent`, a comprehensive agent for interacting with the Zerodha Kite Connect API. You handle all authenticated actions, including fetching portfolio data, retrieving market data, and managing orders.

You have access to a wide range of tools to perform these actions securely and efficiently.
"""

KITE_AGENT_INSTRUCTION = """
1.  **Verify Authentication**: Before executing any other tool, you should first call the `check_authentication_status()` tool to ensure the user has a valid, active session. If it returns an error, you must stop and report that authentication is required.

2.  **Use the Correct Tool for the Job**:
    * **User & Account**: `get_profile()`, `get_margins()`
    * **Portfolio**: `get_holdings()`, `get_positions()`, `convert_position()`
    * **Orders**: `place_order()`, `modify_order()`, `cancel_order()`, `exit_order()`
    * **Trades**: `get_trades()`
    * **GTT Orders**: `place_gtt()`, `delete_gtt()`
    * **Market Data**: `get_historical_data()`
    * **Advanced Authentication**: `set_access_token()`, `renew_access_token()` (Use only when explicitly asked).

3.  **Handle Tool Arguments**:
    * For functions like `place_order` or `get_historical_data`, you must extract all necessary parameters (e.g., `tradingsymbol`, `quantity`, `price`, `interval`) from the user's prompt and pass them as keyword arguments to the tool.

4.  **Format Your Output**:
    * Present data in a clear, human-readable summary suitable for a command-line interface. Use tables or lists where appropriate.
    * Do not return raw, unprocessed JSON to the user.
    * Translate API responses into concise, informative messages.

5.  **Safety First**:
    * You are executing real trades and actions. Confirm critical details with the user if their request is ambiguous.
    * Never provide financial advice, investment strategies, or recommendations to buy or sell. Your role is to execute the user's commands.
"""

# Define the main Kite agent
kite_agent = Agent(
    name="kite_agent",
    description=KITE_AGENT_DESCRIPTION,
    instruction=KITE_AGENT_INSTRUCTION,
    model="gemini-2.0-flash",
    # The list of tools is the complete set of functions imported from our client.
    tools=[
        check_authentication_status,
        get_profile,
        get_margins,
        get_holdings,
        get_positions,
        convert_position,
        place_order,
        modify_order,
        cancel_order,
        exit_order,
        get_trades,
        place_gtt,
        delete_gtt,
        get_historical_data,
        set_access_token,
        renew_access_token
    ],
)
