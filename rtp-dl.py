#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
import requests
from bs4 import BeautifulSoup
import youtube_dl
import base64
from urllib.parse import unquote
import json
from pymkv import MKVFile, MKVTrack
import shutil


def fix_filename(filename):
    # Remove unsafe characters
    filename = "".join([c if c not in ['"', "'", '/', '\\',
                       '*', ':', '?', '<', '>', '|'] else "" for c in filename])
    # Replace spaces to dot
    filename = filename.replace(' ', '.')
    keepcharacters = ('.', '_')
    "".join(c for c in filename if c.isalnum() or c in keepcharacters).rstrip()
    # replace more than 1 dot to 1 dot
    filename = re.sub(r'\.+', ".", filename)
    filename = re.sub(r'\.$', "", filename)  # remove last dot
    filename = filename.replace("?", "")  # remove question mark
    return filename


def parse_episodes(progId):
    page = 1
    while True:
        url = "{}/play/bg_l_ep/?listProgram={}&page={}".format(
            base_url, progId, page)
        print("Scraping Page {} ({})".format(page, url))
        response = requests.get(
            url,
            headers={
                'User-agent': 'Mozilla/5.0',
                'Cookie': 'rtp_cookie_parental=0; rtp_privacy=666; rtp_cookie_privacy=permit 1,2,3,4; googlepersonalization=1; _recid='
            }
        )
        soup = BeautifulSoup(response.content, "html.parser")

        if soup.find('article') is None:
            sys.exit("No more pages.")

        for article in soup.find_all('article'):
            url = article.find('a')['href']
            yield base_url + url
        page += 1


def find_m3u8(html):
    # Search for `var f = {hls : atob(..[...]..)}` and filter m3u8 extension
    whole = re.findall(r'var\s*f\s*=\s*({\s*hls\s*:\s*.+\[.+\].+\s*})', html)
    matches = re.findall(r'\[[^\]]+\]', whole[-1 if len(whole) > 1 else 0])
    m3u8 = None
    for m in matches:
        encoded_list = json.loads(m)
        url = unquote("".join(encoded_list))
        url = base64.b64decode(url).decode("utf-8")
        if url.endswith(".m3u8"):
            m3u8 = url
            break
    return m3u8


def request_episode(url):
    response_ok = False
    attempts = 0

    while not response_ok:
        if attempts >= 3:
            sys.exit('Could not fetch url: {}\nExiting...'.format(url))
        elif attempts >= 1:
            print('Retrying fetch url: {}'.format(url))
        attempts += 1

        r = requests.get(
            url,
            headers={
                'User-agent': 'Mozilla/5.0',
                'Cookie': 'rtp_cookie_parental=0; rtp_privacy=666; rtp_cookie_privacy=permit 1,2,3,4; googlepersonalization=1; _recid='
            }
        )
        if r.ok:
            response_ok = True

    return r


def fetch_episode_data(url):
    r = request_episode(url)
    soup = BeautifulSoup(r.content, "html.parser")
    vod_data_soup = soup.find("div", class_="vod-data")

    # Getting parts
    parts = [{
        "url": url,
        "m3u8": find_m3u8(r.text)
    }]
    if soup.find("div", class_="section-parts"):
        for c in soup.find('div', class_="section-parts").find_all("li")[1:]:
            part_url = base_url+c.find("a").get("href")
            parts.append({
                "url": part_url,
                "m3u8": find_m3u8(request_episode(part_url).text)
            })

    # Find episode name
    episode_name_soup = vod_data_soup.find("p").find(class_="vod-title")
    if episode_name_soup:
        episode_name = episode_name_soup.text.strip()
    else:
        episode_name = None

    # Find episode season
    episode_season_soup = vod_data_soup.find(
        "p").find("span", class_="episode-season")
    if episode_season_soup:
        episode_season = int(
            re.sub(r'^[^\d]*', "", episode_season_soup.text.strip()))
    else:
        episode_season = None

    # Find episode number
    episode_number_soup = vod_data_soup.find(
        "p").find("span", class_="episode-number")
    if episode_number_soup:
        episode_number = episode_number_soup.text.strip()
        episode_number = episode_number.replace("Ep. ", "")
        try:
            episode_number = int(episode_number)
        except:
            should_input = True
            while should_input:
                print("Could not detect episode number, please insert one, available options are:\n",
                      "- N - Unknown episode number \n",
                      "- <number> - Assume this episode number \n",
                      "- <enter> - Ignore this episode and don't download ")
                temp = input()
                if temp.strip() == "":
                    return None
                elif temp.strip().upper() == "N":
                    episode_number = None
                    should_input = False
                else:
                    episode_number = int(temp.strip())
                    should_input = False

    episode_data = {
        "progName": vod_data_soup.find("header").find("h1", class_="h3").find("a").text.strip(),
        "name": episode_name,
        "season": episode_season,
        "episode": int(vod_data_soup.find("p").find("span", class_="episode-number").text.strip().replace("Ep. ", "")),
        "parts": parts
    }
    episode_data["filename"] = fix_filename("{progName} {season_prefix}{season}E{episode:02d} {name}".format(
        **{k: "" if v is None else v for k, v in episode_data.items()}, season_prefix="S" if episode_data["season"] else ""))
    return episode_data


def download(m3u8, filename):
    opts = {
        "outtmpl": filename
    }
    with youtube_dl.YoutubeDL(opts) as ydl:
        print("Downloading {} {}".format(
            episode_data["progName"], episode_data["name"]))
        ydl.download([m3u8])
        return True


if __name__ == "__main__":
    user_params = {"progId": None, "episode": None, "season": None}
    if "-e" in sys.argv:
        user_params["episode"] = int(sys.argv[sys.argv.index("-e")+1])
        sys.argv.pop(sys.argv.index("-e")+1)
        sys.argv.pop(sys.argv.index("-e"))
    if "-s" in sys.argv:
        user_params["season"] = int(sys.argv[sys.argv.index("-s")+1])
        sys.argv.pop(sys.argv.index("-s")+1)
        sys.argv.pop(sys.argv.index("-s"))
    if len(sys.argv) != 2:
        sys.exit(
            "Run with {} [progId] [-e EpisodeNumber: Optional] [-s SeasonNumber: Optional]".format(sys.argv[0]))

    base_url = "https://www.rtp.pt"

    progId_regex_search = re.search('^[pP]?(\d+)$', sys.argv[1])
    if progId_regex_search is None:
        sys.exit("invalid progId")
    progId = progId_regex_search.groups()[0]

    script_path = os.path.dirname(os.path.realpath(__file__))

    for episode_url in parse_episodes(progId):
        # Fetch episode data
        episode_data = fetch_episode_data(episode_url)
        if episode_data is None:
            continue

        # Verify if match user params
        if (user_params["episode"] is not None):
            if (user_params["episode"] != episode_data["episode"]):
                continue
        if (user_params["season"] is not None):
            if (user_params["season"] != episode_data["season"]):
                continue

        downloaded_files = []

        # Setting paths
        download_folder_path = os.path.join(
            os.getcwd(), episode_data["progName"])
        temp_folder_path = os.path.join(download_folder_path, ".temp")
        list_file_path = os.path.join(temp_folder_path, "list.txt")

        # Create temp folder
        os.makedirs(temp_folder_path, exist_ok=True)

        # Download parts
        # and append to a text file
        # so that ffmpeg can manage
        with open(list_file_path, "w") as f:
            for i, u in enumerate(episode_data["parts"]):
                print(u)
                filename_path = "{}.pt{:d}.mp4".format(os.path.join(
                    temp_folder_path, episode_data["filename"]), i+1)
                download(u["m3u8"], filename_path)
                downloaded_files.append(filename_path)
                f.write("file '{}'\n".format(filename_path))

        # Merge parts if more than 1
        if len(downloaded_files) > 1:
            final_file = os.path.join(
                temp_folder_path, "{}.mp4".format(episode_data["filename"]))
            os.system(
                'ffmpeg -safe 0 -f concat -i "{}" -c copy "{}"'.format(list_file_path, final_file))
        else:
            final_file = downloaded_files[0]

        # Make an mkv file with useful information like title and audio language
        mkv = MKVFile(title="{} - {}".format(
            episode_data["progName"], episode_data["name"] if episode_data["name"] else "*Sem nome*"))
        mkv.add_track(MKVTrack(final_file, language="por"))
        mkv.add_track(MKVTrack(final_file, 1, language="por"))
        mkv.mux("{}.mkv".format(os.path.join(
            download_folder_path, episode_data["filename"])))

        # Remove the temporary files
        shutil.rmtree(temp_folder_path)
