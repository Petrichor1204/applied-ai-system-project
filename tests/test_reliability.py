import re

from pawpal_system import Owner, Pet, Task, Scheduler
import guardrails
import evaluation


def test_medical_guardrail():
    # direct pattern detection
    msg = guardrails.check_for_medical_redflags("My cat has not been eating for 2 days and is vomiting")
    assert msg is not None
    assert "veterin" in msg.lower()

    # ensure the scheduler short-circuits LLM calls when log contains red-flag
    owner = Owner("Alice", "08:00", "20:00")
    pet = Pet(name="Milo", species="cat", age=3)
    owner.add_pet(pet)
    pet.add_task(Task(title="feed", duration_minutes=10, priority="high"))
    sched = Scheduler(owner)

    resp = sched.get_pet_tips(pet, daily_log="It is 09:00. My cat has not been eating for 3 days and is vomiting.")
    assert isinstance(resp, str)
    assert "veterin" in resp.lower()
    # include confidence annotation from the short-circuit path
    assert re.search(r"100%|100\%", resp)


def test_evaluation_logging():
    # record a couple of synthetic calls and ensure metrics reflect them
    before = evaluation.get_metrics().get("count", 0)
    evaluation.record_call("test", "ok", 0.7, fallback=True, extra={"tag": "t1"})
    evaluation.record_call("test", "ok2", 0.3, fallback=False, extra={"tag": "t2"})
    metrics = evaluation.get_metrics(last_n=10)
    assert metrics["count"] >= 1
    assert metrics["avg_confidence"] is None or (0.0 <= metrics["avg_confidence"] <= 1.0)
    assert metrics["fallback_rate"] is None or (0.0 <= metrics["fallback_rate"] <= 1.0)
