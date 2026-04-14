#!/bin/bash
# Healthsites Vanilla - Cleanup and Setup Script
# This script implements best practices for Pelican project structure

set -e  # Exit on error

echo "🧹 Healthsites Vanilla Cleanup & Setup"
echo "======================================"
echo ""

# Check we're in the right directory
if [ ! -f "pelicanconf.py" ]; then
    echo "❌ Error: pelicanconf.py not found. Are you in the project root?"
    exit 1
fi

echo "📍 Current directory: $(pwd)"
echo ""

# 1. Remove pelican-plugins
echo "1️⃣  Removing pelican-plugins directory..."
if [ -d "pelican-plugins" ]; then
    rm -rf pelican-plugins/
    echo "   ✅ Removed pelican-plugins/"
else
    echo "   ℹ️  pelican-plugins/ not found (already clean)"
fi

# 2. Remove plugin references from pelicanconf.py
echo ""
echo "2️⃣  Cleaning pelicanconf.py..."
if grep -q "PLUGIN" pelicanconf.py; then
    # Backup original
    cp pelicanconf.py pelicanconf.py.backup
    
    # Remove plugin lines
    sed -i '/PLUGIN_PATHS/d' pelicanconf.py
    sed -i '/PLUGINS/d' pelicanconf.py
    sed -i '/JINJA_ENVIRONMENT/d' pelicanconf.py
    sed -i '/I18N_SUBSITES/d' pelicanconf.py
    
    echo "   ✅ Removed plugin references (backup saved as pelicanconf.py.backup)"
else
    echo "   ℹ️  No plugin references found"
fi

# 3. Create .gitignore
echo ""
echo "3️⃣  Creating .gitignore..."
cat > .gitignore << 'GITIGNORE'
# Pelican
output/
cache/
*.pid
__pycache__/
*.pyc

# Python
venv/
*.egg-info/
.env

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp

# Plugins (if using git submodule)
pelican-plugins/

# Build artifacts
*.log

# Backups
*.backup
*-backup-*/
GITIGNORE
echo "   ✅ Created .gitignore"

# 4. Create requirements.txt
echo ""
echo "4️⃣  Creating requirements.txt..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip freeze > requirements.txt
    echo "   ✅ Created requirements.txt from current environment"
else
    cat > requirements.txt << 'REQUIREMENTS'
pelican==4.9.1
markdown==3.5.1
REQUIREMENTS
    echo "   ✅ Created basic requirements.txt (no venv found)"
fi

# 5. Create publishconf.py
echo ""
echo "5️⃣  Creating publishconf.py..."
cat > publishconf.py << 'PUBLISHCONF'
#!/usr/bin/env python
# -*- coding: utf-8 -*- #

# Import development settings
from pelicanconf import *

# Production URL (update this to your actual domain)
SITEURL = 'https://campaigns.healthsites.io'
RELATIVE_URLS = False

# Feed settings (enable in production)
FEED_ALL_ATOM = 'feeds/all.atom.xml'
CATEGORY_FEED_ATOM = 'feeds/{slug}.atom.xml'

# Optimizations
DELETE_OUTPUT_DIRECTORY = True

# Disable drafts in production
WITH_FUTURE_DATES = False

# Optional: Enable analytics
# GOOGLE_ANALYTICS = 'UA-XXXXXXXXX-X'
PUBLISHCONF
echo "   ✅ Created publishconf.py"

# 6. Create Makefile
echo ""
echo "6️⃣  Creating Makefile..."
cat > Makefile << 'MAKEFILE'
.PHONY: help clean build serve publish deploy

help:
	@echo "Healthsites Campaigns - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "  make clean     - Remove output directory"
	@echo "  make build     - Build site (development)"
	@echo "  make serve     - Build and serve locally"
	@echo "  make publish   - Build for production"
	@echo "  make deploy    - Build and deploy to server"
	@echo ""

clean:
	@echo "🧹 Cleaning output directory..."
	rm -rf output/
	@echo "✅ Clean complete"

build: clean
	@echo "🔨 Building site..."
	pelican content
	@echo "✅ Build complete"

serve: build
	@echo "🌐 Starting development server..."
	@echo "📍 Site available at: http://localhost:8000"
	pelican --listen

publish: clean
	@echo "📦 Building for production..."
	pelican content -s publishconf.py
	@echo "✅ Production build complete"
	@echo "📁 Output in: output/"

deploy: publish
	@echo "🚀 Deployment command placeholder"
	@echo "⚠️  Configure your deployment method in Makefile"
	@echo ""
	@echo "Example:"
	@echo "  rsync -avz output/ user@server:/var/www/campaigns/"
MAKEFILE
echo "   ✅ Created Makefile"

# 7. Create README.md
echo ""
echo "7️⃣  Creating README.md..."
cat > README.md << 'README'
# Healthsites.io Campaigns Site

Multi-country health facility validation campaign website built with Pelican.

README

## 🌍 Site Structure
