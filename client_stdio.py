"""

Asynchronous programming lets a program do multiple things 
at once without waiting for slow tasks to finish first. 
Instead of stopping completely, it starts the slow task, keeps working on other tasks, 
and later comes back when the slow task is done. 
This makes programs faster and more responsive.
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Define server parameters
    # The executable to run (Python interpreter) is provided by command="python"
    server_params = StdioServerParameters(
        command="python",  # The command to run your server
        args=["server.py"],  # Arguments to the command (the server script)
    )

    """
    The first line of code starts the server using the server parameters
    and sets up an asynchronous connection through standard input/output streams.
    - stdio_client() manages the communication.
    
    The second line, establishes a session between the client and the server
    over input/output streams using ClientSession(). It manages the MCP protocol communication over those streams.

    Note: The nested context managers ensure proper cleanup when the connection ends.
    """
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection performing the MCP handshake. This establishes the protocol connection between client and server.
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                # description is just the docstrings
                print(f"  - {tool.name}: {tool.description}")

            # Call our calculator tool
            result = await session.call_tool("calculate", arguments={"expression": "2 + 3"})
            print(f"2 + 3 = {result.content[0].text}")

if __name__ == "__main__":
    # uv run client_stdio.py or python client_stdio.py
    asyncio.run(main())