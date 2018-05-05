#!/usr/bin/env python3.6

from collections import OrderedDict, defaultdict
import random

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

@attr.s
class MyBot:
    bot = attr.ib()
    friends = attr.ib(default="config/friends.txt", converter=utils.file)
    tmp_following = attr.ib(default='config/tmp_following.txt', converter=utils.file)
    unfollowed = attr.ib(default='config/unfollowed.txt', converter=utils.file)
    to_follow = attr.ib(default='config/to_follow.txt', converter=utils.file)
    scraped_friends = attr.ib(default='config/scraped_friends.txt', converter=utils.file)
    skipped = attr.ib(default='skipped.txt', converter=utils.file)

    @property
    def scrapable_friends(self):
        return list(self.friends.set - self.scraped_friends.set)

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
        self.tmp_following.remove(user_id)

    def follow(self, user_id):
        self.bot.follow(user_id)
        if user_id not in self.skipped.list:
            self.tmp_following.append(user_id)
        self.to_follow.remove(user_id)

    @print_starting
    def follow_random(self):
        self.update_to_follow()
        user_id = self.to_follow.random()
        self.follow(user_id)

    @print_starting
    def unfollow_if_max_following(self, max_following=200):
        i = 0
        while len(self.tmp_following.list) > max_following:
            i += 1
            self.unfollow(self.tmp_following.list[0])
            if i > 10:
                break

    @print_starting
    def unfollow_followers_that_are_not_friends(self):
        followers = set(self.bot.followers)
        non_friends_followers = (followers - self.friends.set)
        followings = set(self.bot.get_user_following(self.bot.user_id))
        unfollows = [x for x in followings if x in non_friends_followers]
        for u in unfollows:
            if u not in self.unfollowed.list:
                self.unfollow(u)

    @print_starting
    def unfollow_all_non_friends(self):
        followings = set(self.bot.following)
        unfollows = [x for x in followings if x not in self.friends.list]
        print(f'\nGoing to unfollow {len(unfollows)} "friends"'.)
        for u in unfollows:
            self.unfollow(u)

    @print_starting
    def unfollow_accepted_unreturned_requests(self):
        followings = set(self.bot.following)
        accepted_followings = [u for u in self.tmp_following.list
                               if u in followings and u not in self.friends.set]
        for u in accepted_followings:
            info = c.bot.get_user_info(u)
            try:
                if info['is_private']:
                    print(f'\nUser {info["username"]} is private and accepted my request, but did not follow back.')
                    self.unfollow(u)
            except:
                pass

    @print_starting
    def like_media_from_to_follow(self):
        user_id = self.to_follow.random()
        while self.bot.get_user_info(user_id)['is_private']:
            user_id = self.to_follow.random()
        n = random.randint(2, 4)
        username = self.bot.get_user_info(user_id)['username']
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
        username = self.bot.get_user_info(user_id)['username']
        print(f'Liking {n} medias from `{username}`.')
        medias = self.bot.get_user_medias(user_id)
        self.bot.like_medias(random.sample(medias, n))


if __name__ == '__main__':
    import time
    bot = Bot(max_following_to_followers_ratio=10)
    bot.api.login(**read_config(), use_cookie=True)
    c = MyBot(bot)

    while True:
        try:
            # c.unfollow_all_non_friends()

            funcs = [c.like_media_from_to_follow,
                     c.like_media_from_nonfollowers,
                     c.follow_random,
                     c.unfollow_if_max_following,
                     c.unfollow_followers_that_are_not_friends]
            funcs = random.sample(funcs, 3)
            for f in funcs:
                f()

            print('\nSleeping')
            time.sleep(random.uniform(50, 150))
        except Exception as e: 
            print(str(e))
