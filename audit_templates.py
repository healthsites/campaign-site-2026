import re
from pathlib import Path

template_dir = Path("theme/templates")
report = []

# Collect all .html template files
html_files = sorted(template_dir.glob("*.html"))

for html_file in html_files:
    with open(html_file, 'r') as f:
        content = f.read()
    
    # Look for references to map_image, hero_image, geojson_file
    has_map_image = 'map_image' in content.lower()
    has_hero_image = 'hero_image' in content.lower()
    has_geojson = 'geojson_file' in content.lower()
    has_leaflet = 'leaflet' in content.lower()
    
    report.append({
        'file': html_file.name,
        'has_map_image': has_map_image,
        'has_hero_image': has_hero_image,
        'has_geojson': has_geojson,
        'has_leaflet': has_leaflet,
    })

# Print report
print("\n" + "="*100)
print("HTML TEMPLATES AUDIT REPORT")
print("="*100)
for item in report:
    print(f"\nTemplate: {item['file']}")
    print(f"  References map_image: {item['has_map_image']}")
    print(f"  References hero_image: {item['has_hero_image']}")
    print(f"  References geojson_file: {item['has_geojson']}")
    print(f"  Has Leaflet: {item['has_leaflet']}")

print("\n" + "="*100)
