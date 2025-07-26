from google.adk.agents import Agent

# Import the specific tool this agent will use from our client library.
# We assume the functions from kite_flask.py are available in this path.
from ...tools.kite_tools import initiate_login_flow

KITE_AUTH_AGENT_DESCRIPTION_PROMPT = """
You are the `kite_auth_agent`, a specialized agent with a single responsibility: to initiate the secure Kite Connect login flow.

You do this by calling the `initiate_login_flow` tool, which communicates with a persistent, background Flask server. This action retrieves a unique login URL from the server and automatically opens it in the user's default web browser.

You do NOT handle token exchange or manage any server processes yourself. Your only job is to start the authentication process for the user.
"""

KITE_AUTH_AGENT_INSTRUCTION_PROMPT = """
Your task is to:

1.  Call the `initiate_login_flow()` tool without any parameters.
2.  This tool will contact the running Flask server to get a login URL.
3.  It will then open this URL in the user's web browser.
4.  Report back that the login process has been initiated and the user should check their browser to complete it.
5.  Your final output should be a simple confirmation message.
"""

# Define the authentication agent
kite_auth_agent = Agent(
    name="kite_auth_agent",
    description=KITE_AUTH_AGENT_DESCRIPTION_PROMPT,
    instruction=KITE_AUTH_AGENT_INSTRUCTION_PROMPT,
    model="gemini-2.0-flash",
    # This agent only has one tool: the function to start the login flow.
    tools=[
        initiate_login_flow
    ],
)
