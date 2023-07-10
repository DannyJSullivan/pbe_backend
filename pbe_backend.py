import json
import os
from datetime import datetime, timedelta

import pymongo
import re

import requests
from bs4 import BeautifulSoup
from flask import Flask, send_from_directory, request
from flask_cors import CORS
from flask_restful import Api, reqparse, Resource
import json2html

import pandas as pd

# Flask app setup
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

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
bank_collection = pbe_db.bank
task_collection = pbe_db.tasks


# TODO: When adding new imports, be sure to add them to the requirements.txt file.
#  Run pip freeze > requirements.txt to do so.


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
    update_object(obj_from, obj_to, 'birthplace')
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
            print(e)
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
            print(e)
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
            print(e)
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


# get 10 most recent transactions for a user
def get_user_transactions(forum_name):
    t1 = lookup_transactions(forum_name)
    t2 = lookup_video_transactions(forum_name)
    t3 = lookup_media_transactions(forum_name)
    t4 = lookup_graphic_transactions(forum_name)

    t_list = []

    for t in t1:
        t_list.append(t)
    for t in t2:
        t_list.append(t)
    for t in t3:
        t_list.append(t)
    for t in t4:
        t_list.append(t)

    try:
        t_list.sort(key=lambda tr: datetime.strptime(tr[0], "%m/%d/%Y"))
        return format_most_recent_transactions(t_list, forum_name, False)
    except:
        return format_most_recent_transactions(t1, forum_name, True)


def lookup_transactions(forum_name):
    bank_sheet_id = "15OMqbS-8cA21JFdettLs6A0K4A1l4Vjls7031uAFAkc"
    bank_sheet_range = 'Logs!A:H'

    key = json.loads(os.environ.get("GCP_KEY"))
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(key)

    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=bank_sheet_id,
                                range=bank_sheet_range).execute()
    values = result.get('values', [])

    ts = []

    for row in values:
        if row[2].lower() == forum_name.lower():
            if len(row) < 8:
                ts.append([row[0], row[2], row[6], "N/A"])
            else:
                ts.append([row[0], row[2], row[6], row[7]])

    return ts


def lookup_media_transactions(forum_name):
    bank_sheet_id = "15OMqbS-8cA21JFdettLs6A0K4A1l4Vjls7031uAFAkc"
    bank_sheet_range = 'Media Logs!A:R'

    key = json.loads(os.environ.get("GCP_KEY"))
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(key)

    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=bank_sheet_id,
                                range=bank_sheet_range).execute()
    values = result.get('values', [])

    ts = []

    for row in values:
        if row[1].lower() == forum_name.lower():
            ts.append([row[0], row[1], row[15], row[2] + ": " + row[3]])

    return ts


def lookup_graphic_transactions(forum_name):
    bank_sheet_id = "15OMqbS-8cA21JFdettLs6A0K4A1l4Vjls7031uAFAkc"
    bank_sheet_range = 'Graphic Logs!A:F'

    key = json.loads(os.environ.get("GCP_KEY"))
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(key)

    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=bank_sheet_id,
                                range=bank_sheet_range).execute()
    values = result.get('values', [])

    ts = []

    for row in values:
        if len(row) > 1:
            if row[2].lower() == forum_name.lower():
                if len(row) > 5:
                    ts.append([row[0], row[2], row[3], row[5]])
                else:
                    ts.append([row[0], row[2], row[3], "N/A"])

    return ts


def lookup_video_transactions(forum_name):
    bank_sheet_id = "15OMqbS-8cA21JFdettLs6A0K4A1l4Vjls7031uAFAkc"
    bank_sheet_range = 'Video Logs!A:I'

    key = json.loads(os.environ.get("GCP_KEY"))
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(key)

    service = build('sheets', 'v4', credentials=credentials)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=bank_sheet_id,
                                range=bank_sheet_range).execute()
    values = result.get('values', [])

    ts = []

    for row in values:
        if len(row) > 1 and row[2].lower() == forum_name.lower():
            ts.append([row[0], row[2], row[6], row[3]])

    return ts


def format_most_recent_transactions(ts, forum_name, error):
    if len(ts) == 0:
        return "No transactions found for " + forum_name + "."

    results = []

    for t in ts:
        results.append({'date': t[0], 'forum_name': t[1], 'amount': t[2], 'reason': t[3]})

    return results


def pad_string_r(value, amount):
    return str(value).rjust(amount)


def pad_string_l(value, amount):
    return str(value).ljust(amount)


def ignore_case(x):
    re.compile(x, re.IGNORECASE)


def get_active_player_by_forum_name(name):
    players = pbe_player_collection.find({"forum_name": re.compile(str(name), re.IGNORECASE)})

    player = None
    for p in players:
        print(p)

        if p is not None and "Retired" not in p.get("league") and "Retired" not in p.get("team") \
                and p.get("forum_name").lower() == name.lower():
            player = p

    return player


def get_user_overview(forum_name):
    user_info = get_active_player_by_forum_name(forum_name)
    balance = bank_collection.find_one({"username": user_info["forum_name"]})['balance']
    last_seen = get_last_seen(user_info['user_url'])

    return {
        "player_name": user_info['player_name'],
        "season": user_info["season"],
        "team": user_info["team"],
        "position": user_info["position"],
        "tpe": user_info["tpe"],
        "forum_name": user_info["forum_name"],
        "last_seen": last_seen,
        "last_updated": user_info["last_updated"],
        "balance": balance,
        "tasks": get_tasks(user_info["forum_name"])
    }


def get_last_seen(url):
    page_content = requests.get(url).text
    soup = BeautifulSoup(page_content, "html.parser")

    profile_stats = soup.find("div", attrs={"id": "profile-statistics"})

    divs = profile_stats.findAll("div", attrs={"class": "row2"})

    if len(divs) >= 4:
        return str(divs[2].text).replace("Last Seen: ", "")

    return "Could not find profile info!"


def get_tasks(forum_name):
    topic_nums = []

    tasks = []

    # activity check (only get the top one)
    ac = "https://probaseballexperience.jcink.net/index.php?showforum=77"

    # point tasks (get all forum topics except for the last one
    pt = "https://probaseballexperience.jcink.net/index.php?showforum=56"

    page_content = requests.get(ac).text
    soup = BeautifulSoup(page_content, "html.parser")
    table = soup.find("div", attrs={"id": "topic-list"})
    newest_topic = table.find("tr", attrs={"class": "topic-row"})
    rows = newest_topic.findAll("td", attrs={"class": "row4"})
    link = rows[1].find("a").get("href")
    name = str(rows[1].text).replace("\n", "").split("(")[0].strip()

    topic_nums.append(get_topic_num_from_url(link))

    page_content = requests.get(pt).text
    soup = BeautifulSoup(page_content, "html.parser")
    table = soup.find("div", attrs={"id": "topic-list"})
    rows = table.findAll("tr", attrs={"class": "topic-row"})

    for row in rows:
        # make sure thread is not locked
        if row.find("img", attrs={"title": "Locked thread"}) is None:
            urls = row.findAll("td", attrs={"class": "row4"})
            if len(urls) > 2:
                link = urls[1].find("a").get("href")
                name = str(urls[1].text).replace("\n", "").split("(Pages")[0].strip()
                if name != "Introduction PT":
                    topic_nums.append(get_topic_num_from_url(link))

    for topic_num in topic_nums:
        task_result = did_user_complete_task(forum_name, topic_num)
        tasks.append({task_result[0]: task_result[1]})

    return tasks


def get_topic_num_from_url(url):
    return re.split('&showtopic=', url)[1]


def did_user_complete_task(user, task):
    result = []

    task = task_collection.find_one({"topic_num": task})
    result.append(task.get('task'))

    if task is not None:
        for forum_name in task['names']:
            if user.lower() == forum_name.lower():
                result.append(True)
                return result

        result.append(False)
        return result


# Forum Scraping

class Post:
    forum_name: ""
    date: ""

    def __init__(self, t_forum_name, t_date):
        self.forum_name = t_forum_name
        self.date = t_date

    def as_dict(self):
        return {'forum_name': self.forum_name, 'date': self.date}


class UserPosts:
    forum_name: ""
    dates: []
    count: 0
    money: 0

    def __init__(self, t_forum_name, t_date):
        self.forum_name = t_forum_name
        self.dates = t_date
        self.count = len(set(self.dates))

        money = 0
        if self.count <= 3:
            money = self.count * 250000
        elif 3 < self.count < 7:
            money = 750000 + ((self.count - 3) * 62500)
        elif self.count >= 7:
            money = 1000000

        self.money = money

    def as_dict(self):
        return {'forum_name': self.forum_name, 'money': self.money, 'date': self.dates, 'count': self.count}


def scrape_forum(topic_num):
    url = "https://probaseballexperience.jcink.net/index.php?showtopic=" + topic_num
    page_content = requests.get(url).text
    soup = BeautifulSoup(page_content, "html.parser")

    pages = soup.find("span", attrs={"class": "pagination_pagetxt"})

    if pages is not None:
        pages = pages.text
        page_count = re.sub("Pages: \\(", "", pages)
        page_count = re.sub("\\)", "", page_count)
    else:
        page_count = 1

    page_count = int(page_count)

    posts = []

    # go through each page of posts
    for x in range(1, page_count + 1):
        if x == 1:
            page_content = requests.get(url + "&st=0").text
        else:
            page_content = requests.get(url + "&st=" + str(((x - 1) * 15))).text

        soup = BeautifulSoup(page_content, "html.parser")
        names = soup.findAll("span", attrs={"class": "normalname"})
        dates = soup.findAll("span", attrs={"class": "postdetails"})

        # get every other date since this picks up unrelated info
        del dates[1::2]

        # go through each post on a page, create users for each post and track necessary info
        for i in range(0, len(names)):
            date = dates[i].text.replace("Posted: ", "").split(",")[0]

            if 'Today' in date or 'ago' in date:
                date = datetime.today().strftime("%b %d %Y")
            elif 'Yesterday' in date:
                date = (datetime.today() - timedelta(days=1)).strftime("%b %d %Y")

            post = Post(names[i].text, date)
            posts.append(post)

    user_dates = {}
    for p in posts:
        if user_dates.get(p.forum_name) is not None:
            ud = user_dates.get(p.forum_name)
            ud.append(p.date)
            user_dates.update({p.forum_name: ud})
        else:
            date = [p.date]
            user_dates.update({p.forum_name: date})

    posts_summary = []
    for key in user_dates:
        posts_summary.append(UserPosts(key, user_dates.get(key)))

    # remove first element
    posts.pop(0)

    # export to csv
    filename = export_to_csv(posts_summary, topic_num)
    return send_from_directory("./", filename)


def export_to_csv(posts, topic_num):
    data = pd.DataFrame([p.as_dict() for p in posts])
    data.to_csv("PBE_Forum_Scraper_" + topic_num + ".csv")
    return "PBE_Forum_Scraper_" + topic_num + ".csv"


def scrape_transactions(start_date, end_date):
    # trades
    trades = "https://probaseballexperience.jcink.net/index.php?showforum=172"
    signings = "https://probaseballexperience.jcink.net/index.php?showforum=179"
    bidding = "https://probaseballexperience.jcink.net/index.php?showforum=180"
    cuts = "https://probaseballexperience.jcink.net/index.php?showforum=184"

    urls = []

    print("getting urls from trades...")
    urls.extend(get_relevant_urls(trades, start_date, end_date))
    print("getting urls from signings...")
    urls.extend(get_relevant_urls(signings, start_date, end_date))
    print("getting urls from bids...")
    urls.extend(get_relevant_urls(bidding, start_date, end_date))
    print("getting urls from cuts...")
    urls.extend(get_relevant_urls(cuts, start_date, end_date))

    cm = {}

    counter = 1
    print("scraping transactions & updating members...")
    for url in urls:
        print("scraping url " + str(counter) + " of " + str(len(urls)))
        counter += 1

        compendium_members = scrape_transaction(url)

        for c in compendium_members:
            if is_compendium_member(c):
                if cm.get(c) is None:
                    cm.update({c: 1})
                else:
                    cm.update({c: cm.get(c) + 1})

    print(cm)
    return cm


def get_relevant_urls(url, start, end):
    urls = []
    page_content = requests.get(url).text
    soup = BeautifulSoup(page_content, "html.parser")

    pages = soup.find("span", attrs={"class": "pagination_pagetxt"})

    if pages is not None:
        pages = pages.text
        page_count = re.sub("Pages: \\(", "", pages)
        page_count = re.sub("\\)", "", page_count)
    else:
        page_count = 1

    page_count = int(page_count)

    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')

    # go through each page of posts
    for x in range(1, page_count + 1):
        if x == 1:
            page_content = requests.get(url + "&st=0").text
        else:
            page_content = requests.get(url + "&st=" + str(((x - 1) * 15))).text

        soup = BeautifulSoup(page_content, "html.parser")
        rows = soup.findAll("td", attrs={"class": "row4"})
        dates = soup.findAll("span", attrs={"class": "desc"})

        # get every other date since this picks up unrelated info
        del dates[0::2]

        # get every 4th row since this picks up unrelated info
        del rows[0::2]
        del rows[1::2]

        # get the urls from the rows
        all_urls = []
        for r in rows:
            all_urls.append(r.find("a").get("href"))

        # go through each post on a page, create users for each post and track necessary info
        for i in range(0, len(dates)):

            date = dates[i].text.split("-")[0].strip()\
                .replace("st ", " ").replace("nd ", " ").replace("rd ", " ").replace("th ", " ")

            post_date = datetime.strptime(date, "%d %B %Y")

            if start_date <= post_date <= end_date:
                print("adding url w/ post date of " + str(post_date))
                urls.append(all_urls[i])
            elif start_date > post_date:
                print("start date of " + str(start_date) + " is greater than " + str(post_date) + ". returning urls.")
                return urls

    return urls


def scrape_transaction(url):
    page_content = requests.get(url).text
    soup = BeautifulSoup(page_content, "html.parser")

    navstrip = soup.find("div", attrs={"id": "navstrip"})
    transaction_content = soup.find("div", attrs={"class": "postcolor"})
    forum_names = soup.findAll("span", attrs={"class": "normalname"})

    multiplier = 1
    if "Signings" in navstrip.text:
        transaction_number = transaction_content.findAll("a")
        if len(transaction_number) == 0:
            multiplier = 1
        else:
            multiplier = len(transaction_number)

    members = []

    counter = 0
    for name in forum_names:
        if counter != 0:
            members.extend([name.text] * multiplier)
        counter += 1

    return members


def is_compendium_member(name):
    if "danny" in name:
        return True

    if "jdwrecker" in name:
        return True

    if "Bayley" in name:
        return True

    if "Sen" in name:
        return True

    if "overdoo" in name:
        return True

    if "PersonMann" in name:
        return True

    if "CMac" in name:
        return True

    if "Haseo" in name:
        return True

    return False


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


class PlayersBasicHTML(Resource):
    def get(self):
        return json2html.json2html.convert(json=get_players_basic())


class PlayersBasicActive(Resource):
    def get(self):
        return get_players_active_basic()


class PlayersBasicActiveHTML(Resource):
    def get(self):
        return json2html.json2html.convert(json=get_players_active_basic())


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


class UserTransactions(Resource):
    def get(self, forum_name):
        return get_user_transactions(forum_name)


class UserOverview(Resource):
    def get(self, forum_name):
        return get_user_overview(forum_name)


class ForumScraper(Resource):
    def get(self, topic_num):
        return scrape_forum(topic_num)


class TransactionScraper(Resource):
    def get(self, start_date, end_date):
        return scrape_transactions(start_date, end_date)


# ENDPOINTS
api.add_resource(Home, '/')
api.add_resource(PlayersAll, '/players/all')
api.add_resource(PlayersBasic, '/players/basic')
api.add_resource(PlayersBasicHTML, '/players/basic/html')
api.add_resource(PlayersBasicActive, '/players/basic/active')
api.add_resource(PlayersBasicActiveHTML, '/players/basic/active/html')
api.add_resource(PlayersBasicMajors, '/players/basic/majors')
api.add_resource(PlayersBasicMinors, '/players/basic/minors')
api.add_resource(Teams, '/teams')
api.add_resource(TeamsActive, '/teams/active')
# api.add_resource(PlayersBasic, '/teams/basic/active')
api.add_resource(ForumScraper, '/scrape/<topic_num>')
api.add_resource(TransactionScraper, '/scrape/transactions/<start_date>/<end_date>')

# ENDPOINTS FOR OTHERS
api.add_resource(UserTransactions, '/user/<forum_name>/transactions')  # for Nerji
api.add_resource(UserOverview, '/user/<forum_name>/overview')  # for Nerji

# APPLICATION
if __name__ == '__main__':
    app.run()
