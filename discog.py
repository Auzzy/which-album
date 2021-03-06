import re

from bs4 import BeautifulSoup

import htmlutil
import util

SECTION_NAMES = ["albums", "singles"]
SUB_SECTIONS_EXCLUDE = ["video albums"]
TITLE_COLS = ["title", "song", "album details", "single/ep"]

_HTML_TAG = "[^<]*?(?:\\<[^>]+?\\>[^<]*?)*"
QUOTED_REGEX = "(?:{tag})?[^\"]*?\\\"(?P<quoted>{tag})\\\".*".format(tag=_HTML_TAG)
QUOTED_RE = re.compile(QUOTED_REGEX)

# One of a couple ways to tell a link is broken in HTML. Additionally, href will
# be "/w/index.php?title=<title>&amp;action=edit&amp;redlink=1", and the page
# title will have " (page does not exist)" appended
BROKEN_LINK_CLASS = "new"
CITATION_NEEDED = "citation needed"
HELP_PAGE = "help page"
EDIT = "edit"

def _is_broken(link):
	return "class" in link.attrs and BROKEN_LINK_CLASS in link["class"]

def _citation_needed(link):
	return link.string == CITATION_NEEDED

def _is_help(link):
	return link.string == HELP_PAGE

def _is_edit(link):
	return link.string == EDIT

def _is_special(link):
	return _is_edit(link) or _is_help(link) or _citation_needed(link)


def _match_quoted(tag):
	result = QUOTED_RE.match(str(tag))
	return (result.group("quoted"),result.start("quoted")) if result else (None,len(str(tag)))

def _find_album_element(cell):
	max_index = len(str(cell))
	
	quoted, quoted_start = _match_quoted(cell)
	quoted_container = BeautifulSoup(quoted) if quoted else quoted
	# quoted_start = str(cell).find(str(quoted)) if quoted else max_index
	# print quoted_container
	
	italic = cell.find(("i", "b", "em", "strong"))
	italic_start = str(cell).index(str(italic)) if italic else max_index
	link = cell.find("a", title=True)
	link_start = str(cell).index(str(link)) if link else max_index
	if link:
		link_start = str(cell).index(str(link))
		link_container = BeautifulSoup().new_tag("div")
		link.wrap(link_container)
	else:
		link_start = max_index
		link_container = link
	
	# Finds the first occurrance of eithe rquoted, italic, or linked text. This
	# is most likely to be the album name.
	album_element = min((quoted_container, quoted_start), (italic, italic_start), (link_container, link_start), key=lambda arg: arg[1])
	return album_element[0]

def _extract_page_names(cells):
	page_names = []
	for cell in cells:
		album_element = _find_album_element(cell)
		link = album_element.find("a", title=True)
		if link and not _is_broken(link):
			page_names.append(link["title"])
		
		'''
		link = cell.find("a", title=True)
		if link and not _is_broken(link):
			page_names.append(link["title"])
		'''
	return page_names

def _find_title_column_index(cols):
	title_col_index = None
	for title_col in TITLE_COLS:
		if title_col in cols:
			return cols[title_col]
	return None

def _parse_table(table):
	table = htmlutil.normalize_table(table)
	cols,header_row = htmlutil.get_table_headers(table)
	title_col_index = _find_title_column_index(cols)
	
	page_names = []
	if title_col_index is not None:
		name_cells = [row(("th", "td"))[title_col_index] for row in header_row.find_next_siblings("tr")]
		page_names = _extract_page_names(name_cells)
	return page_names

def _parse_section(site, page_name, section_name):
	section_html = util.get_section(site, page_name, section_name, False)
	section_soup = BeautifulSoup(section_html)
	page_names = []
	for table in section_soup("table"):
		page_names.extend(_parse_table(table))
	return page_names

def parse_discog_page(site, page_name):
	sections = util.map_section_names(site, page_name)
	album_page_names = []
	for section_name in SECTION_NAMES:
		if section_name in sections:
			album_page_names.extend(_parse_section(site, page_name, sections[section_name]))
	return album_page_names

def parse_discog_section(site, artist_page, discog_section):
	page_names = _parse_section(site, artist_page, "Discography")
	if not page_names:
		discog_section_html = site.parse_text(discog_section, False)
		discog_section_soup = BeautifulSoup(discog_section_html)
		page_names = [link["title"] for link in discog_section_soup("a", title=True) if not _is_broken(link) and not _is_special(link)]
	return page_names

def parse_discog(site, artist_page, discog_section, discog_page):
	album_pages = []
	if discog_page:
		album_pages = parse_discog_page(site, discog_page)
	else:
		album_pages = parse_discog_section(site, artist_page, discog_section)
	return set(album_pages)
