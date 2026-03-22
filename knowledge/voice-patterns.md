# Voice Interface Patterns

## Platform Selection

| Platform | When | Reach | Certification |
|----------|------|-------|--------------|
| Alexa Skills Kit | Smart speakers, Echo ecosystem | 500M+ Alexa devices | Amazon certification required |
| Google Actions | Google Home, Android, smart displays | 1B+ Google Assistant devices | Google review required |
| Twilio Voice/IVR | Phone-based IVR, call centers | Any phone number | No certification |
| Custom NLU (Rasa, Dialogflow CX) | Full control, on-premise, privacy | Any platform | Self-managed |

## Conversational Design Principles

### Turn Structure
```
User turn:  "Alexa, what's my next task?"
System turn: "You have 3 tasks due today. The first is 'Review PR for auth module.' Would you like to hear the next one?"

Rules:
- Keep system turns under 30 seconds of speech
- End with a clear prompt for the user's next action
- Never read more than 3 list items without asking to continue
- Always provide an escape hatch ("say 'stop' to exit")
```

### Intent Modeling
```
Intent taxonomy:
  - Launch intent: entry point ("open task manager")
  - Task intents: CRUD operations ("add task", "list tasks", "complete task")
  - Navigation intents: "next", "previous", "go back", "help", "stop"
  - Confirmation intents: "yes", "no", "cancel"

Each intent needs:
  - 15-30 sample utterances (covering natural variations)
  - Slot/entity definitions (task_name, date, priority)
  - Required vs optional slots
  - Disambiguation prompts for ambiguous input
```

### Entity/Slot Types
```
Built-in:  AMAZON.DATE, AMAZON.NUMBER, AMAZON.City, AMAZON.SearchQuery
Custom:    Priority (high, medium, low), Status (todo, in_progress, done)

Entity resolution:
  "urgent" → Priority.high
  "asap" → Priority.high
  "whenever" → Priority.low
```

## Dialog Management

### State Machine Approach
```
LaunchState → MainMenuState → TaskListState → TaskDetailState
                            → CreateTaskState → ConfirmState
                            → SettingsState

Each state defines:
  - Expected intents (what the user might say here)
  - Response template (what to say back)
  - Transitions (which state to go to next)
  - Context data (what we're tracking in this conversation)
```

### Session Persistence
```
Within session:  store in session attributes (in-memory, per conversation)
Across sessions: store in database (user preferences, last task, history)

Session timeout: Alexa (8 seconds response, 30 seconds idle), Google (similar)
```

### Multi-Turn Context
```
User: "Add a task"
System: "What's the task name?"
User: "Review the PR"           ← slot filling
System: "When is it due?"
User: "Tomorrow"                ← slot filling
System: "I'll add 'Review the PR' due tomorrow. Confirm?"
User: "Yes"                     ← confirmation
System: "Done! Task added."
```

## SSML (Speech Synthesis Markup Language)

```xml
<speak>
  You have <say-as interpret-as="cardinal">3</say-as> tasks due today.
  <break time="500ms"/>
  The first is <emphasis level="moderate">Review PR for auth module</emphasis>.
  <break time="300ms"/>
  Would you like to hear the next one?
</speak>
```

### Key SSML Tags
| Tag | Purpose | Example |
|-----|---------|---------|
| `<break>` | Pause | `<break time="500ms"/>` |
| `<emphasis>` | Stress a word | `<emphasis level="strong">urgent</emphasis>` |
| `<say-as>` | Pronounce as type | `<say-as interpret-as="date">2026-03-22</say-as>` |
| `<prosody>` | Speed/pitch/volume | `<prosody rate="slow">important notice</prosody>` |
| `<audio>` | Play sound effect | `<audio src="soundbank://soundlibrary/..."/>` |

## Voice UX Patterns

### Confirmation Patterns
```
Explicit:   "You want to delete task 'Review PR.' Are you sure?" (destructive actions)
Implicit:   "I've marked 'Review PR' as complete. Next task is..." (safe actions)
None:       "Here's your task list:" (read-only actions)
```

### Error Recovery
```
No match:  "I didn't catch that. You can say 'list tasks', 'add task', or 'help'."
No input:  "Are you still there? Say 'help' for options, or 'stop' to exit."
Repeated:  "I'm having trouble understanding. Let me transfer you to the app." (graceful degradation)
Max 3 retries before graceful exit.
```

### Progressive Disclosure
```
BAD:  "You can list tasks, add tasks, complete tasks, delete tasks, set priorities,
       filter by date, assign to team members, or check your schedule."

GOOD: "You can manage tasks or check your schedule. Which would you like?"
      → "For tasks, you can list, add, or complete them. What would you like to do?"
```

## Voice Testing

```
Intent accuracy:   Test each intent with 20+ utterance variations → >95% match rate
Dialog flow:       Automated multi-turn conversation tests (happy path + errors)
Latency:           Response under 8 seconds (Alexa certification requirement)
SSML validation:   Verify SSML renders correctly (no broken tags, natural prosody)
Error recovery:    Test all error paths (no match, no input, invalid slot values)
Regression:        Re-run all tests after model changes
Beta testing:      Real users via Alexa beta testing / Google alpha channel
```

## Platform-Specific Constraints

### Alexa
```
- 8-second response time limit (hard fail if exceeded)
- Session attributes for within-session state (max 24KB)
- APL (Alexa Presentation Language) for multimodal (Echo Show)
- Account linking via OAuth for user identity
- ISP (In-Skill Purchases) for monetization
- ASK CLI for deployment: `ask deploy`
```

### Google Actions
```
- Conversational Actions (webhook-based) or App Actions (Android deep links)
- Rich responses: cards, carousels, media, tables (for smart displays)
- Account linking via Google Sign-In
- Transactions API for purchases
- gactions CLI for deployment
```

### Twilio Voice
```
- TwiML (Twilio Markup Language) for call flow
- <Gather> for DTMF and speech input
- <Say> for text-to-speech (or <Play> for pre-recorded audio)
- Studio for visual IVR builder
- SIP trunking for enterprise PBX integration
- Programmable Voice API for dynamic call routing
```

## Anti-Patterns

```
- Reading long lists without pagination ("You have 47 tasks...")
- Requiring exact phrasing ("Say 'add task' exactly")
- No help command implemented
- No stop/cancel handler (user is trapped)
- Assuming a screen is present (voice-only devices have no display)
- Using technical jargon in spoken responses
- Not handling silence/timeout gracefully
```
