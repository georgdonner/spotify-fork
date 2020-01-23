import datetime

class Users():
  def __init__(self, db):
    self.collection = db['users']

  def get_all(self):
    return self.collection.find()

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

  def add_playlist(self, user, name, playlist_id, playlist_id_original):
    playlist = {
      'name': name,
      'id': playlist_id,
      'original_id': playlist_id_original,
      'last_checked': datetime.datetime.utcnow(),
    }
    self.collection.find_one_and_update(
      {'spotify_id': user},
      {'$push': {'playlists': playlist}},
    )

  def remove_playlist(self, user, playlist_id):
    self.collection.find_one_and_update(
      {'spotify_id': user},
      {'$pull': {'playlists': {'id': playlist_id}}},
    )

  def playlist_updated(self, user, playlist_id):
    self.collection.update_one(
      {'spotify_id': user, 'playlists.id': playlist_id},
      {'$set': {'playlists.$.last_checked': datetime.datetime.utcnow()}}
    )
  