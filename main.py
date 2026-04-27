from pawpal_system import Owner, Pet, Task, Scheduler

# CLI-level guardrails and observability
from guardrails import check_for_medical_redflags, sanitize_text
from evaluation import record_call


def main():
    owner = Owner(name="Jordan", available_start="07:00", available_end="19:00")

    pet1 = Pet(name="Mochi", species="dog", age=3, breed="Shiba")
    pet2 = Pet(name="Nori", species="cat", age=5, breed="Domestic Short Hair")

    owner.add_pet(pet1)
    owner.add_pet(pet2)

    # tasks for Mochi (out-of-order scheduling times)
    task1 = Task(title="Morning walk", duration_minutes=30, priority="high", frequency="daily", preferred_time="morning", start_time="08:00")
    task2 = Task(title="Feed", duration_minutes=15, priority="medium", frequency="daily", preferred_time="morning", start_time="08:00")  # conflict intentionally overlaps

    # task for Nori (out-of-order scheduling times)
    task3 = Task(title="Litter box clean", duration_minutes=20, priority="high", frequency="daily", preferred_time="afternoon", start_time="18:00")
    task4 = Task(title="Play session", duration_minutes=25, priority="low", frequency="daily", preferred_time="evening", start_time="12:30")

    scheduler = Scheduler(owner)
    scheduler.add_task(task1, pet_name="Mochi")
    scheduler.add_task(task2, pet_name="Mochi")
    scheduler.add_task(task3, pet_name="Nori")
    scheduler.add_task(task4, pet_name="Nori")

    plan, conflicts = scheduler.generate_schedule()

    print("Today's Schedule")
    print("-----------------")
    for entry in plan:
        print(
            f"{entry['start']} - {entry['end']}: {entry['pet']} -> {entry['task'].title} "
            f"[{entry['priority']}]"
        )

    print("\nPlan explanation:\n")
    plan_text = scheduler.explain_plan()
    print(sanitize_text(plan_text))
    try:
        record_call("cli_generate_schedule", sanitize_text(plan_text, max_len=1000), scheduler._last_confidence or 0.0, fallback=False, extra={"placed": len(plan), "conflicts": len(conflicts)})
    except Exception:
        pass

    # Demonstrate new sorting and filtering helpers
    all_tasks = owner.get_all_tasks(include_completed=True)
    print("\nAll tasks unsorted:")
    for t in all_tasks:
        print(f"  {t.title} @ {t.start_time} ({'Done' if t.is_completed else 'Pending'})")

    time_sorted = scheduler.sort_by_time(all_tasks)
    print("\nAll tasks sorted by start_time:")
    for t in time_sorted:
        print(f"  {t.title} @ {t.start_time}")

    print("\nFilter tasks (pet_name='Mochi', completed=False):")
    for t in scheduler.filter_tasks(completed=False, pet_name="Mochi"):
        print(f"  {t.title} @ {t.start_time} ({'Done' if t.is_completed else 'Pending'})")

    conflicts = scheduler.detect_conflicts()
    print("\nConflict detection:")
    if conflicts:
        for msg in conflicts:
            print("  WARNING:", sanitize_text(msg))
    else:
        print("  No conflicts detected.")

    # Demonstrate pet tips retrieval with guardrail check
    tips = scheduler.get_pet_tips(pet1)
    red = check_for_medical_redflags(tips)
    print("\nPet tips for", pet1.name)
    if red:
        print(sanitize_text(red))
    else:
        print(sanitize_text(tips))


if __name__ == "__main__":
    main()