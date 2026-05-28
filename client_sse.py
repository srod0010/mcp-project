"""
e need to start our server by executing the server script in a separate terminal, 
using uv run server.py. Also, under the main method of server.py file, ensure to run this server as sse.
 This makes our server active and available at the specified url.

 To run server under sse transport change mcp.run line
 mcp.run(transport="sse", host="127.0.0.1", port=8000)
"""
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():

    # Connect to the server using SSE
    async with sse_client("http://127.0.0.1:8000/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            print("Available tools:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            result = await session.call_tool("calculate",
                                             arguments={"expression": "2 + 3"})
            
            print(f"2 + 3 = {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(main())