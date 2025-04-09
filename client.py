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
from mcp import ClientSession
from mcp.client.stdio import stdio_client
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import asyncio
import json
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client

from dotenv import load_dotenv

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
        print("Initialized SSE client...")
        print("Listing tools...")
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

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

    logger.info(f"Connected to MCP server at {mcp_url}")

    # List available tools
    response = await mcp_client.session.list_tools()
    logger.info(f"Available tools: {', '.join([tool.name for tool in response.tools])}")

    mcp_tools = MCPTools(session=mcp_client.session)

    await mcp_tools.initialize()

    logger.info(f"MCP tools: {mcp_tools}")


    # Create the Agno agent with Gemini model
    agent = Agent(
        instructions="""
You are a **Zerodha Trading Account Assistant**, helping users securely manage their accounts, orders, portfolio, and positions.

### **Responsibilities:**
- Maintain strict confidentiality and require authentication for sensitive actions.
- Assist with **order placement, modification, and cancellation**.
- Provide insights on **portfolio holdings, positions, and available margin**.
- Track **order status, execution details, and trade history**.
- Notify users of **trading restrictions, margin shortfalls, or order rejections**.
- Offer technical assistance for account-related issues.

### **Security Measures:**
- Never store or log credentials.
- Validate all requests for compliance and security.
- Flag suspicious activities immediately.

You **do not** provide real-time market quotes, historical data, or financial advice. Your role is to ensure **secure, efficient, and compliant** account management.
""",
        model=OpenAIChat(
            id="gpt-4o-mini"
        ),
        add_history_to_messages=True,
        num_history_responses=10,
        tools=[mcp_tools],
        show_tool_calls=True,
        markdown=True
    )

    # Example agent execution
    try:
        while True:
            # Get user input
            user_query = input("Enter your query (or 'quit' to exit): ")

            # Check if user wants to quit
            if user_query.lower() == 'quit':
                break

            # Run the agent
            # await agent.aprint_response(user_query, stream=True)
            result = await agent.arun(user_query, stream=True)

            async for response in result:
                if response.content:
                    print(response.content, end="", flush=True)
            print()  # Add newline after response completes

    except Exception as e:
        logger.error(f"Error running agent: {e}")
    finally:
        # Disconnect from the MCP server
        await mcp_client.disconnect()
        logger.info("Disconnected from MCP server")

if __name__ == "__main__":
    asyncio.run(main())
