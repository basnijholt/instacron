#!/usr/bin/env python3.6

from collections import OrderedDict, defaultdict
import random
import pickle
import sys
import time

import attr
from instabot import Bot, utils


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


def print_starting(f):
    from functools import wraps
    from huepy import green, bold
    @wraps(f)
    def wrapper(*args, **kwargs):
        print(green(bold(f'\n\nStarting with `{f.__name__}`.')))
        return f(*args, **kwargs)
    return wrapper


def print_sleep(t):
    t = int(t)
    print(f'Going to sleep for {t} seconds.')
    for remaining in range(t, 0, -1):
        sys.stdout.write(f"\r{remaining} seconds remaining.")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\rDone sleeping!                ")


@attr.s
class MyBot:
    bot = attr.ib()
    friends = attr.ib(default="config/friends.txt", converter=utils.file)
    tmp_following = attr.ib(default='config/tmp_following.txt', converter=utils.file)
    unfollowed = attr.ib(default='config/unfollowed.txt', converter=utils.file)
    to_follow = attr.ib(default='config/to_follow.txt', converter=utils.file)
    scraped_friends = attr.ib(default='config/scraped_friends.txt', converter=utils.file)
    n_followers = attr.ib(default='config/n_followers.txt', converter=utils.file)
    user_infos_file = attr.ib(default='config/user_infos.pickle')
    user_infos = attr.ib(default=None)
    skipped = attr.ib(default='skipped.txt', converter=utils.file)

    @property
    def scrapable_friends(self):
        return list(self.friends.set - self.scraped_friends.set)

    @print_starting
    def update_to_follow(self):
        if len(self.to_follow.list) < 100:
            user_id = random.choice(self.scrapable_friends)
            print(f'Choosing "{user_id}".')
            followers_of_friend = bot.get_user_followers(user_id)
            potential_following = (set(followers_of_friend)
                                   - self.tmp_following.set
                                   - self.friends.set
                                   - self.blacklist.set
                                   - self.unfollowed.set)
            for x in potential_following:
                self.to_follow.append(x)
            self.scraped_friends.append(user_id)
        else:
            return self.to_follow.list
        return self.update_to_follow()

    def unfollow(self, user_id):
        try:
            self.bot.unfollow(user_id)
        except Exception as e:
            print(f'Could not find userinfo, error message: {e}')
        self.unfollowed.append(user_id)
        if user_id in self.bot._following:
            self.bot._following.remove(user_id)
        try:
            to_remove = next(x for x in self.tmp_following.list
                             if x.split(',')[0] == user_id)
            self.tmp_following.remove(to_remove)
        except StopIteration:
            pass

    def follow(self, user_id):
        self.bot.follow(user_id)
        self.bot._following.append(user_id)
        if user_id not in self.skipped.list:
            self.tmp_following.append(f'{user_id},{time.time()}')
        self.to_follow.remove(user_id)

    def get_user_info(self, user_id):
        if self.user_infos is None:
            try:
                with open(self.user_infos_file, 'rb') as f:
                    self.user_infos = pickle.load(f)
            except Exception:
                self.user_infos = defaultdict(dict)

        if user_id in self.user_infos:
            return self.user_infos[user_id]['user_info']
        else:
            print(f'{user_id} is not in the user_infos.pickle file.')
            user_info = self.bot.get_user_info(user_id)
            self.user_infos[user_id]['user_info'] = user_info
            self.user_infos[user_id]['timestamp'] = time.time()

            with open(self.user_infos_file, 'wb') as f:
                pickle.dump(self.user_infos, f)

            return user_info

    @print_starting
    def follow_random(self):
        self.update_to_follow()
        user_id = self.to_follow.random()
        self.follow(user_id)

    @print_starting
    def unfollow_if_max_following(self, max_following=1440):
        i = 0
        while len(self.tmp_following.list) > max_following:
            i += 1
            self.unfollow(self.tmp_following.list[0].split(',')[0])
            if i > 10:
                break

    @print_starting
    def unfollow_after_time(self, days_max=2):
        user_id, t_follow = self.tmp_following.list[0].split(',')
        while time.time() - float(t_follow) > 86400 * days_max:
            self.unfollow(user_id)
            user_id, t_follow = self.tmp_following.list[0].split(',')

    @print_starting
    def unfollow_followers_that_are_not_friends(self):
        followers = set(self.bot.followers)
        non_friends_followers = (followers - self.friends.set)
        followings = set(self.bot.following)
        unfollows = [x for x in followings if x in non_friends_followers]
        for u in unfollows:
            if u not in self.unfollowed.list:
                self.unfollow(u)

    @print_starting
    def unfollow_all_non_friends(self):
        followings = set(self.bot.following)
        unfollows = [x for x in followings if x not in self.friends.list]
        print(f'\nGoing to unfollow {len(unfollows)} "friends".')
        for u in unfollows:
            self.unfollow(u)

    @print_starting
    def unfollow_accepted_unreturned_requests(self, max_hours=1):
        tmp_following, times = zip(*[x.split(',') for x in c.tmp_following.list])
        accepted_followings = [(u, t) for u, t in zip(tmp_following, times)
                               if u in self.bot.following and u not in self.friends.set]
        for u, t in accepted_followings:
            info = self.get_user_info(u)
            try:
                if info['is_private'] and time.time() - t > 3600 * float(max_hours):
                    print(f'\nUser {info["username"]} is private and accepted my '
                          'request, but did not follow back in {max_hours} hours.')
                    self.unfollow(u)
            except:
                pass

    @print_starting
    def like_media_from_to_follow(self):
        user_id = self.to_follow.random()
        while self.get_user_info(user_id)['is_private']:
            user_id = self.to_follow.random()
        n = random.randint(2, 4)
        username = self.get_user_info(user_id)['username']
        print(f'Liking {n} medias from `{username}`.')
        medias = self.bot.get_user_medias(user_id)
        self.bot.like_medias(random.sample(medias, n))
        self.to_follow.remove(user_id)

    @print_starting
    def like_media_from_nonfollowers(self):
        user_ids = list(set(self.bot.following)
                        - set(self.bot.followers)
                        - self.bot.friends_file.set)
        user_id = random.choice(user_ids)
        n = random.randint(2, 4)
        username = self.get_user_info(user_id)['username']
        print(f'Liking {n} medias from `{username}`.')
        medias = self.bot.get_user_medias(user_id)
        picked_medias = random.sample(medias, min(n, len(medias)))
        self.bot.like_medias(picked_medias)

    @print_starting
    def track_followers(self):
        try:
            n_followers_old = int(self.n_followers.list[-1].split(',')[0])
        except IndexError:
            n_followers_old = 0
        n_followers = len(self.bot.followers)
        if n_followers_old != n_followers:
            self.n_followers.append(f'{n_followers},{time.time()}')

if __name__ == '__main__':
    bot = Bot(max_following_to_followers_ratio=10)
    bot.api.login(**read_config(), use_cookie=True)
    c = MyBot(bot)

    funcs = [
        c.follow_random,
        c.unfollow_if_max_following,
        c.unfollow_after_time,
        c.unfollow_accepted_unreturned_requests,
        c.unfollow_followers_that_are_not_friends,
#        c.like_media_from_to_follow,
#        c.like_media_from_nonfollowers,
    ]
    while True:
        n_per_day = 700
        n_seconds = 86400 / n_per_day
        if random.random() < n_seconds / (3 * 3600):
            # Invalidate the cache every ~3 hours
            c.bot._followers = None
        c.track_followers()
        random.shuffle(funcs)
        for f in funcs:
            try:
                f()
            except Exception as e:
                print(str(e))

        print_sleep(abs(random.gauss(n_seconds, 60)))
