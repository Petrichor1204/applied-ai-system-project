**How I used AI**
I used AI to generate the initial system architecture (the main classes) and write the RAG retrieval from scratch. I used specific files for context and gave the rubric t m eet making sure my prompts were not vague. 

Debugging: Example, I caught JSON parsing issue in _query_llm_with_rag
. I used AI-generated tests to surface bugs the AI introduced. 

Design: I used AI to pick the right tool for RAG.

**What are the limitations or biases in your system?**
The bias is that the kb  has more dog content than cat content, so cat owners may get shallower tips. Another thing is that the confidence scores come from the LLM rating itself, meaning it can be wrong and sitll report high confidence. 

**Could your AI be misused, and how would you prevent that?**
The system could treat a problem like a user entering a log about their cat not eaten in 3 days as a scheduling problem instead of a vet emergency. To prevent that, PawPal+ implements a deterministic medical guardrail that scans user inputs and daily logs for red-flag phrases (e.g., "not eating", "vomiting", "difficulty breathing"). When a red flag is detected the system short-circuits any LLM call and returns a high-confidence, hard-coded directive to consult a veterinarian. Guardrail activations are recorded to `logs/reliability.jsonl` for auditing, and automated tests (`tests/test_reliability.py`) verify the detector and logging behavior.

**What surprised you while testing your AI's reliability?**
The malformed JSON test exposed something subtle: when the LLM returns a response that isn't valid JSON, the system still works, but the raw text sometimes leaked internal prompt artifacts into the response string. That's a hidden quality bug that the confidence score alone wouldn't catch — you'd need to also log and inspect the raw output.

**describe your collaboration with AI during this project. Identify one instance when the AI gave a helpful suggestion and one instance where its suggestion was flawed or incorrect.**
Helpful suggestion: When I proposed RAG, Claude suggested using TF-IDF with numpy instead of a vector database like ChromaDB. That was genuinely the right call for my project — no extra dependencies, runs anywhere, and the retrieval quality is good enough for a 14-document KB. 

Flawed suggestion: Claude suggested Anthropic API when I already had Gemini set up and working. If I hadn't checked it, I would have gotten errors later because of mismatches.

**What I used for Evaluation of the LLM**
I used confidence scoring + automated tests + structured logging as a three-layer reliability system.