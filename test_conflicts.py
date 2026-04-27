#!/usr/bin/env python
"""Test conflict detection with suggestions."""

from pawpal_system import Owner, Pet, Task, Scheduler

print("=" * 70)
print("TEST: Add multiple tasks to exceed time window")
print("=" * 70)

owner = Owner('J', '08:00', '12:00')  # Only 4 hours available
pet = Pet(name='Mochi', species='dog', age=3)
owner.add_pet(pet)

# Add tasks that will exceed the 4-hour window
t1 = Task(title='Morning walk', duration_minutes=30, priority='high')
t2 = Task(title='Feeding', duration_minutes=20, priority='medium')
t3 = Task(title='Grooming session', duration_minutes=120, priority='high')
t4 = Task(title='Play time', duration_minutes=90, priority='low')  # This should conflict

pet.add_task(t1)
pet.add_task(t2)
pet.add_task(t3)
pet.add_task(t4)

scheduler = Scheduler(owner)

# Generate without daily log - should still show conflicts with suggestions
print("\n--- WITHOUT daily log ---")
plan, conflicts = scheduler.generate_schedule(daily_log=None)

print(f"\nScheduled tasks: {len(plan)}")
for item in plan:
    print(f"  {item['start']} - {item['end']}: {item['task'].title}")

print(f"\nConflicts detected: {len(conflicts)}")
if conflicts:
    for i, conflict in enumerate(conflicts, 1):
        print(f"\n  Conflict {i}:")
        print(f"    {conflict}")
        if "→ Suggestion:" in conflict:
            print(f"    ✓ Suggestion included!")
        else:
            print(f"    ✗ NO SUGGESTION FOUND")
else:
    print("  (No conflicts)")

print("\n" + "=" * 70)
print("TEST: Same scenario WITH daily log")
print("=" * 70)

log = "It is 10:00, and the morning walk was skipped."
plan2, conflicts2 = scheduler.generate_schedule(daily_log=log)

print(f"\nScheduled tasks: {len(plan2)}")
for item in plan2:
    print(f"  {item['start']} - {item['end']}: {item['task'].title}")

print(f"\nConflicts detected: {len(conflicts2)}")
if conflicts2:
    for i, conflict in enumerate(conflicts2, 1):
        print(f"\n  Conflict {i}:")
        print(f"    {conflict}")
        if "→ Suggestion:" in conflict:
            print(f"    ✓ Suggestion included!")
        else:
            print(f"    ✗ NO SUGGESTION FOUND")
else:
    print("  (No conflicts)")

print("\n" + "=" * 70)

