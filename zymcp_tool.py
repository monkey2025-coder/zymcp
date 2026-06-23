from typing import Any, Generic, Literal, TypeVar, overload, Annotated, get_type_hints, get_origin, get_args, Union
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from pydantic import BaseModel, ConfigDict, Field, FileUrl, TypeAdapter
from pydantic.alias_generators import to_camel
import asyncio
import inspect
from fastapi import FastAPI, APIRouter, HTTPException
import uvicorn


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
    """提取函数返回类型，返回符合MCP协议的outputSchema格式"""
    try:
        hints = get_type_hints(fn)
        return_hint = hints.get('return')
        
        if return_hint is None:
            return {"type": "object", "properties": {}}
        
        json_type = get_json_type(return_hint)
        
        return {
            "type": "object",
            "properties": {
                "result": {
                    "type": json_type
                }
            },
            "required": ["result"]
        }
    except Exception:
        return {"type": "object", "properties": {}}
