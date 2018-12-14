import base64, os, urllib
import dateutil.parser
import requests

CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI')

SCOPES = ['playlist-modify-public', 'playlist-modify-private']

class Spotify:
  def __init__(self, user_id, access_token):
    self.user_id = user_id
    self.auth = {'Authorization': f'Bearer {access_token}'}

  def request(self, url, method='GET'):
    r = requests.request(method, url, headers=self.auth)
    return r.json()

  def get_profile(self):
    r = requests.get('https://api.spotify.com/v1/me', headers=self.auth)
    return r.json()

  def get_playlist(self, playlist_id):
    r = requests.get(
      f'https://api.spotify.com/v1/playlists/{playlist_id}',
      headers=self.auth,
    )
    return r.json()

  def create_playlist(self, name):
    r = requests.post(
      f'https://api.spotify.com/v1/users/{self.user_id}/playlists',
      headers=self.auth,
      json={'name': name, 'public': False},
    )
    return r.json()
  
  def add_tracks(self, playlist_id, track_uris):
    return requests.post(
      f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
      headers=self.auth,
      json={'uris': track_uris},
    )

  def get_track_uris(self, playlist_id, since=None):
    items = []
    r = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=self.auth)
    data = r.json()
    items += data['items']
    while data['next']:
      r = requests.get(data['next'], headers=self.auth)
      data = r.json()
      items += data['items']
    if since:
      def is_new(item, date):
        return dateutil.parser.parse(item['added_at'], ignoretz=True) > date
      items = [item for item in items if is_new(item, since) and not item['is_local']]
    return [item['track']['uri'] for item in items]

  @staticmethod
  def get_playlist_id(playlist_uri):
    return playlist_uri.split(':').pop()

  @staticmethod
  def get_redirect_url():
    auth_query_parameters = {
      'response_type': 'code',
      'scope': ' '.join(SCOPES),
      # 'state': STATE,
      'client_id': CLIENT_ID,
      'redirect_uri': REDIRECT_URI,
    }
    params = '&'.join([f'{key}={urllib.parse.quote(val)}' for key, val in auth_query_parameters.items()])
    return f'https://accounts.spotify.com/authorize?{params}'

  @staticmethod
  def exchange_code(code):
    code_payload = {
      'grant_type': 'authorization_code',
      'code': str(code),
      'redirect_uri': REDIRECT_URI,
      'client_id': CLIENT_ID,
      'client_secret': CLIENT_SECRET,
    }
    r = requests.post('https://accounts.spotify.com/api/token', data=code_payload)
    return r.json()

  @staticmethod
  def update_token(refresh_token):
    client = f'{CLIENT_ID}:{CLIENT_SECRET}'
    base64encoded = base64.b64encode(client.encode())
    headers = {'Authorization': f'Basic {base64encoded.decode()}'}
    payload = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    r = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=payload)
    return r.json()
