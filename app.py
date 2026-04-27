from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from pawpal_system import Owner, Pet, Task, Scheduler
import streamlit as st

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

# Initialize or restore Owner and Scheduler in session state
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_start="08:00", available_end="20:00")

if "scheduler" not in st.session_state:
    st.session_state.scheduler = Scheduler(st.session_state.owner)

owner = st.session_state.owner
scheduler = st.session_state.scheduler

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

st.subheader("Owner Availability")
col1, col2 = st.columns(2)
with col1:
    available_start = st.time_input(
        "Available start",
        value=datetime.strptime(owner.available_start, "%H:%M").time(),
        key="available_start",
    )
with col2:
    available_end = st.time_input(
        "Available end",
        value=datetime.strptime(owner.available_end, "%H:%M").time(),
        key="available_end",
    )

if st.button("Update availability"):
    try:
        owner.set_availability(
            available_start.strftime("%H:%M"),
            available_end.strftime("%H:%M"),
        )
        st.success(f"Updated availability to {owner.available_start} - {owner.available_end}.")
    except ValueError as exc:
        st.error(str(exc))

st.markdown(
    f"**Current schedule window:** {owner.available_start} - {owner.available_end}"
)
st.info(
    "If you want to see conflict warnings, make the window smaller or add more total task minutes."
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Add a Pet")
new_pet_name = st.text_input("New pet name", value="Mochi")
new_pet_species = st.selectbox("Species", ["dog", "cat", "other"], key="pet_species")
new_pet_age = st.number_input("Age", min_value=0, max_value=30, value=3, step=1)
new_pet_breed = st.text_input("Breed", value="Shiba")

if st.button("Add pet"):
    owner.add_pet(Pet(name=new_pet_name, species=new_pet_species, age=new_pet_age, breed=new_pet_breed))
    st.success(f"Added pet {new_pet_name}.")

if owner.pets:
    st.markdown("**Current pets:**")
    for pet in owner.pets:
        st.write(pet.get_info())
else:
    st.info("No pets yet. Add your first pet.")

st.divider()

st.subheader("Pet Care Tips")
if owner.pets:
    tip_pet = st.selectbox("Get tips for pet", [pet.name for pet in owner.pets], key="tip_pet")
    if st.button("Get pet tips"):
        selected_pet = owner.get_pet(tip_pet)
        if selected_pet:
            tips = scheduler.get_pet_tips(selected_pet)
            st.info(tips)
else:
    st.warning("Add a pet to get care tips.")

st.divider()

st.subheader("Add a Task")
if not owner.pets:
    st.warning("Add a pet before adding tasks.")
else:
    task_pet = st.selectbox("Assign to pet", [pet.name for pet in owner.pets])
    task_title = st.text_input("Task title", value="Morning walk", key="task_title")
    task_duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20, key="task_duration")
    task_priority = st.selectbox("Priority", ["low", "medium", "high"], index=2, key="task_priority")
    task_preferred_time = st.selectbox("Preferred time", ["morning", "afternoon", "evening"], index=0)

    if st.button("Add task"):
        new_task = Task(
            title=task_title,
            duration_minutes=int(task_duration),
            priority=task_priority,
            preferred_time=task_preferred_time,
        )
        scheduler.add_task(new_task, pet_name=task_pet)
        st.success(f"Task '{task_title}' added to {task_pet}.")

st.divider()

st.subheader("Daily Log & Schedule Adjustment")
daily_log = st.text_area(
    "Daily log (e.g., 'It is 2 PM, and the 1 PM walk was skipped because of a thunderstorm.')",
    value="",
    key="daily_log",
    help="Describe what has happened so far today. The scheduler will re-analyze your remaining tasks based on this."
)

st.divider()

st.subheader("Build Schedule")
if st.button("Generate schedule"):
    plan, conflicts = scheduler.generate_schedule(daily_log=daily_log if daily_log else None)
    if not plan:
        st.info("No schedule was generated (no tasks or no available time).")
    else:
        st.success("Schedule generated successfully!")
        # Display schedule as a table
        schedule_data = [
            {
                "Time": f"{item['start']} - {item['end']}",
                "Pet": item['pet'],
                "Task": item['task'].title,
                "Priority": item['priority'],
                "Duration (min)": item['task'].duration_minutes,
            }
            for item in plan
        ]
        st.table(schedule_data)
        st.write("---")
        st.text(scheduler.explain_plan())

    # Show conflicts if any
    if conflicts:
        st.warning("⚠️ Scheduling Conflicts Detected:")
        for conflict in conflicts:
            st.warning(conflict)
        st.info("Tip: Consider adjusting task durations, priorities, or your available time window to fit more tasks.")