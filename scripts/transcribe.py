# -*- coding: utf-8 -*-
"""
This module tries to identify
Hungarian version of NE-s (names, locations)
which are written in Cyrillic script
in the Hungarian Prisoner of War Database.
"""

# kiindulópont: ru2hu.py

import argparse
from collections import defaultdict
import csv
import difflib
import json
from math import log
import re
import sys

from extract_location_parts import extract_location_parts as elp
from ru2hu import Transcriptor


# akarunk-e jelölést az alábbiak szerint
IS_MARK = True            # False if '-p'

# ha jelölni akarjuk, hogy mit találtunk meg a termlistán
AS_STRICT = '/S'          # 1. strict-ként megvan simán

AS_LOOSE = '/L'           # 2. loose-ként megvan

STRICT_FIRST_STEP = False
# akarunk-e difflib guess-t
IS_DIFFLIB = True         # False if '-n' 
DIFFLIB_CUTOFF = 0.7      # set by '-f'
DIFFLIB_N = 5             # set by '-n'
AS_DIFFLIB = '/D'         # 3. difflib-ként megvan
FROM_STRICT = '>>'        # difflib esetén a strict alak jele

AS_FALLBACK = '=T'        # 4. ha nincs más, marad a strict

SAR_MARK = '/R'           # search-and-replace mark, see: preprocess.py

LOGBASE = 500             # base for log freq values

# "extremal" character values from "General Pubctuation" unicode block for CHAR_EQUIVALENT_TABLE
C = "‖‗†‡•‣․‥…‧L‰‱′″‴‵‶‷‸‹›※‼‽‾⁁⁂⁃⁄⁅⁆⁇⁈⁉⁊⁋⁌⁍⁎⁏⁐⁑⁒⁓⁔⁕⁖⁗⁘⁙⁚⁛⁜⁝⁞"
# XXX a többkarakteres izék talán nem kellenek, csak egyenként a karakterek...
# XXX esetleg még lehetne: aáoó; eéöő; j|ly|l; sz|s; uú; c|cz
# XXX talán lower() -rel kellene nyomatni? hogyan? XXX
CHAR_EQUIVALENT_TABLE = {

    'gyö': C[0],
    'gye': C[0],
    'Gyö': C[1],
    'Gye': C[1],

    'já': C[2],
    'ja': C[2],
    'Já': C[3],
    'Ja': C[3],

    'jó': C[4],
    'ju': C[4],
    'Jó': C[5],
    'Ju': C[5],

    'a': C[6],
    'á': C[6],
    'o': C[6],
    'A': C[7],
    'Á': C[7],
    'O': C[7],

    'gy': '<HIDE1>',
    'g': C[8],
    'h': C[8],
    '<HIDE1>': 'gy',
    'Gy': '<HIDE2>',
    'G': C[9],
    'H': C[9],
    '<HIDE2>': 'Gy',

    'j': C[10],
    'ly': C[10],
    'J': C[11],
    'Ly': C[11],

    'sz': '<HIDE3>',
    'zs': C[12],
    'z': C[12],
    '<HIDE3>': 'sz',
    'Sz': '<HIDE4>',
    'Zs': C[13],
    'Z': C[13],
    '<HIDE4>': 'Sz',

    'ny': C[14],
    'n': C[14],
    'Ny': C[15],
    'N': C[15],
}


# XXX németre (egyéb nyelvekre) persze másképp kéne mint magyarra!
def make_chars_equivalent(string):

    for k, v in CHAR_EQUIVALENT_TABLE.items():
        string = string.replace(k, v)

    return string


def build_one(data):
    """Initialize one set of transcriptor tools."""

# 1. előkészítjük a loose/strict Transciptorokat

    # XXX legyen portable...
    loose_filename = 'rules/' + data['loose'] + '.json'
    with open(loose_filename) as loose_config:
        loose_table = json.load(loose_config)
    data['loose_trans'] = Transcriptor(loose_table)

    # XXX legyen portable...
    strict_filename = 'rules/' + data['strict'] + '.json'
    with open(strict_filename) as strict_config:
        strict_table = json.load(strict_config)
    data['strict_trans'] = Transcriptor(strict_table)

# 2. előkészítjük a termlist segédlistát

    # XXX legyen portable...
    termlist_filename = 'data/lists/' + data['termlist'] + '.csv'
    with open(termlist_filename) as termlist:
        terms = [
            item.replace(' ', '_')
            for item
            in termlist.read().splitlines()]
        # set()-tel lassabb volt, pedig "5. pont"! hm..
        terms_equiv = [make_chars_equivalent(term) for term in terms]
        terms_equiv2orig = defaultdict(list)
        for term, term_equiv in zip(terms, terms_equiv):
            terms_equiv2orig[term_equiv].append(term)    

        data['terms'] = terms
        data['terms_equiv'] = terms_equiv
        data['terms_equiv2orig'] = terms_equiv2orig

    # XXX legyen portable...
    data['freqs'] = {} # ti. a 'freqs' opcionális!
    if data['freqlist'] is not None:
        freqlist_filename = 'data/freqlists/' + data['freqlist'] + '.csv'
        with open(freqlist_filename) as freqlist:
            # dict of {elem: logfreq}
            data['freqs'] = {
                # XXX szebben?
                # így a 0 is 0 lesz és a log() miatt az 1 is 0 lesz
                # de ez jó így = a hapaxok "nem léteznek" :)
                item.split('\t')[1]: log(int(item.split('\t')[0]), LOGBASE) # XXX jobban?
                for item
                in freqlist.read().splitlines()}

# cache -- mezőnként!

    data['cache'] = defaultdict(str)

    return data


# XXX all data is in-memory!
# XXX persze lehetne egy osztály ez az izé...
def build_infrastructure(config):
    """Initialize all necessary data structures."""

    with open(config) as config:
        infrastructure = json.load(config)

    # XXX str JSON keys -> int python keys
    infrastructure = {int(k):v for k,v in infrastructure.items()}
    for col, data in infrastructure.items():

        data = build_one(data)

        # a fentit megcsináljuk a beágyazott 'strptn' izékre is
        # nem lehet ezt valahogy sokkal egyszerűbben? XXX
        if 'strptn' in data:
            # XXX str JSON keys -> int python keys -- ne legyen 2x!
            data['strptn'] = {int(k):v for k,v in data['strptn'].items()}
            for col_to_match, col_to_match_dict in data['strptn'].items():
                for strptn, strptn_dict in col_to_match_dict.items():
                    strptn_dict = build_one(strptn_dict)

    return infrastructure


def add_score(matches, trans, freqs):
    """
    Returns matches ordered by a score based on:
     * difflib ratio of match and trans
     * frequency of match
    """

    if len(matches) == 1:
        res = matches[0]

    # megmérjük strict vs match távot,
    # és hozzáírjuk a szavakhoz: Jóska[0.52],
    # és sorbatesszük eszerint! :)
    # + még normalizáljuk is max 1-re vmiért...

    elif len(matches) > 1:

        # lehet szebben? :)
        sorted_matches = sorted((
                (match,
                 # score = difflib_ratio + logfreq
                 difflib.SequenceMatcher(None, trans, match).ratio() +
                 (freqs[match] if match in freqs else 0))
                for match
                in matches),
                key=lambda x: (-x[1], x[0]) # fixed order
            )

        # normalize to max 1 (i.e. normalize by max norm)
        maximum = max(max(x[1] for x in sorted_matches), 1) # should be at least 1
        normalized = [(x[0], x[1]/maximum) for x in sorted_matches]

        res = ';'.join("{}[{:.2f}]".format(i[0], i[1]) for i in normalized)

    return res


def process(infrastructure):
    """Do the thing."""

    reader = csv.reader(sys.stdin, delimiter='\t')
    writer = csv.writer(sys.stdout, delimiter='\t')

    for row in reader:
        transcribed_row = row.copy()
        # kell az eredeti, mert hivatkozunk rá!

        # XXX ha row-ban nincs annyiadik col,
        #     ami viszont infrastructure-ban szerepel -> hibát kapunk!
        for col, data in infrastructure.items():

            # ha üres a mező, akkor passz
            if col >= len(row) or not row[col]:
                continue

# 3. vesszük adott mező adott adatát :)

            actual_data = data
            if 'strptn' in data:
                # most ez csak egy ilyen szabályt kezel!
                # XXX (esetleg valahogy tudna többet kezelni?)
                for col_to_match, col_to_match_dict in data['strptn'].items():
                    for strptn, strptn_dict in col_to_match_dict.items():
                        if row[col_to_match] == strptn:
                            actual_data = strptn_dict
                            break
            # vars()-sal lehet jobban? talán nem.
            loose_trans = actual_data['loose_trans']
            strict_trans = actual_data['strict_trans']
            terms = actual_data['terms']
            terms_equiv = actual_data['terms_equiv']
            terms_equiv2orig = actual_data['terms_equiv2orig']
            freqs = actual_data['freqs']
            cache = actual_data['cache']

            # egyszerre csak 1 szót/elemet dolgozunk fel,
            # szóval nem kell a ciklus
            # (a dolgokat, pl. a helyeket, előre daraboljuk fel)
            one_word = row[col].replace(' ', '_')

            transcribed = ''

            # elnézést kérek az egytagú listán futtatott ciklusért
            # azért van, hogy használhassak continue-t :)
            # XXX hogy lehetne jobban (beágyazott if-ek nélkül)
            for word in [ one_word ]:

# legeslegelőszöris megnézzük, hogy a preprocessing.py feldolgozta-e

                if word.endswith(SAR_MARK):
                    transcribed = word
                    continue

# legelőszöris megnézzük a cache-ben

                if word in cache:
                    transcribed = cache[word]
                    continue

# 4. átírjuk strict (#5) szerint: trans = strict(name)

                trans = strict_trans(word)

# 5. ha így "egy-az-egyben" megvan a listán, akkor visszaadjuk
#    (amennyiben '-s' révén kértük ezt a lépést!)

                if STRICT_FIRST_STEP:
                    if trans in terms:
                        result = trans + AS_STRICT
                        transcribed = result
                        cache[word] = result
                        continue

# 6. átírjuk loose (#5) szerint: regex = loose(name)

                # itt jó a re.escape()!
                # mert a "loose" eredménye pont egy regex
                # a "(см." lezáratlan zárójelét oldja meg
                regex = loose_trans(re.escape(word))

# 7. megkeressük az átírt adatot a listán = illesztjük regex-t list-re

                compiled_regex = re.compile(regex)
                matches = list(filter(compiled_regex.fullmatch, terms))

# 8. ha van találat: visszaadjuk az összes találatot + ratio()!

                if matches:

                    res = add_score(matches, trans, freqs)

                    result = res + AS_LOOSE
                    transcribed = result
                    cache[word] = result
                    continue

# 9. még teszünk egy próbát a difflib-bel, ha engedélyezve van

                if IS_DIFFLIB: # 
                    close_matches = difflib.get_close_matches(
                        make_chars_equivalent(trans),
                        terms_equiv,
                        n=DIFFLIB_N, cutoff=DIFFLIB_CUTOFF)

                    if close_matches:

                        matches = [orig
                                   for close_match in close_matches
                                   for orig in terms_equiv2orig[close_match]]

                        matches = list(set(matches))

                        res = add_score(matches, trans, freqs)

                        result = trans + FROM_STRICT + res + AS_DIFFLIB # Forenc>>Ferenc/D
                        transcribed = result
                        cache[word] = result
                        continue

# 10. egyébként... visszaadjuk trans-t (ami egyértelmű) és kész :)

                result = trans + AS_FALLBACK
                transcribed = result
                cache[word] = result

            transcribed_row[col] = transcribed

        writer.writerow(transcribed_row)


def get_args():
    """Handle commandline arguments."""
    pars = argparse.ArgumentParser(description=__doc__)
    pars.add_argument(
        '-c', '--config',
        required=True,
        help="path to a 'metarules' JSON config file",
    )
    pars.add_argument(
        '-s', '--strict-first-step',
        action='store_true',
        help="add a 'simple strict match' step at the beginning",
    )
    pars.add_argument(
        '-x', '--no-difflib',
        action='store_true',
        help="turn off difflib, no approx search, 7x faster",
    )
    pars.add_argument(
        '-f', '--difflib-cutoff',
        type=float,
        help="cutoff for difflib (default={})".format(DIFFLIB_CUTOFF),
    )
    pars.add_argument(
        '-n', '--difflib-n',
        type=float,
        help="for difflib outputs N predictions (default={})".format(DIFFLIB_N),
    )
    pars.add_argument(
        '-p', '--plain',
        action='store_true',
        help="do not mark words according to how they handled, do not use this switch if you want to use `make eval*`",
    )
    arguments = pars.parse_args()
    return arguments


def main():
    """Main."""

    args = get_args()

    # ez sztem mehet a get_args()-ba, és csak a config jöjjön ki

    global STRICT_FIRST_STEP
    STRICT_FIRST_STEP = args.strict_first_step

    global IS_DIFFLIB
    IS_DIFFLIB = not args.no_difflib

    global DIFFLIB_CUTOFF
    if args.difflib_cutoff: DIFFLIB_CUTOFF = args.difflib_cutoff # set by '-f'

    global DIFFLIB_N
    if args.difflib_n: DIFFLIB_N = args.difflib_n                # set by '-n'

    global IS_MARK
    IS_MARK = not args.plain

    if not IS_MARK:
        global AS_STRICT
        global AS_LOOSE
        global AS_DIFFLIB
        global AS_FALLBACK
        AS_STRICT = ''
        AS_LOOSE = ''
        AS_DIFFLIB = ''
        AS_FALLBACK = ''

    infrastructure = build_infrastructure(args.config)
    process(infrastructure)


if __name__ == '__main__':
    main()
