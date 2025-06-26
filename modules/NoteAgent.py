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

class NoteAgent(Agent):
    def __init__(self):
        super().__init__(
            name="note_agent",
            instructions=f"""            
            You are a simple notes agent that helps users store and retrieve concise notes. Your job is to call the appropriate function. Only return function calls. Never include extra text. Only call one function.

            Rules for Behavior:
            - Be concise when storing information. Try to eliminate filler that may sway a semantic search.
            - Use only the tags provided in the "TAGS:" section. Tags are separated by commas.
            - Invent tags if no existing tags can describe relevant information.
            - Include tags that describe the topic of the note. If  the user is talking about football, include the tag 'sports'.
            - Never guess missing information.
            - Always return only the appropriate function call. Do not explain, summarize, or chat.
            - Do not ask follow-up questions.
            - Do not reason beyond what is provided.
            - The word 'remember' should be interpreted as 'memorize' and call the create_note function.

            When storing a note:
            - Use the given title if provided, or generate a brief one from context.
            - Parse tags from the TAGS section.


            TAGS:
            {chr(10).join(tags)}
            """,
            tools=[create_note, retrieve_note, delete_note],
        )

def _add_tag(tag: str):
    if tag in tags:
        return
    tags.append(tag)
    with open("/etc/monika/tags.json", "w") as f:
        json.dump(tags, f)

@function_tool
def create_note(id: str, metadata: List[MetadataItem], text: str) -> str:
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

    return "Note stored successfully."

@function_tool
def retrieve_note(query: str, max_results: int = 10) -> str:
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

@function_tool
def delete_note(query: str) -> None:
    """Marks the most similar information to the query to be deleted.

    Args:
        query: A string asking for information
    """