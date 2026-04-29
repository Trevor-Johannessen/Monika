---
name: spotify
description: Anything music-related — read what song is currently playing, control playback (play, pause, skip, resume), search tracks, manage the queue, add to Liked Songs, list/play playlists, list devices, or transfer playback. Use this whenever the user asks about a song, artist, album, what's playing, or any Spotify action.
---

# Spotify

When the user asks to play music, control playback, search Spotify, manage their queue, list playlists, or read what is currently playing, call the Spotify Web API directly using `bash` + `curl`. You can always assume the user uses Spotify as their music player.

## Behavior

Execute any non-destructive Spotify request immediately. Do **not** ask the user for confirmation, do **not** describe what you are about to do, and do **not** ask follow-up questions — just call the API and reply with a brief confirmation of the result. The user has pre-authorized everything in the "Common endpoints" section below.

The only time you decline and defer to the user is for the destructive actions listed in the "Destructive operations" section. Everything else is fair game and should be done silently.

## Credentials

The user's Spotify credentials are exposed as environment variables:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI`

A user OAuth token is cached at `.cache` in the working directory (or fall back to `/usr/local/bin/monika/.cache` if not present in CWD). The file is JSON shaped like:

```json
{"access_token": "...", "token_type": "Bearer", "expires_at": 1746000000, "refresh_token": "...", "scope": "..."}
```

## Getting a valid access token

1. Read `.cache` and check `expires_at` against the current epoch time (`date +%s`).
2. If still valid, use `access_token` directly.
3. If expired, refresh it:
   ```bash
   curl -s -X POST https://accounts.spotify.com/api/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=refresh_token&refresh_token=$REFRESH_TOKEN&client_id=$SPOTIFY_CLIENT_ID&client_secret=$SPOTIFY_CLIENT_SECRET"
   ```
   The response contains a new `access_token` and `expires_in` (seconds). Write the updated token, `expires_at` (now + `expires_in`), and the original `refresh_token` back to `.cache` so future calls do not re-refresh unnecessarily.

Pass the access token to all API calls as `Authorization: Bearer <token>` against `https://api.spotify.com/v1/...`.

## Common endpoints

- Currently playing: `GET /me/player`
- Skip next: `POST /me/player/next`
- Skip previous: `POST /me/player/previous`
- Pause: `PUT /me/player/pause`
- Resume / start playback: `PUT /me/player/play` (body `{"uris":["spotify:track:ID"]}` or `{"context_uri":"spotify:playlist:ID"}` to play something specific)
- Search: `GET /search?q=<url-encoded query>&type=track&limit=1`
- Add to queue: `POST /me/player/queue?uri=spotify:track:ID`
- Add currently playing to Liked Songs: `PUT /me/tracks?ids=<id>` (look up the id from `GET /me/player` first)
- List user playlists: `GET /me/playlists`
- List devices: `GET /me/player/devices`
- Transfer playback: `PUT /me/player` with body `{"device_ids":["<id>"],"play":true}`

## Destructive operations — NEVER perform

These are the *only* requests you should refuse. They all involve removing saved content from the user's account:

- Deleting a playlist or unfollowing one (`DELETE /playlists/{id}/followers`)
- Removing tracks from a playlist (`DELETE /playlists/{id}/tracks`)
- Removing songs from Liked Songs (`DELETE /me/tracks`)
- Unfollowing artists or users (`DELETE /me/following`)
- Removing saved albums or shows
- Any other `DELETE` request, or any `PUT`/`POST` whose effect is to remove saved content

For any of these, briefly tell the user you cannot perform that action and ask them to do it themselves in the Spotify app. Do not apply this caution to any other request — playback control, queueing, searching, adding to Liked Songs, transferring devices, and reading state are all non-destructive and must be done without asking.

## Response style

Reply briefly in plaintext. No markdown, no links, no URIs. Just confirm what was done (e.g. "Paused.", "Skipped.", "Playing Bohemian Rhapsody by Queen.") or report the requested information concisely.

Ignore album information by default. When reporting what's playing, what was queued, or what was added, give only the track title and artist — never volunteer the album name. Only mention or look up the album if the user specifically asks about it (e.g. "what album is this on", "play the album X").
