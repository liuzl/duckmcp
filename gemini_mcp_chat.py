import os
import asyncio
import click
import json
from contextlib import AsyncExitStack
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(base_url=os.getenv("GEMINI_BASE_URL")),
)

async def run(mcp_config_path: str):
    config = json.load(open(mcp_config_path, 'r', encoding='utf-8'))
    mcp_servers = config.get("mcpServers", {})
    if not mcp_servers:
        await chat_loop()
        return
    active_servers = {name: cfg for name, cfg in mcp_servers.items() if not cfg.get("disabled", False)}
    if not active_servers:
        await chat_loop()
        return
    print(f"启动 {len(active_servers)} 个MCP服务器: {list(active_servers.keys())}")
    server_configs = [(name, StdioServerParameters(
        command=cfg.get("command", "uvx"),
        args=cfg.get("args", []),
        env=cfg.get("env", {}),
    )) for name, cfg in active_servers.items()]
    async with AsyncExitStack() as stack:
        sessions = []
        for server_name, server_params in server_configs:
            try:
                read, write = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                sessions.append(session)
                print(f"✅ {server_name}")
            except Exception as e:
                print(f"❌ {server_name}: {e}")
        await chat_loop(sessions if sessions else None)

async def chat_loop(sessions=None):
    print("开始多轮对话 (输入 'quit' 或 'exit' 退出)")
    config_dict = types.GenerateContentConfig(temperature=0)
    if sessions: config_dict.tools = sessions
    chat = client.aio.chats.create(model="gemini-2.0-flash", config=config_dict)
    while True:
        try:
            prompt = input("\n> ").strip()
            if prompt.lower() in ['quit', 'exit', 'q']:
                break
            if prompt:
                response = await chat.send_message(prompt)
                print(response.text)
        except (KeyboardInterrupt, EOFError):
            break
    print("对话结束")

@click.command()
@click.option('--mcp-config', default='mcp.json', help='MCP配置文件的路径', type=click.Path(exists=True))
def main(mcp_config: str) -> None:
    asyncio.run(run(mcp_config))

if __name__ == "__main__":
    main()