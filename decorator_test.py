from typing import Any, Generic, Literal, TypeVar, overload, Annotated, get_type_hints, get_origin, get_args, Union
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from pydantic import BaseModel, ConfigDict, Field, FileUrl, TypeAdapter
from pydantic.alias_generators import to_camel
import asyncio
import inspect

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

RequestId = Annotated[int, Field(strict=True)] | str

def extract_input_schema(fn: Callable) -> dict[str, Any]:
    """从函数签名中提取 JSON Schema"""
    try:
        sig = inspect.signature(fn)
        type_hints = get_type_hints(fn)
    except Exception:
        return {"type": "object", "properties": {}}
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        param_info = {"type": "string"}  # 默认类型
        
        # 获取类型注解
        if param_name in type_hints:
            param_type = type_hints[param_name]
            param_info["type"] = get_json_type(param_type)
        
        # 获取默认值
        if param.default is not inspect.Parameter.empty:
            param_info["default"] = param.default
        else:
            required.append(param_name)
        
        properties[param_name] = param_info
    
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    
    return schema

def get_json_type(py_type) -> str:
    """将 Python 类型映射到 JSON Schema 类型"""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    
    # 处理 Optional 类型
    origin = get_origin(py_type)
    if origin is Union:
        args = get_args(py_type)
        non_none = [arg for arg in args if arg is type(None)]
        if non_none:
            return get_json_type(non_none[0])
    
    # 处理 list 类型
    if origin is list:
        return "array"
    
    # 处理 dict 类型
    if origin is dict:
        return "object"
    
    # 直接类型映射
    for py_t, json_t in type_map.items():
        if py_t == py_type or py_type is py_t:
            return json_t
    
    return "string"  # 默认返回 string

def extract_return_annotation(fn: Callable) -> dict[str, Any]:
    """提取函数返回类型"""
    try:
        hints = get_type_hints(fn)
        return_hint = hints.get('return')
        
        if return_hint is None:
            return {"type": "string"}
        
        return {"type": get_json_type(return_hint)}
    except Exception:
        return {"type": "string"}

class MCPModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

class BaseMetadata(MCPModel):
    name: str
    title: str | None = None
    
class Meta(MCPModel):
    pass

class Tool(BaseMetadata):
    description: str | None = None
    inputSchema: dict[str, Any] | None = {}
    outputSchema: dict[str, Any] | None = {}
    meta: Meta | None = Field(alias="_meta", default=None)
    
class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"]
    id: RequestId
    result: dict[str, Any]

class Test:

    def __init__(self):
        self.tools = {}

    def add_tool(self, fn: _CallableT, name: str, title: str, description: str, meta: dict[str, Any], structured_output: bool):
        input_schema = extract_input_schema(fn)
        return_annotation = extract_return_annotation(fn)
        
        self.tools[name] = {
            "name": name,
            "title": title,
            "description": description,
            "meta": meta,
            "structured_output": structured_output,
            "fn": fn,
            "input_schema": input_schema,
            "output_schema": return_annotation,
        }

    def tool(
        self,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
    ) -> Callable[[_CallableT], _CallableT]:
        def decorator(fn: _CallableT) -> _CallableT:
            self.add_tool(
                fn,
                name=name,
                title=title,
                description=description,
                meta=meta,
                structured_output=structured_output,
            )
            return fn
        return decorator

    async def list_tools(self) -> list[Tool]:
        tools = self.tools.values()
        return [
            Tool(
                name=info["name"],
                title=info["title"],
                description=info["description"],
                inputSchema=info.get("input_schema"),
                outputSchema=info.get("output_schema"),
                meta=info.get("meta"),
            )
            for info in tools
        ]

    async def _send_response(self, request_id: RequestId, response):
        jsonrpc_response = JSONRPCResponse(
                jsonrpc="2.0",
                id=request_id,
                result=response,
            )
        return jsonrpc_response

mcp_list = Test()

@mcp_list.tool(name="test", title="test", description="test", meta={"test": "test"}, structured_output=True)
def test(TEST: str, OPTIONAL: int = 123) -> str:
    """测试函数"""
    print('test2222')
    return_str= f"test {TEST} {OPTIONAL}"
    return return_str

async def main():
    tools = await mcp_list.list_tools()
    print("工具列表:", tools)
    
    response = await mcp_list._send_response("1", {"tools": tools})
    print("\nJSONRPCResponse 对象:", response)
    print("\n转换为 JSON 字符串:")
    print(response.model_dump_json(indent=2))

asyncio.run(main())





