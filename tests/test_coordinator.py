import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from coordinator import Task, coordinate, ANSWER

def test_deps_order():
    tasks = [Task("a", "explore", 1000), Task("b", "plan", 1000, deps=["a"])]
    r = coordinate(tasks, global_budget=5000)
    ids = [x["task"] for x in r["assignments"]]
    assert ids.index("a") < ids.index("b")
    assert r["answer"] == ANSWER

if __name__ == "__main__":
    test_deps_order(); print("ok")
