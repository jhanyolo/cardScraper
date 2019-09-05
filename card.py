import urllib
import csv
import os.path
from bs4 import BeautifulSoup, SoupStrainer
import requests

CONST_NO_RARITY = 'nr'
CONST_ULTRA_GOLDEN = 'ug'
CONST_CARD_RANK = 'a'
CONST_SECRET = 's'
CONST_FULLAHEAD_SECRET = 'ss'
image_error_list = []
data_list = []		# stores data to write to csv file
fieldnames = ['Handle', 'Title', 'Body (HTML)', 'Vendor', 'Type', 'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name', 'Option2 Value', 'Option3 Name', 'Option3 Value', 'Variant SKU', 'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price', 'Variant Compare At Price', 'Variant Requires Shipping', 'Variant Taxable', 'Variant Barcode', 'Image Src', 'Image Position', 'Image Alt Text', 'Gift Card', 'SEO Title', 'SEO Description', 'Google Shopping / Google Product Category', 'Google Shopping / Gender', 'Google Shopping / Age Group', 'Google Shopping / MPN', 'Google Shopping / AdWords Grouping', 'Google Shopping / AdWords Labels', 'Google Shopping / Condition', 'Google Shopping / Custom Product', 'Google Shopping / Custom Label 0', 'Google Shopping / Custom Label 1', 'Google Shopping / Custom Label 2', 'Google Shopping / Custom Label 3', 'Google Shopping / Custom Label 4', 'Variant Image', 'Variant Weight Unit', 'Variant Tax Code', 'Cost per item']


# return booster url based on user input
def get_booster_url(booster_name):
	result = requests.get('https://duelmasters.fandom.com/wiki/Duel_Masters_Wiki', timeout=5)
	strainer = SoupStrainer('div', class_='lightbox-caption')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	booster_list = soup.find_all('a')

	for i in booster_list:
		if booster_name == i['title'][0:len(booster_name)]:
			return 'https://duelmasters.fandom.com' + i['href']

	return False


# get card code
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
		dmwiki_card = {'code': '', 'card_link': ''}

		# replace unicode nbsp(\xa0) with space, and split to get card code
		dmwiki_card['code'] = i.getText().replace(u'\xa0', u' ').split(' ')[0]
		dmwiki_card['code'] = dmwiki_card['code'].lower()

		dmwiki_card['card_link'] = 'https://duelmasters.fandom.com' + i.find('a')['href']
		dmwiki_dict_list.append(dmwiki_card)

	return dmwiki_dict_list


# retrieve card code, jap_name, imagelink
def get_fullahead_dict_list(booster_name):
	# get total number of pages
	counter = 1
	htmllink = 'https://fullahead-dm.com/?mode=srh&cid=&keyword=' + booster_name + '&sort=n&page='
	result = requests.get(htmllink + str(counter), timeout=5)
	strainer = SoupStrainer('span', class_='pagerTxt')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

	total_items = int(soup.find('strong').getText()[1:-1])
	pages = total_items // 101 + 1
	fullahead_dict_list = []

	# load all cards returned from the search
	while counter != pages + 1:
		if counter != 1:
			result = requests.get(htmllink + str(counter), timeout=5)

		strainer = SoupStrainer('div', class_='indexItemBox')
		soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
		card_list = soup.find('div', class_='indexItemBox').find_all('div')

		# get necessary card info in fullahead_dict and add to list
		for card_div in card_list:
			card_title = card_div.find('span', class_='itenName').getText()

			# get fullahead info of non-damaged cards
			if 'キズ格安' not in card_title:
				fullahead_dict = get_fullahead_dict(card_title, booster_name, card_div)
				fullahead_dict_list.append(fullahead_dict)

		counter += 1

	return fullahead_dict_list


def get_fullahead_dict(card_title, booster_name, card_div):
	fullahead_dict = {	'code': '',
								'jap_name': '',
								'image': '',
								'price': ''}

	# get card code and jap name
	if len(card_title.split(booster_name)) == 1:
		code = card_title.split(booster_name)[0][1:]
	else:
		code = card_title.split(booster_name)[1][1:]

	temp = ''
	for a in range(len(code)):
		if is_english(code[a]) or code[a] == '/' or code[a] == '秘':
			temp += code[a]

			if temp.count('/') == 2:
				break
		else:
			break

	# use temp string to split the fullahead_name and get jap_name
	jap_name = card_title.split(temp)[1]

	if jap_name.count('/') > 0 and is_english(jap_name.split('/')[0]):
		jap_name = jap_name.split('/')[1]

	fullahead_dict['jap_name'] = jap_name

	# continue getting card code
	code = temp[:-1].replace('/', '-')

	# format secret card code
	if '秘' in code:
		code = code.replace('秘', CONST_SECRET, 1)

		if code[-2:] == CONST_FULLAHEAD_SECRET:
			code = code[:-3]

	# format ultra golden card and no rarity
	if code[0].upper() == 'G':
		code += ('-' + CONST_ULTRA_GOLDEN)
	elif code.count('-') == 0:  # no rarity at end of string:
		code += ('-' + CONST_NO_RARITY)

	code = (booster_name + '-' + code).lower()
	fullahead_dict['code'] = code

	# get image
	fullahead_dict['image'] = card_div.find('span', class_='itemImg').find('img')['src']

	# find rarity & get price
	rarity = fullahead_dict['code'].rsplit('-', 1)[1]

	if rarity.upper() == 'C':
		price = 0.3
	elif rarity.upper() == 'U':
		price = 0.5
	elif rarity.upper() == 'R':
		price = 1
	else:
		price = card_div.find('span', class_='itemPrice').find('strong').getText()
		price = price.split('円')[0]

		if ',' in price:
			price = price.replace(',', '')

		price = round(int(price) / 80)

		if price == 0:
			price = 0.3

	fullahead_dict['price'] = price

	return fullahead_dict


# -*- coding: utf-8 -*-
def is_english(s):
	try:
		s.encode(encoding='utf-8').decode('ascii')
	except UnicodeDecodeError:
		return False
	else:
		return True


# get string till delimiter (excluding)
def get_str_till_delimiter(string, delimiter):
	result = ''
	for s in string:
		if s == delimiter:
			break

		result += s

	return result


def compare_wiki_fullahead(dmwiki_card, fullahead_card):
	dmwiki_code = dmwiki_card.split('/')[0]
	fullahead_code = fullahead_card.split('-', 3)[2]

	if dmwiki_code == fullahead_code:
		return True
	else:
		return False


# get card name, bodyhtml and image link
def get_english_name_bodyHTMl(card_link, jap_name):
	# get english name
	result = requests.get(card_link, timeout=5)
	strainer = SoupStrainer('table', class_='wikitable')
	soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
	english_name = soup.find('th').find(text=True)

	body_html = '<p>Title:' + english_name + '[' + jap_name + ']</p><p>Game: Duel Masters</p><p>Condition: Rank A - Mint / near mint condition, no visible damage, bent, or crease but may have few white spots on edges</p>'

	return english_name, body_html


# return product in dictionary form
def get_product_dict(card_handle, english_name, body_html, booster_name, fullahead_price):
	product_dict = {}

	for i in fieldnames:
		product_dict[i] = ''

	product_dict['Handle'] = card_handle
	product_dict['Title'] = get_title(card_handle, english_name)
	product_dict['Body (HTML)'] = body_html
	product_dict['Vendor'] = 'Cardboard Collectible'
	product_dict['Tags'] = card_handle.split('-')[0] + ', ' + booster_name + ', Duel Masters'
	product_dict['Published'] = 'True'
	product_dict['Option1 Name'] = 'Title'
	product_dict['Option1 Value'] = 'Default Title'
	product_dict['Variant Grams'] = 0
	product_dict['Variant Inventory Tracker'] = 'shopify'
	product_dict['Variant Inventory Policy'] = 'deny'
	product_dict['Variant Fulfillment Service'] = 'manual'
	product_dict['Variant Price'] = fullahead_price
	product_dict['Variant Requires Shipping'] = 'TRUE'
	product_dict['Variant Taxable'] = 'FALSE'
	product_dict['Image Position'] = 1
	product_dict['Gift Card'] = 'FALSE'
	product_dict['Variant Weight Unit'] = 'kg'

	return product_dict


def get_title(card_handle, english_name):
	# dmrp-09-m3-mas-m3a
	card_handle_split_list = card_handle.split('-')

	card_title = 'Duel Masters - '

	# add booster name, card serial num and english name
	card_title += card_handle_split_list[0].upper() + card_handle_split_list[1].upper() + ' '
	card_title += card_handle_split_list[2].upper() + '/' + card_handle_split_list[4][:-1].upper() + ' '
	card_title += english_name + ' '

	rarity = card_handle_split_list[3]
	if rarity == 's':
		card_title += '(Secret) [Rank:A]'
	else:
		card_title += '[Rank:A]'

	return card_title


def load_data(dmwiki_dict_list, fullahead_dict_list, booster_name):
	print('Loading products from {0}.'.format(booster_name))
	counter = 0
	total = len(fullahead_dict_list)

	for full in fullahead_dict_list:
		for dmwiki in dmwiki_dict_list:
			if compare_wiki_fullahead(dmwiki['code'], full['code']):
				english_name, bodyhtml = get_english_name_bodyHTMl(dmwiki['card_link'], full['jap_name'])
				card_handle = full['code'] + '-' + dmwiki['code'].split('/')[1] + CONST_CARD_RANK
				price = full['price']

				product_dict = get_product_dict(card_handle, english_name, bodyhtml, booster_name, price)
				data_list.append(product_dict)
				counter += 1
				print('Loading: {0}/{1}'.format(counter, total), end='\r')
				break
	print()


# check if card is secret from fullahead_dict
def is_secret(product_title):
	return 'Secret' in product_title


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


# save data as csv
def save_data(booster_name):
	filepath = booster_name + '.csv'
	with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
		writer.writeheader()

		for i in data_list:
			writer.writerow(i)

		csvfile.close()

	print('CSV file created!')
	print()


def write_image_dl_error_file():
	if len(image_error_list) > 0:
		with open('imageErrors.txt', 'w') as file:
			for i in image_error_list:
				file.write(i + '\n')

			file.close()


def main():
	booster_name = input('Enter booster pack name (eg. dmrp-10) or press q to quit: ').upper()
	while(booster_name != 'q'):
		if get_booster_url(booster_name):
				fullahead_dict_list = get_fullahead_dict_list(booster_name)
				dmwiki_dict_list = get_dmwiki_dict_list(get_booster_url(booster_name))
				load_data(dmwiki_dict_list, fullahead_dict_list, booster_name)
				save_data(booster_name)
				make_directory(booster_name)
				download_images(fullahead_dict_list, booster_name)
				write_image_dl_error_file()
				break
		else:
			print(booster_name + " cannot be found.")
			print('Returning to booster pack input..')
			print()
			booster_name = input('Enter booster pack name (eg. dmrp-10) or press q to quit: ').upper()


if __name__ == '__main__':
	main()
