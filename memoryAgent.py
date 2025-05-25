__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from agents import Agent
import json
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from agents import Agent, function_tool
from typing_extensions import TypedDict, List

# Initalize clients
chroma_client = chromadb.PersistentClient(path="/var/lib/monika/memory.d")
openai_client = OpenAI()

# Set up embedding function
ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key_env_var="OPENAI_API_KEY",
    model_name="text-embedding-3-small",
)

# Get chroma collection
collection = chroma_client.get_or_create_collection(
    name="my_documents",
    embedding_function=ef,
)

# Get current tag list
with open("/etc/monika/tags.json", "r") as f:
    tags = json.load(f)

class MetadataItem(TypedDict):
    key: str
    value: str

class MemorizeAgent(Agent):
    def __init__(self):
        super().__init__(
            name="memorize_agent",
            instructions=f"""            
            You are the memorize agent within a larger AI assistant system. Your role is to store important information that may help with future tasks or context restoration. Follow the instructions below exactly.

            INSTRUCTIONS:
            1. Trigger Condition:
                - Only act if the user (or another agent) is explicitly asking you to “memorize” or “remember” something.
                - If the instruction includes words like “memorize,” “remember,” or “store this,” treat it as a command to store the provided content.

            2. Deduplication Check:
                - BEFORE storing, check if this exact or very similar content has already been stored using the `retrieve` tool or equivalent.
                - If the content is already memorized (or near-duplicate), DO NOTHING and RETURN immediately.

            3. Action:
                - If the deduplication check confirms the content is new, use the `memorize` tool to store it.
                - After memorizing, RETURN immediately. Do not do anything else.

            4. Tagging Guidance:
                - Use only the predefined metadata tags listed below when categorizing content.
                - Only create a new tag if it is clearly unique and essential for future identification.

            5. Output Policy:
                - NEVER return any chat output. Do not generate messages or summaries.

            TAGS:
            {chr(10).join(tags)}
            """,
            tools=[memorize],
            model="o4-mini",
        )

class RecallAgent(Agent):
    def __init__(self):
        super().__init__(
            name="recall_agent",
            instructions=f"""            
            You are a reasoning agent within a larger AI assistant. Your sole purpose is to determine if additional context is required and if so, to call the recall tool. Follow these instructions exactly:
            
            INSTRUCTIONS:
                - First, analyze the user’s most recent request and compare it with the immediate past context. Ask yourself: “Is anything unclear or missing that would prevent a confident response?”
                - If and only if there is a clear, specific piece of information missing that is critical to responding, then call the recall tool once.
                - Never call the recall tool more than one time per user request, regardless of the result.
                - If the context seems sufficient, do nothing. Do not generate or return any output.
                - Never return chat output or say anything to the user.
                - If you have already used recall, do nothing further for this request.
            """,
            tools=[recall],
            model="o4-mini",
        )

def _add_tag(tag: str):
    if tag in tags:
        return
    tags.append(tag)
    with open("/etc/monika/tags.json", "w") as f:
        json.dump(tags, f)

@function_tool
def memorize(id: str, metadata: List[MetadataItem], text: str) -> str:
    """Stores information in a vector database for future retrieval.

    Args:
        id: A unique identifier for the information. The ID should relate to the information being stored.
        metadata: A list of key value pairs describing the information. Also referred to as 'tags'
        text: The actual information to be stored and retrieved

    Returns:
        A string commenting on the success of the insertion
    """
    # Check that id is unique
    if collection.get(ids=[id])['ids']:
        return f'The id "{id}" is already in use.'

    # Generate embedding
    embeddings = ef(
        input=[text]
    )

    # Transcribe embeddings
    metadata_dict = {}
    for pair in metadata:
        for tag in pair:
            _add_tag(tag)
            metadata_dict[tag] = pair[tag]
    # Store text
    try:
        collection.add(
            ids=[id],
            embeddings=embeddings,
            documents=[text],
            metadatas=metadata_dict
        )
    except Exception as e:
        return e

    return "Success."

@function_tool
def recall(query: str, max_results: int = 10) -> str:
    """Searches the vector database for information similar to a query.

    Args:
        query: A string asking for information
        max_results: The maximum amount of enteries to return

    Returns:
        A string commenting on the success of the retrieval
    """
    result =  collection.query(
        query_texts=[query],
        n_results=max_results,
        include=["documents"]
    )
    if result['ids'] == [[]]:
        return "Couldn't find any information."
    return result