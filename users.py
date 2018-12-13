import datetime

class Users():
  def __init__(self, db):
    self.collection = db['users']

  def add_playlist(self, user, playlist_id, playlist_id_original):
    playlist = {
      'id': playlist_id,
      'original_id': playlist_id_original,
      'last_checked': datetime.datetime.utcnow(),
    }
    self.collection.find_one_and_update(
      {'spotify_id': user},
      {'$push': {'playlists': playlist}},
    )

  def create_user(self, spotify, refresh_token):
    profile = spotify.get_profile()
    user = {
      'spotify_id': profile['id'],
      'refresh_token': refresh_token,
      'playlists': [],
    }
    if not self.collection.find_one({'spotify_id': profile['id']}):
      self.collection.insert_one(user)
    return user
  