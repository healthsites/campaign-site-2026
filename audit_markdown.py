from pathlib import Path

content_dir = Path("content/campaigns")
report = []

for md_file in sorted(content_dir.rglob("*.md")):
    with open(md_file, 'r') as f:
        content = f.read()

    try:
        front_matter = {}
        for line in content.splitlines():
            if not line.strip() or line.strip() == '---':
                break
            if ':' in line:
                key, _, val = line.partition(':')
                front_matter[key.strip()] = val.strip()

        if front_matter:
            report.append({
                'file': str(md_file),
                'template': front_matter.get('Template', front_matter.get('template', 'N/A')),
                'slug': front_matter.get('Slug', front_matter.get('slug', 'N/A')),
                'has_map_image': 'Map_image' in front_matter or 'map_image' in front_matter,
                'has_hero_image': 'hero_image' in front_matter,
                'has_geojson_file': 'geojson_file' in front_matter,
                'map_image': front_matter.get('Map_image', front_matter.get('map_image', None)),
                'hero_image': front_matter.get('hero_image', None),
            })
    except Exception as e:
        print(f"Error parsing {md_file}: {e}")

print("\n" + "="*100)
print("MARKDOWN FILES AUDIT REPORT")
print("="*100)
for item in report:
    print(f"\nFile: {item['file']}")
    print(f"  Template: {item['template']}")
    print(f"  Slug: {item['slug']}")
    print(f"  Has Map_image: {item['has_map_image']} → {item['map_image']}")
    print(f"  Has hero_image: {item['has_hero_image']} → {item['hero_image']}")
    print(f"  Has geojson_file: {item['has_geojson_file']}")

print("\n" + "="*100)
print(f"SUMMARY: {len(report)} files found")
print("="*100)

with open('audit_report_markdown.txt', 'w') as f:
    for item in report:
        f.write(f"{item['file']}\n")
        f.write(f"  Template: {item['template']}\n")
        f.write(f"  Map_image: {item['map_image']}\n")
        f.write(f"  hero_image: {item['hero_image']}\n\n")

print("\nReport saved to audit_report_markdown.txt")
