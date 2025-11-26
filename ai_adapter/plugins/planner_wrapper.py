# ai_adapter/plugins/planner_wrapper.py
from ai_adapter.planner.self_loop import Planner, SAFE_INTENTS_DEFAULT

def run(goal: str, steps: int = 8) -> int:
    try:
        planner = Planner(allowed_intents=set(SAFE_INTENTS_DEFAULT), max_steps=int(steps), confirm=False)
        planner.run(goal)
        return 0
    except Exception as e:
        print(f"Planner error: {e}")
        return 1

