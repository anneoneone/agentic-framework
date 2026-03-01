# Shared Knowledge - live-moafunk

Cross-cutting knowledge for all agents in this stack.

## API Endpoints

### Public API (no auth)
| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/api/stream/status` | Stream online status |

### Admin API (requires Bearer token)
| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/login` | Get auth token |
| `GET` | `/api/artists` | List artists |
| `GET` | `/api/artists/:id` | Artist detail |
| `POST` | `/api/artists` | Create artist |
| `GET` | `/api/shows` | List shows |
| `POST` | `/api/shows` | Create show |
| `GET` | `/api/users` | List users |
| `POST` | `/api/shows/:id/soundcloud/upload` | Upload recording to SoundCloud |
| `POST` | `/api/shows/:id/soundcloud/privacy` | Toggle SoundCloud track privacy |

### WebSocket
| Path | Purpose |
|------|---------|
| `/ws/stream` | Audio streaming WebSocket |

## Database Schema

SQLite database at `data/unheard.db`:

- `users` - Admin user accounts
- `artists` - Artist submissions
- `shows` - Radio shows
- `show_artists` - Many-to-many: shows ↔ artists

## Environment Variables

### Backend
```bash
DATABASE_URL=sqlite:data/unheard.db
S3_ENDPOINT=https://your-r2-endpoint.r2.cloudflarestorage.com
S3_BUCKET=moafunk-media
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
ADMIN_PASSWORD_HASH=argon2-hash
JWT_SECRET=xxx

# Telegram bot (all optional — bot disabled if token unset)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ADMIN_CHAT_ID=-1001234567890
TELEGRAM_INSTAGRAM_ACCOUNT=prod

# SoundCloud (all optional — disabled if client_id unset)
SOUNDCLOUD_CLIENT_ID=xxx
SOUNDCLOUD_CLIENT_SECRET=xxx
SOUNDCLOUD_ACCESS_TOKEN=xxx
```

### Frontend
```bash
VITE_API_URL=https://admin.live.moafunk.de
VITE_STREAM_HLS_URL=https://stream.moafunk.de/live/stream-io/index.m3u8
VITE_STREAM_FLV_URL=https://stream.moafunk.de/live/stream-io.flv
```

## Deployment URLs

| Environment | URL |
|-------------|-----|
| Main site | `https://live.moafunk.de` |
| Admin panel | `https://admin.live.moafunk.de` |
| Stream HLS | `https://stream.moafunk.de/live/stream-io/index.m3u8` |
| Stream FLV | `https://stream.moafunk.de/live/stream-io.flv` |

## Telegram Bot Notifications

The backend integrates with Telegram to send admin notifications about system events.

### Configuration

Three environment variables control the Telegram bot:

```bash
# Bot token from @BotFather (required for Telegram integration)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# Chat ID where notifications are sent (required)
TELEGRAM_ADMIN_CHAT_ID=-1001234567890

# Optional: Thread/topic ID within the chat (for organized channels)
TELEGRAM_TOPIC_ID=26
```

If `TELEGRAM_BOT_TOKEN` is not set, all Telegram features are disabled (no-op).

### Notification Types

| Event | Trigger | Message Format |
|-------|---------|----------------|
| **Artist submission** | New artist submits form | Photo with artist info, track previews |
| **Show artist update** | Artist assigned/removed from show | Show cover + artist list (debounced) |
| **Stream start/stop** | Live stream begins/ends | Simple status message |

### Show Update Notifications (Debounced)

When artists are assigned to or removed from shows, notifications are **debounced for 30 seconds**:

1. User assigns/removes artist → notification scheduled
2. If another change happens within 30s → previous notification cancelled, new one scheduled
3. After 30s of inactivity → single notification sent with final state

**Message format:**
```
[SHOW COVER IMAGE]

<SHOW_TITLE> was updated: <ARTIST_NAME> was added/removed

Current Artists:
• Artist 1
• Artist 2
• Artist 3

[Link to show page]
```

**Fallback behavior:**
- If show has no cover → sends text-only message
- If cover download fails → falls back to text-only
- If Telegram API fails → logs warning, doesn't break main flow

### Implementation Details

- **Module:** `source/backend/src/telegram_notify.rs`
- **State:** `AppState.pending_show_notifications` tracks scheduled tasks
- **Debouncing:** Uses `Arc<Mutex<HashMap<show_id, JoinHandle>>>` to cancel pending tasks
- **Error handling:** All notification failures are logged but never propagate to API responses

## SoundCloud Integration

The backend uploads final show recordings to SoundCloud as private tracks, with a frontend toggle to make them public.

### Configuration

Three environment variables control SoundCloud integration (all optional — disabled if unset):

```bash
# OAuth2 client credentials from SoundCloud app settings
SOUNDCLOUD_CLIENT_ID=your-client-id
SOUNDCLOUD_CLIENT_SECRET=your-client-secret

# Static access token (preferred over OAuth flow if set)
SOUNDCLOUD_ACCESS_TOKEN=your-access-token
```

If `SOUNDCLOUD_CLIENT_ID` is not set, all SoundCloud features are disabled (no-op).

### Auto-Upload Flow

When a final recording is uploaded (via single or chunked upload), SoundCloud upload is triggered automatically in a fire-and-forget `tokio::spawn`:

1. Recording uploaded → DB updated with recording URL
2. `soundcloud::is_configured()` checked → if false, skipped silently
3. `soundcloud::upload_track()` called with show data
4. Track uploaded as **private** by default
5. DB updated with `soundcloud_track_id`, `soundcloud_url`, `soundcloud_uploaded_at`

### Track Metadata

| Field | Value |
|-------|-------|
| **Title** | `Show Title — Artist A, Artist B` |
| **Description** | AI show bio + artist SoundCloud/Instagram links |
| **Artwork** | Show cover image from R2 (`shows/{id}/cover.png`) |
| **Privacy** | Private (default) |

**Description format:**
```
[AI-generated show bio]

Artists:
• Artist Name — soundcloud.com/handle · instagram.com/handle
```

### Privacy Toggle

Admins can toggle track privacy from the show detail page:

- **Make Public** → `PUT /tracks/:id` with `sharing=public`
- **Make Private** → `PUT /tracks/:id` with `sharing=private`

DB field `soundcloud_public` tracks current state.

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/shows/:id/soundcloud/upload` | Manual upload/re-upload to SoundCloud |
| `POST` | `/api/shows/:id/soundcloud/privacy` | Toggle track privacy (`{ "public": true }`) |

### Implementation Details

- **Module:** `source/backend/src/soundcloud.rs`
- **Auth:** Prefers static `SOUNDCLOUD_ACCESS_TOKEN`, falls back to OAuth2 client credentials flow via `reqwest::basic_auth()`
- **Upload:** Multipart POST to `https://api.soundcloud.com/tracks` with `asset_data` and optional `artwork_data`
- **Error handling:** Upload failures in auto-trigger are logged as warnings, never propagate to API responses
- **Frontend UI:** SoundCloud section in `ShowDetailPage.vue` below recording actions — shows status, link, privacy badge, and toggle/upload buttons

## Code Style

### Rust
- Use `cargo fmt` and `cargo clippy`
- Error handling: `thiserror` for types, `anyhow` for context
- Async: Always use `tokio` runtime

### TypeScript/Vue
- Use `<script setup lang="ts">`
- Extract logic to composables
- Pinia for shared state
- ESLint + Prettier formatting

## Git Workflow

- `main` branch triggers deployments
- Frontend changes → GitHub Pages
- Backend/admin changes → Docker → Lightsail
