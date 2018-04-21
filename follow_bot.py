#!/usr/bin/env python3.6

from collections import OrderedDict, defaultdict
import random

import attr
from instabot import Bot
from instacron import read_config


def print_starting(f):
    from functools import wraps
    from huepy import green, bold
    @wraps(f)
    def wrapper(*args, **kwargs):
        print(bold(green(f'Starting with `{f.__name__}`.')))
        return f(*args, **kwargs)
    return wrapper


@attr.s
class file:
    fname = attr.ib()
    
    @property
    def list(self):
        with open(self.fname, 'r') as f:
            return [x.strip('\n') for x in f.readlines()]

    @property
    def set(self):
        return set(self.list)

    def append(self, item):
        with open(self.fname, 'a') as f:
            f.write(f'{item}\n')
              
    def remove(self, x):
        x = str(x)
        items = self.list
        with open(self.fname, 'w') as f:
            for item in items:
                if item != x:
                    f.write(f'{item}\n')
    
    def random(self):
        return random.choice(self.list)

    def remove_duplicates(self):
        return list(OrderedDict.fromkeys(self.list))

    def save_list(self, items):
        with open(self.fname, 'w') as f:
            for item in items:
                f.write(f'{item}\n')


@attr.s
class files:
    bot = attr.ib()
    friends = attr.ib(default="config/friends.txt", converter=file)
    tmp_following = attr.ib(default='config/tmp_following.txt', converter=file)
    unfollowed = attr.ib(default='config/unfollowed.txt', converter=file)
    to_follow = attr.ib(default='config/to_follow.txt', converter=file)
    scraped_friends = attr.ib(default='config/scraped_friends.txt', converter=file)
    skipped = attr.ib(default='skipped.txt', converter=file)

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
        self.bot.unfollow(user_id)
        self.unfollowed.append(user_id)
        self.tmp_following.remove(user_id)

    def follow(self, user_id):
        self.bot.follow(user_id)
        if user_id not in self.skipped.list:
            self.tmp_following.append(user_id)
        self.to_follow.remove(user_id)

    def follow_random(self):
        self.update_to_follow()
        user_id = self.to_follow.random()
        self.follow(user_id)

    @print_starting
    def unfollow_if_max_following(self, max_following=300):
        """If following a new person every 5 minutes, this 
        gives a person 4 days to follow back."""
        i = 0
        while len(self.tmp_following.list) > max_following:
            i += 1
            self.unfollow(self.tmp_following.list[0])
            if i > 10:
                break

    @print_starting
    def unfollow_followers_that_are_not_friends(self):
        followers = set(self.bot.get_user_followers(self.bot.user_id))
        non_friends_followers = (followers - self.friends.set)
        followings = set(self.bot.get_user_following(self.bot.user_id))
        unfollows = [x for x in followings if x in non_friends_followers]
        for u in unfollows:
            self.unfollow(u)

    @print_starting
    def unfollow_accepted_unreturned_requests(self):
        followings = set(self.bot.get_user_following(self.bot.user_id))
        accepted_followings = [u for u in self.followed.list if u in followings and u not in self.friends.set]
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
        n = random.randint(2, 6)
        username = self.bot.get_user_info(user_id)['username']
        print(f'Liking {n} medias from `{username}`.')
        self.bot.like_user(user_id, n)


if __name__ == '__main__':
    import time
    bot = Bot(max_following_to_followers_ratio=10)
    bot.login(**read_config())
    c = files(bot)

    while True:
        c.like_media_from_to_follow()
        c.follow_random()
        c.unfollow_if_max_following()
        c.unfollow_followers_that_are_not_friends()
        time.sleep(random.uniform(3, 6))
