import re
from pathlib import Path

# Define updates
updates = [
    {
        'file': 'content/campaigns/senegal.md',
        'remove': ['hero_image: /theme/images/senegal-regions.png'],
        'add': 'geojson_file: sen_admin1.geojson'
    },
    {
        'file': 'content/campaigns/saint-louis.md',
        'remove': ['Map_image: /theme/images/validated-healthsites-saint-louis1.png'],
        'add': 'geojson_file: sen_admin1.geojson'
    },
    {
        'file': 'content/campaigns/senegal/index-fr.md',
        'remove': ['Map_image: /theme/images/senegal-regions.png'],
        'add': 'geojson_file: sen_admin1.geojson'
    },
    {
        'file': 'content/campaigns/senegal/saint-louis-fr.md',
        'remove': [],
        'add': 'geojson_file: sen_admin1.geojson'
    }
]

for update in updates:
    filepath = Path(update['file'])
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Remove old fields
    for remove_line in update['remove']:
        content = content.replace(remove_line + '\n', '')
        print(f"✓ Removed: {remove_line}")
    
    # Add new field (after Status: published line)
    if 'Status: published' in content:
        content = content.replace(
            'Status: published',
            f'Status: published\ngeojson_file: sen_admin1.geojson'
        )
        print(f"✓ Added geojson_file to {filepath}")
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated: {filepath}\n")

print("All markdown files updated!")
