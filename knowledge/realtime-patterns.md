# Real-Time Communication Patterns

## Technology Selection

| Technology | When | Tradeoffs |
|-----------|------|-----------|
| WebSocket | Bidirectional, low latency (chat, gaming, collaboration) | Complex scaling, connection management |
| Server-Sent Events (SSE) | Server-to-client only (live feeds, notifications) | Simple, HTTP-native, auto-reconnect |
| Long polling | Legacy browser support, simple fallback | Higher latency, more server load |
| WebRTC | Peer-to-peer (video, audio, screen share) | Complex NAT traversal, STUN/TURN |

**Default: WebSocket for bidirectional, SSE for server-push only.** Most SaaS apps need WebSocket.

## WebSocket Lifecycle

```
1. Connect:      Client opens WebSocket, sends auth token
2. Authenticate: Server validates token, associates connection with user
3. Subscribe:    Client subscribes to channels/rooms
4. Heartbeat:    Ping/pong every 30s to detect dead connections
5. Message:      Bidirectional JSON messages
6. Reconnect:    Client reconnects with exponential backoff on disconnect
7. Disconnect:   Clean shutdown, remove from room/presence
```

## Framework Selection

| Stack | Library | Features |
|-------|---------|----------|
| Node.js | Socket.IO | Rooms, namespaces, auto-fallback, Redis adapter |
| Node.js | ws | Lightweight, native WebSocket only |
| Rails | Action Cable | Channels, Redis pub/sub, ActiveRecord integration |
| Django | Channels | ASGI, Redis channel layer, groups |
| Go | gorilla/websocket, nhooyr/websocket | Lightweight, high-performance |

## Channel/Room Patterns

```
Public channels:   Anyone can subscribe (e.g., live scores, announcements)
Private channels:  Require authorization (e.g., team chat, project updates)
Presence channels: Track who is online (e.g., collaboration, typing indicators)
User channels:     One per user (e.g., personal notifications)
```

### Authorization
```
On subscribe request:
1. Verify user is authenticated
2. Check user has access to the requested channel
3. For private channels: verify membership/role
4. Reject unauthorized subscriptions (close connection or send error)
```

## Scaling WebSocket Servers

### The Problem
WebSocket connections are stateful. A message sent to Server A must reach users connected to Server B.

### Solution: Redis Pub/Sub Adapter
```
Server A ──publish──→ Redis ──subscribe──→ Server B
                                         ──subscribe──→ Server C

All servers subscribe to the same Redis channels.
When a message arrives for a room, publish to Redis.
All servers receive it and forward to their local connections.
```

**Socket.IO:** `@socket.io/redis-adapter`
**Action Cable:** Built-in Redis adapter
**Django Channels:** `channels_redis`

### Connection Limits
```
Per server: ~10,000 concurrent connections (depends on memory)
Per process: set ulimit for open file descriptors
Load balancer: use sticky sessions (WebSocket needs same server for duration)
Health check: separate HTTP health endpoint (not WebSocket)
```

## Message Patterns

### Broadcast (one-to-many)
```
Server sends to all subscribers of a channel
Use for: announcements, live updates, feed items
```

### Direct (one-to-one)
```
Server sends to a specific user's channel
Use for: notifications, private messages, typing indicators
```

### Request-Response (over WebSocket)
```
Client sends request with ID, server responds with same ID
Use for: real-time queries, collaborative operations
Include timeout on client side (5s default)
```

## Client-Side Patterns

### Reconnection
```
On disconnect:
1. Wait: 1s, then 2s, then 4s, then 8s... (exponential backoff)
2. Add jitter (random 0-1s) to prevent thundering herd
3. Max reconnect attempts: 10 (then show "connection lost" UI)
4. On reconnect: re-authenticate, re-subscribe, fetch missed messages
```

### Optimistic Updates
```
1. Apply change locally immediately (optimistic)
2. Send change to server via WebSocket
3. Server broadcasts confirmed change to all subscribers
4. If conflict: server sends correction, client reverts optimistic update
```

### Offline Queue
```
If disconnected:
1. Queue outgoing messages locally
2. On reconnect: send queued messages in order
3. Deduplicate by message ID on server
```

## Testing WebSocket

```
Unit:        Test message handlers in isolation (mock the socket)
Integration: Connect real WebSocket client, send/receive messages
Load:        Use Artillery or k6 for WebSocket load testing
Key tests:
  - Auth: reject unauthenticated connections
  - Rooms: messages only reach subscribed users
  - Reconnect: client recovers after disconnect
  - Ordering: messages arrive in send order
```
