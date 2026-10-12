"""No installation-specific defaults. Configuration errors never expose values."""
import hashlib
import json
import re
from shadow import SOURCE_KEYS

class ConfigurationError(ValueError): pass

def load_sources(path):
    try:
        with open(path,encoding='utf-8') as f: options=json.load(f)
        sources=options['sources']
        if not isinstance(sources,dict) or set(sources)!=set(SOURCE_KEYS): raise ValueError
        for key,value in sources.items():
            domain='binary_sensor' if key=='workday' else 'sensor'
            if not isinstance(value,str) or not re.fullmatch(domain+r'\.[a-z0-9_]+',value): raise ValueError
        if len(set(sources.values()))!=len(sources): raise ValueError
    except (OSError,ValueError,TypeError,KeyError):
        raise ConfigurationError('invalid_or_missing_source_settings') from None
    return sources

def fingerprint(sources):
    return hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
