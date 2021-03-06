#!/usr/bin/env python3.6

import atexit
import random
import sys
import time
from contextlib import suppress
from functools import wraps

import attr
from diskcache import Cache
from huepy import bold, green
from instabot import Bot, utils


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


def print_starting(f):
    from huepy import green, bold

    @wraps(f)
    def wrapper(*args, **kwargs):
        print(green(bold(f"\n\nStarting with `{f.__name__}`.")))
        return f(*args, **kwargs)

    return wrapper


def stop_spamming(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        last_json = args[0].bot.api.last_json
        if last_json is not None and last_json.get("message") == "feedback_required":
            print("The bot is spamming! Pause the program before I get banned.")
            print_sleep(3600 * 5)
        return f(*args, **kwargs)

    return wrapper


def print_sleep(t):
    t = int(t)
    print(f"Going to sleep for {t} seconds.")
    for remaining in range(t, 0, -1):
        sys.stdout.write(f"\r{remaining} seconds remaining.")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\rDone sleeping!                ")


@attr.s
class MyBot:
    bot = attr.ib()
    friends = attr.ib(default="config/friends.txt", converter=utils.file)
    tmp_following = attr.ib(default="config/tmp_following.txt", converter=utils.file)
    unfollowed = attr.ib(default="config/unfollowed.txt", converter=utils.file)
    to_follow = attr.ib(default="config/to_follow.txt", converter=utils.file)
    scraped_friends = attr.ib(
        default="config/scraped_friends.txt", converter=utils.file
    )
    n_followers = attr.ib(default="config/n_followers.txt", converter=utils.file)
    user_infos = attr.ib(default="config/user_infos", converter=Cache)
    skipped = attr.ib(default="skipped.txt", converter=utils.file)

    def __attrs_post_init__(self):
        atexit.register(self.close)

    @property
    def scrapable_friends(self):
        """Friends that I can set scrape for followers."""
        return list(self.friends.set - self.scraped_friends.set)

    @print_starting
    def update_to_follow(self):
        """Update the 'to_follow' list recusively if it gets too short."""
        if len(self.to_follow.list) < 1:
            user_id = random.choice(self.scrapable_friends)
            username = self.get_user_info(user_id)["username"]
            print(f'Choosing "{user_id}", {username}.')
            followers_of_friend = bot.get_user_followers(user_id)
            potential_following = (
                set(followers_of_friend)
                - self.tmp_following.set
                - self.friends.set
                - self.bot.blacklist_file.set
                - self.unfollowed.set
            )
            to_follow = self.to_follow.list + list(potential_following)
            self.to_follow.save_list(to_follow)
            self.scraped_friends.append(user_id)
        else:
            return self.to_follow.list
        return self.update_to_follow()

    @stop_spamming
    def unfollow(self, user_id):
        """Unfollow 'user_id' and remove from 'self.tmp_following'."""
        with suppress(Exception):
            print(f"Unfollowing {user_id}")
            self.bot.api.unfollow(user_id)

        self.unfollowed.append(user_id)

        with suppress(StopIteration):
            to_remove = next(
                x for x in self.tmp_following.list if x.split(",")[0] == user_id
            )
            self.tmp_following.remove(to_remove)

        with suppress(ValueError):
            self.bot.following.remove(user_id)

    @stop_spamming
    def follow(self, user_id, tmp_follow=True):
        self.bot.follow(user_id)
        self.bot.following.append(user_id)
        if tmp_follow and user_id not in self.skipped.list:
            self.tmp_following.append(f"{user_id},{time.time()}")
        self.to_follow.remove(user_id)

    def get_user_info(self, user_id):
        if user_id not in self.user_infos:
            print(f"{user_id} is not in the user_info database.")
            user_info = self.bot.get_user_info(user_id)
            self.user_infos.set(user_id, user_info, expire=86400 * 60, tag="user_info")
        return self.user_infos[user_id]

    @stop_spamming
    def follow_random(self):
        self.update_to_follow()
        user_id = self.to_follow.random()
        self.follow(user_id)

    @print_starting
    def unfollow_if_max_following(self, max_following=1440):
        """Automatically unfollow if 'max_following' is receached
        but only 10 at the time."""
        i = 0
        while len(self.tmp_following.list) > max_following:
            i += 1
            self.unfollow(self.tmp_following.list[0].split(",")[0])
            if i > 10:
                break

    @print_starting
    def unfollow_after_time(self, days_max=4):
        """Automatically unfollow if 'days_max' is receached
        but only 10 at the time."""
        user_id, t_follow = self.tmp_following.list[0].split(",")
        i = 0
        while time.time() - float(t_follow) > 86400 * days_max:
            i += 1
            self.unfollow(user_id)
            user_id, t_follow = self.tmp_following.list[0].split(",")
            if i > 10:
                break

    @print_starting
    def unfollow_followers_that_are_not_friends(self):
        """XXX: what does this do again?"""
        followers = set(self.bot.followers)
        non_friends_followers = followers - self.friends.set
        followings = set(self.bot.following)
        unfollows = [x for x in followings if x in non_friends_followers]
        for u in unfollows:
            if u not in self.unfollowed.list:
                self.unfollow(u)

    @stop_spamming
    @print_starting
    def unfollow_all_non_friends(self):
        """Unfollow EVERYONE that is not in 'self.friends.'"""
        followings = set(self.bot.following)
        unfollows = [x for x in followings if x not in self.friends.list]
        print(f'\nGoing to unfollow {len(unfollows)} "friends".')
        for u in unfollows:
            self.unfollow(u)

    @stop_spamming
    @print_starting
    def unfollow_accepted_unreturned_requests(self, max_hours=1):
        """Unfollow if a private_user accepted my request but doesn't follow back."""
        tmp_following, times = zip(*[x.split(",") for x in c.tmp_following.list])
        accepted_followings = [
            (u, t)
            for u, t in zip(tmp_following, times)
            if u in self.bot.following and u not in self.friends.set
        ]
        for u, t in accepted_followings:
            info = self.get_user_info(u)
            try:
                if info["is_private"] and time.time() - t > 3600 * float(max_hours):
                    print(
                        f'\nUser {info["username"]} is private and accepted my '
                        "request, but did not follow back in {max_hours} hours."
                    )
                    self.unfollow(u)
            except BaseException:
                pass

    @print_starting
    @stop_spamming
    def like_media_from_to_follow(self):
        """Like media from people that are in 'self.to_follow' and
        then remove them from the list."""
        user_id = self.to_follow.random()
        while self.get_user_info(user_id)["is_private"]:
            user_id = self.to_follow.random()
        n = random.randint(2, 4)
        username = self.get_user_info(user_id)["username"]
        print(f"Liking {n} medias from `{username}`.")
        medias = self.bot.get_user_medias(user_id)
        self.bot.like_medias(random.sample(medias, n))
        self.to_follow.remove(user_id)

    @print_starting
    @stop_spamming
    def like_media_from_nonfollowers(self):
        user_ids = list(
            set(self.bot.following) - set(self.bot.followers) - self.friends.set
        )
        user_id = random.choice(user_ids)
        n = random.randint(2, 4)
        username = self.get_user_info(user_id)["username"]
        print(f"Liking {n} medias from `{username}`.")
        medias = self.bot.get_user_medias(user_id)
        picked_medias = random.sample(medias, min(n, len(medias)))
        self.bot.like_medias(picked_medias)

    @print_starting
    @stop_spamming
    def follow_and_like(self):
        self.update_to_follow()
        if self.bot.reached_limit("likes"):
            print(green(bold(f"\nOut of likes, pausing for 10 minutes.")))
            self.print_sleep(600)
            return
        user_id = self.to_follow.random()
        busy = True
        while busy:
            if self.get_user_info(user_id)["is_private"] or not self.bot.check_user(
                user_id
            ):
                user_id = self.to_follow.random()
                self.to_follow.remove(user_id)
            else:
                busy = False

        username = self.get_user_info(user_id)["username"]
        medias = self.bot.get_user_medias(user_id)
        self.to_follow.remove(user_id)
        if medias and self.lastest_post(medias) < 21:  # days
            n = min(random.randint(4, 10), len(medias))
            print(f"Liking {n} medias from `{username}`.")
            self.bot.like_medias(random.sample(medias, n))
            self.follow(user_id, tmp_follow=True)
        else:
            # Abandon user and call self recusively.
            self.follow_and_like()

    def lastest_post(self, medias):
        media = self.bot.get_media_info(medias[0])
        date = media[0]["taken_at"]
        age_in_days = (time.time() - date) / 3600 / 24
        print(f"lastest post is {age_in_days} days old.")
        return age_in_days

    @print_starting
    def track_followers(self):
        try:
            n_followers_old = int(self.n_followers.list[-1].split(",")[0])
        except IndexError:
            n_followers_old = 0
        n_followers = len(self.bot.followers)
        if n_followers_old != n_followers:
            self.n_followers.append(f"{n_followers},{time.time()}")

    @print_starting
    def unfollow_failed_unfollows(self):
        """This will unfollow users that were already supposed to be
        unfollowed but something has gone wrong. Maximum 15 unfollows per call."""
        tmp_following = [u.split(",")[0] for u in self.tmp_following.list]
        users = set(bot.following) - set(tmp_following) - self.friends.set
        manually_followed = set(users) - self.unfollowed.set
        to_unfollow = set(users) - manually_followed
        print(f"Going to unfollow {len(to_unfollow)} users")
        for i, u in enumerate(to_unfollow):
            if i <= 15:
                self.unfollow(u)

    @print_starting
    def refollow_friends(self):
        """"Refollow everyone in 'self.friends' because a bug sometimes causes
        accidental unfollows."""
        for u in self.friends.list:
            if u not in self.bot.following:
                self.follow(u, tmp_follow=False)

    def close(self):
        print("Closing user_infos database.")
        self.user_infos.close()


if __name__ == "__main__":
    bot = Bot(max_following_to_followers_ratio=20, max_following_to_follow=5000)
    bot.api.login(**read_config(), use_cookie=False)
    c = MyBot(bot)
    # c.refollow_friends()
    funcs = [
        # c.follow_and_like,
        c.unfollow_if_max_following,
        c.unfollow_after_time,
        c.unfollow_accepted_unreturned_requests,
        c.unfollow_failed_unfollows,
        # c.follow_random,
        # c.unfollow_followers_that_are_not_friends,
        # c.like_media_from_to_follow,
        # c.like_media_from_nonfollowers,
        # c.unfollow_all_non_friends,
    ]

    to_unfollow = utils.file("to_unfollow.txt")
    for u in to_unfollow.list:
        user_id = bot.get_user_id_from_username(u)
        c.unfollow(user_id)
        to_unfollow.remove(u)
        time.sleep(20)

    while True:
        n_per_day = 200
        n_seconds = 86400 / n_per_day
        t_start = time.time()
        if random.random() < n_seconds / (5 * 3600):
            # Invalidate the cache every ~5 hours
            c.bot._followers = None
        c.track_followers()
        random.shuffle(funcs)
        for f in funcs:
            try:
                f()
            except Exception as e:
                print(str(e))

        wait_for = n_seconds - (time.time() - t_start)
        print_sleep(max(random.gauss(wait_for, 60), 0))
