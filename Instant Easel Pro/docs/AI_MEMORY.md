# How the AI remembers (AI Coding > Projects, AI Chat > Chats)

A small local model can only see so much at once (about 8,000 tokens), so memory is split into layers.
What matters every time is always there; everything else is looked up only when a question needs it.

| Layer | Where | When the AI sees it |
|---|---|---|
| **Your rules** | `user_rules.md`, one per user (each copy of the app is its own user) | Every request |
| **Project memory** | `project.md`: what it does, rules, never-do, what to look for, commands | Every request |
| **Summary so far** | `summary.md`: the older conversation, compressed | Every request |
| **Recent messages** | The last 8, word for word | Every request |
| **Notes** | `notes.md`: "remember: …" and facts you approved | When they match the question |
| **Older messages** | Every message ever, word for word, searchable | When they match the question |
| **Project library** | Your code and documents, indexed | When they match the question |
| **The web** | A quick search (off / when needed / always) | When the answer needs current information |

**Tips (from current best practice):**

- **Keep project memory short and specific.** It's sent with every request.
- **Prohibitions:** write "Never …" for them; it works better than "prefer …".
- **Skip the obvious:** leave out what the code already shows and generic advice like "write clean code".
- **"Update memory from this talk":** the AI drafts changes to the project memory. You edit them and save, or cancel.
- **Compressing:** it happens by itself when a conversation gets long. Older messages stay searchable word for word.

All of it lives on the AI drive (Settings > AI Storage), under `memory/<coding|chat>/<user>/projects/<name>/`.
