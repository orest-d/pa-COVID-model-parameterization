import argparse

import networkx


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    return parser.parse_args()


def main(country_iso3):

    pass


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
