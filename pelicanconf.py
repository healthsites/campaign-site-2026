#!/usr/bin/env python
# -*- coding: utf-8 -*- #

AUTHOR = 'Healthsites.io'
SITENAME = 'healthsites.io'
SITEURL = ''

PATH = 'content'
TIMEZONE = 'UTC'
DEFAULT_LANG = 'en'

# Theme
THEME = 'theme'
THEME_STATIC_DIR = 'theme'

# ============================================================================
# NAVIGATION MENUS
# ============================================================================

# English menu
MENUITEMS = (
    ('About', '/about.html'),
    ('Campaigns', '/campaigns/'),
)

# French menu
MENUITEMS_FR = (
    ('À propos', '/fr/about.html'),
    ('Campagnes', '/fr/campaigns/'),
)

# Campaigns submenu (for future dropdown)
CAMPAIGNS_MENU = {
    'senegal': {
        'en': 'Senegal',
        'fr': 'Sénégal',
        'url': '/campaigns/senegal/',
        'regions': [
            {'slug': 'saint-louis', 'name': {'en': 'Saint-Louis', 'fr': 'Saint-Louis'}},
            {'slug': 'tambacounda', 'name': {'en': 'Tambacounda', 'fr': 'Tambacounda'}},
            {'slug': 'matam', 'name': {'en': 'Matam', 'fr': 'Matam'}},
        ]
    },
    'mozambique': {
        'en': 'Mozambique',
        'fr': 'Mozambique',
        'url': '/campaigns/mozambique/',
    },
    'nigeria': {
        'en': 'Nigeria',
        'fr': 'Nigéria',
        'url': '/campaigns/nigeria/',
    },
}

# ============================================================================
# CONTENT SETTINGS
# ============================================================================

# Disable blog/articles
ARTICLE_SAVE_AS = ''
ARTICLE_URL = ''

# Pages
PAGE_SAVE_AS = '{slug}.html'
PAGE_URL = '{slug}.html'

# Direct templates
DIRECT_TEMPLATES = []

# Feeds
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Pagination
DEFAULT_PAGINATION = False
RELATIVE_URLS = True