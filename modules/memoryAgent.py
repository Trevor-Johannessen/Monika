__import__("pysqlite3")
import sys

sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

import json

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

chroma_client = chromadb.PersistentClient(path="/var/lib/monika/memory.d")
openai_client = OpenAI()

ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key_env_var="OPENAI_API_KEY",
    model_name="text-embedding-3-small",
)

collection = chroma_client.get_or_create_collection(
    name="my_documents",
    embedding_function=ef,
)

with open("/etc/monika/tags.json", "r") as f:
    tags = json.load(f)


def _build_instructions() -> str:
    return (
        "You are an agent in charge of storing and retrieving information (also known as memories). "
        "Use the provided strings to search for relevant information. A good indicator that information "
        "is important to store is if the user responds with a statement instead of a question. Below is "
        "a list of metadata tags to use when querying. Do not add new tags unless it is unique enough to "
        "help with identification.\n\n"
        "You MUST call a tool (memorize or remember) before answering — do not respond from your own "
        "knowledge.\n\n"
        f"TAGS:\n{chr(10).join(tags)}"
    )


@tool(
    "memorize",
    "Stores information in a vector database for future retrieval.",
    {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "A unique identifier for the information. The ID should relate to the information being stored.",
            },
            "metadata": {
                "type": "array",
                "description": "A list of key value pairs describing the information. Also referred to as 'tags'.",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["key", "value"],
                },
            },
            "text": {
                "type": "string",
                "description": "The actual information to be stored and retrieved.",
            },
        },
        "required": ["id", "metadata", "text"],
    },
)
async def memorize(args):
    if collection.get(ids=[args["id"]])["ids"]:
        return {
            "content": [{"type": "text", "text": f'The id "{args["id"]}" is already in use.'}],
            "is_error": True,
        }

    embeddings = ef(input=[args["text"]])

    try:
        collection.add(
            ids=[args["id"]],
            embeddings=embeddings,
            documents=[args["text"]],
            metadatas={item["key"]: item["value"] for item in args["metadata"]},
        )
    except Exception as e:
        return {"content": [{"type": "text", "text": str(e)}], "is_error": True}

    return {"content": [{"type": "text", "text": "Success."}]}


@tool(
    "remember",
    "Searches the vector database for information similar to a query.",
    {"query": str, "max_results": int},
)
async def remember(args):
    result = collection.query(
        query_texts=[args["query"]],
        n_results=args.get("max_results", 10),
        include=["documents"],
    )
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}


memory_tools_server = create_sdk_mcp_server(
    name="memory_tools",
    version="1.0.0",
    tools=[memorize, remember],
)


def build_memory_agent(model: str):
    @tool(
        "memory_agent",
        "Routes memory storage and retrieval requests to a specialized agent. Pass the user's request as 'request'.",
        {"request": str},
    )
    async def memory_agent(args):
        text = ""
        async for msg in query(
            prompt=args["request"],
            options=ClaudeAgentOptions(
                system_prompt=_build_instructions(),
                mcp_servers={"memory_tools": memory_tools_server},
                allowed_tools=[
                    "mcp__memory_tools__memorize",
                    "mcp__memory_tools__remember",
                ],
                tools=[],
                permission_mode="bypassPermissions",
                model=model,
            ),
        ):
            if isinstance(msg, ResultMessage) and msg.subtype == "success":
                text = msg.result
        return {"content": [{"type": "text", "text": text}]}

    return memory_agent
