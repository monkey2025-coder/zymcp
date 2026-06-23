from typing import Any, Generic, Literal, TypeVar, overload, Annotated, get_type_hints, get_origin, get_args, Union
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from pydantic import BaseModel, ConfigDict, Field, FileUrl, TypeAdapter
from pydantic.alias_generators import to_camel
import asyncio
import inspect
from fastapi import FastAPI, APIRouter, HTTPException
import uvicorn

from zymcp_tool import extract_input_schema, extract_return_annotation, get_json_type
from zymcp_type import Tool, JSONRPCResponse, RequestId, MCPModel, BaseMetadata, Meta, _CallableT


class zymcp:

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

    def _create_mcp_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.get("/")
        async def get_mcp():
            return {
                "name": "MCP Server",
                "protocolVersion": "2025-11-25",
                "capabilities": {
                    "tools": {}
                }
            }
        
        @router.post("/")
        async def post_mcp(request: dict[str, Any]):
            method = request.get("method")
            request_id = request.get("id")
            jsonrpc_version = request.get("jsonrpc", "2.0")
            
            if not method:
                return JSONRPCResponse(
                    jsonrpc=jsonrpc_version,
                    id=request_id,
                    result={"error": {"code": -32600, "message": "Missing 'method' in request"}}
                )
            
            if method == "initialize":
                params = request.get("params", {})
                client_protocol_version = params.get("protocolVersion", "")
                
                return JSONRPCResponse(
                    jsonrpc=jsonrpc_version,
                    id=request_id,
                    result={
                        "protocolVersion": "2025-11-25",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "zymcp",
                            "version": "1.0.0",
                            "title": "ZY MCP Server",
                            "description": "A Model Context Protocol server implementation"
                        }
                    }
                )
            
            elif method == "tools/list":
                tools = await self.list_tools()
                return JSONRPCResponse(
                    jsonrpc=jsonrpc_version,
                    id=request_id,
                    result={
                        "tools": [tool.model_dump(by_alias=True) for tool in tools]
                    }
                )
            
            elif method == "tools/call":
                params = request.get("params", {})
                tool_name = params.get("name")
                
                if not tool_name:
                    return JSONRPCResponse(
                        jsonrpc=jsonrpc_version,
                        id=request_id,
                        result={"error": {"code": -32602, "message": "Missing tool name"}}
                    )
                
                if tool_name not in self.tools:
                    return JSONRPCResponse(
                        jsonrpc=jsonrpc_version,
                        id=request_id,
                        result={"error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}}
                    )
                
                arguments = params.get("arguments", {})
                tool_info = self.tools[tool_name]
                fn = tool_info["fn"]
                
                try:
                    if asyncio.iscoroutinefunction(fn):
                        result = await fn(**arguments)
                    else:
                        result = fn(**arguments)
                    
                    return JSONRPCResponse(
                        jsonrpc=jsonrpc_version,
                        id=request_id,
                        result={"result": result}
                    )
                except Exception as e:
                    return JSONRPCResponse(
                        jsonrpc=jsonrpc_version,
                        id=request_id,
                        result={"error": {"code": -32000, "message": str(e)}}
                    )
            else:
                return JSONRPCResponse(
                    jsonrpc=jsonrpc_version,
                    id=request_id,
                    result={"error": {"code": -32601, "message": f"Unknown method: {method}"}}
                )
        
        return router

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs
    ):
        app = FastAPI(title="MCP Server", version="1.0.0")
        mcp_router = self._create_mcp_router()
        app.mount("/mcp", mcp_router)
        
        @app.get("/")
        async def root():
            return {"message": "MCP Server is running", "docs": "/docs", "mcp": "/mcp"}
        
        uvicorn.run(app, host=host, port=port, **kwargs)

testzymcp = zymcp()

@testzymcp.tool(name="test", title="test", description="test", meta={"test": "test"}, structured_output=True)
def test(TEST: str, OPTIONAL: int = 123) -> str:
    """测试函数"""
    print('test2222')
    return_str= f"test {TEST} {OPTIONAL}"
    return return_str

@testzymcp.tool(name="test2", title="test2", description="只是测试用的函数", meta={"test": "test"}, structured_output=True)
def test2(TEST: str, OPTIONAL: int = 123) -> str:
    return_str= f"这个是自定义的zymcp test {TEST} {OPTIONAL}"
    return return_str

testzymcp.run()