# Omnichannel Coordination Patterns

## Architecture Overview

```
         Web ──→ Web BFF ──┐
       Mobile ──→ Mobile BFF ──┤
        Voice ──→ Voice BFF ──┼──→ API Gateway ──→ Core Services ──→ Database
       Device ──→ Device BFF ──┤              ──→ Event Bus
                               └──→ Shared Identity Service
```

Each channel has its own BFF (Backend for Frontend). All BFFs connect to shared core services through an API gateway. A unified identity service ties users across channels.

## Unified User Identity

### Identity Linking
```
A single user may interact via:
  - Web: email + password login
  - Mobile: biometric + OAuth
  - Voice: account linking via OAuth
  - Device: device certificate + user association

Identity resolution service:
  1. Each channel authenticates independently
  2. Authentication produces a channel-specific token
  3. Token maps to a canonical user_id in the identity service
  4. All downstream services use canonical user_id

Identity linking flow:
  1. User signs up on web (creates identity: user_123)
  2. User installs mobile app, logs in with same email → links to user_123
  3. User enables Alexa skill, completes account linking → links to user_123
  4. User registers IoT device, associates in app → links to user_123
```

### Anonymous-to-Known Transition
```
Web visitor (anonymous) browses → creates cart → registers → identity created
Mobile user installs app → uses as guest → signs up → guest data migrated to identity
Device operates without user → user claims device in app → linked to identity

Key: preserve pre-registration data and associate it on identity creation
```

## Cross-Channel Session Continuity

### Session Model
```json
{
  "session_id": "sess_abc123",
  "user_id": "user_123",
  "active_channel": "web",
  "context": {
    "current_task": "task_456",
    "last_action": "viewing_details",
    "position_in_flow": "step_3_of_5"
  },
  "channel_history": [
    { "channel": "mobile", "action": "created_task", "timestamp": "..." },
    { "channel": "web", "action": "viewing_details", "timestamp": "..." }
  ]
}
```

### Session Handoff
```
Scenario: user starts creating a task on mobile, switches to web to finish

1. Mobile app saves session state: { current_task: draft_789, fields_completed: [name, date] }
2. User opens web app
3. Web app queries session service: "any active session for user_123?"
4. Session service returns the in-progress task creation
5. Web app offers: "Continue creating 'Review PR' from your phone?"
6. User confirms → web loads the draft with fields pre-filled
```

### Implementation
```
Storage: Redis with user-scoped keys (session:{user_id}:active)
TTL: 30 minutes for active sessions, 24 hours for drafts
Eviction: channel-specific sessions expire independently
Conflict: if user is active on two channels, latest action wins
```

## Channel-Adaptive Content

### Content Model (Structured, Not Pre-Formatted)
```json
{
  "type": "task",
  "id": "task_456",
  "title": "Review PR for auth module",
  "description": "Check security patterns and test coverage",
  "due_date": "2026-03-23",
  "priority": "high",
  "assignee": { "name": "Paul", "avatar_url": "..." },
  "attachments": [{ "name": "screenshot.png", "url": "...", "size_kb": 245 }]
}
```

### Channel-Specific Rendering
| Field | Web | Mobile | Voice | Device |
|-------|-----|--------|-------|--------|
| title | Full text | Full text | Spoken with SSML | Truncated to 20 chars |
| description | Full HTML | Markdown | First sentence only | Omitted |
| due_date | Formatted date | Relative ("tomorrow") | Spoken ("due tomorrow") | Unix timestamp |
| avatar_url | Full image | Thumbnail (48px) | Omitted | Omitted |
| attachments | Inline preview | Download link | "1 attachment" (count only) | Omitted |

### BFF Responsibility
Each BFF transforms the shared content model into its channel format. Core services return structured data — BFFs shape it.

## BFF (Backend for Frontend) Pattern

### When to Use
```
Use BFF when:
  - Different channels need different response shapes
  - Channel-specific aggregation (mobile needs 1 API call, web can make 3)
  - Channel-specific auth (cookies for web, bearer for mobile, OAuth for voice)
  - Channel-specific rate limits and caching strategies

Do NOT use BFF when:
  - All channels consume the same API shape
  - You have < 2 channels
  - The added operational complexity isn't justified
```

### BFF Ownership
```
The team that owns the channel owns its BFF:
  - Web team owns web-bff
  - Mobile team owns mobile-bff
  - Voice team owns voice-bff

Each BFF is deployed independently.
Each BFF has its own test suite.
BFFs share no code (they may share type definitions via a shared contract package).
```

### BFF vs API Gateway
```
API Gateway handles:     BFF handles:
  - Auth (JWT validation)   - Data aggregation
  - Rate limiting            - Response shaping
  - TLS termination          - Channel-specific logic
  - Request routing          - Channel-specific caching
  - CORS                     - Channel-specific auth flow
  - Logging                  - Offline hints (mobile)
```

## Notification Channel Routing

### User Preference Model
```
Preference matrix (user_id, channel, category, urgency):

                  | Email | Push | In-App | SMS  | Voice |
  Security        | ✓     | ✓    | ✓      | ✓    | ✓     |  (cannot disable)
  Task assigned   | -     | ✓    | ✓      | -    | -     |
  Task completed  | -     | -    | ✓      | -    | -     |
  Daily digest    | ✓     | -    | -      | -    | -     |
  Marketing       | opt-in| -    | -      | -    | -     |
```

### Routing Logic
```
1. Determine notification category and urgency
2. Look up user preferences for this category
3. Filter to channels where user has opted in
4. For each enabled channel:
   - Check quiet hours (don't push at 3am)
   - Check device availability (is mobile app installed?)
   - Format for channel (email template vs push notification vs SSML)
5. Send via each enabled channel
6. Deduplicate: if user reads on one channel, mark as read on all
```

## Shared Event Bus

```
Events flow across all channels:

user.task.created →
  Web:    live update via WebSocket
  Mobile: push notification
  Voice:  available on next query
  Device: LED indicator update

Architecture:
  Any channel → Core Service → Event Bus (Redis Streams / Kafka / SQS)
  Event Bus → Channel-specific consumers
  Each consumer formats and delivers per channel

Event format (channel-agnostic):
{
  "type": "task.created",
  "source": "task-service",
  "user_id": "user_123",
  "data": { "task_id": "task_789", "title": "Review PR" },
  "timestamp": "2026-03-22T10:00:00Z"
}
```

## Offline/Sync Across Channels

```
Mobile and device channels must work offline:

1. Local database (SQLite on mobile, flash storage on device)
2. Queue mutations while offline (create, update, delete)
3. On reconnect: sync queued mutations to server
4. Server resolves conflicts (last-write-wins with vector clock)
5. Server pushes missed events to the reconnected client
6. UI shows sync status indicator (synced / syncing / offline)

Conflict resolution:
  - Same field edited on two channels → latest timestamp wins
  - Structural conflicts (delete + edit) → server decides, notifies user
  - Critical data (payments) → never allow offline mutation
```

## Cross-Channel Analytics

```
Unified user journey:
  1. All channels emit events with canonical user_id
  2. Events flow to analytics pipeline (Segment, Amplitude, custom)
  3. Journey stitching: correlate events across channels by user_id + time
  4. Attribution: which channel contributed to conversion?
  5. Channel effectiveness: task completion rate per channel

Key metrics:
  - Channel adoption: % of users on each channel
  - Cross-channel usage: % of users on 2+ channels
  - Channel switching: how often users move between channels
  - Per-channel conversion rate
  - Time-to-completion per channel (is voice faster for simple tasks?)
```
