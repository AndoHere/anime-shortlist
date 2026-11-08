"""Company adapters. To add a company, create a module next to these with:

NAME, SLUG, SITE, ROLE   display name, file slug, site domain, what the company does
LIST_URL                 the page the titles come from (linked in the page header)
list_titles(refresh)     -> [{"url", ...hints such as "ja", "en", "year", "poster", "tags", "label"}]
details(item, refresh)   -> {"images": [...], "trailers": [youtube ids], "official": [url], ...optional
                             "poster", "ja", "romaji", "year", "director", "synopsis"}

then add it to COMPANIES below and run build.py.

An adapter may set "co" on a title to label it with another company name (see hakuhodo.py).
A title listed by several companies is shown once (build.merge_duplicates): the first company in this
list keeps the entry, and the others' names, links, images and trailers are added to it.
"""
from companies import aniplex, gaga, hakuhodo, production_ig

COMPANIES = [gaga, production_ig, hakuhodo, aniplex]
