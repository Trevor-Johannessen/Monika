__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

from agents import Agent
import json
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from agents import Agent, function_tool, ModelSettings
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

class MemoryAgent(Agent):
    def __init__(self):
        super().__init__(
            name="memory_agent",
            instructions=f"""
            
            You are an agent in charge or storing and retrieving information (also known as memories). Use the provided strings to search for relevant infromation. A good indicator that information is important to store is if the user responds with a statement instead of a question. Below is a list of metadata tags to use when querying. Do not add new tags unless it is unqiue enough to help with identification.
            
            TAGS:
            {chr(10).join(tags)}
            """,
            model_settings=ModelSettings(tool_choice="required"),
            tools=[memorize, remember]
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

    # Store text
    try:
        collection.add(
            ids=[id],
            embeddings=embeddings,
            documents=[text],
            metadatas=metadata
        )
    except Exception as e:
        return e

    return "Success."

@function_tool
def remember(query: str, max_results: int = 10) -> str:
    """Searches the vector database for information similar to a query.

    Args:
        query: A string asking for information
        max_results: The maximum amount of enteries to return

    Returns:
        A string commenting on the success of the retrieval
    """
    return collection.query(
        query_texts=[query],
        n_results=max_results,
        include=["documents"]
    )