from dataclasses import dataclass
from typing import Optional


@dataclass
class Pet:
    name: str
    species: str
    age: int
    breed: Optional[str] = None

    def get_info(self) -> str:
        pass


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low", "medium", "high"
    is_completed: bool = False
    preferred_time: Optional[str] = None  # "morning", "afternoon", "evening"

    def mark_complete(self) -> None:
        pass

    def mark_incomplete(self) -> None:
        pass

    def __repr__(self) -> str:
        pass


class Owner:
    def __init__(self, name: str, available_start: str, available_end: str):
        self.name = name
        self.available_start = available_start  # e.g. "08:00"
        self.available_end = available_end      # e.g. "20:00"
        self.pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        pass

    def get_schedule_window(self) -> tuple[str, str]:
        pass


class Scheduler:
    def __init__(self, owner: Owner, pet: Pet):
        self.owner = owner
        self.pet = pet
        self.tasks: list[Task] = []
        self.schedule: list = []

    def add_task(self, task: Task) -> None:
        pass

    def generate_schedule(self) -> list:
        pass

    def explain_plan(self) -> str:
        pass
