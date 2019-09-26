#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os.path
import random
import tempfile
import time
from collections import Counter
from glob import glob
from json import loads

import dateutil.parser
import emoji
import exifread
import geocoder
import instabot
import numpy as np
import parse
import PIL.Image
import pycountry
import wikiquotes
from instabot.api.api_photo import compatible_aspect_ratio, get_image_size
from requests import get
from termcolor import colored

from continents import continents


def read_config(cfg="~/.config/instacron/config"):
    """Read the config.

    Create a config file at `cfg` with the
    following information and structure:
        my_user_name
        my_difficult_password
    """
    import os.path

    _cfg = os.path.expanduser(cfg)
    try:
        with open(_cfg, "r") as f:
            user, pw = [s.replace("\n", "") for s in f.readlines()]
    except Exception:
        import getpass

        print(f"\nReading config file `{cfg}` didn't work")
        user = input("Enter username and hit enter\n")
        pw = getpass.getpass("Enter password and hit enter\n")
        save_config = input(f"Save to config file `{cfg}` (y/N)? ").lower() == "y"
        if save_config:
            os.makedirs(os.path.dirname(_cfg), exist_ok=True)
            with open(_cfg, "w") as f:
                f.write(f"{user}\n{pw}")
    return {"username": user, "password": pw}


def correct_ratio(photo):
    return compatible_aspect_ratio(get_image_size(photo))


def get_all_photos(uploaded_file, photo_folder):
    with open(uploaded_file, encoding="utf-8") as f:
        uploaded = [line.rstrip() for line in f]
    photos = glob(os.path.join(photo_folder, "*.jpg"))
    photos = photos_to_upload(photos, uploaded)
    return photos


def choose_random_photo(uploaded_file, photo_folder):
    photos = get_all_photos(uploaded_file, photo_folder)
    photo = random.choice(photos)  # choose a random photo
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
            _photos = list(
                {photo for photo, count in counter.items() if count == count_min}
            )
    else:
        # Not all photos have been uploaded yet
        _photos = [p for p in photos if os.path.basename(p) not in uploaded]
    return _photos


def get_lat_long_from_exif(exif):
    def dms2dd(degrees, minutes, seconds, direction):
        dd = degrees + minutes / 60 + seconds / 3600
        if direction in "SW":
            dd *= -1
        return dd

    d, m, s = eval(exif["GPS GPSLatitude"].printable)
    lat = dms2dd(d, m, s, exif["GPS GPSLatitudeRef"].printable)
    d, m, s = eval(exif["GPS GPSLongitude"].printable)
    long_ = dms2dd(d, m, s, exif["GPS GPSLongitudeRef"].printable)
    return lat, long_


def get_info_from_exif(fname):
    with open(fname, "rb") as f:
        tags = exifread.process_file(f)
    try:
        lat, long_ = get_lat_long_from_exif(tags)
        for i in range(10):
            r = geocoder.osm([lat, long_], method="reverse").current_result
            if r is not None:
                break
            time.sleep(0.1)
        address = r
    except Exception:
        address = None
    date = dateutil.parser.parse(tags["Image DateTime"].printable)
    return address, date


def get_place_hashtags(city, country):
    hashtags = []
    continent = continents.get(country)
    for key in [country, continent]:
        if key:
            key = key.replace(" ", "").lower()
            hashtags += [f"visit{key}", key]
    if city:
        hashtags.append(city.replace(" ", "").lower())
    if country:
        hashtags.append(f'ig_{country.replace(" ", "").lower()}')
    return hashtags


def get_location_caption_and_hashtags(photo):
    """All my photos are named like `854-20151121-Peru-Cusco.jpg`"""
    try:
        templates = [
            "{i}-{date}-{country}-{city}-{rest}.jpg",
            "{i}-{date}-{country}-{city}.jpg",
        ]
        parsed = None
        for template in templates:
            parsed = parse.parse(template, os.path.basename(photo))
            if parsed is not None:
                d = parsed.named
                date = dateutil.parser.parse(d["date"])
                country = d["country"]
                city = d["city"]
                flag = emoji.emojize(f":{country.replace(' ', '_')}:")
                city_str = f", {city}" if city else ""
                caption = f"   Taken in {country}{city_str} on {date:%d %B %Y}." + flag
                hashtags = get_place_hashtags(country, city)
                return caption, hashtags
        raise Exception("Didn't find a matching template.")
    except Exception as e:
        print(e)
        print("Getting info from EXIF data.")
        address, date = get_info_from_exif(photo)
        try:
            country_code = address.country_code.upper()
            country = pycountry.countries.get(alpha_2=country_code).name
            flag = emoji.emojize(f":{country.replace(' ', '_')}:")
            caption_part = f"in {address.address}" + flag
        except Exception as e:
            print(e)
            caption_part = "somewhere" + emoji.emojize(":world_map:")
        hashtags = get_place_hashtags(address.country, address.city)
        caption = f"   Taken {caption_part} on {date:%d %B %Y}."
        return caption, hashtags


def _get_random_quote():
    response = get(
        "http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=en"
    )
    response = loads(response.text)
    quote = response["quoteText"]
    author = response["quoteAuthor"]  # noqa: F841
    return quote


def get_random_quote(from_person=True):
    if from_person:
        ppl = ["Hunter S. Thompson", "Albert Einstein", "Charles Bukowski"]
        person = random.choice(ppl)
        return wikiquotes.random_quote(person, "English")

    for _ in range(10):
        try:
            return _get_random_quote()
        except Exception:
            time.sleep(1)
            pass


def random_emoji():
    # Don't return a random flag (hence the `islower`)
    emojis = [
        e
        for e, unicode in emoji.UNICODE_EMOJI.items()
        if unicode[1].islower() and len(e) == 1
    ]
    return random.choice(emojis)


def get_camera_settings(fname):
    with open(fname, "rb") as f:
        tags = exifread.process_file(f)
    brand = tags["Image Make"].printable
    model = tags["Image Model"].printable
    lens = tags["EXIF LensModel"].printable
    focal_length = tags["EXIF FocalLength"]
    shutter_speed = tags["EXIF ExposureTime"].printable
    apeture = tags["EXIF FNumber"].printable
    iso = tags["EXIF ISOSpeedRatings"].printable
    s = f" {brand} {model} | {lens} @ {focal_length} mm | ƒ/{apeture} | {shutter_speed} sec | ISO {iso}"
    return emoji.emojize(":camera:") + "⚙: " + s


def get_caption(fname):
    from hashtags import EXTRA_HASHTAGS

    location_caption, location_hashtags = get_location_caption_and_hashtags(fname)

    caption = random_emoji() + random_emoji() + location_caption

    # Advertize the Python script
    caption += "#instacron " + emoji.emojize(":snake:") + " www.instacron.nijho.lt"
    spacer = "\n" + 3 * ".\n"
    caption += spacer + get_camera_settings(fname) + spacer

    extra_hashtags = EXTRA_HASHTAGS.copy()
    random.shuffle(extra_hashtags)
    extra_hashtags += location_hashtags
    extra_hashtags = extra_hashtags[-27:]
    random.shuffle(extra_hashtags)  # both shuffles are useful
    caption += " ".join("#" + h for h in extra_hashtags)

    return caption


def fix_photo(photo):
    with open(photo, "rb") as f:
        img = PIL.Image.open(f)
        img = strip_exif(img)
        if not correct_ratio(photo):
            img = get_highest_entropy(img)
        photo = os.path.join(tempfile.gettempdir(), "instacron.jpg")
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
    return data[y : y + h, x : x + w]


def get_highest_entropy(img, min_ratio=4 / 5, max_ratio=90 / 47):
    from scipy.optimize import minimize_scalar

    w, h = img.size
    data = np.array(img)
    ratio = w / h
    if ratio > max_ratio:
        # Too wide
        w_max = int(max_ratio * h)

        def _crop(x):
            return crop(x, y=0, data=data, w=w_max, h=h)

        xy_max = w - w_max
    else:
        # Too narrow
        h_max = int(w / min_ratio)

        def _crop(y):
            return crop(x=0, y=y, data=data, w=w, h=h_max)

        xy_max = h - h_max
    x = minimize_scalar(
        lambda xy: -entropy(_crop(xy)), bounds=(0, xy_max), method="bounded"
    ).x
    return PIL.Image.fromarray(_crop(x))


def strip_exif(img):
    """Strip EXIF data from the photo to avoid a 500 error."""
    data = list(img.getdata())
    image_without_exif = PIL.Image.new(img.mode, img.size)
    image_without_exif.putdata(data)
    return image_without_exif


def append_to_uploaded_file(uploaded_file, photo):
    with open(uploaded_file, "a") as f:
        f.write(photo + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Instacron.")
    parser.add_argument(
        "--fname",
        metavar="fname",
        type=str,
        default=None,
        help="filename of the photo, random if empty.",
    )
    parser.add_argument(
        "--caption_only", action="store_true", help="only return the caption."
    )
    args = parser.parse_args()
    caption = get_random_quote()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    uploaded_file = os.path.join(dir_path, "uploaded.txt")

    if args.fname is None:
        photo_folder = os.path.join(dir_path, "photos")
        photo = choose_random_photo(uploaded_file, photo_folder)
    else:
        photo = args.fname

    pic = fix_photo(photo)
    caption += get_caption(photo)
    print(caption)

    if not args.caption_only:
        print(f"Uploading `{photo}`")
        print(os.path.basename(photo))
        bot = instabot.Bot()
        bot.login(**read_config())
        upload = bot.upload_photo(pic, caption=caption)

        # After succeeding append the fname to the uploaded.txt file
        photo_base = os.path.basename(photo)
        if upload:
            time.sleep(4)
            print(colored(f"Upload of {photo_base} succeeded.", "green"))
            append_to_uploaded_file(uploaded_file, photo_base)
        else:
            print(colored(f"Upload of {photo_base} failed.", "red"))
        bot.logout()


if __name__ == "__main__":
    main()
