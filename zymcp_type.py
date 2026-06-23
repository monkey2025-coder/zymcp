from typing import Any, Generic, Literal, TypeVar, overload, Annotated, get_type_hints, get_origin, get_args, Union
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from pydantic import BaseModel, ConfigDict, Field, FileUrl, TypeAdapter
from pydantic.alias_generators import to_camel


_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

RequestId = Annotated[int, Field(strict=True)] | str

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
    id: RequestId | None = None
    result: dict[str, Any]