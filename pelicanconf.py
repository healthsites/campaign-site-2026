#!/usr/bin/env python
# -*- coding: utf-8 -*- #

AUTHOR = 'Healthsites.io'
SITENAME = 'healthsites.io'
SITEURL = 'http://127.0.0.1:8000'

PATH = 'content'
TIMEZONE = 'UTC'
DEFAULT_LANG = 'en'

THEME = 'theme'
THEME_STATIC_DIR = 'theme'

# ============================================================================
# NAVIGATION MENUS
# Leading slash is required on all paths.
# ============================================================================

MENUITEMS = (
    ('About', '/about/'),
    ('Campaigns', '/campaigns/'),
)

MENUITEMS_FR = (
    ('À propos', '/about/'),
    ('Campagnes', '/campaigns/'),
)

MENUITEMS_PT = (
    ('Sobre', '/about/'),
    ('Campanhas', '/campaigns/'),
)

MENUITEMS_AR = (
    ('حول', '/about/'),
    ('الحملات', '/campaigns/'),
)

# ============================================================================
# CONTENT SETTINGS
# ============================================================================

PAGE_URL = '{slug}/'
PAGE_SAVE_AS = '{slug}/index.html'

# '' catches root-level pages (about.md etc.)
PAGE_PATHS = ['', 'campaigns', 'pages', 'about']

PAGE_EXCLUDES = ['fr', 'pt', 'ar']
ARTICLE_EXCLUDES = ['fr', 'pt', 'ar']

ARTICLE_URL = ''
ARTICLE_SAVE_AS = ''
ARTICLE_PATHS = []

# ============================================================================
# PLUGINS & i18n
# ============================================================================

PLUGINS = ['i18n_subsites']

I18N_TEMPLATES_LANG = 'en'

I18N_SUBSITES = {
    'fr': {
        'SITENAME': 'healthsites.io (FR)',
        'SITEURL': 'http://127.0.0.1:8000/fr',
        'PAGE_PATHS': ['', 'about', 'campaigns'],
        'PAGE_EXCLUDES': ['pages', 'campaigns'],
        'MENUITEMS': (
            ('À propos', '/about/'),
            ('Campagnes', '/campaigns/'),
        ),
    },
    'pt': {
        'SITENAME': 'healthsites.io (PT)',
        'SITEURL': 'http://127.0.0.1:8000/pt',
        'PAGE_PATHS': ['', 'about', 'campaigns'],
        'PAGE_EXCLUDES': ['pages', 'campaigns'],
        'MENUITEMS': (
            ('Sobre', '/about/'),
            ('Campanhas', '/campaigns/'),
        ),
    },
    'ar': {
        'SITENAME': 'healthsites.io (AR)',
        'SITEURL': 'http://127.0.0.1:8000/ar',
        'PAGE_PATHS': ['', 'about', 'campaigns'],
        'PAGE_EXCLUDES': ['pages', 'campaigns'],
        'MENUITEMS': (
            ('حول', '/about/'),
            ('الحملات', '/campaigns/'),
        ),
    },
}

I18N_UNTRANSLATED_PAGES = 'cleanurl'

# ============================================================================
# TECHNICAL SETTINGS
# ============================================================================

DELETE_OUTPUT_DIRECTORY = True
RELATIVE_URLS = False

DIRECT_TEMPLATES = ['index']
INDEX_SAVE_AS = 'index.html'

FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

DEFAULT_PAGINATION = False
