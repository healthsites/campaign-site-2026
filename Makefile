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

PELICAN = venv/bin/python3 -m pelican

build: clean
	@echo "🔨 Building site..."
	$(PELICAN) content
	@echo "✅ Build complete"

serve: build
	@echo "🌐 Starting development server..."
	@echo "📍 Site available at: http://localhost:8000"
	$(PELICAN) --listen

publish: clean
	@echo "📦 Building for production..."
	$(PELICAN) content -s publishconf.py
	@echo "✅ Production build complete"
	@echo "📁 Output in: output/"

deploy: publish
	@echo "🚀 Deployment command placeholder"
	@echo "⚠️  Configure your deployment method in Makefile"
	@echo ""
	@echo "Example:"
	@echo "  rsync -avz output/ user@server:/var/www/campaigns/"
