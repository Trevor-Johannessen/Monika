import os
from agents import function_tool
from agentModel import AgentModel


class FilesystemAgent(AgentModel):
    def __init__(self, settings={}):
        super().__init__(
            name="filesystem_agent",
            settings=settings,
            instructions="""
            You are an agent responsible for reading and writing files and directories on the local filesystem.
            Use the provided tools to fulfill any file-related requests from the user.
            Always use absolute paths. When listing directories, summarize the contents clearly.
            """,
            tools=[read_file, write_file, list_directory, create_directory, delete_file],
        )


@function_tool
def read_file(path: str) -> str:
    """Reads the contents of a file.

    Args:
        path: Absolute path to the file to read.

    Returns:
        The file contents as a string, or an error message.
    """
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


@function_tool
def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating it if it does not exist.

    Args:
        path: Absolute path to the file to write.
        content: The content to write to the file.

    Returns:
        A string indicating success or an error message.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return "Success."
    except Exception as e:
        return f"Error writing file: {e}"


@function_tool
def list_directory(path: str) -> str:
    """Lists the contents of a directory.

    Args:
        path: Absolute path to the directory to list.

    Returns:
        A newline-separated list of entries, or an error message.
    """
    try:
        entries = os.listdir(path)
        result = []
        for entry in sorted(entries):
            full = os.path.join(path, entry)
            kind = "DIR" if os.path.isdir(full) else "FILE"
            result.append(f"[{kind}] {entry}")
        return "\n".join(result) if result else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


@function_tool
def create_directory(path: str) -> str:
    """Creates a directory and any missing parent directories.

    Args:
        path: Absolute path of the directory to create.

    Returns:
        A string indicating success or an error message.
    """
    try:
        os.makedirs(path, exist_ok=True)
        return "Success."
    except Exception as e:
        return f"Error creating directory: {e}"


@function_tool
def delete_file(path: str) -> str:
    """Deletes a file.

    Args:
        path: Absolute path to the file to delete.

    Returns:
        A string indicating success or an error message.
    """
    try:
        os.remove(path)
        return "Success."
    except Exception as e:
        return f"Error deleting file: {e}"
