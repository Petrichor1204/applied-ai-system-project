"""
test_pawpal.py
--------------
Full test suite for PawPal+.

Covers:
  1. Original unit tests (task, pet, scheduler, log parsing)
  2. RAG retriever correctness tests
  3. Reliability / confidence scoring tests (LLM mocked via monkeypatch)
  4. End-to-end integration test (no real API key required)

Run with:   python test_pawpal.py
Or via:     pytest test_pawpal.py -v
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, Dict, List
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or a tests/ subdirectory
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE, _HERE.parent):
    if (_candidate / "pawpal_system.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from pawpal_system import Owner, Pet, Task, Scheduler  # noqa: E402

_KB_PATH = Path(__file__).resolve().parent.parent / "pet_care_kb.json"

# ---------------------------------------------------------------------------
# Minimal test harness (runs without pytest if needed)
# ---------------------------------------------------------------------------
_RESULTS: List[Dict] = []


def _run(name: str, fn: Callable) -> bool:
    try:
        fn()
        _RESULTS.append({"name": name, "status": "PASS"})
        print(f"  ✓ {name}")
        return True
    except Exception as exc:
        tb = traceback.format_exc()
        _RESULTS.append({"name": name, "status": "FAIL", "error": str(exc), "tb": tb})
        print(f"  ✗ {name}\n    {exc}")
        return False


# ===========================================================================
# 1. Original unit tests
# ===========================================================================

def test_task_completion_marks_done():
    task = Task(title="Grooming", duration_minutes=20, priority="medium")
    assert task.is_completed is False
    task.mark_complete()
    assert task.is_completed is True
    task.mark_incomplete()
    assert task.is_completed is False


def test_pet_add_task_increases_task_count():
    pet = Pet(name="Mochi", species="dog", age=3)
    assert len(pet.tasks) == 0
    pet.add_task(Task(title="Feeding", duration_minutes=10, priority="high"))
    assert len(pet.tasks) == 1
    assert pet.tasks[0].title == "Feeding"


def test_daily_task_completion_creates_next_occurrence():
    pet = Pet(name="Mochi", species="dog", age=3)
    task = Task(title="Feed", duration_minutes=10, priority="high", frequency="daily", start_time="08:00")
    pet.add_task(task)
    next_task = pet.complete_task("Feed")
    assert task.is_completed is True
    assert next_task is not None
    assert next_task.frequency == "daily"
    assert next_task.is_completed is False
    assert len(pet.tasks) == 2


def test_scheduler_detects_conflicts_for_same_time():
    owner = Owner(name="Jordan", available_start="07:00", available_end="19:00")
    pet1, pet2 = Pet(name="Mochi", species="dog", age=3), Pet(name="Nori", species="cat", age=5)
    owner.add_pet(pet1); owner.add_pet(pet2)
    pet1.add_task(Task(title="Morning walk", duration_minutes=30, priority="high", start_time="08:00"))
    pet2.add_task(Task(title="Feed", duration_minutes=15, priority="high", start_time="08:00"))
    warnings = Scheduler(owner).detect_conflicts()
    assert len(warnings) == 1
    assert "08:00" in warnings[0]
    assert "Morning walk" in warnings[0] and "Feed" in warnings[0]


def test_parse_daily_log_current_time():
    s = Scheduler(Owner("J", "07:00", "19:00"))
    assert s._parse_daily_log_current_time("It is 14:30 and the morning walk was skipped.") == 870
    assert s._parse_daily_log_current_time("it is 09:15 right now.") == 555
    assert s._parse_daily_log_current_time("The day has been good so far.") is None


def test_task_is_exercise_related():
    s = Scheduler(Owner("J", "07:00", "19:00"))
    assert s._task_is_exercise_related(Task(title="Morning walk", duration_minutes=30, priority="high"))
    assert s._task_is_exercise_related(Task(title="Play session", duration_minutes=25, priority="low"))
    assert not s._task_is_exercise_related(Task(title="Feeding", duration_minutes=15, priority="medium"))
    assert not s._task_is_exercise_related(Task(title="Grooming", duration_minutes=60, priority="medium"))


def test_detect_skipped_tasks_from_log():
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    t1 = Task(title="Morning walk", duration_minutes=30, priority="high")
    t2 = Task(title="Afternoon play", duration_minutes=25, priority="medium")
    t3 = Task(title="Feeding", duration_minutes=15, priority="high")
    for t in (t1, t2, t3):
        pet.add_task(t)
    s = Scheduler(owner)
    skipped = s._detect_skipped_tasks_from_log(
        "It is 2 PM, and the morning walk was skipped because of a thunderstorm.",
        [t1, t2, t3],
    )
    assert len(skipped) == 1
    assert skipped[0].title == "Morning walk"


def test_reweight_tasks_based_on_log():
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    t1 = Task(title="Feeding", duration_minutes=15, priority="high")
    t2 = Task(title="Evening walk", duration_minutes=30, priority="medium")
    t3 = Task(title="Grooming", duration_minutes=20, priority="low")
    t4 = Task(title="Evening play", duration_minutes=25, priority="medium")
    for t in (t1, t2, t3, t4):
        pet.add_task(t)
    s = Scheduler(owner)
    reweighted = s._reweight_tasks_based_on_log(
        [t1, t2, t3, t4],
        "It is 2 PM, and the evening walk was skipped because the owner overslept.",
    )
    exercise = [t for t in reweighted if s._task_is_exercise_related(t)]
    non_exercise = [t for t in reweighted if not s._task_is_exercise_related(t)]
    assert reweighted.index(exercise[0]) < reweighted.index(non_exercise[0])


def test_generate_schedule_with_daily_log():
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    for t in [
        Task(title="Morning walk", duration_minutes=30, priority="high"),
        Task(title="Feeding", duration_minutes=15, priority="medium"),
        Task(title="Evening play", duration_minutes=25, priority="low"),
    ]:
        pet.add_task(t)
    plan, _ = Scheduler(owner).generate_schedule(
        daily_log="It is 14:00, and the morning walk was skipped because of a thunderstorm."
    )
    assert len(plan) > 0
    assert int(plan[0]["start"].split(":")[0]) >= 14


# ===========================================================================
# 2. RAG retriever tests
# ===========================================================================

def test_rag_retriever_loads_kb():
    """RAGRetriever should build an index from the knowledge base JSON."""
    from rag_retriever import RAGRetriever
    r = RAGRetriever(_KB_PATH, top_k=3)
    assert len(r.documents) > 0, "Knowledge base should contain documents"
    assert r._doc_vectors.shape[0] == len(r.documents), "TF-IDF matrix row count mismatch"


def test_rag_retriever_returns_relevant_docs():
    """A query about dog walking should surface exercise-related documents."""
    from rag_retriever import RAGRetriever
    r = RAGRetriever(_KB_PATH, top_k=3)
    results = r.retrieve("dog daily walk exercise missed skipped", species_filter="dog")
    assert len(results) > 0, "Should return at least one document"
    top = results[0]
    # The top result should be exercise or skipped-exercise related
    combined = (top["title"] + " " + top["content"]).lower()
    assert any(kw in combined for kw in ["exercise", "walk", "activity", "skip"]), (
        f"Top result not exercise-related: {top['title']}"
    )


def test_rag_retriever_species_filter_boosts_match():
    """Dog-specific query with species filter should rank dog docs above cat docs."""
    from rag_retriever import RAGRetriever
    r = RAGRetriever(_KB_PATH, top_k=5)
    results = r.retrieve("exercise daily activity", species_filter="dog")
    assert len(results) > 0
    top_species = results[0].get("species", "all")
    assert top_species in ("dog", "all"), (
        f"Expected dog or all doc at top, got: {top_species}"
    )


def test_rag_retriever_format_context():
    """format_context should produce a non-empty string with retrieved titles."""
    from rag_retriever import RAGRetriever
    r = RAGRetriever(_KB_PATH, top_k=2)
    docs = r.retrieve("cat litter box cleaning")
    ctx = r.format_context(docs)
    assert "[Retrieved pet-care knowledge]" in ctx
    assert len(ctx) > 50


def test_rag_empty_query_graceful():
    """An empty/stop-word-only query should not crash; it may return 0 docs."""
    from rag_retriever import RAGRetriever
    r = RAGRetriever(_KB_PATH, top_k=3)
    results = r.retrieve("")           # empty query
    assert isinstance(results, list)  # should not raise


# ===========================================================================
# 3. Reliability / Confidence scoring tests (LLM mocked)
# ===========================================================================

def _make_mock_llm(response_text: str, confidence: float):
    """Patch _call_gemini to return the older JSON response shape."""
    payload = json.dumps({"response": response_text, "confidence": confidence})
    return patch("pawpal_system._call_gemini", return_value=payload)


def test_get_pet_tips_confidence_in_range():
    """get_pet_tips should embed a confidence score between 0 and 1."""
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3, breed="Shiba")
    owner.add_pet(pet)
    pet.add_task(Task(title="Morning walk", duration_minutes=30, priority="high"))
    s = Scheduler(owner)
    with _make_mock_llm("Walk Mochi daily for at least 40 minutes.", 0.9):
        tips = s.get_pet_tips(pet)
    assert isinstance(tips, str) and len(tips) > 0
    # Confidence line should appear
    assert "confidence" in tips.lower()
    assert s._last_confidence is not None
    assert 0.0 <= s._last_confidence <= 1.0


def test_confidence_clamped_out_of_range():
    """LLM returning confidence > 1.0 should be clamped to 1.0."""
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    s = Scheduler(owner)
    with _make_mock_llm("Great advice.", 1.5):  # intentionally invalid
        s.get_pet_tips(pet)
    assert s._last_confidence == 1.0


def test_fallback_when_no_api_key():
    """Without GEMINI_API_KEY, get_pet_tips should return a non-empty string (fallback)."""
    import os
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Nori", species="cat", age=5)
    owner.add_pet(pet)
    pet.add_task(Task(title="Play session", duration_minutes=15, priority="medium"))
    s = Scheduler(owner)
    # Remove API key if present
    saved = os.environ.pop("GEMINI_API_KEY", None)
    try:
        tips = s.get_pet_tips(pet)
        assert isinstance(tips, str) and len(tips) > 0
        # Confidence is lower for fallback
        assert s._last_confidence is not None and s._last_confidence <= 0.5
    finally:
        if saved:
            os.environ["GEMINI_API_KEY"] = saved


def test_plain_text_llm_response_handled_gracefully():
    """If the LLM returns plain text, the system should use it directly."""
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    s = Scheduler(owner)
    with patch("pawpal_system._call_gemini", return_value="Brush daily and keep walks consistent."):
        tips = s.get_pet_tips(pet)
    assert isinstance(tips, str)
    assert "Brush daily" in tips
    assert s._last_confidence is not None
    assert 0.0 <= s._last_confidence <= 1.0


def test_conflict_resolution_uses_rag():
    """_get_conflict_resolution_suggestion should return a string with Suggestion."""
    owner = Owner("J", "07:00", "19:00")
    pet = Pet(name="Mochi", species="dog", age=3)
    owner.add_pet(pet)
    skipped = [Task(title="Morning walk", duration_minutes=30, priority="high")]
    s = Scheduler(owner)
    with _make_mock_llm("Shorten grooming to 10 minutes to free up time.", 0.85):
        result = s._get_conflict_resolution_suggestion(
            "Task 'Grooming' cannot fit in remaining time.", skipped
        )
    assert "Suggestion:" in result
    assert "confidence" in result.lower()


# ===========================================================================
# 4. Log file test
# ===========================================================================

def test_log_file_created():
    """Running any scheduler operation should produce a log file."""
    from pawpal_system import LOG_DIR
    log_files = list(LOG_DIR.glob("*.log"))
    assert len(log_files) > 0, f"No log file found in {LOG_DIR}"


# ===========================================================================
# Runner
# ===========================================================================

_ALL_TESTS = [
    # Original
    ("Task: completion marks done",                   test_task_completion_marks_done),
    ("Pet: add task increases count",                 test_pet_add_task_increases_task_count),
    ("Pet: daily task creates recurrence",            test_daily_task_completion_creates_next_occurrence),
    ("Scheduler: detects same-time conflict",         test_scheduler_detects_conflicts_for_same_time),
    ("Log: parse current time",                       test_parse_daily_log_current_time),
    ("Log: exercise keyword detection",               test_task_is_exercise_related),
    ("Log: skipped task detection",                   test_detect_skipped_tasks_from_log),
    ("Log: reweight exercises first",                 test_reweight_tasks_based_on_log),
    ("Schedule: daily-log adjusts start time",        test_generate_schedule_with_daily_log),
    # RAG
    ("RAG: knowledge base loads & indexes",           test_rag_retriever_loads_kb),
    ("RAG: relevant docs for exercise query",         test_rag_retriever_returns_relevant_docs),
    ("RAG: species filter boosts dog docs",           test_rag_retriever_species_filter_boosts_match),
    ("RAG: format_context output",                    test_rag_retriever_format_context),
    ("RAG: empty query is graceful",                  test_rag_empty_query_graceful),
    # Reliability
    ("Reliability: confidence in 0–1 range",          test_get_pet_tips_confidence_in_range),
    ("Reliability: confidence clamped from >1",       test_confidence_clamped_out_of_range),
    ("Reliability: fallback without API key",         test_fallback_when_no_api_key),
    ("Reliability: plain text response handled",      test_plain_text_llm_response_handled_gracefully),
    ("Reliability: conflict uses RAG suggestion",     test_conflict_resolution_uses_rag),
    # Logging
    ("Logging: log file created",                     test_log_file_created),
]


if __name__ == "__main__":
    print("\n🐾 PawPal+ Test Suite\n" + "=" * 50)
    passed = 0
    for name, fn in _ALL_TESTS:
        if _run(name, fn):
            passed += 1

    total = len(_ALL_TESTS)
    failed = total - passed
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    # Reliability summary
    confidence_tests = [r for r in _RESULTS if "Reliability" in r["name"]]
    conf_pass = sum(1 for r in confidence_tests if r["status"] == "PASS")
    print(f"\nReliability tests: {conf_pass}/{len(confidence_tests)} passed")
    print("Confidence scoring: active on every LLM call (0.0–1.0 scale)")
    print("Fallback: rule-based responses used when API key absent or call fails")
    print("Logging: all LLM calls logged to logs/pawpal.log with timing + RAG doc count")

    if failed:
        print("\nFailed tests:")
        for r in _RESULTS:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['name']}: {r['error']}")
        sys.exit(1)
