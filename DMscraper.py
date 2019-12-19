import urllib
import csv
import os.path
from bs4 import BeautifulSoup, SoupStrainer
import requests


CONST_EXCHANGE_RATE = 80  # SGD/JPY
CONST_CARD_RANK = 'a'
CONST_FULLAHEAD_SECRET = ['秘', 'SS']
image_error_list = []
unloaded_cards_error_list = []


# add User-agent to urlib headers to bypass bot detection
def add_headers_to_urllib():
	opener = urllib.request.build_opener()
	opener.addheaders = [('User-agent', 'Mozilla/5.0')]
	urllib.request.install_opener(opener)


# return booster url based on user input
def get_dmwiki_booster_url(booster_name):
	result = requests.get('https://duelmasters.fandom.com/wiki/Duel_Masters_Wiki', timeout=5)
	strainer = SoupStrainer('div', class_='lightbox-caption')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	# check if card sets in 'Recent and Upcoming Sets' matches user's desired card set
	booster_list = soup.find_all('a')
	for i in booster_list:
		# return link if booster exists
		if booster_name == i['title'][:len(booster_name)]:
			return 'https://duelmasters.fandom.com' + i['href']
	print('Booster not found on DM wiki')
	print()
	return False


# get card code and link to card from dmwiki
def get_dmwiki_dict_list(dmwiki_link):
	result = requests.get(dmwiki_link, timeout=5)

	# strain out content and get card lists in between <h2>"Contents"</h2> and <h2>"Cycles"</h2>
	strainer = SoupStrainer('div', id='mw-content-text')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
	soup = str(soup).split('Contents</span></h2>')[1].split('<h2><span class="mw-headline"')[0]
	soup = BeautifulSoup(soup, 'lxml', parse_only=SoupStrainer('li'))

	card_list = soup.find_all('li')
	dmwiki_dict_list = []
	for i in card_list:
		dmwiki_card = {	'code': '',
						'english_name': ''}

		# replace unicode nbsp(\xa0) with space, and split to get card code
		dmwiki_card['code'] = i.getText().replace('\xa0', ' ').split(' ')[0]
		dmwiki_card['code'] = dmwiki_card['code'].split('/')[0].upper()

		dmwiki_card['english_name'] = i.find('a')['title']
		dmwiki_dict_list.append(dmwiki_card)

	print('DM wiki information loaded!')
	print()
	return dmwiki_dict_list


# return booster url based on user input (if it exists)
def get_fullahead_booster_url(booster_name):
	try:
		result = requests.get('https://fullahead-dm.com/?mode=srh&cid=&keyword=', timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)
	strainer = SoupStrainer('div', class_='categoryBox')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	# check if card sets in FA sidebar
	booster_list = soup.find_all('a')
	for i in booster_list:
		# return link if booster exists
		if i.get_text() == booster_name:
			booster_url = i.attrs['href']

			# some urls are incomplete
			if 'https://fullahead-dm.com' not in booster_url:
				booster_url = 'https://fullahead-dm.com' + booster_url
			return booster_url
	return False


# retrieve card code, jap_name, imagelink
def get_fullahead_dict_list(booster_url, booster_name):
	print('Retrieving products from Fullahead...')

	# get total number of pages by finding total number of cards
	# each page has 100 cards maximum
	counter = 1
	htmllink = f"{booster_url}&sort=n&page="
	try:
		result = requests.get(htmllink + str(counter), timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)
	strainer = SoupStrainer('span', class_='pagerTxt')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	total_items = int(soup.find('strong').get_text()[1:-1])
	pages = total_items // 101 + 1
	fullahead_dict_list = []

	# load all cards returned from the search
	card_counter = 0
	while counter != pages + 1:
		if counter != 1:
			result = requests.get(htmllink + str(counter), timeout=5)

		soup = BeautifulSoup(result.content, 'lxml')
		card_list = soup.find('div', class_='indexItemBox').find_all('div')

		# get necessary card info in fullahead_dict and add to list
		for card_div in card_list:
			card_url = card_div.find('a').attrs['href']
			card_title = card_div.find('span', class_='itenName').get_text()
			price_jpy = card_div.find('span', class_='itemPrice').find('strong').get_text()

			# get fullahead info of desired cards
			# キズ格安 = damaged , 宅配便のみ = local courier(mostly non-cards)
			if 'キズ格安' not in card_title and '宅配便のみ' not in card_title:
				fullahead_dict = get_fullahead_dict(card_url, card_title, booster_name, price_jpy)
				fullahead_dict_list.append(fullahead_dict)
				card_counter += 1
				print('Loading: {0}/{1}'.format(card_counter, total_items), end='\r')
		counter += 1

	return fullahead_dict_list


def get_fullahead_dict(card_url, card_title, booster_name, price_jpy):
	fullahead_dict = {	'handle': '',
						'code': '',
						'rarity': '',
						'jap_name': '',
						'image': '',
						'price': ''}

	# dmbd formatting different in fullahead
	# truncate from 'dmbd' to 'bd'
	booster_split = booster_name
	if 'DMBD' in booster_name:
		booster_split = booster_split[2:]

	# get code by splitting card title with booster name
	# code will be the next information after booster name in card_title (e.g. DMRP-10/G7/)
	temp = card_title.split(booster_split)
	if len(temp) == 1:
		remaining_info = temp[0][1:]
	else:
		remaining_info = temp[1][1:]
	code = remaining_info.split('/', 1)[0]
	fullahead_dict['code'] = code

	# get rarity for card
	rarity = remaining_info.split('/', 3)[1]
	fullahead_dict['rarity'] = rarity

	# get price by converting JPY to SGD
	price = price_jpy.split('円')[0]
	if ',' in price:
		price = price.replace(',', '')
	price = int(price)

	if price < CONST_EXCHANGE_RATE:
		price = round(price / CONST_EXCHANGE_RATE, 1)

		if rarity.upper() == 'C':
			price = max(price, 0.3)
		elif rarity.upper() == 'U':
			price = max(price, 0.5)
		else:
			price = 1
	else:
		price = round(price / CONST_EXCHANGE_RATE)

	fullahead_dict['price'] = price

	# get jap name by storing all characters before the jap name in 'temp' string
	# and split the string using 'temp'
	temp = ''
	for i in range(len(remaining_info)):
		if is_english(remaining_info[i]) or remaining_info[i] == '/' or remaining_info[i] == '秘' or remaining_info[i] == '超':
			temp += remaining_info[i]

			if temp.count('/') == 2:
				break
		else:
			break
	jap_name = card_title.split(temp)[1]

	if jap_name.count('/') > 0 and is_english(jap_name.split('/')[0]):
		jap_name = jap_name.split('/')[1]

	fullahead_dict['jap_name'] = jap_name

	# get FA handle name and price from individual card page
	try:
		result = requests.get('https://fullahead-dm.com' + card_url, timeout=5)
	except requests.exceptions.RequestException as e:
		print(e)
	strainer = SoupStrainer('div', class_='product_detail_area cf')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	# get image
	image_list = soup.find_all('img', class_={'zoom-tiny-image'})
	fullahead_dict['image'] = image_list[0].attrs['src']

	# get handle name
	card_table_details = soup.find_all('td')
	fullahead_dict['handle'] = card_table_details[0].get_text()

	return fullahead_dict


# check if can be encoded with ASCII, which are Latin alphabet and some other characters
# -*- coding: utf-8 -*-
def is_english(s):
	try:
		s.encode(encoding='utf-8').decode('ascii')
	except UnicodeDecodeError:
		return False
	else:
		return True


# combine information from fullahead and dmwiki for each card, format the data and add to data_list
def load_data(dmwiki_dict_list, fullahead_dict_list, booster_name):
	data_list = []
	print('Processing products from {0}.'.format(booster_name))
	counter = 0
	total = len(fullahead_dict_list)

	for full in fullahead_dict_list:
		# checks if card is added to data_list
		check_if_added = False
		for dmwiki in dmwiki_dict_list:
			if dmwiki['code'] == full['code']:
				product_dict = get_product_dict(full, dmwiki, booster_name)
				data_list.append(product_dict)
				counter += 1
				check_if_added = True
				print('Loading: {0}/{1}'.format(counter, total), end='\r')
				break
		# add to error_list if card is added
		if not check_if_added:
			unloaded_cards_error_list.append(full)
	print()
	return data_list


# used in load_data() to return product dictionary to be added to csv file
# arguments should ONLY contain matching FA and dmwiki cards
def get_product_dict(full_dict, dmwiki_dict, booster_name):
	product_dict = {}
	product_dict['Handle'] = full_dict['handle'] + CONST_CARD_RANK
	product_dict['Title'] = get_title(full_dict, dmwiki_dict['english_name'], booster_name)
	product_dict['Body (HTML)'] = '<p>Title: {0} [{1}]</p><p>Game: Duel Masters</p><p>Condition: Rank A - Mint / near mint condition, no visible damage, bent, or crease but may have few white spots on edges</p>'.format(dmwiki_dict['english_name'], full_dict['jap_name'])
	product_dict['Vendor'] = 'Cardboard Collectible'
	product_dict['Tags'] = booster_name.split('-', 1)[0] + ', ' + booster_name + ', Duel Masters'
	product_dict['Published'] = 'True'
	product_dict['Option1 Name'] = 'Title'
	product_dict['Option1 Value'] = 'Default Title'
	product_dict['Variant Grams'] = 0
	product_dict['Variant Inventory Tracker'] = 'shopify'
	product_dict['Variant Inventory Policy'] = 'deny'
	product_dict['Variant Fulfillment Service'] = 'manual'
	product_dict['Variant Price'] = full_dict['price']
	product_dict['Variant Requires Shipping'] = 'TRUE'
	product_dict['Variant Taxable'] = 'FALSE'
	product_dict['Image Position'] = 1
	product_dict['Gift Card'] = 'FALSE'
	product_dict['Variant Weight Unit'] = 'kg'

	return product_dict


# format card_title to be used in get_product_title
def get_title(full_dict, english_name, booster_name):
	# format card_title
	# add booster name(dmrp10), card serial num(g1/g7) and english name sequentially
	card_title = 'Duel Masters - {0}/{1} {2}'.format(booster_name.upper(), full_dict['code'], english_name)

	# adds (secret) to secret cards and card rank to all cards
	if full_dict['rarity'] in CONST_FULLAHEAD_SECRET:
		card_title += ' (Secret) [Rank:A]'
	else:
		card_title += ' [Rank:A]'

	return card_title


# save data as csv
def save_data(booster_name, data_list):
	filepath = booster_name + '.csv'
	fieldnames = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value', 'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price', 'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position', 'Image Alt Text', 'Gift Card', 'SEO Title', 'SEO Description', 'Google Shopping / Google Product Category', 'Google Shopping / Gender', 'Google Shopping / Age Group', 'Google Shopping / MPN', 'Google Shopping / AdWords Grouping', 'Google Shopping / AdWords Labels', 'Google Shopping / Condition', 'Google Shopping / Custom Product', 'Google Shopping / Custom Label 0', 'Google Shopping / Custom Label 1', 'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3', 'Google Shopping / Custom Label 4', 'Variant Image', 'Variant Weight Unit', 'Variant Tax Code', 'Cost per item']
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


def download_images(fullahead_dict_list, booster_name):
	print('Downloading Images...')

	counter = 0
	total = len(fullahead_dict_list)
	cardCounter = 1

	for i in fullahead_dict_list:
		try:
			if len(str(cardCounter)) == 1:
				imgName = '00' + str(cardCounter)
			elif len(str(cardCounter)) == 2:
				imgName = '0' + str(cardCounter)
			else:
				imgName = cardCounter

			urllib.request.urlretrieve(i['image'], '{0}/{1}.jpg'.format(booster_name, imgName))
			counter += 1
			cardCounter += 1

			print('Downloading: {0}/{1}'.format(counter, total), end='\r')
		except ValueError:
			image_error_list.append(i['code'])

	print()
	if counter == total:
		print('All images are downloaded!')
	else:
		print('Not all images are downloaded (some images may not exist on fullahead)')


# outputs cards info that have image downloading errors
# or that they are not loaded into data_list to be written to CSV file
def write_error_files(booster_name):
	if image_error_list:
		text_file_name = booster_name + 'imageErrors.txt'
		print('Image download is incomplete, creating error txt file...')
		with open(text_file_name, 'w') as file:
			for i in image_error_list:
				file.write(i + '\n')
			print(text_file_name + ' created!')
	if unloaded_cards_error_list:
		text_file_name = booster_name + 'cardErrors.txt'
		print('Loading of cards is incomplete, creating error txt file...')
		with open(text_file_name, 'w') as file:
			for i in unloaded_cards_error_list:
				file.write(i['code'] + '\n')
			print(text_file_name + ' created!')


def main():
	add_headers_to_urllib()
	booster_name = input('Enter booster pack name (eg. dmrp-10) or press q to quit: ').upper()
	while(booster_name != 'q'):
		dmwiki_link = get_dmwiki_booster_url(booster_name)
		if dmwiki_link:
			dmwiki_dict_list = get_dmwiki_dict_list(dmwiki_link)
			fa_booster_url = get_fullahead_booster_url(booster_name)

			if fa_booster_url:
				fullahead_dict_list = get_fullahead_dict_list(fa_booster_url, booster_name)
				data_list = load_data(dmwiki_dict_list, fullahead_dict_list, booster_name)
				save_data(booster_name, data_list)
				make_directory(booster_name)
				download_images(fullahead_dict_list, booster_name)
				write_error_files(booster_name)
			else:
				print('Booster not found on Fullahead')
				print('Ending program...')
				print()
			break
		else:
			print(booster_name + " cannot be found.")
			print('Returning to booster pack input..')
			print()
			booster_name = input('Enter booster pack name (eg. dmrp-10) or press q to quit: ').upper()


if __name__ == '__main__':
	main()
