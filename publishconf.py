#!/usr/bin/env python
# -*- coding: utf-8 -*- #

# Import development settings
from pelicanconf import *

# Production URL — served from the custom domain via GitHub Pages
SITEURL = 'https://campaigns.healthsites.io'
RELATIVE_URLS = False

# Feed settings (enable in production)
FEED_ALL_ATOM = 'feeds/all.atom.xml'
CATEGORY_FEED_ATOM = 'feeds/{slug}.atom.xml'

# Optimizations
DELETE_OUTPUT_DIRECTORY = True

# Disable drafts in production
WITH_FUTURE_DATES = False
