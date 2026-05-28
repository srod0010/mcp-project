import asyncio
import json
import litellm
import warnings

# AsyncExitStack is a helper that allows us to open multiple asynchronous context managers and then close them all in one call.
# We'll use it to keep track of stdio_client (the transport connecting us to MCP)
# and the ClientSession itself
from contextlib import AsyncExitStack
from typing import Any, Dict, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

session: ClientSession = None
exit_stack = AsyncExitStack()
model = "gpt-4o"

async def connect_to_server(server_script_path: str = "server.py"):
    """Connect to the MCP server and list available tools."""
    global session, exit_stack

    # This subprocess is expected to run the MCP server and the file contains the implementation of the server.
    server_params = StdioServerParameters(
        command="python",
        args=[server_script_path]
    )
    # actually launch the subprocess (co-routine)
    stdio_transport = await exit_stack.enter_async_context(
        stdio_client(server_params)
    )
    # stdio is reader interface (ie what MCP server prints out)
    # write is writer interface (What MCP server receives)
    stdio, write = stdio_transport

    # when eventually call await exit_stack.aclose() it will close session and 
    # kill the underlying process
    session = await exit_stack.enter_async_context(
        ClientSession(stdio, write)
    )

    # MCP handshake - establish connection between client server connection
    await session.initialize()

async def get_mcp_tools() -> List[Dict[str, Any]]:
    """Retrieve the MCP tools in the Litellm/OpenAI function format."""

    global session

    # list all the tools
    tools_result = await session.list_tools()

    print("Connected to server with tools:")
    for tool in tools_result.tools:
        print(f" - {tool.name} which does {tool.description}")
    
    # LiteLLM (and OpenAI’s “function-calling” API) expects each tool/function to be provided in a specific JSON format
    formatted = []
    for tool in tools_result.tools:
        formatted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
        )
    return formatted


async def process_query(query: str) -> str:

    global session, model
    tools = await get_mcp_tools()

    # First pass: let Litellm decide if it needs to call a tool
    first_response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": query}],
        tools=tools,
        tool_choice="auto",
    )
    # Extract the assistant message
    assistant_message = first_response.choices[0].message
    print(f"Assistant message {assistant_message}")
    messages: List[Dict[str, Any]] = [{"role": "user", "content": query}, assistant_message]

    # Check if Litellm wants to call any tools
    calls = assistant_message.tool_calls or assistant_message.function_call
    if calls:
        # Run tool calls
        calls_list = calls if isinstance(calls, list) else [calls]

        for call in calls_list:
            if call.function:  # newer Litellm structure
                tool_name = call.function.name
                raw_args = call.function.arguments
            else:
                tool_name = call.name
                raw_args = call.arguments

            try:
                parsed_args = json.loads(raw_args)
            except Exception:
                parsed_args = raw_args

            # Get user permission to execute tool
            print(f"\nAssistant requests tool: {tool_name}({parsed_args})")
            permission = input("Allow execution? (y/n): ").strip().lower()

            if permission == "y":
                result = await session.call_tool(tool_name, arguments=parsed_args)
                tool_output = result.content[0].text
                print(f"→ {tool_name} returned: {tool_output}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id if hasattr(call, "id") else None,
                    "content": tool_output,
                })
            else:
                denied_msg = f"[Tool '{tool_name}' denied]"
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id if hasattr(call, "id") else None,
                    "content": denied_msg,
                })
                print(f"→ Skipped {tool_name}")

        # Second pass: ask Litellm for a reply now that tool output is available
        # Note: in second pass can use tool_choice="none" to ensure a final text response without calling other tools
        second_response = await litellm.acompletion(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="none",
        )

        return second_response.choices[0].message.content.strip()
    else:
        return assistant_message.content.strip() # Litellm answered without needing any tools
    

async def cleanup():
    """Close the MCP client session cleanly."""
    # First close ClientSession
    # Then kill underlying subprocess eg MCP server that was launched by python server.py
    global exit_stack
    await exit_stack.aclose()

async def main():
    await connect_to_server("server.py")

    query = input("Ask a question \n").strip()

    if not query:
        print("No query provided. using default: \n")
        query = """What is 90 multiplied by 68.6.
                Also tell the weather in Lucknow.
                Use MCP tools for both."""

    print(f"\nQuery: {query}")

    response = await process_query(query)
    print(f"\nFinal Response: {response}")

    await cleanup()
    print("Connection terminated successfully!")


if __name__ == "__main__":
    # uv run client_stdio_with_llm.py or python client_stdio_with_llm.py
    asyncio.run(main())