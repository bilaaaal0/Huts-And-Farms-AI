from typing import List
from pydantic import BaseModel, Field
from langchain_core.tools import tool


class CalculatorInput(BaseModel):
    numbers: List[float] = Field(description="List of numbers to sum.")


@tool("sum_tool", args_schema=CalculatorInput)
def sum_tool(numbers: List[float]) -> float:
    """Sum a list of numbers."""
    return sum(numbers)
