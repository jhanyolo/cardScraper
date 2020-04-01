import duelMasters.DMscraper as dm
import battleSpirits.BSscraper as bs
import ZX.ZXscraper as zx
import priceUpdater.priceUpdater as pu
import sys

def mainMenu() -> None:
    print('=' * 30)
    print('Cardboard Collectible System')
    print('=' * 30)

    while True:
        print("- Scrapers\n"
        "1. Duel Masters\n"
        "2. Battle Spirits\n"
        "3. ZX\n\n"
        "- General\n"
        "4. Update prices\n")

        userInput = input('Select option (or press q to quit): ')

        if userInput in ['1', '2', '3', '4', 'q']:
            print()
            return userInput
        else:
            print('Invalid input, please enter again\n')


def main():
    userInput = mainMenu()

    if userInput == '1':
        dm.main()
    elif userInput == '2':
        bs.main()
    elif userInput == '3':
        zx.main()
    elif userInput == '4':
        pu.main()
    else:
        print('Exiting system...')
        sys.exit(1)


if __name__ == '__main__':
    main()