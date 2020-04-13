import csv
import urllib
import requests
import os.path
import time
from bs4 import BeautifulSoup, SoupStrainer
from typing import Union

from general.constants import *

dm_error_list = []
bs_error_list = []
zx_error_list = []
price_difference_list = []


# add User-agent to urlib headers to bypass bot detection
def add_headers_to_urllib() -> None:
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)')]
    urllib.request.install_opener(opener)


# extract handle from csv and populate handle list
# extract only duelMasters/battleSpirit singles and rank S/A
def load_data(filepath: str) -> Union[list, list, list]:
    dm_data_list = []
    bs_data_list = []
    zx_data_list = []
    try:
        with open(filepath, encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # not a sealed product and rank is 'A' or 'S'
                if 'Sealed Products' not in row['Tags'] and check_card_rank(row):
                    if 'duel masters' in row['Tags'].lower():
                        dm_data_list.append(dict(row))
                    elif 'battle spirits' in row['Tags'].lower():
                        bs_data_list.append(dict(row))
                    elif 'zx' in row['Tags'].lower():
                        zx_data_list.append(dict(row))
        return dm_data_list, bs_data_list, zx_data_list
    except FileNotFoundError:
            print('File not found! Please try again.')
            print()

    print('Products from csv loaded!')
    print()


# check if card has card rank 's' or 'a'
def check_card_rank(row):
    card_rank = row['Handle'][-1].lower()
    return card_rank == 'a' or card_rank == 's'


# FOR DUEL MASTERS
# get price from fullahead using product handle (IN JAP YEN)
def get_fullahead_dm_price(handle_name: str) -> Union[int, bool]:
    # search fullahead
    try:
        handle_name = handle_name[:-1]  # remove trailing card rank
        htmlLink = 'https://fullahead-dm.com/?mode=srh&cid=&keyword=' + handle_name
        result = requests.get(htmlLink, timeout=5)

        # parse search page using strainer and soup
        strainer = SoupStrainer('div', class_='indexItemBox')
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
        items_div = soup.find('div', class_='indexItemBox')

        items_list = items_div.find_all('div')

        # the handle name should only return 1 unique product
        # return False if >1 product is returned in searched product
        if len(items_list) == 1:
            pricejpy_fullahead_text = items_list[0].find('span', class_='itemPrice').find('strong').get_text()
            card_name = items_list[0].find('span', class_='itenName').get_text()
            price = convert_fullahead_price(pricejpy_fullahead_text, card_name, handle_name)
            return price
        else:
            return False
    except Exception as e:
        print(e)
        return False


# reformat fullahead price text to get numerical value and return SGD price
# card that are < 1 SGD are priced either by standard rarity price or FA price (whichever is higher)
def convert_fullahead_price(pricejpy_fullahead_text: str, card_name: str, handle_name: str) -> int:
    # get price by converting JPY to SGD
    price = pricejpy_fullahead_text.split('円')[0]
    if ',' in price:
        price = price.replace(',', '')
    price = int(price)

    # format price based on rarity if price is < 1 SGD
    if price < CONST_EXCHANGE_RATE:
        price = round(price / CONST_EXCHANGE_RATE, 1)
        rarity_c_or_u = get_rarity_of_common_or_uncommon(card_name, handle_name)
        if rarity_c_or_u:
            if rarity_c_or_u == 'C':
                price = max(price, 0.3)
            elif rarity_c_or_u == 'U':
                price = max(price, 0.5)
        else:
            price = 1
    else:
        price = round(price / CONST_EXCHANGE_RATE)

    return price


# return rarity if common or uncommon, else return false
def get_rarity_of_common_or_uncommon(card_name: str, handle_name: str) -> Union[str, bool]:
    # get booster name to split it from card_name
    booster_name = '-'.join(handle_name.split('-')[:2]).upper()

    # truncate dmbd to bd due to FA naming conventions
    if booster_name[:4] == 'DMBD':
        booster_name = booster_name[2:]
    card_name_split_list = card_name.upper().split(booster_name)

    if len(card_name_split_list) < 2:
        return False

    rarity = card_name_split_list[1]
    rarity = rarity.split('/', 3)[2].upper()

    if rarity in ['C', 'U']:
        return rarity
    else:
        return False


# FOR BATTLE SPIRITS
# get JPY price from bigweb using product handle and convert to SGD
def get_bigweb_bs_price(handle_name: str) -> Union[int, bool]:
    # search bigweb
    try:
        handle_name = handle_name[:-1]  # remove trailing card rank
        htmlLink = 'http://www.bigweb.co.jp/ver2/battlespirits_index.php?search=yes&type_id=142&action=search&shape=1&seriesselect=&tyselect=&colourselect=&langselect=&condiselect=&selecttext={}&search1=+シ+ン+グ+ル+検+索+#a3054049'.format(handle_name)
        result = requests.get(htmlLink, timeout=5)

        # parse search page using strainer and soup
        strainer = SoupStrainer('div', class_=['watermat abc', 'watermat abcd'])
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)
        product_list = soup.find_all('div', attrs={'class': ['watermat abc', 'watermat abcd']})

        price = False
        # return price if card can be found
        if len(product_list) == 1:
            price = product_list[0].find('span', class_={'yendtr'}).get_text()
            price = price.split('円')[0]
        else:
            for product in product_list:
                card_id = product.find('div', id='rightbottom').get_text().split()[-1]
                if card_id.upper() == handle_name.upper():
                    price = product.find('span', class_={'yendtr'}).get_text()
                    price = price.split('円')[0]

        # convert price from JPY to SGD, else return False
        if price:
            price = int(price)
            if price < CONST_EXCHANGE_RATE:
                price = round(price / CONST_EXCHANGE_RATE, 1)
            else:
                price = round(price / CONST_EXCHANGE_RATE)
        return price
    except Exception as e:
        print(e)
        return False


# FOR ZX
# get JPY price from Yuyu-tei using product handle and convert to SGD
def get_yyt_zx_price(handle_name: str) -> Union[int, bool]:
    try:
                # remove trailing card rank and split into 'ver' and 'cid'
        handle_name_split = handle_name[:-1].split('-', 1)
        ver = handle_name_split[0]
        cid = handle_name_split[1]

        htmlLink = f"https://yuyu-tei.jp/game_zx/carddetail/cardpreview.php?VER={ver}&CID={cid}&MODE=sell"
        result = requests.get(htmlLink, timeout=5)
        time.sleep(1)

        # parse search page using strainer and soup
        strainer = SoupStrainer('div', id='main')
        soup = BeautifulSoup(result.content, 'lxml', parse_only=strainer)

        # get jap_price
        jap_price = soup.find('p', class_='price').get_text().strip()
        yen_counter = jap_price.count('円')

        # cards that contains 2 '円' is on sale (has original price & discounted price)
        if yen_counter == 2:
            jap_price = jap_price.split('円')[0]

        jap_price = jap_price.replace('円', '')
        rarity = soup.find('td', colspan=3).get_text().strip().split(' ', 1)[0].lower()
        price = convert_yyt_jpy_to_sgd(jap_price, rarity)
        return price
    except Exception as e:
        print(e)
        return False


# FOR ZX: convert price from JPY to SGD based on rarity 
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

    return sgd_price


def save_updated_csvfile(dm_data_list: list, bs_data_list: list, zx_data_list: list) -> None:
    print('Creating new csvfile...')
    
    updated_filepath = os.path.expanduser("updated.csv")
    with open(updated_filepath, 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for item in dm_data_list:
            writer.writerow(item)
        for item in bs_data_list:
            writer.writerow(item)
        for item in zx_data_list:
            writer.writerow(item)
    print()
    print('Updated CSV file saved!')


def get_user_filepath_input() -> Union[str, bool]:
    userinput = input('Enter csv file (filename.csv) to be updated (q to quit): ')
    filepath = os.path.expanduser(f"{userinput}.csv")
    while not os.path.isfile(filepath):
        if userinput.lower() == 'q':
            return False
        print('File entered does not exist. Please try again')
        print()
        userinput = input('Enter csv file (filename.csv) to be updated (q to quit): ')
        filepath = os.path.expanduser(f"{userinput}.csv")
    print()
    return filepath


def write_error_text(error_list: list, text_file_name: str) -> None:
    if error_list:
        tcg_name = text_file_name.split('_',1)[0].upper()
        print(f'Updating of {tcg_name} cards is incomplete, creating error txt file...')
        filepath = os.path.expanduser(f"{text_file_name}.txt")
        with open(filepath, 'w', encoding='utf-8') as file:
            for i in error_list:
                file.write(i + '\n')
            print(text_file_name + ' created!')


def write_price_diff_csv(price_difference_list: list, csv_file_name: str) -> None:
    if price_difference_list:
        fieldnames = ['Handle', 'Title', 'Original Price', 'Updated Price']

        print('Generate CSV file for huge price disparities...')
        filepath = os.path.expanduser(f"{csv_file_name}.csv")
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for i in price_difference_list:
                writer.writerow(i)

            print(csv_file_name + ' created!')
            print()    


def write_error_files() -> None:
    write_error_text(dm_error_list, 'DM_updateErrors')
    write_error_text(bs_error_list, 'BS_updateErrors')
    write_error_text(zx_error_list, 'ZX_updateErrors')
    write_price_diff_csv(price_difference_list, 'price_difference_list')


def update_prices(data_list: list, tcg_name: int, error_list: list) -> None:
    # update price for loaded cards in data_list
    if data_list:
        loaded_counter = 0
        unloaded_counter = 0
        total = len(data_list)
        print(f'Retrieving {tcg_name.upper()} price...')
        for d in data_list:
            # update price in bs data list and add cards that return > 1 or < 1 card
            # in product search to error_list
            if tcg_name.lower() == 'dm':
                price = get_fullahead_dm_price(d['Handle'])
            elif tcg_name.lower() == 'bs':
                price = get_bigweb_bs_price(d['Handle'])
            elif tcg_name.lower() == 'zx':
                price = get_yyt_zx_price(d['Handle'])
            else:
                print("Exiting system: Error in determining type of TCG")
                sys.exit(1)

            if price:
                # add to list if price difference too large
                if abs(float(price) - float(d['Variant Price'])) >= CONST_PRICE_DIFFERENCE:
                    card = {}
                    card['Handle'] = d['Handle']
                    card['Title'] = d['Title']
                    card['Original Price'] = d['Variant Price']
                    card['Updated Price'] = price
                    price_difference_list.append(card)
                d['Variant Price'] = price
                loaded_counter += 1
            else:
                error_list.append(d['Handle'])
                unloaded_counter += 1
            print('Retrieving: {0}/{1} (Cards not loaded: {2})'.format(loaded_counter, total, unloaded_counter), end='\r')
        print('\n')


def main():
    print("=" * 15)
    print("Price Updater")
    print("=" * 15)
    filepath = get_user_filepath_input()
    if filepath:
        add_headers_to_urllib()
        dm_data_list, bs_data_list, zx_data_list = load_data(filepath)

        # update prices for all TCG
        update_prices(dm_data_list, 'dm' , dm_error_list)
        update_prices(bs_data_list, 'bs' , bs_error_list)
        update_prices(zx_data_list, 'zx' , zx_error_list)

        save_updated_csvfile(dm_data_list, bs_data_list, zx_data_list)
        write_error_files()
    else:
        print('Exiting system...')


if __name__ == '__main__':
    start_time = time.time()
    main()
    elapsed_time = (time.time() - start_time)
    minutes = elapsed_time // 60
    seconds = elapsed_time - minutes * 60
    print('Time Elapsed: {0} minute(s) {1:.2f} seconds'.format(minutes, seconds))
