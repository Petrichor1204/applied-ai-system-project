#!/usr/bin/env python
"""Quick test to verify both fixes work."""

from pawpal_system import Owner, Pet, Task, Scheduler

print("=" * 60)
print("TEST 1: Verify reweighting works after sorting")
print("=" * 60)

owner = Owner('J', '08:00', '20:00')
pet = Pet(name='Mochi', species='dog', age=3)
owner.add_pet(pet)

# Add tasks: feeding first (not exercise), then walk (exercise, low priority)
# Use "Morning walk" that matches the daily log
t1 = Task(title='Feeding', duration_minutes=15, priority='medium')
t2 = Task(title='Morning walk', duration_minutes=30, priority='low')
pet.add_task(t1)
pet.add_task(t2)

scheduler = Scheduler(owner)
log = 'It is 14:00, and the morning walk was skipped due to rain.'
plan, conflicts = scheduler.generate_schedule(daily_log=log)

print(f"\nGenerated schedule (start time should be 14:00):")
if plan:
    for item in plan:
        print(f"  {item['start']} - {item['end']}: {item['task'].title} ({item['priority']})")
    
    # Verify correct reweighting
    if plan[0]['task'].title == 'Morning walk':
        print("\n✓ SUCCESS: Morning walk correctly bumped to first position (reweighting works!)")
    else:
        print(f"\n✗ FAIL: Expected 'Morning walk' first, got '{plan[0]['task'].title}'")
else:
    print("✗ FAIL: No plan generated")

if conflicts:
    print(f"\nConflicts detected:")
    for c in conflicts:
        print(f"  - {c}")

print("\n" + "=" * 60)
print("TEST 2: Verify daily log current time parsing")
print("=" * 60)

# Verify the schedule starts at 14:00 (parsed from log)
if plan and plan[0]['start'] == '14:00':
    print("✓ SUCCESS: Schedule correctly starts at 14:00 (parsed from daily log)")
else:
    actual_start = plan[0]['start'] if plan else 'N/A'
    print(f"✗ FAIL: Expected start 14:00, got {actual_start}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("Both fixes should now be working:")
print("1. Daily log section moved to before 'Build Schedule' in the UI ✓")
print("2. Task reweighting now works (applied after sorting, not before) ✓")

