from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from pawpal_system import Owner, Pet, Task, Scheduler
import streamlit as st

# UI-level guardrails and observability
from guardrails import check_for_medical_redflags, sanitize_text
from evaluation import record_call

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


# (Pet Care Tips moved below the Daily Log so it can use the actual user input)

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

st.subheader("Pet Care Tips")
if owner.pets:
    tip_pet = st.selectbox("Get tips for pet", [pet.name for pet in owner.pets], key="tip_pet")
    if st.button("Get pet tips"):
        selected_pet = owner.get_pet(tip_pet)
        if selected_pet:
            # Check for medical red-flags in the daily log or pet summary before calling LLM
            combined = (daily_log or "") + " " + selected_pet.get_info()
            red = check_for_medical_redflags(combined)
            if red:
                st.warning(red)
                record_call("guardrail_medical_ui", sanitize_text(red), 1.0, fallback=False, extra={"pet": selected_pet.name})
            else:
                tips = scheduler.get_pet_tips(selected_pet, daily_log=daily_log if daily_log else None)
                display = sanitize_text(tips, max_len=2000)
                st.info(display)
                try:
                    record_call("ui_get_pet_tips", sanitize_text(display, max_len=1000), scheduler._last_confidence or 0.0, fallback=False, extra={"pet": selected_pet.name})
                except Exception:
                    st.error("Failed to record telemetry for this call.")
else:
    st.warning("Add a pet to get care tips.")

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
            st.warning(sanitize_text(conflict))
        try:
            record_call(
                "generate_schedule",
                sanitize_text(scheduler.explain_plan(), max_len=1000),
                scheduler._last_confidence or 0.0,
                fallback=False,
                extra={"placed": len(plan), "conflicts": len(conflicts)},
            )
        except Exception:
            st.error("Failed to record schedule telemetry.")
    st.info("Tip: Consider adjusting task durations, priorities, or your available time window to fit more tasks.")