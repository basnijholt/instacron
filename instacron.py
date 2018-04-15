#!/usr/bin/env python3.6

from glob import glob
from json import loads
import os.path
import random
import time

import dateutil.parser
import emoji
import instabot
import parse
from requests import get


def read_config(cfg='~/.config/instacron/config'):
    """Read the config.

    Create a config file at `cfg` with the
    following information and structure:
        my_user_name
        my_difficult_password
    """
    _cfg = os.path.expanduser(cfg)
    try:
        with open(_cfg, 'r') as f:
            user, pw = [s.replace('\n', '') for s in f.readlines()]
    except Exception:
        import getpass
        print(f"\nReading config file `{cfg}` didn't work")
        user = input('Enter username and hit enter\n')
        pw = getpass.getpass('Enter password and hit enter\n')
        save_config = input(f"Save to config file `{cfg}` (y/N)? ").lower() == 'y'
        if save_config:
            os.makedirs(os.path.dirname(_cfg), exist_ok=True)
            with open(_cfg, 'w') as f:
                f.write(f'{user}\n{pw}')
    return {'username': user, 'password': pw}


def get_all_photos(uploaded_file, photo_folder):
    with open(uploaded_file) as f:
        uploaded = [line.rstrip() for line in f]

    photos = glob(os.path.join(photo_folder, '*.jpg'))
    photos = [photo for photo in photos if os.path.basename(photo) not in uploaded]
    return photos


def choose_random_photo(uploaded_file, photo_folder):
    photos = get_all_photos(uploaded_file, photo_folder)
    photo = random.choice(photos) # choose a random photo
    return photo


def parse_photo_name(photo):
    """All my photos are named like `854-20151121-Peru-Cusco.jpg`"""
    templates = ['{i}-{date}-{country}-{city}-{rest}.jpg',
                 '{i}-{date}-{country}-{city}.jpg']
    parsed = None
    for template in templates:
        parsed = parse.parse(template, photo)
        if parsed is not None:
            d = parsed.named
            if 'rest' in d:
                d['rest'] = d['rest'].replace('-', ' ')
            d['date'] = dateutil.parser.parse(d['date'])
            return d


def _get_random_quote():
    response = get('http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en')
    response = loads(response.text)
    quote = response['quoteText']
    author = response['quoteAuthor']
    return quote


def get_random_quote():
    for _ in range(10):
        try:
            return _get_random_quote()
        except Exception:
            time.sleep(1)
            pass


def random_emoji():
    # Don't return a random flag (hence the `islower`)
    emojis = [e for e, unicode in emoji.UNICODE_EMOJI.items()
              if unicode[1].islower() and len(e) == 1]
    return random.choice(emojis)


def parse_photo_info(photo_info):
    country = photo_info["country"]
    flag = country.replace(' ', '_')
    flag = emoji.emojize(f':{flag}:')

    # Add two random emojis, the date, and the location info with flag emoji
    date = "{:%d %B %Y}".format(photo_info['date'])
    city = photo_info["city"]
    caption = random_emoji() + random_emoji() + 3 * ' '
    caption += f'Taken in {country}, {city} {flag} on {date}. '

    # Advertize the Python script
    hashtags = ['instacron', country.lower(), city.lower().replace(' ', '')]
    caption += ' '.join('#' + h for h in hashtags)
    caption += emoji.emojize(':snake:') + ' www.instacron.nijho.lt'

    return caption


def append_to_uploaded_file(uploaded_file, photo):
    with open(uploaded_file, 'a') as f:
        f.write(os.path.basename(photo) + '\n')


def main():
    caption = get_random_quote()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    photo_folder = os.path.join(dir_path, 'photos')
    uploaded_file = os.path.join(dir_path, 'uploaded.txt')
    photo = choose_random_photo(uploaded_file, photo_folder)
    photo_info = parse_photo_name(os.path.basename(photo))
    if photo_info:
        caption += parse_photo_info(photo_info)
    
    print(f'Uploading `{photo}` with caption:\n\n {caption}')

    bot = instabot.Bot()
    bot.login(**read_config())
    upload = bot.uploadPhoto(photo, caption=caption)
    print(upload)
    # After succeeding append the fname to the uploaded.txt file
    if upload:
        append_to_uploaded_file(uploaded_file, photo)
    bot.logout()

if __name__ == "__main__":
    main()
