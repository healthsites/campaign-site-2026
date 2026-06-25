#!/usr/bin/env python
# -*- coding: utf-8 -*- #
import json
import pathlib

AUTHOR = 'Healthsites.io'
SITENAME = 'healthsites.io'
SITEURL = 'http://127.0.0.1:8000'

PATH = 'content'
TIMEZONE = 'UTC'
DEFAULT_LANG = 'en'

THEME = 'theme'
THEME_STATIC_DIR = 'theme'

# ============================================================================
# NAVIGATION MENUS - English only (MVP)
# French support reserved for Phase 2, post-Senegal validation
# ============================================================================

MENUITEMS = (
    ('Home', '/'),
    ('About', '/about/'),
    ('Campaigns', '/campaigns/'),
)

PAGE_URL = '{slug}/'
PAGE_SAVE_AS = '{slug}/index.html'
PAGE_PATHS = ['', 'campaigns', 'pages', 'about']
PAGE_EXCLUDES = ['fr']
ARTICLE_EXCLUDES = ['fr']

ARTICLE_URL = ''
ARTICLE_SAVE_AS = ''
ARTICLE_PATHS = []

I18N_TEMPLATES_LANG = 'en'

# French subsite configuration reserved for Phase 2
# Uncomment and add content/fr/ files when ready to launch French support
I18N_SUBSITES = {}

I18N_UNTRANSLATED_PAGES = 'cleanurl'

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

GOFUNDME_URL = 'https://www.gofundme.com/f/senegal-health-facility-data-collaborative'
WORKING_GROUP_FORM_URL = 'https://healthsites.io/contact'
GITHUB_DISCUSSION_URL = 'https://github.com/healthsites/healthsites/discussions'

PLUGIN_PATHS = ['plugins']
PLUGINS = ['pelican.plugins.sitemap', 'twitter_timeline_loader']

SITEMAP = {
    'format': 'xml',
    'priorities':  {'pages': 0.8, 'indexes': 1.0, 'articles': 0.5},
    'changefreqs': {'pages': 'monthly', 'indexes': 'weekly', 'articles': 'monthly'},
}

STATIC_PATHS = ['extra/robots.txt', 'extra/google993ae26acd637a81.html']
EXTRA_PATH_METADATA = {'extra/robots.txt': {'path': 'robots.txt'}, 'extra/google993ae26acd637a81.html': {'path': 'google993ae26acd637a81.html'}}

SITEDESCRIPTION = 'Open, community-validated health facility data in OpenStreetMap, built through emergency health mapping campaigns.'

_tl_path = pathlib.Path('theme/static/twitter_timeline_data.json')
if _tl_path.exists():
    JINJA_GLOBALS = {'timeline': json.loads(_tl_path.read_text(encoding='utf-8'))}
else:
    JINJA_GLOBALS = {}

MARKDOWN = {
    'extension_configs': {
        'markdown.extensions.extra': {},
        'markdown.extensions.meta': {},
        'markdown.extensions.md_in_html': {},
    },
    'output_format': 'html5',
}