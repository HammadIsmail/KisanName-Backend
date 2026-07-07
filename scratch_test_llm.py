from crewai import Task
from typing import Any

def my_callback(output: Any):
    print("Callback called!", output)

try:
    t = Task(description="test", expected_output="test", callback=my_callback)
    print("Success, Task accepts callback")
except Exception as e:
    print("Failed:", e)
