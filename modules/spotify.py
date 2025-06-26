import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from agents import Agent, function_tool, ModelSettings

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope='user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-read-private user-library-modify user-library-read'
))

"""
    TODO:
        - Add function for restarting song (remember to delete from prompt)
        - Add function to get device ids (similar to getting song ids)
        - Add functions to control volume
"""

class SpotifyAgent(Agent):
    def __init__(self):
        super().__init__(
            name="spotify_agent",
            instructions="""
                You control Spotify settings of the user of a chatbot. Use the provided tools to fulfill any requests as necessary.
                Answer only in plaintext and do not provide any links. Do not use Markdown or any other stylings.
                Some tips:
                    - You can restart a song by going to the previous song, and then going to the next song.
            """,
            tools=[
                getTrackUrl,
                getCurrentSong,
                skipToNext,
                skipToPrevious,
                togglePlayback,
                addToQueue,
                transferPlayback,
                addToLikedSongs,
                playPlaylist
            ],
            model_settings=ModelSettings(tool_choice="required"),
        )

@function_tool
def getTrackUrl(title: str, artist: str) -> str:
    """Searches for and returns the Spotify URL for a track based on title and artist.
    
    Args:
        title: The title of the song to search for
        artist: The artist who performed the song
    
    Returns:
        The Spotify URL for the matching track, or an error message if not found
    """
    try:
        results = sp.search(q=f"track:{title} artist:{artist}", type='track', limit=1)
        if not results['tracks']['items']:
            return f"Could not find track '{title}' by {artist}"
        return results['tracks']['items'][0]['external_urls']['spotify']
    except Exception as e:
        return f"Error searching for track: {str(e)}"

@function_tool
def getCurrentSong() -> dict:
    """Gets information about the currently playing song.
    
    Returns:
        Information about the current song including name, artist, album, etc.
    """
    try:
        current = sp.current_playback()
        if not current:
            return "No song is currently playing"
        return current
    except Exception as e:
        return f"Error getting current song: {str(e)}"

@function_tool
def skipToNext() -> str:
    """Skips to the next song in queue."""
    try:
        sp.next_track()
        return "Skipped to next song."
    except Exception as e:
        return f"Error skipping to next song: {str(e)}"

@function_tool
def skipToPrevious() -> str:
    """Skips to the previous song."""
    try:
        sp.previous_track()
        return "Skipped to previous song."
    except Exception as e:
        return f"Error skipping to previous song: {str(e)}"

@function_tool
def togglePlayback(play: bool) -> str:
    """Toggles playback between play and pause.
    
    Args:
        play: True to play, False to pause
    """
    try:
        if play:
            sp.start_playback()
            return "Playing."
        else:
            sp.pause_playback()
            return "Paused."
    except Exception as e:
        return f"Error {'playing' if play else 'pausing'} playback: {str(e)}"

@function_tool
def addToQueue(track_uri: str) -> str:
    """Adds a song to the end of the current queue.
    
    Args:
        track_uri: The Spotify URI of the track to add
    """
    try:
        sp.add_to_queue(track_uri)
        return "Added song to queue."
    except Exception as e:
        return f"Error adding song to queue: {str(e)}"

@function_tool
def transferPlayback(device_id: str) -> str:
    """Transfers playback to a different device.
    
    Args:
        device_id: The Spotify device ID to transfer playback to
    """
    try:
        sp.transfer_playback(device_id=device_id, force_play=True)
        return "Transferred playback to new device."
    except Exception as e:
        return f"Error transferring playback: {str(e)}"

@function_tool
def addToLikedSongs() -> str:
    """Adds the currently playing song to your Liked Songs library."""
    try:
        current = sp.current_playback()
        if not current or not current.get('item'):
            return "No track currently playing."
        
        track_id = current['item']['id']
        sp.current_user_saved_tracks_add([track_id])
        return "Added current song to Liked Songs."
    except Exception as e:
        return f"Error adding song to Liked Songs: {str(e)}"

@function_tool
def playPlaylist(playlist_name: str) -> str:
    """Starts playing a playlist from your library that matches the given name.
    
    Args:
        playlist_name: The name of the playlist to play
    """
    try:
        playlists = sp.current_user_playlists()
        playlist_uri = None
        
        for playlist in playlists['items']:
            if playlist['name'].lower() == playlist_name.lower():
                playlist_uri = playlist['uri']
                break
                
        if not playlist_uri:
            return f"Could not find playlist named '{playlist_name}'"
            
        sp.start_playback(context_uri=playlist_uri)
        return f"Started playing playlist '{playlist_name}'"
    except Exception as e:
        return f"Error starting playlist playback: {str(e)}"

@function_tool
def playSong(track_id: str) -> str:
    """Plays a song by its Spotify track ID.
    
    Args:
        track_id: The Spotify track ID to play
    """
    try:
        track_uri = f"spotify:track:{track_id}"
        
        # Get track info first to include in response
        track = sp.track(track_id)
        track_name = track['name']
        artist_name = track['artists'][0]['name']
            
        # Play the track
        sp.start_playback(uris=[track_uri])
        return f"Playing '{track_name}' by {artist_name}"
    except Exception as e:
        return f"Error playing song: {str(e)}"



