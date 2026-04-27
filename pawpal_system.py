"""
pawpal_system.py
----------------
Core domain classes for PawPal+.

New in this version:
  - RAG-grounded LLM calls via Gemini 2.5 Flash (with fallback)
  - Confidence scoring embedded in every LLM response
  - Structured logging (file + console) for every AI call
  - Full error handling / guardrails on the LLM path
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Suppress the google.generativeai deprecation warning
warnings.filterwarnings('ignore', message='.*google.generativeai.*')

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

import requests

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_log_file = LOG_DIR / "pawpal.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("pawpal_system")

# ---------------------------------------------------------------------------
# RAG retriever (lazy-loaded so tests that don't need it stay fast)
# ---------------------------------------------------------------------------
_KB_PATH = Path(__file__).parent / "pet_care_kb.json"
_retriever = None  # initialised on first use


def _get_retriever():
    """Return the singleton RAGRetriever, initialising it on first call."""
    global _retriever
    if _retriever is None:
        try:
            from rag_retriever import RAGRetriever
            _retriever = RAGRetriever(_KB_PATH, top_k=3)
            logger.info("RAG retriever initialised from %s", _KB_PATH)
        except Exception as exc:
            logger.warning("Could not initialise RAG retriever: %s", exc)
            _retriever = _NullRetriever()
    return _retriever


class _NullRetriever:
    """Fallback when the knowledge base is unavailable."""
    def retrieve(self, query: str, species_filter=None):
        return []

    def format_context(self, docs):
        return "(Knowledge base unavailable.)"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _parse_time(value: str) -> int:
    """Convert HH:MM string to minutes since midnight."""
    try:
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.hour * 60 + parsed.minute
    except ValueError as exc:
        raise ValueError(f"Invalid time format: {value}. Expected HH:MM") from exc


def _format_time(minutes: int) -> str:
    """Convert minutes since midnight back to HH:MM."""
    minutes = max(0, min(minutes, 24 * 60 - 1))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low", "medium", "high"
    frequency: Optional[str] = None
    preferred_time: Optional[str] = None
    start_time: Optional[str] = None
    due_date: Optional[str] = None
    is_completed: bool = False

    def __post_init__(self):
        if self.start_time is not None:
            _parse_time(self.start_time)
        if self.due_date is not None:
            try:
                datetime.fromisoformat(self.due_date)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid due_date format: {self.due_date}. Expected YYYY-MM-DD"
                ) from exc
        if self.duration_minutes <= 0:
            raise ValueError("Task duration_minutes must be > 0")
        if self.priority.lower() not in ("low", "medium", "high"):
            raise ValueError("Task priority must be 'low', 'medium', or 'high'")
        self.priority = self.priority.lower()

    def mark_complete(self) -> Optional["Task"]:
        self.is_completed = True
        if self.frequency in ("daily", "weekly"):
            days = 1 if self.frequency == "daily" else 7
            next_date = datetime.today().date() + timedelta(days=days)
            return Task(
                title=self.title,
                duration_minutes=self.duration_minutes,
                priority=self.priority,
                frequency=self.frequency,
                preferred_time=self.preferred_time,
                start_time=self.start_time,
                due_date=next_date.isoformat(),
                is_completed=False,
            )
        return None

    def mark_incomplete(self) -> None:
        self.is_completed = False

    def get_info(self) -> str:
        status = "Done" if self.is_completed else "Pending"
        freq = f", {self.frequency}" if self.frequency else ""
        pref = f", preferred: {self.preferred_time}" if self.preferred_time else ""
        return (
            f"Task('{self.title}', {self.duration_minutes}m, priority={self.priority}{freq}{pref}) "
            f"[{status}]"
        )

    def __repr__(self) -> str:
        return self.get_info()


@dataclass
class Pet:
    name: str
    species: str
    age: int
    breed: Optional[str] = None
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        if not isinstance(task, Task):
            raise TypeError("pet.add_task requires a Task instance")
        self.tasks.append(task)

    def remove_task(self, title: str) -> bool:
        for i, task in enumerate(self.tasks):
            if task.title == title:
                del self.tasks[i]
                return True
        return False

    def get_info(self) -> str:
        breed = f" ({self.breed})" if self.breed else ""
        return f"{self.name}{breed}: {self.species}, {self.age} years old, {len(self.tasks)} tasks"

    def get_pending_tasks(self) -> List[Task]:
        return [t for t in self.tasks if not t.is_completed]

    def complete_task(self, title: str) -> Optional[Task]:
        for task in self.tasks:
            if task.title == title:
                next_task = task.mark_complete()
                if next_task is not None:
                    self.add_task(next_task)
                return next_task
        raise ValueError(f"Task '{title}' not found")


class Owner:
    def __init__(self, name: str, available_start: str, available_end: str):
        self.name = name
        self.available_start = available_start
        self.available_end = available_end
        self.pets: List[Pet] = []
        self._start_minutes = _parse_time(available_start)
        self._end_minutes = _parse_time(available_end)
        if self._start_minutes >= self._end_minutes:
            raise ValueError("available_start must be before available_end")

    def set_availability(self, available_start: str, available_end: str) -> None:
        start_minutes = _parse_time(available_start)
        end_minutes = _parse_time(available_end)
        if start_minutes >= end_minutes:
            raise ValueError("available_start must be before available_end")
        self.available_start = available_start
        self.available_end = available_end
        self._start_minutes = start_minutes
        self._end_minutes = end_minutes

    def add_pet(self, pet: Pet) -> None:
        if not isinstance(pet, Pet):
            raise TypeError("Owner.add_pet requires a Pet instance")
        if any(p.name == pet.name for p in self.pets):
            raise ValueError(f"Owner already has a pet named '{pet.name}'")
        self.pets.append(pet)

    def get_pet(self, name: str) -> Optional[Pet]:
        return next((p for p in self.pets if p.name == name), None)

    def get_all_tasks(self, include_completed: bool = False) -> List[Task]:
        tasks = [t for pet in self.pets for t in pet.tasks]
        return tasks if include_completed else [t for t in tasks if not t.is_completed]

    def get_schedule_window(self) -> Tuple[str, str]:
        return self.available_start, self.available_end



genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
_MODEL = "gemini-2.5-flash"   # free tier, fast

def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    model = genai.GenerativeModel(
        model_name=_MODEL,
        system_instruction=system_prompt,
    )
    response = model.generate_content(user_prompt)
    return response.text


def _normalize_llm_text(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    lines = [line.strip() for line in text.splitlines()]
    if len(lines) > 1:
        return "\n".join(line for line in lines if line)
    return re.sub(r"\s+", " ", text)


def _strip_code_fence(text: str) -> str:
    """Remove a simple Markdown code fence if the model wraps its answer."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```"):
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
    return "\n".join(lines).strip()


def _confidence_from_retrieval(docs: List[Dict]) -> float:
    """Estimate confidence from retrieved KB relevance when the LLM returns prose."""
    if not docs:
        return 0.55
    best_score = max(float(doc.get("score", 0.0)) for doc in docs)
    return max(0.55, min(0.9, 0.65 + best_score))


def _parse_llm_response(raw: str, default_confidence: float) -> Tuple[str, float]:
    """
    Prefer human-readable prose, while still accepting the older JSON wrapper
    used by tests and previous prompt versions.
    """
    candidate = _strip_code_fence(raw)
    if not candidate:
        return "", default_confidence

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return _normalize_llm_text(candidate), default_confidence

    if isinstance(parsed, dict):
        response_text = _normalize_llm_text(str(parsed.get("response", "")))
        confidence = float(parsed.get("confidence", default_confidence))
        return response_text, max(0.0, min(1.0, confidence))

    return _normalize_llm_text(candidate), default_confidence


def _rule_based_fallback(prompt: str) -> str:
    """Simple keyword-driven fallback used when the API key is absent or the call fails."""
    p = prompt.lower()
    if "conflict" in p or "cannot fit" in p:
        return (
            "Consider shortening lower-priority tasks or splitting grooming sessions "
            "across two days to free up time for essential care."
        )
    if "skip" in p or "miss" in p or "exercise" in p or "walk" in p:
        return (
            "If outdoor exercise was missed, try a 10-minute indoor fetch or obedience "
            "training session to keep your pet mentally and physically stimulated."
        )
    if "feed" in p or "food" in p or "meal" in p:
        return (
            "Keep feeding times consistent — irregular meal schedules can cause "
            "digestive upset, especially in dogs."
        )
    return (
        "Ensure your pet has adequate time for both physical exercise and mental "
        "stimulation throughout the day. Consistency is key."
    )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
    EXERCISE_KEYWORDS = ["walk", "play", "run", "fetch", "exercise", "activity"]

    def __init__(self, owner: Owner):
        if not isinstance(owner, Owner):
            raise TypeError("Scheduler requires an Owner instance")
        self.owner = owner
        self.schedule: List[Dict] = []
        self._last_confidence: Optional[float] = None  # set after each LLM call

    # ------------------------------------------------------------------
    # Task management helpers
    # ------------------------------------------------------------------

    def add_task(self, task: Task, pet_name: str) -> None:
        if not isinstance(task, Task):
            raise TypeError("Scheduler.add_task requires a Task instance")
        pet = self.owner.get_pet(pet_name)
        if pet is None:
            raise ValueError(f"Pet named '{pet_name}' not found")
        pet.add_task(task)

    def _sort_tasks(self, tasks: List[Task]) -> List[Task]:
        return sorted(
            tasks,
            key=lambda t: (self.PRIORITY_RANK.get(t.priority, 3), t.duration_minutes, t.title),
        )

    def sort_by_time(self, tasks: List[Task]) -> List[Task]:
        return sorted(
            tasks,
            key=lambda t: _parse_time(t.start_time) if t.start_time else float("inf"),
        )

    def filter_tasks(
        self, completed: Optional[bool] = None, pet_name: Optional[str] = None
    ) -> List[Task]:
        pets = self.owner.pets
        if pet_name is not None:
            pet = self.owner.get_pet(pet_name)
            if pet is None:
                return []
            pets = [pet]
        filtered = []
        for pet in pets:
            for task in pet.tasks:
                if completed is not None and task.is_completed != completed:
                    continue
                filtered.append(task)
        return filtered

    def detect_conflicts(self) -> List[str]:
        tasks = self.owner.get_all_tasks(include_completed=True)
        time_map: Dict[str, List[Task]] = defaultdict(list)
        for task in tasks:
            if task.start_time:
                time_map[task.start_time].append(task)
        warnings = []
        for time_slot, slot_tasks in time_map.items():
            if len(slot_tasks) > 1:
                titles = [t.title for t in slot_tasks]
                warnings.append(
                    f"Conflict at {time_slot}: {len(slot_tasks)} tasks scheduled concurrently "
                    f"({', '.join(titles)})."
                )
        return warnings

    # ------------------------------------------------------------------
    # RAG-grounded LLM helper
    # ------------------------------------------------------------------

    def _query_llm_with_rag(
        self,
        user_prompt: str,
        rag_query: str,
        species_filter: Optional[str] = None,
        max_tokens: int = 400,
    ) -> Tuple[str, float]:
        """
        Retrieve relevant KB documents, inject them into the prompt, call the LLM,
        and return human-readable advice with an internal confidence score.

        Returns
        -------
        (response_text, confidence_score)
            confidence_score is 0.0-1.0.
        """
        retriever = _get_retriever()
        docs = retriever.retrieve(rag_query, species_filter=species_filter)
        context = retriever.format_context(docs)

        system_prompt = (
            "You are PawPal+, an expert pet care assistant. "
            "Use the retrieved knowledge below to ground your response. "
            "Reply in plain, human-readable text. Do not use JSON, code fences, "
            "logs, or internal metadata. Keep the response concise and actionable. "
            "If the knowledge is incomplete, say so simply.\n\n"
            f"{context}"
        )

        t0 = time.perf_counter()
        raw = ""
        default_confidence = _confidence_from_retrieval(docs)
        try:
            raw = _call_gemini(system_prompt, user_prompt)
            elapsed = time.perf_counter() - t0
            logger.info(
                "LLM call OK | model=%s | elapsed=%.2fs | prompt_len=%d | rag_docs=%d",
                _MODEL, elapsed, len(user_prompt), len(docs),
            )
            response_text, confidence = _parse_llm_response(raw, default_confidence)
        except ValueError as exc:
            logger.warning("LLM response could not be parsed (%s); using raw text.", exc)
            response_text = _normalize_llm_text(raw) if raw else ""
            confidence = 0.5
        except RuntimeError as exc:
            elapsed = time.perf_counter() - t0
            logger.warning(
                "LLM call FAILED (%.2fs): %s - falling back to rule-based response.", elapsed, exc
            )
            # Use the retrieved context to pick the best rule-based answer
            combined_prompt = f"{user_prompt}\n\nContext:\n{context}"
            response_text = _rule_based_fallback(combined_prompt)
            confidence = 0.4  # lower confidence for fallback

        if not response_text:
            response_text = _rule_based_fallback(user_prompt)
            confidence = 0.3

        self._last_confidence = confidence
        logger.info("LLM confidence score: %.2f", confidence)
        return response_text, confidence

    # ------------------------------------------------------------------
    # Public AI methods
    # ------------------------------------------------------------------

    def get_pet_tips(self, pet: Pet, daily_log: Optional[str] = None) -> str:
        """
        Generate RAG-grounded care tips for a pet.

        The returned string always includes the confidence score so users know
        how reliable the advice is.
        """
        pending = [t for t in pet.tasks if not t.is_completed]
        task_titles = [t.title for t in pending] or ["none"]
        breed_clause = f" ({pet.breed})" if pet.breed else ""

        rag_query = (
            f"{pet.species} {pet.breed or ''} {pet.age} year old care tips "
            + " ".join(task_titles)
        )
        user_prompt = (
            f"Give 2-3 concise, actionable care tips for {pet.name}, "
            f"a {pet.age}-year-old {pet.species}{breed_clause}. "
            f"Pending tasks: {', '.join(task_titles)}."
        )
        if daily_log:
            user_prompt += f"\nContext from today's log: {daily_log}"

        response, confidence = self._query_llm_with_rag(
            user_prompt=user_prompt,
            rag_query=rag_query,
            species_filter=pet.species,
        )
        return f"{response}\n\n_(AI confidence: {confidence:.0%})_"

    def _get_conflict_resolution_suggestion(
        self, conflict_msg: str, skipped_tasks: List[Task]
    ) -> str:
        """Return conflict message with a RAG-grounded resolution suggestion appended."""
        skipped_titles = [t.title for t in skipped_tasks] or ["none"]
        rag_query = f"scheduling conflict resolution skipped {' '.join(skipped_titles)}"
        user_prompt = (
            f"Scheduling conflict: {conflict_msg}\n"
            f"Previously skipped tasks: {', '.join(skipped_titles)}.\n"
            "Suggest one concise action to resolve or mitigate this conflict."
        )
        response, confidence = self._query_llm_with_rag(
            user_prompt=user_prompt,
            rag_query=rag_query,
        )
        return f"{conflict_msg} → Suggestion: {response} (confidence: {confidence:.0%})"

    # ------------------------------------------------------------------
    # Schedule generation
    # ------------------------------------------------------------------

    def generate_schedule(
        self,
        daily_log: Optional[str] = None,
        include_completed: bool = False,
    ) -> Tuple[List[Dict], List[str]]:
        """Generate a daily schedule for all pending tasks."""
        tasks = self.owner.get_all_tasks(include_completed=include_completed)
        if not tasks:
            self.schedule = []
            return [], []

        tasks = [t for t in tasks if t.duration_minutes > 0]
        tasks = self._sort_tasks(tasks)
        if daily_log:
            tasks = self._reweight_tasks_based_on_log(tasks, daily_log)

        current_minute = _parse_time(self.owner.available_start)
        if daily_log:
            parsed = self._parse_daily_log_current_time(daily_log)
            if parsed is not None:
                current_minute = parsed

        end_minute = _parse_time(self.owner.available_end)
        skipped_tasks = self._detect_skipped_tasks_from_log(daily_log, tasks) if daily_log else []

        plan: List[Dict] = []
        conflicts: List[str] = []

        for task in tasks:
            if task.is_completed:
                continue
            task_end = current_minute + task.duration_minutes
            pet_of_task = next((p for p in self.owner.pets if task in p.tasks), None)
            pet_name = pet_of_task.name if pet_of_task else "unknown"

            if task_end > end_minute:
                conflict_msg = (
                    f"Task '{task.title}' for {pet_name} ({task.duration_minutes}m) "
                    "cannot fit in remaining time."
                )
                # Always add LLM-based resolution suggestion (skipped_tasks may be empty if no daily log)
                conflict_msg = self._get_conflict_resolution_suggestion(
                    conflict_msg, skipped_tasks
                )
                logger.warning("Schedule conflict: %s", conflict_msg)
                conflicts.append(conflict_msg)
                continue

            plan.append(
                {
                    "pet": pet_name,
                    "task": task,
                    "start": _format_time(current_minute),
                    "end": _format_time(task_end),
                    "priority": task.priority,
                }
            )
            current_minute = task_end

        self.schedule = plan
        logger.info(
            "Schedule generated: %d tasks placed, %d conflicts for owner '%s'",
            len(plan), len(conflicts), self.owner.name,
        )
        return plan, conflicts

    def explain_plan(self) -> str:
        if not self.schedule:
            return "No schedule generated yet or no tasks available."
        lines = [
            f"Schedule for {self.owner.name} "
            f"({self.owner.available_start}-{self.owner.available_end}):"
        ]
        for entry in self.schedule:
            lines.append(
                f"{entry['start']} - {entry['end']}: {entry['task'].title} "
                f"for {entry['pet']} [priority={entry['priority']}]"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Daily-log analysis helpers
    # ------------------------------------------------------------------

    def _parse_daily_log_current_time(self, daily_log: str) -> Optional[int]:
        match = re.search(r"[Ii]t is (\d{1,2}):(\d{2})", daily_log)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))
        return None

    def _task_is_exercise_related(self, task: Task) -> bool:
        title_lower = task.title.lower()
        return any(kw in title_lower for kw in self.EXERCISE_KEYWORDS)

    def _detect_skipped_tasks_from_log(
        self, daily_log: str, all_tasks: List[Task]
    ) -> List[Task]:
        skipped = []
        log_lower = daily_log.lower()
        for task in all_tasks:
            if task.is_completed:
                continue
            tl = task.title.lower()
            patterns = [
                f"skip {tl}", f"skip the {tl}", f"missed {tl}", f"missed the {tl}",
                f"cancelled {tl}", f"{tl} was skipped", f"{tl} was missed",
                f"the {tl} was skipped", f"the {tl} was missed",
            ]
            if any(p in log_lower for p in patterns):
                skipped.append(task)
        return skipped

    def _reweight_tasks_based_on_log(
        self, tasks: List[Task], daily_log: str
    ) -> List[Task]:
        skipped = self._detect_skipped_tasks_from_log(daily_log, tasks)
        if not any(self._task_is_exercise_related(t) for t in skipped):
            return tasks
        exercise = [t for t in tasks if self._task_is_exercise_related(t)]
        non_exercise = [t for t in tasks if not self._task_is_exercise_related(t)]
        return exercise + non_exercise
