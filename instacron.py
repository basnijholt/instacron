#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-


from collections import Counter
from glob import glob
from json import loads
import operator
import os.path
import random
import tempfile
import time

import dateutil.parser
import emoji
import instabot
from instabot.api.api_photo import compatible_aspect_ratio, get_image_size
import numpy as np
import parse
import PIL.Image
from requests import get
from termcolor import colored

from continents import continents


def read_config(cfg='~/.config/instacron/config'):
    """Read the config.

    Create a config file at `cfg` with the
    following information and structure:
        my_user_name
        my_difficult_password
    """
    import os.path
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


def correct_ratio(photo):
    return compatible_aspect_ratio(get_image_size(photo))


def get_all_photos(uploaded_file, photo_folder):
    with open(uploaded_file) as f:
        uploaded = [line.rstrip() for line in f]
    photos = glob(os.path.join(photo_folder, '*.jpg'))
    photos = photos_to_upload(photos, uploaded)
    return photos


def choose_random_photo(uploaded_file, photo_folder):
    photos = get_all_photos(uploaded_file, photo_folder)
    photo = random.choice(photos) # choose a random photo
    return photo


def photos_to_upload(photos, uploaded):
    """Check which photos it can upload.

    When all pictures in the photo folder have been uploaded
    it starts to upload old pictures again."""

    # Remove files from `uploaded` that are not present
    # in `photos` any more.
    photos_base = [os.path.basename(p) for p in photos]
    uploaded = [p for p in uploaded if p in photos_base]

    if not uploaded:
        return photos

    # Create a counter
    counter = Counter(uploaded)
    n_counts = sorted(set(counter.values()))
    count_min = min(counter.values())

    if len(uploaded) >= count_min * len(photos):
        # Photos all have been uploaded already
        if len(n_counts) == 1:
            # Every photo is uploaded the same amount of times
            _photos = list(counter.keys())
        elif len(n_counts) > 1:
            # There are some photos uploaded N times, while other are
            # uploaded N+1 times.

            # Remove the photos with the lowest count and select
            # the images with the second lowest count.
            _photos = list({photo for photo, count in counter.items()
                            if count == count_min})
    else:
        # Not all photos have been uploaded yet
        _photos = [p for p in photos if os.path.basename(p) not in uploaded]
    return _photos


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
    continent = continents[country] if country in continents else None
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
    caption += ' '
    caption += emoji.emojize(':snake:') + ' www.instacron.nijho.lt'
    caption += '\n' + 5*'.\n'
    extra_hashtags = [
        'backpacker', 'wanderlust', 'sonya6000', 'earthoutdoors',
        'travel', 'traveling', 'beautifuldestinations', 'earthofficial',
        'nature', 'theglobewanderer', 'earthpix', 'earthfocus',
        'discoverearth', 'stayandwander', 'modernoutdoors',
        'awesome_earthpix', 'takemoreadventures', 'globetrotter',
        f'visit{country.lower()}', f'ig_{country.lower()}',
    ]
    if continent:
        continent = continent.replace(" ", "").lower()
        extra_hashtags += [f'visit{continent}', continent]
    random.shuffle(extra_hashtags)
    caption += ' '.join('#' + h for h in extra_hashtags)

    return caption


def fix_photo(photo):
    with open(photo, 'rb') as f:
        img = PIL.Image.open(f)
        img = strip_exif(img)
        if not correct_ratio(photo):
            img = get_highest_entropy(img)
        photo = os.path.join(tempfile.gettempdir(), 'instacron.jpg')
        img.save(photo)
    return photo


def entropy(data):
    """Calculate the entropy of an image"""
    hist = np.array(PIL.Image.fromarray(data).histogram())
    hist = hist / hist.sum()
    hist = hist[hist != 0]
    return -np.sum(hist * np.log2(hist))


def crop(x, y, data, w, h):
    x = int(x)
    y = int(y)
    return data[y:y+h, x:x+w]


def get_highest_entropy(img, min_ratio=4/5, max_ratio=90/47):
    from scipy.optimize import minimize_scalar
    w, h = img.size
    data = np.array(img)
    ratio = w / h
    if ratio > max_ratio:
        # Too wide
        w_max = int(max_ratio * h)
        _crop = lambda x: crop(x, y=0, data=data, w=w_max, h=h)
        xy_max = w - w_max
    else:
        # Too narrow
        h_max = int(w / min_ratio)
        _crop = lambda y: crop(x=0, y=y, data=data, w=w, h=h_max)
        xy_max = h - h_max
    x = minimize_scalar(lambda xy: -entropy(_crop(xy)),
                        bounds=(0, xy_max),
                        method='bounded').x
    return PIL.Image.fromarray(_crop(x))


def strip_exif(img):
    """Strip EXIF data from the photo to avoid a 500 error."""
    data = list(img.getdata())
    image_without_exif = PIL.Image.new(img.mode, img.size)
    image_without_exif.putdata(data)
    return image_without_exif


def append_to_uploaded_file(uploaded_file, photo):
    with open(uploaded_file, 'a') as f:
        f.write(photo + '\n')


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
    upload = bot.upload_photo(fix_photo(photo), caption=caption)
    
    # After succeeding append the fname to the uploaded.txt file
    photo_base = os.path.basename(photo)
    if upload:
        print(colored(f'Upload of {photo_base} succeeded.', 'green'))
        append_to_uploaded_file(uploaded_file, photo_base)
    else:
        print(colored(f'Upload of {photo_base} failed.', 'red'))
    bot.logout()

if __name__ == "__main__":
    main()
