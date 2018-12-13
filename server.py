import os, urllib
from dotenv import load_dotenv
from flask import Flask, request, redirect, render_template, session
import requests
import pymongo

CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI')

load_dotenv()
db = pymongo.MongoClient(os.environ.get('MONGODB_URI'))['spotify-fork']
app = Flask(__name__)
app.secret_key = CLIENT_SECRET

def auth_header(access_token):
  return { 'Authorization': f'Bearer {access_token}' }

@app.route('/')
def index():
  return render_template('index.html')

def create_playlist(name):
  r = requests.post(
    f'https://api.spotify.com/v1/users/{session["spotify_id"]}/playlists',
    headers=auth_header(session['access_token']),
    json={'name': name, 'public': False},
  )
  return r.json()

def get_track_uris(data):
  return [item['track']['uri'] for item in data['items']]

def add_tracks(playlist_id, track_uris):
  requests.post(
    f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
    headers=auth_header(session['access_token']),
    json={'uris': track_uris},
  )

def fork_playlist(playlist_uri):
  playlist_id = playlist_uri.split(':').pop()
  r = requests.get(
    f'https://api.spotify.com/v1/playlists/{playlist_id}',
    headers=auth_header(session['access_token']),
  )
  data = r.json()
  created = create_playlist(data['name'])
  # Switch to tracks as data, because the subsequent /tracks calls will return exactly that
  data = data['tracks']
  add_tracks(created['id'], get_track_uris(data))
  while data['next']:
    print('next page')
    r = requests.get(
      f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
      headers=auth_header(session['access_token']),
    )
    data = r.json()
    add_tracks(created['id'], get_track_uris(data))
  return created

@app.route('/fork', methods=['POST'])
def fork():
  playlist_uri = request.form['playlist']
  fork_playlist(playlist_uri)
  return 'Forked!'

scopes = ['playlist-modify-public', 'playlist-modify-private']
auth_query_parameters = {
  'response_type': 'code',
  'scope': ' '.join(scopes),
  # 'state': STATE,
  'client_id': CLIENT_ID,
  'redirect_uri': REDIRECT_URI,
}

@app.route('/login')
def login():
  print(auth_query_parameters)
  params = '&'.join([f'{key}={urllib.parse.quote(val)}' for key, val in auth_query_parameters.items()])
  return redirect(f'https://accounts.spotify.com/authorize?{params}')

def create_user(access_token, refresh_token):
  r = requests.get('https://api.spotify.com/v1/me', headers=auth_header(access_token))
  profile = r.json()
  user = {
    'spotify_id': profile['id'],
    'refresh_token': refresh_token,
  }
  if not db['users'].find_one({ 'spotify_id': profile['id'] }):
    db['users'].insert_one(user)
  return user

@app.route('/callback')
def callback():
  code = request.args['code']
  code_payload = {
    'grant_type': 'authorization_code',
    'code': str(code),
    'redirect_uri': REDIRECT_URI,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
  }
  r = requests.post('https://accounts.spotify.com/api/token', data=code_payload)
  post_data = r.json()
  user = create_user(post_data['access_token'], post_data['refresh_token'])
  session['access_token'] = post_data['access_token']
  session['spotify_id'] = user['spotify_id']
  return redirect('/')
