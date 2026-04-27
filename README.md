# PawPal+ (Module 2 Project)

PawPal+ is a Streamlit-based pet care planning assistant designed to help busy pet owners manage and schedule daily care tasks for their pets. By inputting pet details, task priorities, and available time windows, the app generates an optimized daily schedule, explains the reasoning, and highlights any scheduling conflicts.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

## Features

PawPal+ implements several key algorithms and features for effective pet care scheduling:

- **Task Sorting Algorithm**: Tasks are sorted by priority (high > medium > low), then by duration (shorter first), and finally by title alphabetically. This ensures high-priority tasks are scheduled first.
- **Time Window Scheduling**: Tasks are packed sequentially into the owner's available time window (e.g., 08:00-20:00), starting from the earliest available slot. Tasks that exceed the remaining time are skipped.
- **Conflict Detection and Warnings**: If a task cannot fit into the schedule due to time constraints, it is flagged as a conflict with a descriptive message (e.g., "Task 'X' for Pet Y (30m) cannot fit in remaining time"). The UI displays these warnings prominently.
- **Task Completion Tracking**: Tasks can be marked as complete or incomplete, filtering them from future schedules.
- **Pet-Specific Task Assignment**: Tasks are assigned to specific pets, allowing multi-pet households to have individualized care plans.
- **Preferred Time Support**: Tasks can specify preferred times (morning, afternoon, evening), though the current algorithm prioritizes priority over preferences.
- **Schedule Explanation**: Generates a human-readable explanation of the schedule, including task timings and priorities.
- **Session Persistence**: Uses Streamlit's session state to persist owner, pets, and tasks across app interactions.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd pawpal-starter
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Usage

1. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Open your browser to the provided URL (usually `http://localhost:8501`).

3. Add pets and tasks via the UI forms.

4. Generate a schedule to see the optimized plan and any conflicts.

### Example Workflow

- Add an owner (pre-configured as "Jordan" with 08:00-20:00 availability).
- Add pets (e.g., "Mochi" the dog).
- Add tasks (e.g., "Morning walk" - 30m, high priority).
- Click "Generate schedule" to view the sorted plan in a table format, with explanations and warnings.

## Testing

Run the test suite to verify core functionality:

```bash
python -m pytest
```

Tests cover task completion, pet task addition, and basic scheduling behaviors.

## Architecture

The app is built with the following components:

- **pawpal_system.py**: Core classes (`Pet`, `Task`, `Owner`, `Scheduler`) implementing the business logic.
- **app.py**: Streamlit UI for user interaction.
- **main.py**: Demo script for testing the system.
- **tests/test_pawpal.py**: Unit tests for key behaviors.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Make changes and add tests.
4. Submit a pull request.

## License

This project is for educational purposes. See LICENSE for details.

## Testing PawPal+

Run the test suite with:
```bash
.venv/bin/python -m pytest tests/test_pawpal.py -q
```

The tests cover critical scheduling behaviors including:
- Task completion and status management
- Pet task management (adding/removing tasks)
- Recurring task logic (daily tasks create next occurrences when completed)
- Conflict detection (warnings for tasks scheduled at the same time)
- Sorting correctness (tasks returned in chronological order by start time)

## AI Reliability Evidence

PawPal+ includes several checks so the AI path can be measured instead of only appearing to work:

- **Automated tests:** `tests/test_pawpal.py` verifies RAG retrieval, confidence scoring, fallback behavior when `GEMINI_API_KEY` is missing, plain-text LLM responses, conflict suggestions, and log-file creation.
- **Confidence scoring:** every AI helper stores a confidence score from `0.0` to `1.0`; normal LLM prose uses retrieved-document relevance, while fallback responses receive lower confidence.
- **Logging and error handling:** LLM calls log model name, elapsed time, prompt length, retrieved document count, confidence, and fallback failures to `logs/pawpal.log`.
- **Human evaluation:** sample outputs should be reviewed for usefulness, factual grounding in `pet_care_kb.json`, and whether the advice is concise enough for a pet owner to act on.

Latest local reliability run: **20 out of 20 tests passed**. The AI fallback path worked when the Gemini API key was missing, plain-text AI output was accepted without JSON parsing warnings, and confidence scores stayed inside the expected `0.0` to `1.0` range. Reliability is strongest when the knowledge base has relevant context; confidence is intentionally lower when context or API access is missing.

**Demo**
![alt text](<Screenshot 2026-03-31 at 11.04.08 AM.png>)
![alt text](<Screenshot 2026-03-31 at 11.04.20 AM.png>)
