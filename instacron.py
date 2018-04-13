#!/usr/bin/env python3.6

from glob import glob
from json import loads
import os.path
import random

import dateutil.parser
import emoji
from instabot import Bot
import parse
from requests import get


def read_config():
    # Read the config
    with open(os.path.expanduser('~/.config/instacron/config'), 'r') as f:
        """Create a config file at ~/.config/instacron/config with the
        following information and structure:
            my_user_name
            my_difficult_password
        """
        user, pw = [s.replace('\n', '') for s in f.readlines()]
    return {'username': user, 'password': pw}


def get_all_photos(uploaded_file, photo_folder):
    with open(uploaded_file) as f:
        uploaded = [line.rstrip() for line in f]

    photos = glob(os.path.join(photo_folder, '*'))
    photos = [photo for photo in photos if os.path.basename(photo) not in uploaded]
    return photos


def choose_random_photo(uploaded_file, photo_folder):
    photos = get_all_photos(uploaded_file, photo_folder)
    photo = random.choice(photos) # choose a random photo
    return photo


def parse_photo_name(photo):
    """All my photos are named like `854-20151121-Peru-Cusco.jpg`"""
    parsed = parse.parse('{i}-{date}-{country}-{city}-{rest}.jpg', photo)
    if parsed is None:
        parsed = parse.parse('{i}-{date}-{country}-{city}.jpg', photo)
    if parsed is not None:
        d = parsed.named
        if 'rest' in d:
            d['rest'] = d['rest'].replace('-', ' ')
        d['date'] = dateutil.parser.parse(d['date'])
        return d


def get_random_quote():
    response = get('http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en')
    response = loads(response.text)
    quote = response['quoteText']
    author = response['quoteAuthor']
    return quote


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

    # instagram = InstagramAPI(*read_config())
    bot = Bot()
    bot.login(**read_config())

    # instagram.login()
    upload = bot.uploadPhoto(photo, caption=caption)
    print(upload)
    # After succeeding append the fname to the uploaded.txt file
    if upload:
        append_to_uploaded_file(uploaded_file, photo)


if __name__ == "__main__":
    main()
