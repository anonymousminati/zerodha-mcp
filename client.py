#!/usr/bin/env python
# client.py
import os
import agno
import asyncio
import logging
import argparse
from agno.models.openai import OpenAIChat
from agno.agent import Agent, RunResponse
from agno.tools.mcp import MCPTools
from agno.tools.thinking import ThinkingTools
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.logging import RichHandler
from rich.prompt import Prompt
from rich import print as rprint
from rich.theme import Theme
from rich.text import Text
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv

# Suppress httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configure rich logging
logging.basicConfig(
    level=logging.ERROR,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)
logger = logging.getLogger(__name__)

# Define custom theme
custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "danger": "bold red",
    "success": "bold green",
    "query": "bold blue",
    "response": "bold green",
    "assistant": "bold magenta",
    "user": "bold magenta"
})

# Initialize rich console with custom theme
console = Console(theme=custom_theme)

load_dotenv()

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_sse_server(self, server_url: str):
        """Connect to an MCP server running with SSE transport"""
        # Store the context managers so they stay alive
        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session: ClientSession = await self._session_context.__aenter__()

        # Initialize
        await self.session.initialize()

        # List available tools to verify connection
        # console.print("[success]✓[/success] [info]Initialized SSE client...[/info]")
        response = await self.session.list_tools()
        logger.debug(f"[info]Connected to server with {len(response.tools)} tools available[/info]")

    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    async def disconnect(self):
        """Disconnect from the MCP server"""
        await self.cleanup()

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='MCP Client')
    parser.add_argument('--host', help='MCP server host (default: localhost)')
    parser.add_argument('--port', type=int, help='MCP server port (default: 8001)')
    args = parser.parse_args()

    # Get MCP host and port from args or environment variables
    mcp_host = args.host or os.environ.get("MCP_HOST", "localhost")
    mcp_port = args.port or int(os.environ.get("MCP_PORT", "8001"))
    mcp_url = f"http://{mcp_host}:{mcp_port}/sse"

    mcp_client = MCPClient()

    await mcp_client.connect_to_sse_server(mcp_url)

    logger.debug(f"[info]Connected to MCP server at {mcp_url}[/info]")

    # List available tools
    response = await mcp_client.session.list_tools()
    logger.debug(f"[info]Available tools: {', '.join([tool.name for tool in response.tools])}[/info]")

    mcp_tools = MCPTools(session=mcp_client.session)

    await mcp_tools.initialize()

    logger.debug(f"[info]MCP tools initialized[/info]")

    # Create the Agno agent with Gemini model
    agent = Agent(
        instructions="""
You are a Zerodha Trading Account Assistant, helping users securely manage their accounts, orders, portfolio, and positions.

# Important Instructions:
- ALWAYS respond in plain text. NEVER use markdown formatting (no asterisks, hashes, or code blocks).
- Respond in human-like conversational, friendly, and professional tone in concise manner.

# Authentication Steps (must be followed if no access token is generated):
1. Generate a Kite login URL and ask the user to log in.
2. Once the user completes login, request the request token from them.
3. Use the request token to generate and validate the access token.
4. Proceed only if the access token is valid.

#Responsibilities:
- Check if the user is authenticated.
- Assist with order placement, modification, and cancellation.
- Provide insights on portfolio holdings, positions, and available margin.
- Track order status, execution details, and trade history.

# Limitations:
You do not provide real-time market quotes, historical data, or financial advice. Your role is to ensure secure, efficient, and compliant account management.
""",
        model=OpenAIChat(
            id="gpt-4o-mini"
        ),
        add_history_to_messages=True,
        num_history_responses=10,
        tools=[ThinkingTools(),mcp_tools],
        show_tool_calls=True,
        markdown=True,
        read_tool_call_history=True,
        read_chat_history=True,
        tool_call_limit=10
    )

    # Welcome message

    console.print()

    console.print("[info]Welcome to Zerodha! I'm here to assist you with managing your trading account, orders, portfolio, and positions. How can I help you today?[/info]", style="response")


    try:
        while True:
            # Add spacing before the prompt
            console.print()
            # Get user input with rich prompt
            user_query = Prompt.ask("[query]Enter your query:[/query] [dim](or 'quit' to exit)[/dim]")



            # Check if user wants to quit
            if user_query.lower() == 'quit':
                break


                # Add spacing before the prompt
            console.print()
            # Display user query
            console.print(f"[user]You:[/user] {user_query}")
            # Add spacing before the assistant's response
            console.print()
            console.print(f"[assistant]Assistant:[/assistant] ", end="")

            # Run the agent and stream the response
            result = await agent.arun(user_query, stream=True)
            async for response in result:
                # Check for tool calls
                # Note: The exact structure of 'response' and 'tool_calls' depends on the 'agno' library.
                # This assumes 'response' has a 'tool_calls' attribute which is a list of dicts.
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    console.print() # Add spacing before tool call info
                    console.print("[bold yellow]🛠️  Executing Tools:[/bold yellow]")
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get('name', 'N/A')
                        tool_args = tool_call.get('arguments', '{}') # Default to string '{}'
                        console.print(f"  - [cyan]{tool_name}[/cyan] with args: [dim]{tool_args}[/dim]")
                    console.print() # Add spacing after tool call info

                # Check for regular content
                if response.content:
                    console.print(response.content, style="response", end="")

            console.print()  # Add newline after the full response
            console.print()  # Add extra spacing after the response

    except Exception as e:
        logger.error(f"[danger]Error running agent: {e}[/danger]")
    finally:
        # Disconnect from the MCP server
        await mcp_client.disconnect()
        logger.debug("[info]Disconnected from MCP server[/info]")

if __name__ == "__main__":
    asyncio.run(main())
