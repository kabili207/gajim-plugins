# -*- coding: utf-8 -*-

import os
import json
import threading

from plugins import GajimPlugin
from plugins.helpers import log_calls
from common import gajim
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class MusicTrackInfo(object):
    __slots__ = ['title', 'album', 'artist', 'duration', 'track_number',
        'paused', 'url', 'albumartist']

class TunesServer(BaseHTTPRequestHandler):
    def __init__(self, post_callback, *args):
        self.post_callback = post_callback
        BaseHTTPRequestHandler.__init__(self, *args)

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write("[]")

    def do_HEAD(self):
        self._set_headers()
        
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        tune_data = json.loads(post_data)
        self.post_callback(tune_data)
        self._set_headers()
        self.wfile.write("[]")

class HttpTunesPlugin(GajimPlugin):
    @log_calls('HttpTunesPlugin')
    def init(self):
        self.config_dialog = None
        self.artist = self.title = self.source = ''

    @log_calls('HttpTunesPlugin')
    def activate(self):
        self._last_playing_music = None
        def handler(*args):
            TunesServer(self.properties_changed, *args)
        self.httpd = HTTPServer(('localhost', 6305), handler)
        self.thread = threading.Thread(target = self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @log_calls('HttpTunesPlugin')
    def deactivate(self):
        assassin = threading.Thread(target = self.httpd.shutdown)
        assassin.daemon = True
        assassin.start()

    def properties_changed(self, tunes):
        if not tunes['is_playing']:
            self.title = self.artist = self.source = ''
            self.music_track_changed(None)
            return

        if not tunes['has_song']:
            return

        data = tunes['song']
        info = MusicTrackInfo()
        info.title = data["title"]
        info.album = data["album"]
        info.artist = data["artist"]
        info.albumartist = data["album_artist"]
        info.duration = data['time']

        self._last_playing_music = info
        self.music_track_changed(info)

    @log_calls('HttpTunesPlugin')
    def music_track_changed(self, music_track_info):
        accounts = gajim.connections.keys()
        
        is_paused = hasattr(music_track_info, 'paused') and \
            music_track_info.paused == 0
        if not music_track_info or is_paused:
            artist = title = source = ''
        else:
            artist = music_track_info.artist
            title = music_track_info.title
            source = music_track_info.album
        for acct in accounts:
            if not gajim.account_is_connected(acct):
                continue
            if not gajim.connections[acct].pep_supported:
                continue
            if not gajim.config.get_per('accounts', acct, 'publish_tune'):
                continue
            if gajim.connections[acct].music_track_info == music_track_info:
                continue
            gajim.connections[acct].send_tune(artist, title, source)
            gajim.connections[acct].music_track_info = music_track_info