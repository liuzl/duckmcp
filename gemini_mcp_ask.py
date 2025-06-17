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

async def run(mcp_config_path: str, prompt: str):
    config = json.load(open(mcp_config_path, 'r', encoding='utf-8'))
    mcp_servers = config.get("mcpServers", {})
    if not mcp_servers:
        await call_ai(prompt)
        return
    active_servers = {name: config for name, config in mcp_servers.items() if not config.get("disabled", False)}
    if not active_servers:
        await call_ai(prompt)
        return
    print(f"启动 {len(active_servers)} 个MCP服务器: {list(active_servers.keys())}")
    server_configs = []
    for server_name, server_config in active_servers.items():
        server_params = StdioServerParameters(
            command=server_config.get("command", "uvx"),
            args=server_config.get("args", []),
            env=server_config.get("env", {}),
        )
        server_configs.append((server_name, server_params))
    async with AsyncExitStack() as stack:
        sessions = []
        failed_servers = []
        for server_name, server_params in server_configs:
            try:
                read, write = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                sessions.append(session)
                print(f"✅ 成功连接到MCP服务器: {server_name}")                    
            except Exception as e:
                print(f"❌ 连接MCP服务器 {server_name} 失败: {e}")
                failed_servers.append(server_name)
                continue
        if not sessions:
            await call_ai(prompt)
            return
        if failed_servers:
            print(f"以下服务器连接失败但将继续使用其他服务器: {failed_servers}")
        await call_ai(prompt, sessions=sessions)

async def call_ai(prompt: str, sessions=None):
    config_dict = types.GenerateContentConfig(temperature=0)
    if sessions: config_dict.tools = sessions
    response = await client.aio.models.generate_content(model="gemini-2.0-flash", contents=prompt, config=config_dict)
    print(response.text)

@click.command()
@click.option('--mcp-config', default='mcp.json', help='MCP配置文件的路径', type=click.Path(exists=True))
@click.option('--prompt', '-p', required=True, help='要发送给AI的提示内容')
def main(mcp_config: str, prompt: str) -> None:
    asyncio.run(run(mcp_config, prompt))

if __name__ == "__main__":
    main()