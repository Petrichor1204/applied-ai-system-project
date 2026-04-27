# PawPal+

## Title And Summary

**PawPal+** is an AI-assisted pet care planning app that helps busy pet owners turn scattered care responsibilities into a daily schedule. Users can add pets, assign tasks such as feeding, walking, grooming, play, or litter-box cleaning, and generate a plan based on task priority, duration, available time, and daily updates.

The project matters because pet care is repetitive but easy to disrupt. PawPal+ combines deterministic scheduling logic with retrieval-grounded AI advice, so the system can both build a practical plan and explain what to do when the plan breaks.

## Original Project: Modules 1-3

My original Modules 1-3 project was also called **PawPal+**. Its original goal was to model a pet care planning system with core object-oriented classes: `Owner`, `Pet`, `Task`, and `Scheduler`.

In the early version, PawPal+ could store pets and tasks, sort care tasks by priority, generate a basic daily schedule, and detect simple conflicts. The final version extends that foundation with a Streamlit interface, RAG-based pet care tips, Gemini-powered conflict suggestions, confidence scoring, logging, and automated reliability tests.

## Current Capabilities

- Add pets with name, species, age, and breed.
- Add pet-specific care tasks with duration, priority, frequency, preferred time, and completion status.
- Generate a daily schedule inside the owner's available time window.
- Sort tasks by priority, duration, and title.
- Detect scheduling conflicts when tasks cannot fit.
- Reweight exercise tasks when a daily log says a walk or play session was missed.
- Retrieve pet-care knowledge from `pet_care_kb.json` using a lightweight TF-IDF RAG retriever.
- Generate human-readable AI care tips and conflict suggestions with confidence scores.
- Log AI calls, failures, fallback behavior, and confidence values to `logs/pawpal.log`.

## Architecture Overview

The updated system diagram is in [system_diagram.md](system_diagram.md). It shows the current runtime architecture, class relationships, RAG/AI flow, logging, and test coverage. The older UML image in [uml_final.png](uml_final.png) shows the original object model from the earlier project phase.

- `Owner` stores the user's availability window and owns a list of pets.
- `Pet` stores animal details and that pet's task list.
- `Task` represents one care activity, including priority, duration, recurrence, preferred time, and completion state.
- `Scheduler` coordinates the workflow: it pulls tasks from the owner, sorts them, builds a schedule, detects conflicts, interprets daily logs, and calls AI helpers.

At runtime, the app follows this flow:

```text
Streamlit UI (app.py)
        |
        v
Domain model (Owner, Pet, Task, Scheduler)
        |
        +--> Scheduling and conflict detection
        |
        +--> RAGRetriever (rag_retriever.py)
                  |
                  v
             pet_care_kb.json
        |
        +--> Gemini API, if GEMINI_API_KEY is set
        |
        +--> Rule-based fallback, if AI is unavailable
        |
        v
logs/pawpal.log
```

The deterministic scheduler handles the core plan because schedule generation should be predictable and testable. The AI layer is used for advice, explanation, and conflict mitigation, where flexible language is useful.

## Setup Instructions

### 1. Clone The Repository

```bash
git clone <repository-url>
cd applied-ai-system-final
```

### 2. Create And Activate A Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Optional: Add A Gemini API Key

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

If no key is provided, PawPal+ still runs using rule-based fallback advice. This is intentional so the app can be demonstrated and tested without paid API access.

### 5. Run The Streamlit App

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

### 6. Run The Tests

```bash
.venv/bin/python -m pytest tests/test_pawpal.py -q
```

## Sample Interactions

These examples show representative inputs and outputs from the current system. Exact Gemini wording may vary, but the behavior is tested with mocked AI responses and fallback paths.

### Example 1: Pet Care Tips

Input:

```text
Pet: Mochi
Species: dog
Age: 3
Breed: Shiba
Pending task: Morning walk, 30 minutes, high priority
Action: Get pet tips
```

Resulting AI output:

```text
Keep Mochi's walk consistent and aim for regular daily exercise. Add a short training or sniffing session if the walk has to be shortened, since Shibas benefit from both physical activity and mental stimulation.

_(AI confidence: 90%)_
```

### Example 2: Schedule Generation

Input:

```text
Owner availability: 08:00-12:00
Pet: Mochi
Tasks:
- Grooming session, 120 minutes, high priority
- Morning walk, 30 minutes, high priority
- Feeding, 20 minutes, medium priority
- Play time, 90 minutes, low priority
Action: Generate schedule
```

Resulting schedule:

```text
08:00 - 08:30: Morning walk for Mochi [priority=high]
08:30 - 10:30: Grooming session for Mochi [priority=high]
10:30 - 10:50: Feeding for Mochi [priority=medium]
10:50 - 12:00: Play time cannot fully fit, so it is reported as a conflict.
```

Resulting AI conflict suggestion:

```text
Task 'Play time' for Mochi (90m) cannot fit in remaining time. Suggestion: Shorten the play session or split it into smaller activities later in the day. (confidence: 81%)
```

### Example 3: Daily Log Adjustment

Input:

```text
Daily log: It is 14:00, and the morning walk was skipped because of rain.
Tasks:
- Feeding, 15 minutes, medium priority
- Morning walk, 30 minutes, low priority
Action: Generate schedule
```

Resulting behavior:

```text
14:00 - 14:30: Morning walk for Mochi [priority=low]
14:30 - 14:45: Feeding for Mochi [priority=medium]
```

The scheduler starts at 14:00 because it parsed the daily log. It also moves the exercise-related task earlier because the log says the walk was skipped.

## Design Decisions

- **Object-oriented core:** I kept the original `Owner`, `Pet`, `Task`, and `Scheduler` structure because it maps cleanly to the real-world domain. This makes the code easy to explain and test.
- **Scheduler pulls tasks from pets:** I chose not to let `Scheduler` maintain a separate master task list. The owner owns pets, pets own tasks, and the scheduler reads from that source of truth.
- **Deterministic scheduling before AI:** The app uses rules for ordering and fitting tasks because schedules need predictable behavior. AI is used for tips and conflict suggestions, not for silently deciding the whole plan.
- **Lightweight RAG instead of a vector database:** `rag_retriever.py` uses TF-IDF over a small JSON knowledge base. This is simpler and easier to run locally than a full embedding database, though it is less semantically powerful.
- **Confidence scoring and fallback:** The AI path reports confidence and falls back to rule-based advice when the API key is missing or an AI call fails. The trade-off is that fallback advice is more generic, but the app remains usable.
- **Simple conflict model:** The scheduler reports tasks that cannot fit in the time window and separately detects identical `start_time` conflicts. A future version could detect overlapping manually assigned time ranges more deeply.

## Testing Summary

The current test suite is in [tests/test_pawpal.py](tests/test_pawpal.py). It covers core scheduling behavior, recurring tasks, conflict detection, daily-log parsing, RAG retrieval, confidence scoring, fallback behavior, plain-text AI responses, conflict suggestions, and log-file creation.

Latest local run:

```text
20 out of 20 tests passed.
```

What worked:

- The scheduler correctly sorts tasks and respects the owner's time window.
- Daily logs can adjust the current start time and prioritize missed exercise tasks.
- RAG retrieval returns relevant pet-care documents from `pet_care_kb.json`.
- The AI layer handles plain human-readable responses.
- Confidence values stay within the expected `0.0` to `1.0` range.
- Missing API keys trigger fallback advice instead of crashing the app.

What did not work at first:

- Earlier tests still referenced an old Anthropic function name after the implementation moved to Gemini.
- Some tests looked for the knowledge base in `tests/knowledge/pet_care_kb.json`, while the actual file lives at the project root.
- The first AI prompt required JSON, but Gemini sometimes returned normal prose. I changed the prompt to request human-readable text and kept JSON parsing only as a compatibility fallback.

What I learned:

- AI features need measurable reliability, not just impressive demos.
- Logging, confidence scores, and fallback paths make AI behavior easier to debug.
- Keeping deterministic business logic separate from generative advice makes the system more trustworthy.

## Reflection

This project taught me that AI is most useful when it is part of a system, not the entire system. The scheduler, data model, tests, and logs create structure; the AI adds flexible advice on top of that structure.

I also learned that being the lead architect means making judgment calls about what AI should and should not control. For PawPal+, I wanted the schedule to be explainable and testable, so I used normal code for planning and used AI only where natural language helped the user.

The biggest problem-solving lesson was that reliability comes from iteration. Each bug, stale reference, or confusing AI response revealed where the system needed a clearer boundary, a better test, or a simpler design.

## Project Files

- [app.py](app.py): Streamlit user interface.
- [pawpal_system.py](pawpal_system.py): domain classes, scheduler, AI helper, confidence scoring, and logging.
- [rag_retriever.py](rag_retriever.py): TF-IDF retriever for pet-care knowledge.
- [pet_care_kb.json](pet_care_kb.json): local knowledge base used for RAG.
- [tests/test_pawpal.py](tests/test_pawpal.py): automated reliability and behavior tests.
- [main.py](main.py): console demo.
- [system_diagram.md](system_diagram.md): updated architecture and class diagram.
- [uml_final.png](uml_final.png): earlier UML diagram from the original project phase.

## Demo Screenshots

![PawPal+ demo screenshot 1](<Screenshot 2026-03-31 at 11.04.08 AM.png>)

![PawPal+ demo screenshot 2](<Screenshot 2026-03-31 at 11.04.20 AM.png>)
