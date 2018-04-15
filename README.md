# `instacron` Instagram for the lazy
Automatically upload a photo to Instagram

Takes a random photo from the folder `photos` and adds a caption with a random quote. For example:
>  Just as treasures are uncovered from the earth, so virtue appears from good deeds, and wisdom appears from a pure and peaceful mind. To walk safely through the maze of human life, one needs the light of wisdom and the guidance of virtue.  🌬🌱   Taken in Colombia, Villavieja 🇨🇴 on 13 January 2016.  #instacron 🐍 www.instacron.nijho.lt

> Luck is what happens when preparation meets opportunity.  ⚽🚌   Taken in Colombia, Cali 🇨🇴 on 25 October 2015.  #instacron 🐍 www.instacron.nijho.lt

> I think and that is all that I am.  💔🤷   Taken in Peru, Cusco 🇵🇪 on 21 November 2015.  #instacron 🐍 www.instacron.nijho.lt


### Why does this exist?
I like to take [pictures](https://www.instagram.com/bnijholt/) that I would like to share with the world but I am way too lazy to upload them using the app.

### Installation
You need Python≥3.6

Clone the repo with
```
git clone git@github.com:basnijholt/instacron.git
```
and install the requirements with
```
cd instacron
pip install -r requirements.txt
```

### Usage
* Put photos in [`photos`](photos) (see the expected filename structuce [here](photos).)
* Create a config file at `~/.config/instacron/config` with the following information and structure:
```
my_user_name
my_difficult_password
```
* run `python instacron.py`

Alternatively setup a cronjob.

### Troubleshooting
See the [FAQ: Understanding Responses from Instagram](https://github.com/mgp25/Instagram-API/wiki/FAQ#understanding-responses-from-instagram) in the `mgp25/Instagram-API` repository for information about the error codes the Instagram API might return.
