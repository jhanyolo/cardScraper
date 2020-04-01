from bs4 import BeautifulSoup, SoupStrainer
import requests
import sys
import urllib
from tqdm import tqdm
import os.path
import csv
import time

from general.constants import *

image_error_list= []


# add User-agent to urlib headers to bypass bot detection
def add_headers_to_urllib() -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)')]
    urllib.request.install_opener(opener)


# Display card sets for the latest two sets in 'Z/X Roadmap' section
# returns link to desired cardset in zxtcg.fandom.com
def menu() -> str:
    print('=' * 20)
    print('Z/X CARD SCRAPER')
    print('=' * 20)

    upcoming_sets_dict_list = get_upcoming_sets(2)
    for index, cardSet in enumerate(upcoming_sets_dict_list):
        print(f"{index + 1}: {cardSet['title']}")
    print()

    user_choice = input('Select card set or press q to quit: ').lower()

    while user_choice not in ['1', '2', 'q']:
        user_choice = input('Select option 1 or 2 or press q to quit: ').lower()

    if user_choice == 'q':
        print('Exiting system...')
        sys.exit(1)

    print()
    return upcoming_sets_dict_list[int(user_choice) - 1]['link']


# get title and htmlLink for the latest two sets in 'Z/X Roadmap' section
def get_upcoming_sets(setCount: int) -> dict:
    try:
        result = requests.get('https://zxtcg.fandom.com/wiki/Main_Page', timeout=5)
        strainer = SoupStrainer('div', class_="rcs-container")
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

        # get the latest 2 sets on the calendar
        # latest sets are at the end of the list
        upcomingSets = soup.find_all('div', class_='floatnone')
        upcoming_sets_dict_list = []
        for i in upcomingSets:
            upcomingSetDict = {'title': '',
                               'link': ''}

            upcomingSetDict['title'] = i.find('a')['title']
            upcomingSetDict['link'] = f"https://zxtcg.fandom.com{i.find('a')['href'].strip()}"
            upcoming_sets_dict_list.append(upcomingSetDict)

        return upcoming_sets_dict_list
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)


# get booster prefix to be searched on yuyutei
def get_booster_prefix(htmlLink: str) -> str:
    try:
        result = requests.get(htmlLink, timeout=5)
        strainer = SoupStrainer('aside')
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
        booster_prefix = soup.find_all('div', class_="pi-data-value pi-font")[-1].get_text().lower()
        return booster_prefix
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)


def get_yuyutei_dict_list(booster_prefix: str) -> list:
    try:
        print('Loading information from Yuyu-tei')
        htmlLink = f"https://yuyu-tei.jp/game_zx/sell/sell_price.php?ver={booster_prefix}"
        print(htmlLink)
        result = requests.get(htmlLink, timeout=5)
        strainer = SoupStrainer('ul', class_='card_list')
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

        # get required info for all cards and add to list
        yyt_dict_list = []
        cards_li_list = soup.find_all('li')
        counter=1
        for i in tqdm(cards_li_list):
            yyt_dict = {'handle': '',
                        'code': '',
                        'jap_name': '',
                        'rarity': '',
                        'image_link': '',
                        'price': ''}
            # get unique handle                        
            ver = i.find('input', {'name':'item[ver]'})['value']
            cid = i.find('input', {'name':'item[cid]'})['value']
            yyt_dict['handle'] = f'{ver}-{cid}'

            yyt_dict['code'] = i.find('p', class_='id').get_text().strip().lower()
            yyt_dict['jap_name'] = i.find('p', class_='name').get_text().strip()

            # jap_name too long, need to access the individual card page to get full jap name
            if yyt_dict['jap_name'][-3:] == '...':
                try:
                    htmlLink = f"https://yuyu-tei.jp{i.find('a')['href'].strip()}"
                    result = requests.get(htmlLink, timeout=5)
                    time.sleep(1)
                    strainer = SoupStrainer('p', class_=['image', 'btn'])
                    soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
                    jap_name = soup.find('img')['alt']

                    # initial string contains code + jap name,split to get jap name only
                    jap_name = jap_name.lower().split(yyt_dict['code'])[1]
                    yyt_dict['jap_name'] = jap_name
                except requests.exceptions.RequestException as e:
                    print(e)
                    sys.exit(1)
                except Exception as e:
                    print(e)
                    sys.exit(1)

            yyt_dict['rarity'] = i['class'][1].rsplit('rarity_', 1)[1].lower()
            yyt_dict['image_link'] = i.find('img')['src'].replace('90_126', 'front')
            
            if 'https' not in yyt_dict['image_link'].lower():
                yyt_dict['image_link'] = f"https://yuyu-tei.jp{yyt_dict['image_link']}"

            # extract jap_price (numerical value only)
            jap_price = i.find('p', class_='price').get_text().strip()
            yen_counter = jap_price.count('円')

            if yen_counter == 2:
                # contains 2 '円' as its on sale (has original price & discounted price)
                jap_price = jap_price.split('円')[0]

            jap_price = jap_price.replace('円', '')

            # function converts jpy to sgd, taking rarity into account
            yyt_dict['price'] = convert_yyt_jpy_to_sgd(jap_price, yyt_dict['rarity'])

            yyt_dict_list.append(yyt_dict)

        print()
        return yyt_dict_list
    except requests.exceptions.RequestException as e:
        print("Failed to connect to Yuyutei")
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)


# convert price from JPY to SGD based on rarity
def convert_yyt_jpy_to_sgd(jap_price: str, rarity: str) -> str:
    # round up to 1 decimal if sgd_price < 1 
    sgd_price = int(jap_price)
    if sgd_price < CONST_EXCHANGE_RATE:
        sgd_price = round(sgd_price / CONST_EXCHANGE_RATE, 1)
    else:
        sgd_price = round(sgd_price / CONST_EXCHANGE_RATE)

    # check if prices hit minimum
    if rarity == 'n' and sgd_price < 0.3:
        sgd_price = 0.3
    elif rarity == 'nh' and sgd_price < 1:
        sgd_price = 1
    elif rarity == 'r' and sgd_price < 1:
        sgd_price = 1
    elif rarity == 'rh' and sgd_price < 2:
        sgd_price = 2

    return str(sgd_price)


# get card info in dict format and return a List of all cards
# has to use valid zx wiki link to 'zxtcg.fandom.com'
def get_zx_wiki_dict_list(htmlLink: str) -> list:
    try:
        print('Loading information from zxtcg.fandom.com')
        result = requests.get(htmlLink, timeout=5)
        strainer = SoupStrainer('div', id="mw-content-text")
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

        
        # get required info for all cards and add to list
        zx_wiki_dict_list = []
        card_tr_list = soup.find('table', class_=['wikitable', 'sortable', 'jquery-tablesorter']).find_all('tr')[1:]
        for card in tqdm(card_tr_list):
            card_info_dict = {'code': '',
                              'english_name': ''}

            card_details = card.find_all('a')
            card_info_dict['code'] = card_details[0]['title'].lower()
            card_info_dict['english_name'] = card_details[1].get_text().strip()
            zx_wiki_dict_list.append(card_info_dict)

        print()
        return zx_wiki_dict_list
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)


# combine information from yyt_dict_list & zx_wiki_dict_list
# return a list to be loaded into csv file
def get_product_dict_list(yyt_dict_list: list, zx_wiki_dict_list: list, booster_prefix: str) -> list:
    print('Formatting card information')

    product_dict_list = []
    for yyt_dict in tqdm(yyt_dict_list):
        for zx_wiki_dict in zx_wiki_dict_list:
            if yyt_dict['code'] == zx_wiki_dict['code']:
                product_dict = get_product_dict(yyt_dict, zx_wiki_dict, booster_prefix)
                product_dict_list.append(product_dict)

    return product_dict_list


# combine information of cards that have the same code
def get_product_dict(yyt_dict: dict, zx_wiki_dict: dict, booster_prefix: str) -> dict:
    # initialise product dict with csv field names
    product_dict = {}
    for i in fieldnames:
        product_dict[i] = ''

    # check if card is holo or secret:
    holo_check = CONST_YYT_HOLO in yyt_dict['jap_name']
    secret_check = CONST_YYT_SECRET in yyt_dict['jap_name']
    eframe_check = CONST_YYT_ENJOY_FRAME in yyt_dict['jap_name']

    # hacky check if there's a logic error for holo and secret checks
    if holo_check and secret_check == True:
        print('card has both holo and secret in japanese name (Needs debugging)')

    # format handle based on holo, enjoy frame,secret and normal cards
    title_substr = ''
    if holo_check:
        if eframe_check:
            title_substr = '(Enjoy Frame) '
        else:
            title_substr = '(Holo) '
    elif secret_check:
        title_substr = '(Secret) '

    product_dict['Handle'] = f"{yyt_dict['handle']}{CONST_CARD_RANK}"
    product_dict['Title'] = f"Z/X - {yyt_dict['code']} {zx_wiki_dict['english_name']} {title_substr}[Rank:A]"
    product_dict['Body (HTML)'] = '<p>Title: ' + zx_wiki_dict['english_name'] + ' [' + yyt_dict['jap_name'] + ']</p> <p>Game: Z/X</p> <p>Condition: Rank A - Mint / near mint condition, no visible damage, bent, or crease but may have few white spots on edges</p>'
    product_dict['Vendor'] = 'Cardboard Collectible'

    # get desired tag based on name of the intial letters in booster_prefix
    tag = ''
    for i in booster_prefix:
        if i.isdigit():
            break
        tag += i

    if tag == 'b':
        tag = 'booster'
    elif tag in ['sd', 'c']:
        tag = 'starterDeck'
    elif tag == 'p':
        tag = 'promo'
    else:
        tag = 'extra'

    product_dict['Tags'] = tag + ', ' + booster_prefix + ', zx'
    product_dict['Published'] = 'True'
    product_dict['Option1 Name'] = 'Title'
    product_dict['Option1 Value'] = 'Default Title'
    product_dict['Variant Grams'] = 0
    product_dict['Variant Inventory Tracker'] = 'shopify'
    product_dict['Variant Inventory Policy'] = 'deny'
    product_dict['Variant Fulfillment Service'] = 'manual'
    product_dict['Variant Price'] = yyt_dict['price']
    product_dict['Variant Requires Shipping'] = 'TRUE'
    product_dict['Variant Taxable'] = 'FALSE'
    product_dict['Image Position'] = 1
    product_dict['Gift Card'] = 'FALSE'
    product_dict['Variant Weight Unit'] = 'kg'

    return product_dict


def make_directory(booster_prefix: str) -> None:
    try:
        # Create target Directory
        dirpath = os.path.expanduser(f"~/Desktop/{booster_prefix}")
        os.mkdir(dirpath)
    except FileExistsError:
        print("Directory ", booster_prefix, " already exists")


# save data as csv
def save_data(booster_prefix, product_dict_list):
    filepath = os.path.expanduser(f"~/Desktop/{booster_prefix}.csv")

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i in product_dict_list:
            writer.writerow(i)

        print('CSV file created!')
        print()


def download_images(yyt_dict_list: list, booster_prefix: str) -> None:
    print('Downloading Images...')

    cardpage_counter = 1
    filepath = os.path.expanduser(f"~/Desktop/{booster_prefix}")
    for i in tqdm(yyt_dict_list):
        try:
            if len(str(cardpage_counter)) == 1:
                imgName = '00' + str(cardpage_counter)
            elif len(str(cardpage_counter)) == 2:
                imgName = '0' + str(cardpage_counter)
            else:
                imgName = cardpage_counter

            img_filepath = os.path.expanduser(f"~/Desktop/{booster_prefix}/{imgName}.jpg")
            urllib.request.urlretrieve(i['image_link'], img_filepath)
            cardpage_counter += 1
        # stores the card code of cards that were not downloaded in image_error_list
        except ValueError:
            image_error_list.append(i['code'])


def main():
    add_headers_to_urllib()
    zx_wiki_html_link = menu()
    booster_prefix = get_booster_prefix(zx_wiki_html_link)

    yyt_dict_list = get_yuyutei_dict_list(booster_prefix)
    if yyt_dict_list:
        # format and save the data derived from zx-fandom & yuyutei
        zx_wiki_dict_list = get_zx_wiki_dict_list(zx_wiki_html_link)
        product_dict_list = get_product_dict_list(yyt_dict_list, zx_wiki_dict_list, booster_prefix)
        save_data(booster_prefix, product_dict_list)

        # download card images
        make_directory(booster_prefix)
        download_images(yyt_dict_list, booster_prefix)
    else:
        print('Error retrieving card set from Yuyutei! (Card set may not be on Yuyutei yet)')
        sys.exit(1)


if __name__ == '__main__':
    main()
