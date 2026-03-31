import anthropic
import inspect
from typing import get_type_hints, get_origin, get_args

client = anthropic.AsyncAnthropic()

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _parse_docstring(doc):
    """Parse Google-style docstring into description and arg descriptions."""
    if not doc:
        return "", {}
    lines = doc.strip().split("\n")
    desc_lines = []
    arg_descs = {}
    in_args = False
    current_arg = None

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if stripped.lower().startswith("returns:"):
            in_args = False
            continue
        if in_args:
            if ":" in stripped:
                candidate = stripped.split(":", 1)[0].strip()
                if " " not in candidate:
                    current_arg = candidate
                    arg_descs[current_arg] = stripped.split(":", 1)[1].strip()
                    continue
            if current_arg and stripped:
                arg_descs[current_arg] += " " + stripped
        elif stripped:
            desc_lines.append(stripped)

    return " ".join(desc_lines), arg_descs


def _type_to_schema(py_type):
    """Convert a Python type hint to JSON schema."""
    origin = get_origin(py_type)
    if origin is list:
        args = get_args(py_type)
        if args:
            return {"type": "array", "items": _type_to_schema(args[0])}
        return {"type": "array"}
    # TypedDict support
    if isinstance(py_type, type) and hasattr(py_type, '__annotations__'):
        props = {}
        req = []
        for k, v in py_type.__annotations__.items():
            props[k] = _type_to_schema(v)
            req.append(k)
        return {"type": "object", "properties": props, "required": req}
    return {"type": TYPE_MAP.get(py_type, "string")}


def function_tool(func):
    """Decorator to register a function as a tool with auto-generated schema."""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    desc, arg_descs = _parse_docstring(inspect.getdoc(func))

    properties = {}
    required = []
    for name, param in sig.parameters.items():
        schema = _type_to_schema(hints.get(name, str))
        if name in arg_descs:
            schema["description"] = arg_descs[name]
        properties[name] = schema
        if param.default is inspect.Parameter.empty:
            required.append(name)

    func._tool_schema = {
        "name": func.__name__,
        "description": desc,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    }
    return func


class ModelSettings:
    def __init__(self, tool_choice=None):
        self.tool_choice = tool_choice


class AgentModel:
    def __init__(self, name, instructions, tools=[], model_settings=None, settings={}):
        self.name = name
        self.instructions = instructions
        self.model = settings.get('default_model', 'claude-sonnet-4-6')

        self.tool_choice = {"type": "auto"}
        if model_settings and model_settings.tool_choice == "required":
            self.tool_choice = {"type": "any"}

        self._tool_map = {}
        self._tool_schemas = []
        self._agent_tools = {}

        for t in tools:
            # Server-side tools (e.g. web_search) are passed as raw dicts
            if isinstance(t, dict):
                self._tool_schemas.append(t)
                continue
            if hasattr(t, '_tool_schema'):
                schema = t._tool_schema
                self._tool_map[schema['name']] = t
                self._tool_schemas.append(schema)
                if hasattr(t, '_agent'):
                    self._agent_tools[schema['name']] = t._agent

    def as_tool(self, name, description):
        """Create a tool that delegates to this agent."""
        def handler(request: str) -> str:
            pass

        handler._tool_schema = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "request": {"type": "string", "description": "The request to pass to this agent"}
                },
                "required": ["request"],
            }
        }
        handler._agent = self
        return handler

    async def run(self, messages):
        """Run the agent with tool-use loop. Returns (final_text, conversation)."""
        conversation = list(messages)

        kwargs = {
            "model": self.model,
            "system": self.instructions,
            "messages": conversation,
            "max_tokens": 4096,
        }
        if self._tool_schemas:
            kwargs["tools"] = self._tool_schemas
            kwargs["tool_choice"] = self.tool_choice

        response = await client.messages.create(**kwargs)

        # After first turn with required tool use, switch to auto
        if self.tool_choice.get("type") == "any" and "tool_choice" in kwargs:
            kwargs["tool_choice"] = {"type": "auto"}

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            conversation.append({
                "role": "assistant",
                "content": [block.model_dump() for block in response.content]
            })
            conversation.append({"role": "user", "content": tool_results})
            kwargs["messages"] = conversation

            response = await client.messages.create(**kwargs)

        text = "".join(b.text for b in response.content if hasattr(b, 'text'))
        conversation.append({"role": "assistant", "content": text})

        return text, conversation

    async def _execute_tool(self, name, inputs):
        if name in self._agent_tools:
            text, _ = await self._agent_tools[name].run(
                [{"role": "user", "content": inputs["request"]}]
            )
            return text
        return self._tool_map[name](**inputs)
