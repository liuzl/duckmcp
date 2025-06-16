import os
import asyncio
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        base_url=os.getenv("GEMINI_BASE_URL"),
    ),
)

server_params = StdioServerParameters(
    command="uvx",
    args=[
        "mcp-server-motherduck",
        "--db-path",
        "my_local_db.duckdb",
    ],
)

async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            prompt = f"一共有多少张数据表？以及分别都是哪些表"
            await session.initialize()
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    tools=[session],
                ),
            )
            print(response.text)


if __name__ == "__main__":
    asyncio.run(run())