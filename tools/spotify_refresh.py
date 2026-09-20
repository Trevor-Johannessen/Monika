#!/mnt/fs1/shared/venvs/monika/bin/python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credentials import read_json
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Spotify API credentials
_spotify = read_json("spotify.json")
SPOTIFY_CLIENT_ID = _spotify.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = _spotify.get('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = _spotify.get('SPOTIFY_REDIRECT_URI')

# Absolute so dev and the systemd service share one token regardless of cwd.
CACHE_PATH = os.path.join(
    os.getenv("MONIKA_CREDENTIALS_DIR") or os.path.expanduser("~/.credentials"),
    "spotify.cache",
)

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope='user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private user-library-modify user-library-read',
    cache_path=CACHE_PATH,
    open_browser=False
))

print(sp.current_playback())
