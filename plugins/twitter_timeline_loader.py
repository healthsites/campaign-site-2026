import json
import os
from pelican import signals

def inject_timeline_data(generator):
    """Inject twitter_timeline_data.json into page context at build time."""
    timeline_path = os.path.join(generator.settings['PATH'], 'twitter_timeline_data.json')
    
    if os.path.exists(timeline_path):
        with open(timeline_path) as f:
            timeline_data = json.load(f)
        
        generator.context['timeline_data'] = json.dumps(timeline_data)
    else:
        print(f"Warning: {timeline_path} not found")

def register():
    signals.page_generator_finalized.connect(inject_timeline_data)
