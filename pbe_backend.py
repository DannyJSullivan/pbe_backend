import os
import random
import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv
import pymongo
from bson import ObjectId
import re

from flask import Flask
from flask_cors import CORS
from flask_restful import Api, reqparse, Resource
from unidecode import unidecode
import datetime

from oauth2client.service_account import ServiceAccountCredentials
import gspread
import json
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import requests
import time
from bs4 import BeautifulSoup

# Flask app setup
app = Flask(__name__)
api = Api(app)
parser = reqparse.RequestParser()
cors = CORS(app)

# MongoDB connections
mongo_uri = os.getenv("MONGO_URI")
client = pymongo.MongoClient(mongo_uri)
pbe_db = client.pbe
pbe_task_collection = pbe_db.tasks
pbe_player_collection = pbe_db.players


# HELPER METHODS
def ignore_case(x):
    re.compile(x, re.IGNORECASE)


def update_object(obj_from, obj_to, key):
    if obj_from.get(key) is not None and obj_from.get(key) != "":
        obj_to.update({key: obj_from.get(key)})
    else:
        if 'tpe' in key or 'number' in key or 'babip_' in key \
                or 'ak_' in key or 'gap_' in key or 'power_' in key \
                or 'ep_' in key or 'speed' in key or 'steal' in key \
                or 'bunt' in key or 'field_' in key or 'arm' in key \
                or 'double_' in key or 'c_' in key or 'mov_' in key \
                or 'con_' in key or 'stamina' in key or 'hold_' in key \
                or 'gb_' in key or 'fastball' in key or 'sinker' in key \
                or 'cutter' in key or 'curveball' in key \
                or 'slider' in key or 'changeup' in key \
                or 'splitter' in key or 'forkball' in key \
                or 'circle_' in key or 'screwball' in key \
                or 'knuckle' in key:
            obj_to.update({key: 0})
        else:
            obj_to.update({key: 'N/A'})


def get_player_info(obj_from, obj_to):
    update_object(obj_from, obj_to, 'player_forum_code')
    update_object(obj_from, obj_to, 'forum_name')
    update_object(obj_from, obj_to, 'team')
    update_object(obj_from, obj_to, 'league')
    update_object(obj_from, obj_to, 'conference')
    update_object(obj_from, obj_to, 'division')
    update_object(obj_from, obj_to, 'season')
    update_object(obj_from, obj_to, 'tpe')
    update_object(obj_from, obj_to, 'user_forum_code')
    update_object(obj_from, obj_to, 'last_updated')
    update_object(obj_from, obj_to, 'player_name')
    update_object(obj_from, obj_to, 'normalized_name')
    update_object(obj_from, obj_to, 'position')
    update_object(obj_from, obj_to, 'discord')
    update_object(obj_from, obj_to, 'tpe_banked')
    update_object(obj_from, obj_to, 'bats')
    update_object(obj_from, obj_to, 'throws')
    update_object(obj_from, obj_to, 'archetype')
    return obj_to


def get_batter_info(obj_from, obj_to):
    return obj_to


def get_pitcher_info(obj_from, obj_to):
    return obj_to


# return all possible info
def get_players_all():
    players = []
    cursor = pbe_player_collection.find({})
    for document in cursor:
        del document['_id']
        players.append(document)

    return players


# return all common info
def get_players_basic():
    players = []
    cursor = pbe_player_collection.find({})
    for player in cursor:
        p = {}
        players.append(get_player_info(player, p))
    return players


# return all common info for active players
def get_players_active_basic():
    players = []
    cursor = pbe_player_collection.find({})
    for player in cursor:
        p = {}
        try:
            if 'Retired' not in player['team']:
                players.append(get_player_info(player, p))
        except Exception as e:
            print('Player has no team: https://probaseballexperience.jcink.net/index.php?showtopic=28451'
                  + player['player_forum_code'])
    return players


# return all common info for players in the majors
def get_players_majors():
    players = []
    cursor = pbe_player_collection.find({})
    for player in cursor:
        p = {}
        try:
            if 'Retired' not in player['team'] and 'Draftees' not in player['team'] and 'Free Agents' \
                    not in player['team'] and 'MiLPBE' not in player['league']:
                players.append(get_player_info(player, p))
        except Exception as e:
            print('Player has no team or league: https://probaseballexperience.jcink.net/index.php?showtopic=28451'
                  + player['player_forum_code'])
    return players


# return all common info for players in the minors
def get_players_minors():
    players = []
    cursor = pbe_player_collection.find({})
    for player in cursor:
        p = {}
        try:
            if 'Retired' not in player['team'] and 'Draftees' not in player['team'] and 'Free Agents' \
                    not in player['team'] and player['league'] != 'PBE':
                players.append(get_player_info(player, p))
        except Exception as e:
            print('Player has no team or league: https://probaseballexperience.jcink.net/index.php?showtopic=28451'
                  + player['player_forum_code'])
    return players


# return teams w/ consolidated info
def get_teams():
    teams_list = []
    players = pbe_player_collection.find({})
    for player in players:
        try:
            team_list_counter = 0
            team_exists = False
            for team in teams_list:
                if team['name'] in player['team']:
                    team_exists = True
                    break
                team_list_counter = team_list_counter + 1

            if team_exists:
                team_to_update = teams_list[team_list_counter]
                tpe_total = team_to_update.get('tpe') + player['tpe']
                avg_tpe = round(tpe_total / (team_to_update.get('player_count') + 1), 2)
                teams_list[team_list_counter].update({'tpe': tpe_total,
                                                      'average_tpe': avg_tpe,
                                                      'player_count': team_to_update.get('player_count') + 1})
            else:
                teams_list.append({'name': player['team'],
                                   'league': player['league'],
                                   'conference': player['conference'],
                                   'division': player['division'],
                                   'tpe': player['tpe'],
                                   'average_tpe': player['tpe'],
                                   'player_count': 1})
        except Exception as e:
            print('Error getting team for player: https://probaseballexperience.jcink.net/index.php?showtopic=28451'
                  + player['player_forum_code'])
            print(e)

    return teams_list


def get_teams_active():
    teams_list = []
    players = pbe_player_collection.find({})
    for player in players:
        try:
            if 'Retired' not in player['team'] and 'Free Agents' not in player['team'] \
                    and 'Draftees' not in player['team']:
                team_list_counter = 0
                team_exists = False
                for team in teams_list:
                    if team['name'] in player['team']:
                        team_exists = True
                        break
                    team_list_counter = team_list_counter + 1

                if team_exists:
                    team_to_update = teams_list[team_list_counter]
                    tpe_total = team_to_update.get('tpe') + player['tpe']
                    avg_tpe = round(tpe_total / (team_to_update.get('player_count') + 1), 2)
                    teams_list[team_list_counter].update({'tpe': tpe_total,
                                                          'average_tpe': avg_tpe,
                                                          'player_count': team_to_update.get('player_count') + 1})
                else:
                    teams_list.append({'name': player['team'],
                                       'league': player['league'],
                                       'conference': player['conference'],
                                       'division': player['division'],
                                       'tpe': player['tpe'],
                                       'average_tpe': player['tpe'],
                                       'player_count': 1})
        except Exception as e:
            print('Error getting team for player: https://probaseballexperience.jcink.net/index.php?showtopic=28451'
                  + player['player_forum_code'])
            print(e)

    return teams_list


# return only position players
def get_players_batters():
    return


# return only pitchers
def get_players_pitchers():
    return


# get information for specific player
def get_player(player_id):
    return


# get information for specific user
def get_user(user_id):
    return


# TODO: scrape stats, return them here...
def get_player_stats(player_id):
    return


# TODO: scrape bank, return them here...
def get_player_bank():
    return


# ENDPOINT CLASSES
class Home(Resource):
    def get(self):
        return 'PBE Backend Service'


class PlayersAll(Resource):
    def get(self):
        return get_players_all()


class PlayersBasic(Resource):
    def get(self):
        return get_players_basic()


class PlayersBasicActive(Resource):
    def get(self):
        return get_players_active_basic()


class PlayersBasicMajors(Resource):
    def get(self):
        return get_players_majors()


class PlayersBasicMinors(Resource):
    def get(self):
        return get_players_minors()


class Teams(Resource):
    def get(self):
        return get_teams()


class TeamsActive(Resource):
    def get(self):
        return get_teams_active()


# ENDPOINTS
api.add_resource(Home, '/')
api.add_resource(PlayersAll, '/players/all')
api.add_resource(PlayersBasic, '/players/basic')
api.add_resource(PlayersBasicActive, '/players/basic/active')
api.add_resource(PlayersBasicMajors, '/players/basic/majors')
api.add_resource(PlayersBasicMinors, '/players/basic/minors')
api.add_resource(Teams, '/teams')
api.add_resource(TeamsActive, '/teams/active')
# api.add_resource(PlayersBasic, '/teams/basic/active')

# APPLICATION
if __name__ == '__main__':
    app.run()
