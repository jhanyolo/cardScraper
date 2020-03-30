from bs4 import BeautifulSoup, SoupStrainer
import requests
import urllib
import os.path
import csv
from tqdm import tqdm

from general.constants import *

unloaded_cards_error_list = []
image_error_list = []


# return bigweb booster url based on user input
# checks if booster exists
def get_bigweb_booster_url(booster_name):
	try:
		result = requests.get('http://www.bigweb.co.jp/ver2/battlespirits_index.php', timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)
	else:
		strainer = SoupStrainer('td', id='box_1')
		soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
		booster_set_list = soup.find('select').find_all('option')

		booster_name = '[{}]'.format(booster_name)
		for i in booster_set_list:
			if booster_name in i.get_text():
				booster_value = i.attrs['value']
				return 'http://www.bigweb.co.jp/ver2/battlespirits_index.php?search=yes&type_id=142&action=search&shape=1&seriesselect=' + booster_value + '&tyselect=&colourselect=&langselect=&condiselect=&selecttext=&search1=+%E3%82%B7+%E3%83%B3+%E3%82%B0+%E3%83%AB+%E6%A4%9C+%E7%B4%A2+&page=0'
		return False


# get essential info from bigweb for a card based on its unique card_id (BS43-X01)
def get_bigweb_dict(card_id, jpy_price):
	bigweb_dict = {	'code': '',
					'jap_name': '',
					'image_link': '',
					'price': '',
					'reprint_code': ''}
	try:
		result = requests.get('http://www.bigweb.co.jp/ver2/pd2.php?card_id=' + card_id, timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)

	soup = BeautifulSoup(result.content, 'lxml')

	#  get card code from the last row
	rows = soup.find_all('tr')
	card_code = rows[-1].get_text().split(':')[1].strip()

	# if card is a reprint, code will be in a different format
	# replace bigweb delimiter (※), '(' and  ')' with underscore (_)
	# cuurent format = currentSetCode※(originalCode)
	# e.g. SD47-19※(LM16-03)
	if CONST_BIGWEB_REPRINT_SEPARATOR in card_code:
		bigweb_dict['reprint_code'] = card_code.split(CONST_BIGWEB_REPRINT_SEPARATOR)[1]
		if '(' == bigweb_dict['reprint_code'][0] and ')' == bigweb_dict['reprint_code'][-1]:
			bigweb_dict['reprint_code'] = bigweb_dict['reprint_code'][1:-1]

		card_code = card_code.replace(CONST_BIGWEB_REPRINT_SEPARATOR, CONST_NEW_REPRINT_SEPARATOR)

	card_code = card_code.replace('(', CONST_NEW_REPRINT_SEPARATOR).replace(')', CONST_NEW_REPRINT_SEPARATOR)
	bigweb_dict['code'] = card_code.upper()

	# title_html contains jap name ending with delimiter '/' (e.g. 戦国龍皇ジークフリート・魁/)
	# BSC sets reprinted cards(RPC) contain the original print card code in title_html
	# together with the jap name (e.g. 戦国龍皇ジークフリート・魁/※BSC30-X01)
	title_html = soup.find('title').get_text()

	# get the original card code of RPCs from title_html if it exists
	if CONST_BIGWEB_REPRINT_SEPARATOR in title_html and '予約' not in title_html:
		if CONST_BIGWEB_REPRINT_SEPARATOR + '(' in title_html:
			bigweb_dict['reprint_code'] = title_html.split(CONST_BIGWEB_REPRINT_SEPARATOR)[1][1:-1]
		else:
			bigweb_dict['reprint_code'] = title_html.split(CONST_BIGWEB_REPRINT_SEPARATOR)[1]

	jap_name = title_html
	if 'SC】' in title_html:
		jap_name = title_html.split('】', 1)[1]
	if '/' in jap_name:
		jap_name = jap_name.split('/')[0]

	bigweb_dict['jap_name'] = jap_name

	# convert yen to sgd and assign value to dict
	price = int(jpy_price)

	if price < CONST_EXCHANGE_RATE:
		price = round(price / CONST_EXCHANGE_RATE, 1)
	else:
		price = round(price / CONST_EXCHANGE_RATE)

	bigweb_dict['price'] = price

	bigweb_dict['image_link'] = 'http://www.bigweb.co.jp' + soup.find('img').attrs['src'].split('?')[0]

	return bigweb_dict


# retrieve card code, jap_name, imagelink and price
def get_bigweb_dict_list(bigweb_booster_url):
	print('Retrieving data from bigweb..')

	bigweb_dict_list = []
	card_counter = 0  # counts number of cards to display cards loaded
	page_counter = 0  # counts number of pages read

	# get total page number and beautifulSoup with card information
	try:
		result = requests.get(bigweb_booster_url, timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)
	strainer = SoupStrainer('div', class_='pickup')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
	total_pages = len(soup.find_all('form')[1].find_all('span'))

	# read all cards on all available pages
	while page_counter != total_pages:
		if page_counter != 0:
			bigweb_booster_url = bigweb_booster_url[:-1] + str(page_counter)
			result = requests.get(bigweb_booster_url, timeout=5)
		strainer = SoupStrainer('div', class_=['watermat abc', 'watermat abcd'])
		soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

		# create bigweb_dict for each card and add to list
		product_list = soup.find_all('div', attrs={'class': ['watermat abc', 'watermat abcd']})
		for product in product_list:
			# get card id
			card_id = product.find('a').attrs['onclick']
			card_id = card_id.split('(', 1)[1].split(')', 1)[0]

			# get price (not found in individual product page
			jpy_price = product.find('span').get_text()[:-1]

			bigweb_dict = get_bigweb_dict(card_id, jpy_price)
			bigweb_dict_list.append(bigweb_dict)
			card_counter += 1
			print('Loading: {0}'.format(card_counter), end='\r')

		page_counter += 1
	print('\n')
	return bigweb_dict_list


# get code and english name of each card from BS wiki
def get_bswiki_dict_list(booster_name):
	try:
		result = requests.get('https://battle-spirits.fandom.com/wiki/' + booster_name, timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)

	strainer = SoupStrainer('div', id='mw-content-text')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	# The 3 for loops removes irrelevant information till only <tr> elements containing cards info remains
	# removes last table containing card sets
	for i in soup.find_all('table', class_="toccolours"):
		i.decompose()

	# removes tables that does not contain card info
	for i in soup.find_all('table', attrs={'cellspacing': '0'}):
		i.decompose()

	# removes headers and empty rows
	for i in soup.find_all('tr'):
		if i.findChildren('th'):
			i.decompose()
		if i.get_text().isspace():
			i.decompose()

	# load card data to bswiki_dict_list
	bswiki_dict_list = []

	tables = soup.find_all('tr')
	for row in tables:
		bswiki_dict = {	'code': '',
						'english_name': ''}

		row_details = row.find_all('td')[:2]

		# get code
		bswiki_dict['code'] = row_details[0].get_text().strip().upper()

		# manually add booster name for BS sets
		# BS sets do not include booster name in wiki card code
		if 'BS' in booster_name and booster_name[2] != 'C' and '-' not in bswiki_dict['code']:
			bswiki_dict['code'] = booster_name + '-' + bswiki_dict['code']

		# get english name
		bswiki_dict['english_name'] = row_details[1].get_text().strip()

		bswiki_dict_list.append(bswiki_dict)

	return bswiki_dict_list


# get ONLY parallel cards from fullahead
# FA parallel cards are cross referenced to accurately match the english name to the correct card
def get_fa_parallel_code_list(search_field, booster_name):
	url = 'https://fullahead-tcg.com/?mode=srh&cid=&keyword=' + search_field + booster_name
	try:
		result = requests.get(url, timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)

	strainer = SoupStrainer('div', class_='indexItemBox')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	fa_parallel_dict_list = []
	for data in soup.find_all('span', class_="itenName"):
		fa_dict = {	'code': '',
					'jap_name': ''}

		# splitting by '-' is the best way to get japanese name as format changes dramatically from set to set
		# the only thing constant is that there will only be one '-' in the card code (e.g. SD43-31)
		# Example of format: NOT_CONSTANT_STUFF BSC34-X01 JAP_NAME NOT_CONSTANT_STUFF
		code = data.get_text().split('-', 1)
		booster_code = code[0].rsplit('】', 1)[1]
		code = code[1]

		# remove trailing '【' if any, some codes may contain extra info inside【 】brackets
		if '【' in code:
			code = code.split('【')[0]
		code = code.strip().split(' ')
		# may or may not have a rarity sign at the last index of the list
		# remove the last index if rarity exists to prevent it from appearing in jap_name
		if is_english(code[-1]):
			code = code[:-1]

		# format card code
		# some revival (RV) cards have a space (eg. BS-43RV X01) and needs to be joined tgt (BS43-RVX01)
		if code[0] == 'RV':
			fa_dict['code'] = '{0}-{1}{2}'.format(booster_code, code[0], code[1])
			fa_dict['jap_name'] = ' '.join(code[2:])
		else:
			fa_dict['code'] = '{0}-{1}'.format(booster_code, code[0])
			fa_dict['jap_name'] = ' '.join(code[1:])

		fa_parallel_dict_list.append(fa_dict)

	return fa_parallel_dict_list


# check if can be encoded with ASCII, which are Latin alphabet and some other characters
# -*- coding: utf-8 -*-
def is_english(s):
	try:
		s.encode(encoding='utf-8').decode('ascii')
	except UnicodeDecodeError:
		return False
	else:
		return True


# combine information from bigweb and bswiki for each card, format the data and add to data_list
def load_data(bigweb_dict_list, bswiki_dict_list, fa_parallel_dict_list, booster_name):
	print('Formatting products data from {0}.'.format(booster_name))
	data_list = []
	counter = 0
	total = len(bigweb_dict_list)

	for bigweb in bigweb_dict_list:
		# checks if card is added to data_list
		check_if_added = False
		for bswiki in bswiki_dict_list:
			# bigweb_dict matches the correct bswiki_dict, format the data and add to data_list
			if compare_bigweb_bswiki(bigweb, bswiki, fa_parallel_dict_list):
				product_dict = get_product_dict(bigweb, bswiki, booster_name)
				data_list.append(product_dict)
				counter += 1
				check_if_added = True
				print('Loading: {0}/{1}'.format(counter, total), end='\r')
				break

		# adds card to error file if its info is not added to data_list
		if not check_if_added:
			unloaded_cards_error_list.append(bigweb)
	print()
	return data_list


# check if codes compared are equivalent
# 1. parallel cards require additional cross reference to FullAhead due to irregular card format
# eg. Bigweb: BS43-X01P == Fullahead: 【パラレル】BS43-RVX01 == BSwiki: BS43-RVX01
def compare_bigweb_bswiki(bigweb_dict, bswiki_dict, fa_parallel_dict_list):
	bswiki_code = bswiki_dict['code']

	# bs wiki uses original card code of RPCs
	# check reprint card codes first as CP01 will give false positive for parallel
	if bigweb_dict['reprint_code']:
		return bigweb_dict['reprint_code'] == bswiki_code
	else:
		bigweb_code = bigweb_dict['code']

	# parallel cards require extra cross reference from FullAhead
	# parallel formats: BS47-X01P, BSC34-XP01 (from spliting('-'), 'P' is last index and second index respectively)
	if bigweb_code[-1].upper() == CONST_PARALLEL or bigweb_code.split('-')[1][1].upper() == CONST_PARALLEL:
		bigweb_jap_name = bigweb_dict['jap_name']
		temp = bigweb_code.upper().replace(CONST_PARALLEL, '', 1)
		return temp == bswiki_code

		# get bswiki compatible code from fullahead(FA) by comparing FA with current
		for card in fa_parallel_dict_list:
			if card['jap_name'] == bigweb_jap_name:
				return card['code'] == bswiki_code
		# if not in FA parallel cards, means the is either
		# 1. false positive due to bigweb formatting, and remove the trailing 'P' (e.g BS43-CP01P)
		# 2. CP01 will give false positive and will match with corresponding bswiki_code
		return bigweb_code[:-1] == bswiki_code or bigweb_code == bswiki_code

	return bigweb_code == bswiki_code


# used in load_data() to return product dictionary to be added to csv file
# arguments should ONLY contain matching bigweb and bswiki cards
def get_product_dict(bigweb_dict, bswiki_dict, booster_name):
	# initialise product dict with csv field names
	product_dict = {}
	for i in fieldnames:
		product_dict[i] = ''

	product_dict['Handle'] = bigweb_dict['code'] + CONST_CARD_RANK
	product_dict['Title'] = get_title(bigweb_dict['code'], bswiki_dict['english_name'])
	product_dict['Body (HTML)'] = '<p>Title: ' + bswiki_dict['english_name'] + ' [' + bigweb_dict['jap_name'] + ']</p> <p>Game: Battle Spirits</p> <p>Condition: Rank A - Mint / near mint condition, no visible damage, bent, or crease but may have few white spots on edges</p>'
	product_dict['Vendor'] = 'Cardboard Collectible'

	tag = ''
	for i in booster_name:
		if i.isdigit():
			break
		tag += i

	product_dict['Tags'] = tag + ', ' + booster_name + ', Battle Spirits'
	product_dict['Published'] = 'True'
	product_dict['Option1 Name'] = 'Title'
	product_dict['Option1 Value'] = 'Default Title'
	product_dict['Variant Grams'] = 0
	product_dict['Variant Inventory Tracker'] = 'shopify'
	product_dict['Variant Inventory Policy'] = 'deny'
	product_dict['Variant Fulfillment Service'] = 'manual'
	product_dict['Variant Price'] = bigweb_dict['price']
	product_dict['Variant Requires Shipping'] = 'TRUE'
	product_dict['Variant Taxable'] = 'FALSE'
	product_dict['Image Position'] = 1
	product_dict['Gift Card'] = 'FALSE'
	product_dict['Variant Weight Unit'] = 'kg'

	return product_dict


# format title for csv usage in get_product_dict()
def get_title(card_handle, english_name):
	card_title = 'Battle Spirits - ' + english_name

	if card_handle[-1] == CONST_PARALLEL:
		card_title += ' (Secret) [Rank:A]'
	else:
		card_title += ' [Rank:A]'

	return card_title


# only call this after load_data()
# save data as csv
def save_data(booster_name, data_list):
	fieldnames = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value', 'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price', 'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position', 'Image Alt Text', 'Gift Card', 'SEO Title', 'SEO Description', 'Google Shopping / Google Product Category', 'Google Shopping / Gender', 'Google Shopping / Age Group', 'Google Shopping / MPN', 'Google Shopping / AdWords Grouping', 'Google Shopping / AdWords Labels', 'Google Shopping / Condition', 'Google Shopping / Custom Product', 'Google Shopping / Custom Label 0', 'Google Shopping / Custom Label 1', 'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3', 'Google Shopping / Custom Label 4', 'Variant Image', 'Variant Weight Unit', 'Variant Tax Code', 'Cost per item']

	filepath = booster_name + '.csv'
	with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
		writer.writeheader()

		for i in data_list:
			writer.writerow(i)

		print('CSV file created!')
		print()


def make_directory(booster_name):
	try:
		# Create target Directory
		os.mkdir(booster_name)
	except FileExistsError:
		print("Directory ", booster_name, " already exists")

# add User-agent to urlib headers to bypass bot detection
def add_headers_to_urllib() -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)')]
    urllib.request.install_opener(opener)

def download_images(yyt_dict_list: list, booster_prefix: str) -> None:
    print('Downloading Images...')

    cardpage_counter = 1

    for i in tqdm(yyt_dict_list):
        try:
            if len(str(cardpage_counter)) == 1:
                imgName = '00' + str(cardpage_counter)
            elif len(str(cardpage_counter)) == 2:
                imgName = '0' + str(cardpage_counter)
            else:
                imgName = cardpage_counter

            urllib.request.urlretrieve(i['image_link'], f"{booster_prefix}/{imgName}.jpg")            
            cardpage_counter += 1
        # stores the card code of cards that were not downloaded in image_error_list
        except ValueError:
            image_error_list.append(i['code'])


# outputs cards info that have image downloading errors
# or that they are not loaded into data_list to be written to CSV file
def write_error_files(booster_name):
	print('Card set information is incomplete, creating error txt files...')

	# output card images that are not downloaded into text file
	if image_error_list:
		text_file_name = booster_name + 'imageErrors.txt'
		with open(text_file_name, 'w') as file:
			for i in image_error_list:
				file.write(i + '\n')
			print(text_file_name + ' created!')

	# output cards info that are not added to csv file into text file
	if unloaded_cards_error_list:
		text_file_name = booster_name + 'cardErrors.txt'
		with open(text_file_name, 'w') as file:
			for i in unloaded_cards_error_list:
				file.write(i['code'] + '\n')
			print(text_file_name + ' created!')


def main():
	add_headers_to_urllib()
	print("=" * 24)
	print("Battle Spirits Scraper")
	print("=" * 24)
	booster_name = input('Enter booster pack name (eg. bs48) or press q to quit: ').upper()
	while booster_name != 'Q':
		bigweb_booster_url = get_bigweb_booster_url(booster_name)
		if bigweb_booster_url:
			# retrieve info from bigweb, BS wiki and FullAhead
			bigweb_dict_list = get_bigweb_dict_list(bigweb_booster_url)
			bswiki_dict_list = get_bswiki_dict_list(booster_name)

			# get all possible parallel cards from FullAhead using 3 different searchfields as naming convention is different for different sets
			# 1:【パラレル】BS44
			# 2:【SECRET】【BS44
			# 3:【SECRET】BS44-X01
			fa_parallel_dict_list = get_fa_parallel_code_list('%A1%DA%A5%D1%A5%E9%A5%EC%A5%EB%A1%DB', booster_name)
			fa_parallel_dict_list += get_fa_parallel_code_list('%A1%DASECRET%A1%DB%A1%DA', booster_name)
			fa_parallel_dict_list += get_fa_parallel_code_list('%A1%DASECRET%A1%DB', booster_name)

			# load all cards info into data_list and save to csv file
			data_list = load_data(bigweb_dict_list, bswiki_dict_list, fa_parallel_dict_list, booster_name)
			save_data(booster_name, data_list)

			# download images
			make_directory(booster_name)
			download_images(bigweb_dict_list, booster_name)

			# output error files if any
			if image_error_list or unloaded_cards_error_list:
				write_error_files(booster_name)
			break
		else:
			print(booster_name + " cannot be found.")
			print('Returning to booster pack input..')
			print()
			booster_name = input('Enter booster pack name (eg. bs-10) or press q to quit: ').upper()


if __name__ == '__main__':
	main()
