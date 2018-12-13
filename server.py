import base64, datetime, os, urllib
from dotenv import load_dotenv
from flask import Flask, request, redirect, render_template, session
import requests
import pymongo

from spotify import Spotify

load_dotenv()
db = pymongo.MongoClient(os.environ.get('MONGODB_URI'))['spotify-fork']
app = Flask(__name__)
app.secret_key = os.environ.get('SPOTIFY_CLIENT_SECRET')

@app.route('/')
def index():
  session['expires'] = datetime.datetime.now()
  if 'access_token' in session and session['expires'] > datetime.datetime.now():
    return render_template('index.html')
  if 'spotify_id' in session:
    user = db['users'].find_one({'spotify_id': session['spotify_id']})
    token_info = Spotify.update_token(user['refresh_token'])
    session['access_token'] = token_info['access_token']
    session['expires'] = datetime.datetime.now() + datetime.timedelta(0, token_info['expires_in'])
    return render_template('index.html')
  return redirect('/login')

def add_playlist(user, playlist_id, playlist_id_original):
  playlist = {
    'id': playlist_id,
    'original_id': playlist_id_original,
    'last_checked': datetime.datetime.utcnow(),
  }
  db['users'].find_one_and_update(
    {'spotify_id': user},
    {'$push': {'playlists': playlist}},
  )

def get_track_uris(data):
  return [item['track']['uri'] for item in data['items']]

def fork_playlist(spotify, playlist_uri):
  playlist_id = Spotify.get_playlist_id(playlist_uri)
  data = spotify.get_playlist(playlist_id)
  created = spotify.create_playlist(data['name'])
  # Switch to tracks as data, because the subsequent /tracks calls will return exactly that
  data = data['tracks']
  spotify.add_tracks(created['id'], get_track_uris(data))
  while data['next']:
    data = spotify.request(data['next'])
    spotify.add_tracks(created['id'], get_track_uris(data))
  add_playlist(session['spotify_id'], created['id'], playlist_id)
  return created

@app.route('/fork', methods=['POST'])
def fork():
  playlist_uri = request.form['playlist']
  spotify = Spotify(session['spotify_id'], session['access_token'])
  fork_playlist(spotify, playlist_uri)
  return 'Forked!'

@app.route('/login')
def login():
  return redirect(Spotify.get_redirect_url())

def create_user(spotify, refresh_token):
  profile = spotify.get_profile()
  user = {
    'spotify_id': profile['id'],
    'refresh_token': refresh_token,
    'playlists': [],
  }
  if not db['users'].find_one({ 'spotify_id': profile['id'] }):
    db['users'].insert_one(user)
  return user

@app.route('/callback')
def callback():
  code = request.args['code']
  token_info = Spotify.exchange_code(code)
  spotify = Spotify(None, token_info['access_token'])
  user = create_user(spotify, token_info['refresh_token'])
  session['access_token'] = token_info['access_token']
  session['expires'] = datetime.datetime.now() + datetime.timedelta(0, token_info['expires_in'])
  session['spotify_id'] = user['spotify_id']
  return redirect('/')
