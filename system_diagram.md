# PawPal+ Updated System Diagram

This diagram reflects the current codebase: Streamlit UI, domain model, scheduler, RAG retriever, Gemini AI path, rule-based fallback, logging, and tests.

## Runtime Architecture

```mermaid
flowchart TD
    User["User / Pet Owner"] --> UI["Streamlit UI\napp.py"]

    UI --> Owner["Owner\navailability + pets"]
    UI --> Pet["Pet\nname, species, age, breed"]
    UI --> Task["Task\ntitle, duration, priority,\nfrequency, preferred time,\ncompletion state"]
    UI --> Scheduler["Scheduler\npawpal_system.py"]

    Owner --> Pet
    Pet --> Task
    Scheduler --> Owner
    Scheduler --> Task

    Scheduler --> Schedule["Generated Schedule\nordered task plan"]
    Scheduler --> Conflicts["Conflict Warnings\ncannot fit / same start time"]
    Scheduler --> DailyLog["Daily Log Parsing\ncurrent time + skipped tasks"]

    Scheduler --> AIHelper["AI Helper\n_query_llm_with_rag"]
    AIHelper --> Retriever["RAGRetriever\nrag_retriever.py"]
    Retriever --> KB["Pet Care Knowledge Base\npet_care_kb.json"]
    Retriever --> Context["Retrieved Context\ntop relevant documents"]

    Context --> AIHelper
    AIHelper --> Gemini{"GEMINI_API_KEY set?"}
    Gemini -->|Yes| GeminiAPI["Gemini 2.5 Flash\nhuman-readable advice"]
    Gemini -->|No / failure| Fallback["Rule-Based Fallback\nsafe generic advice"]

    GeminiAPI --> AIOutput["Pet Tips / Conflict Suggestions\nwith confidence score"]
    Fallback --> AIOutput

    Scheduler --> Logs["Structured Logs\nlogs/pawpal.log"]
    AIHelper --> Logs

    Tests["Automated Tests\ntests/test_pawpal.py"] --> Owner
    Tests --> Pet
    Tests --> Task
    Tests --> Scheduler
    Tests --> Retriever
    Tests --> AIHelper
```

## Core Class Relationships

```mermaid
classDiagram
    class Owner {
        +str name
        +str available_start
        +str available_end
        +List~Pet~ pets
        +set_availability(start, end)
        +add_pet(pet)
        +get_pet(name)
        +get_all_tasks(include_completed)
        +get_schedule_window()
    }

    class Pet {
        +str name
        +str species
        +int age
        +str breed
        +List~Task~ tasks
        +add_task(task)
        +remove_task(title)
        +get_pending_tasks()
        +complete_task(title)
        +get_info()
    }

    class Task {
        +str title
        +int duration_minutes
        +str priority
        +str frequency
        +str preferred_time
        +str start_time
        +str due_date
        +bool is_completed
        +mark_complete()
        +mark_incomplete()
        +get_info()
    }

    class Scheduler {
        +Owner owner
        +List schedule
        +add_task(task, pet_name)
        +sort_by_time(tasks)
        +filter_tasks(completed, pet_name)
        +detect_conflicts()
        +generate_schedule(daily_log, include_completed)
        +explain_plan()
        +get_pet_tips(pet, daily_log)
    }

    class RAGRetriever {
        +Path kb_path
        +int top_k
        +List documents
        +retrieve(query, species_filter)
        +format_context(docs)
    }

    class GeminiAPI {
        +generate_content(prompt)
    }

    Owner "1" o-- "*" Pet : owns
    Pet "1" o-- "*" Task : has
    Scheduler --> Owner : reads pets and tasks
    Scheduler --> Task : sorts and schedules
    Scheduler --> RAGRetriever : retrieves context
    RAGRetriever --> GeminiAPI : provides grounded context
    Scheduler --> GeminiAPI : requests advice
```

## Reliability And Observability

```mermaid
flowchart LR
    Tests["tests/test_pawpal.py"] --> Unit["Unit Checks\nTask, Pet, Owner, Scheduler"]
    Tests --> RAG["RAG Checks\nKB loads + relevant docs"]
    Tests --> AI["AI Reliability Checks\nconfidence + fallback + plain text"]
    Tests --> LogCheck["Log Check\npawpal.log exists"]

    AI --> Confidence["Confidence Score\n0.0 to 1.0"]
    AI --> Fallback["Fallback Behavior\nno API key / failed call"]
    AI --> PlainText["Human-Readable Output\nno JSON required"]

    Runtime["Runtime AI Calls"] --> Logs["logs/pawpal.log"]
    Runtime --> Confidence
    Runtime --> Fallback
```
