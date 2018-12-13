import base64, datetime, os, urllib
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

def update_token(refresh_token):
  client = f'{CLIENT_ID}:{CLIENT_SECRET}'
  base64encoded = base64.b64encode(client.encode())
  headers = {'Authorization': f'Basic {base64encoded.decode()}'}
  payload = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
  r = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=payload)
  return r.json()

@app.route('/')
def index():
  session['expires'] = datetime.datetime.now()
  if 'access_token' in session and session['expires'] > datetime.datetime.now():
    return render_template('index.html')
  if 'spotify_id' in session:
    user = db['users'].find_one({'spotify_id': session['spotify_id']})
    token_info = update_token(user['refresh_token'])
    session['access_token'] = token_info['access_token']
    session['expires'] = datetime.datetime.now() + datetime.timedelta(0, token_info['expires_in'])
    return render_template('index.html')
  return redirect('/login')

def create_playlist(name):
  r = requests.post(
    f'https://api.spotify.com/v1/users/{session["spotify_id"]}/playlists',
    headers=auth_header(session['access_token']),
    json={'name': name, 'public': False},
  )
  return r.json()

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
  add_playlist(session['spotify_id'], created['id'], playlist_id)
  # Switch to tracks as data, because the subsequent /tracks calls will return exactly that
  data = data['tracks']
  add_tracks(created['id'], get_track_uris(data))
  while data['next']:
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
  params = '&'.join([f'{key}={urllib.parse.quote(val)}' for key, val in auth_query_parameters.items()])
  return redirect(f'https://accounts.spotify.com/authorize?{params}')

def create_user(access_token, refresh_token):
  r = requests.get('https://api.spotify.com/v1/me', headers=auth_header(access_token))
  profile = r.json()
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
  session['expires'] = datetime.datetime.now() + datetime.timedelta(0, post_data['expires_in'])
  session['spotify_id'] = user['spotify_id']
  return redirect('/')
