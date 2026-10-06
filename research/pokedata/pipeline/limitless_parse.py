"""Distinguish a missing/unparseable print section from an empty print list."""
import html
import re

def parse_prints(document, japanese):
    label = 'JP. Prints' if japanese else 'Int. Prints'
    start = document.find(label)
    if start < 0:
        return None
    end = document.find('</table>', start)
    if end < 0:
        return None
    segment = document[start:end]
    prefix = '/cards/jp/' if japanese else '/cards/'
    pattern = (r'href=[\"\']/cards/' + ('jp/' if japanese else '') +
               r'([A-Za-z0-9+\-]+)/([^\"\'/]+)[\"\'][^>]*>\s*([^<]+?)\s*<span')
    found = [(c, n, html.unescape(name).strip()) for c, n, name in re.findall(pattern, segment)
             if japanese or c.lower() != 'jp']
    # Links exist but none could be parsed: never interpret as an empty catalog.
    if prefix in segment and not found:
        return None
    return found
