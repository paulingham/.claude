---
name: "voice-scaffold"
description: "Use when user wants to Scaffold a voice skill/action for Alexa, Google Actions, or Twilio IVR. Generates project structure, intent model, handler stubs, SSML templates, and test harness."
context: fork
agent: software-engineer
argument-hint: "Voice platform and skill purpose (e.g., 'Alexa task management skill')"
---

# Voice Scaffold

## What This Skill Does

Scaffolds a voice skill or IVR flow: project structure, intent/entity model, handler stubs with SSML, dialog management, test harness, and deployment config. Produces a working skeleton that can be built out via TDD.

## When to Invoke

- Building a new voice skill (Alexa, Google Actions)
- Adding IVR/phone channel (Twilio Voice)
- Adding voice channel to an existing omnichannel product

## Process

### Step 1: Determine Voice Platform

| Signal | Platform |
|--------|----------|
| `ask-sdk` in deps or `skill.json` | Alexa Skills Kit |
| `@assistant/conversation` or `actions.yaml` | Google Actions |
| `twilio` in deps or TwiML files | Twilio Voice |
| User specifies | As specified |

### Step 2: Generate Project Structure

**Alexa:**
```
skill/
  models/
    en-US.json          — Interaction model (intents, slots, utterances)
  lambda/
    src/
      handlers/         — Intent handlers (LaunchHandler, TaskListHandler, etc.)
      interceptors/     — Request/response interceptors (logging, localization)
      util/             — SSML builders, session helpers, API clients
    index.ts            — Handler registration
  skill.json            — Skill manifest
  ask-resources.json    — ASK CLI config
```

**Google Actions:**
```
actions/
  actions.yaml          — Action definitions
  custom/
    intents/            — Intent definitions with training phrases
    types/              — Entity/type definitions
    scenes/             — Scene definitions (dialog flow)
    global/             — Global handlers (fallback, no-match)
  webhooks/
    src/
      handlers/         — Fulfillment handlers per scene
      util/             — Response builders, session management
    index.ts
```

**Twilio:**
```
src/
  handlers/
    incoming-call.ts    — Entry point handler
    gather-input.ts     — DTMF and speech input handlers
    task-menu.ts        — IVR menu handlers
  flows/
    main-flow.json      — Studio flow definition (if using Studio)
  twiml/
    templates/          — Reusable TwiML response templates
  util/
    speech.ts           — Text-to-speech helpers
    dtmf.ts             — DTMF input mapping
```

### Step 3: Generate Intent/Interaction Model

Define intents based on the skill's domain:

```json
{
  "intents": [
    {
      "name": "LaunchIntent",
      "samples": ["open {app_name}", "start {app_name}", "launch {app_name}"]
    },
    {
      "name": "ListItemsIntent",
      "samples": ["list my {item_type}", "show me my {item_type}", "what are my {item_type}"],
      "slots": [{ "name": "item_type", "type": "ItemType" }]
    },
    {
      "name": "CreateItemIntent",
      "samples": ["add a {item_type}", "create a new {item_type} called {item_name}"],
      "slots": [
        { "name": "item_type", "type": "ItemType" },
        { "name": "item_name", "type": "AMAZON.SearchQuery", "required": true }
      ]
    },
    { "name": "AMAZON.HelpIntent", "samples": [] },
    { "name": "AMAZON.StopIntent", "samples": [] },
    { "name": "AMAZON.CancelIntent", "samples": [] },
    { "name": "AMAZON.FallbackIntent", "samples": [] }
  ]
}
```

Generate 15-30 sample utterances per intent covering natural variations.

### Step 4: Generate Handler Stubs

Each handler follows the pattern:
```typescript
export const ListTasksHandler = {
  canHandle(input) {
    return input.requestEnvelope.request.type === 'IntentRequest'
      && input.requestEnvelope.request.intent.name === 'ListTasksIntent';
  },
  async handle(input) {
    const tasks = await taskService.listForUser(getUserId(input));
    const speech = buildTaskListSSML(tasks);
    return input.responseBuilder
      .speak(speech)
      .reprompt('Would you like to hear more, or add a new task?')
      .getResponse();
  }
};
```

Include stubs for: Launch, Help, Stop, Cancel, Fallback, SessionEnded, and Error handlers.

### Step 5: Generate SSML Templates

```typescript
function buildTaskListSSML(tasks: Task[]): string {
  if (tasks.length === 0) {
    return '<speak>You have no tasks. Would you like to add one?</speak>';
  }
  const count = tasks.length;
  const first = tasks[0].title;
  return `<speak>
    You have <say-as interpret-as="cardinal">${count}</say-as> tasks.
    <break time="300ms"/>
    The first is <emphasis level="moderate">${first}</emphasis>.
    <break time="200ms"/>
    Would you like to hear the next one?
  </speak>`;
}
```

### Step 6: Generate Test Harness

```typescript
describe('ListTasksHandler', () => {
  it('lists tasks when user has tasks', async () => {
    const input = buildMockInput('ListTasksIntent');
    mockTaskService.listForUser.mockResolvedValue([{ title: 'Review PR' }]);
    const response = await ListTasksHandler.handle(input);
    expect(response.outputSpeech.ssml).toContain('1 task');
    expect(response.outputSpeech.ssml).toContain('Review PR');
  });

  it('handles empty task list', async () => {
    const input = buildMockInput('ListTasksIntent');
    mockTaskService.listForUser.mockResolvedValue([]);
    const response = await ListTasksHandler.handle(input);
    expect(response.outputSpeech.ssml).toContain('no tasks');
  });
});
```

### Step 7: Generate Deployment Config

- **Alexa**: ASK CLI config (`ask deploy`), Lambda function config
- **Google**: gactions CLI config, Cloud Functions deploy
- **Twilio**: Functions deploy config, Studio flow publish

### Step 8: Certification Checklist

Platform-specific requirements that must be met before submission:
- Response time under limits (Alexa: 8s)
- All built-in intents handled (Help, Stop, Cancel)
- Fallback intent implemented (graceful error handling)
- Session management correct (no data leaks between users)
- Privacy policy URL provided
- Skill icon/assets provided

## Phase Output

```
Verdict: VOICE_SCAFFOLDED
Next: Implement business logic via /build-implementation (TDD against handler stubs)
Artifacts: [project structure, intent model, handler stubs, SSML templates, test harness, deploy config]
Platform: [Alexa/Google/Twilio]
```
$ARGUMENTS
