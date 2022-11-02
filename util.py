import os
import datetime
import scholarly
from tqdm import tqdm
import multiprocessing
from termcolor import colored


##############
# UTILITY FXNS
##############

def collect_authors_from_lists(author_lists):
    """ Load from autor list files into a single list of author names """
    author_list = []
    for a in author_lists:
        assert os.path.isfile(a), "The given author list file '{}' is not a file!".format(a)
        with open(a, 'rt') as f:
            # (a) author name lists are expected to contain single full names per line
            # (b) the "#" character initiates comment sections in a line. only keep data until the first #
            # (c) discard empty line entries
            author_list.extend([c.strip() for c in [b.split('#')[0] for b in f.read().split('\n')] if len(c) > 0])
    return tuple(author_list)


def fetch_single_author_info(a):
        # fetch basic info of single author name or id
        a = a.strip() #clean dangling whitespaces.
        tqdm.write('Collecting info for "{}"'.format(a))

        info = []
        if len([seg for seg in a.split() if len(seg) > 0]) == 1:
            # attempt resolution after unique, whitespaceless id first
            try:
                info = scholarly.scholarly.search_author_id(a)
            except:
                # capturing exception in case an invalid author id has been passed
                pass
            if info: info = [info]

        if not info:
            # resolution of id not attempted or succesfull.
            # trying for author resolution by name
            info = list(scholarly.scholarly.search_author(a))

        if len(info) == 0:
            # no match. return None.
            tqdm.write(colored('ERROR! No author info for "{}"'.format(a), 'red'))
            return None

        elif len(info) > 1:
            # warning: multiple matches
            tqdm.write(colored('WARNING! Multiple ({}) entries for "{}" discovered:\n{}\nPlease specify author further! Returning first encountered entry for now.'.format(
                        len(info),
                        a,
                        '\n'.join(['({}) "{}@{}" (id:{})'.format(i, ii['name'],ii['affiliation'],ii['scholar_id']) for i, ii in enumerate(info)])
                        ),
                        'yellow')
                        )
            info = info[0]

        else:
            # all is fine.
            info = info[0]

        # add additional author info.
        info = scholarly.scholarly.fill(info, sections=['counts', 'indices']) #, 'publications'])
        # manually add default author icon if no author url is given in profile
        if not 'url_picture' in info:
            info['url_picture'] = 'https://scholar.google.com/citations?view_op=medium_photo&user={}'.format(info['scholar_id'])
        return info


def fetch_author_infos(authors, asynchronously=False):
    if asynchronously:
        # create twice as many workers as CPUs, as the created load per job will be minimal.
        # most of the time is spent waiting for responses from google scholar anyway.
        with multiprocessing.Pool(multiprocessing.cpu_count()*2) as workerpool:
            info = [i for i in tqdm(workerpool.imap(fetch_single_author_info, authors), unit=' entries', postfix='collecting author data (async)', total=len(authors))]
    else:
        info =[ fetch_single_author_info(a) for a in tqdm(authors, unit=' entries', postfix='collecting author data')]

    return [i for i in info if i] # return entries which are not None


def author_record_line_column_heads():
    return 'datestring citations hindex i10index'

def format_author_record_line(datestring, citedby, hindex='none', i10index='none'):
    return'{} {} {} {}'.format(datestring, citedby, hindex, i10index)


def create_extend_author_records(author_infos, output_directory):
    # (1) make sure output dir and /authors subdir exists.
    # (2) create/append to a file /authors/author-id which contains all the things.
    # (2.1) first line of file is a header (TODO which may be updated later automatically)
    # (2.2) then all info.
    today = datetime.datetime.today()
    datestring = '{}-{}-{}'.format(str(today.year).zfill(4), str(today.month).zfill(2), str(today.day).zfill(2))
    author_folder = '{}/authors'.format(output_directory)

    if not os.path.isdir(author_folder):
        tqdm.write('Creating author output folder {}'.format(author_folder))
        os.makedirs(author_folder)

    for a in author_infos:
        author_id = a['scholar_id']
        author_file = '{}/{}.txt'.format(author_folder, author_id)
        tqdm.write('Writing citation info for "{}" to "{}"'.format(a['name'], author_file))

        preamble = '' # optional preamble in case no preexisting file exists yet. this will contain sort-of static header info
        if not os.path.isfile(author_file):
            # prepare header info and past year(s) cites
            # header first. here also, '#' works as a comment flag
            preamble += '# {}, {}\n'.format(a['name'], a['affiliation'])
            preamble += '# {}\n'.format(author_record_line_column_heads())
            citedby = 0
            for year in sorted(a['cites_per_year'].keys()):
                if year < today.year:
                    citedby += a['cites_per_year'][year]
                    # set "past years" citation date to the last day of the year.
                    preamble += '{}\n'.format(format_author_record_line('{}-{}-{}'.format(year, 12, 31), citedby=citedby))

        # write the update with the (updated) preamble
        with open(author_file, 'at') as f:
            if not 'citedby' in a: a['citedby'] = 0 # set citedby-field of yet uncited author
            f.write('{}{}\n'.format(preamble, format_author_record_line(datestring, a['citedby'], a['hindex'], a['i10index'])))




def check_if_data_available_for(authors, directory):
    # checks if data (files) are already available for the selected authors by
    # 1) first checking if a file name exists (ie if there is a google scholar ID match)
    # 2) and double-checks if necessary by asking scholarly.
    # returns (and replaces) all author IDs as google scholar ids

    invalids = [] # collect entries with no data available.

    # convert authors to list to allow for manipulation
    authors = list(authors)
    for i in range(len(authors)):
        a = authors[i]

        # 1) check for filename matches
        path = os.path.join(directory, a+'.txt')
        if os.path.isfile(os.path.join(path)):
            continue

        # 2) no match. consulting scholarly. if success replace entry with scholar id
        # TODO update to support asynchronous fetching. export into separate check-and-replace loop. for now, keep it.
        scholar_info = fetch_single_author_info(a)
        if scholar_info:
            a = scholar_info['scholar_id']
            authors[i] = a

            path = os.path.join(directory, a+'.txt')
            if os.path.isfile(os.path.join(path)):
                continue

        # 3) still no match shoot warning and collect author for removal
        tqdm.write(colored('WARNING! No recorded author data available for {}. Removing from plotting selection.'.format(a), 'yellow'))
        invalids.append(a)

    # clean up author list of invalid entries before returning
    # TODO make selection unique by temporarily casting to set?
    return tuple([a for a in authors if a not in invalids])