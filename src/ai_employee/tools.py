"""Thin typed LangChain tools; all business decisions live in CompanyService."""

from langchain_core.tools import StructuredTool

from .contracts import CONTRACTS
from .service import CompanyService


def build_tools(service: CompanyService) -> dict[str, StructuredTool]:
    def wrap(name):
        def invoke(**arguments):
            return service.execute(name, **arguments)
        return invoke

    def invalid_arguments(_error):
        return {"ok": False, "error": {"code": "invalid_arguments", "message": "Arguments must match the tool schema."}}

    return {name: StructuredTool.from_function(
        func=wrap(name), name=name, description=description, args_schema=schema,
        handle_validation_error=invalid_arguments,
    ) for name, (schema, description) in CONTRACTS.items()}
