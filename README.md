# Vreeo Music & Games

Private Discord bot for one server. Music is the current completed module; games/economy/progression are scaffolded for the next phase.

## Music

### Playback
- `/play <query>` — YouTube search, YouTube URL, YouTube Music URL, Spotify track URL
- YouTube playlists and Spotify playlists/albums
- `/search <query>` — up to 5 results with selection buttons
- `/nowplaying`
- `/pause`, `/resume`, `/skip`, `/previous`, `/stop`
- `/volume 0-150`
- `/seek` — absolute `1:30`, relative `+30` / `-15`
- `/loop off|track|queue`
- `/shuffle`
- `/autoplay`
- `/247`

### Queue
- `/queue show`
- `/queue remove`
- `/queue move`
- `/queue clear`
- `/queue jump`
- Queue limit is configurable with `MAX_QUEUE_SIZE`

### Audio
- `/filter off|bassboost|nightcore|vaporwave|karaoke|8d|tremolo|rotation`
- `/speed 0.5-2.0`
- FFmpeg reconnect options
- Fresh yt-dlp extraction before playback to avoid stale stream URLs
- Seek/effect changes preserve the current playback position

### Personal music
- `/favorite add|remove|list|play`
- `/playlist create|list|delete|rename|add|remove|play`
- `/history show|clear`
- Now Playing has interactive controls and a Favorite button

### Permissions
- Members can play/search and remove their own queued tracks
- DJ/Admin controls are gated by Administrator/Manage Server or `DISCORD_DJ_ROLE_ID`
- Optional dedicated music text channel via `/settings music-channel` or `MUSIC_CHANNEL_ID`

### Spotify
Spotify is metadata/search only. Spotify tracks are resolved to an available YouTube source for playback; Spotify audio is never ripped.
Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` to enable Spotify search and playlist/album expansion.

## Environment

Copy `.env.example` and provide:
- `DISCORD_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- optional `DISCORD_GUILD_ID`
- optional `DISCORD_DJ_ROLE_ID`
- optional `MUSIC_CHANNEL_ID`
- optional Spotify credentials
- optional `MAX_QUEUE_SIZE` / `MAX_PLAYLIST_SIZE`

Run the schema in `database/schema.sql` in the new Supabase project.

## Runtime

The Docker image includes:
- Python 3.12
- FFmpeg
- Deno for yt-dlp YouTube JavaScript challenge solving
- yt-dlp + yt-dlp-ejs

CI performs Python compilation, unit tests, and Docker image build.
