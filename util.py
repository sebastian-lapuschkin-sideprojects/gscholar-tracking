import os
import datetime
import scholarly
import numpy as np
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


def load_author_data(author_ids, directory):
    # loads the data of an author as given via author_id (google scholar id), expected to be found in directory,
    # and returns it as a dictionary aligned to the list of authors in author_ids
    # we can already assume that the target file exists, given a previous call to check_if_data_available_for

    author_data = []
    for a in author_ids:
        author_file = '{}/{}.txt'.format(directory, a.strip())
        with open(author_file) as f:
            # read data and prepare some fields for time series
            lines = f.read().replace('#','').strip().split('\n')
            name, affiliation = lines[0].split(',',1)
            date = []
            citations = []
            h_index = []
            i10_index = []

            # now read the actual data.
            for line in lines[2::]:
                d,c,h,i = line.split()
                date.append(d)
                citations.append(int(c))
                h_index.append(0 if h == 'none' else int(h))
                i10_index.append(0 if i == 'none' else int(i))

            # package everything
            author_blob = {
                        'name'          : name,
                        'affiliation'   : affiliation,
                        'scholar_id'    : a,
                        'date'          :  np.array([datetime.datetime.strptime(di, '%Y-%m-%d').timestamp() for di in date]),
                        'date_str'      :  np.array(date),
                        'citations'     :  np.array(citations),
                        'h_index'       :  np.array(h_index),
                        'i10_index'     :  np.array(i10_index)
                        }
            author_data.append(author_blob)

    # return the read data.
    return author_data


def desparsify_time_series_data(author_data, some_filter_options=None):
    # fills in each authors measurement gaps in a day-accurate way over a commonly spanned sequence of time.
    # returns the now densely populated measures for any next steps.

    # initiate some date vals. assume date sequences are in order. figure out relevant time interval.
    min_date, max_date = author_data[0]['date'][[0,-1]]
    for a in author_data[1::]:
        tmp_min, tmp_max = a['date'][[0,-1]]
        min_date = min(min_date, tmp_min)
        max_date = max(max_date, tmp_max)

    # disclaimer: we compare time strings since we are only interested in per-day resolution
    min_date_str = datetime.datetime.fromtimestamp(min_date).strftime('%Y-%m-%d')
    max_date_str = datetime.datetime.fromtimestamp(max_date).strftime('%Y-%m-%d')

    # for each autor, fill in the gaps in single-day increments:
    # date, date_str, citations, h_index, i10_index
    seconds_per_day = 24*60*60 # this is the unit of temporal increments in single-day accuracy
    for a in author_data:
        # 1) fill in author data from the beginning by prepending.
        if min_date_str < a['date_str'][0]:
            date_pre        = np.arange(min_date, a['date'][0], seconds_per_day)
            date_str_pre    = np.array([datetime.datetime.fromtimestamp(d).strftime('%Y-%m-%d') for d in date_pre])
            citations_pre   = np.zeros_like(date_pre, dtype=int)
            h_index_pre     = np.zeros_like(date_pre, dtype=int)
            i10_index_pre   = np.zeros_like(date_pre, dtype=int)

            a['date'] = np.concatenate((date_pre, a['date']), axis=0)
            a['date_str'] = np.concatenate((date_str_pre, a['date_str']), axis=0)
            a['citations'] = np.concatenate((citations_pre, a['citations']), axis=0)
            a['h_index'] = np.concatenate((h_index_pre, a['h_index']), axis=0)
            a['i10_index'] = np.concatenate((i10_index_pre, a['i10_index']), axis=0)


        # 2) fill in the gaps in this author's recordings. by stepping through and collecting/updating missing values
        date_curr       = int(min_date) # this should be the first value of the author's date
        date_curr_str   = datetime.datetime.fromtimestamp(date_curr).strftime('%Y-%m-%d')
        citations_curr  = 0
        h_index_curr    = 0
        i10_index_curr  = 0

        date_filler      = []
        date_str_filler  = []
        citations_filler = []
        h_index_filler   = []
        i10_index_filler = []

        for i in range(a['date'].size):
            # we directly compare (well formatted) date time strings in per-day-resolution to avid issues with summer and winter time.
            d = int(a['date'][i])
            d_str = a['date_str'][i]

            # three cases (1 and 2 could be collapsed to reduce some redundant code...):
            #   2.0) d_str < date_curr_str. should not happen, we have sub-day steps in the recording then. throw a warning, but treat as 1 without advancing date_curr
            if d_str < date_curr_str:
                tqdm.write(colored(str(i) + ' Warning/Error! potential redundant measurement or sub-day time steps discovered!', 'red'))
                tqdm.write(colored(str(i) + ' d < date_curr with d = {} ({}) and date_curr = {} ({})'.format(d, a['date_str'][i], date_curr,  datetime.datetime.fromtimestamp(date_curr) ), 'red'))
                citations_curr = a['citations'][i]
                h_index_curr   = a['h_index'][i]
                i10_index_curr = a['i10_index'][i]

            #   2.1) d == date_curr. all is well. this is the initial case. update curr_values, advance date_curr, continue
            if d_str == date_curr_str:
                citations_curr = a['citations'][i]
                h_index_curr   = a['h_index'][i]
                i10_index_curr = a['i10_index'][i]

                # advance "real" time in prep for next step in measurement space
                date_curr += seconds_per_day
                date_curr_str = datetime.datetime.fromtimestamp(date_curr).strftime('%Y-%m-%d')
                continue #post condition: date_curr is prepared for the next loop


            #   2.2) d > date_curr. we have one or more missing values. advance date_curr until d is reached, filling the fillers. then continue
            while d_str > date_curr_str:
                date_str_filler.append(date_curr_str)
                date_filler.append(datetime.datetime.strptime(date_curr_str, '%Y-%m-%d').timestamp()) # convert from string time stamp to avoid time zone issues with +-1 hours
                citations_filler.append(citations_curr)
                h_index_filler.append(h_index_curr)
                i10_index_filler.append(i10_index_curr)

                # advance time, until we are head-up with measurement time. this is now the present. nothing to do but to read the present into curr. this happens outside the loop
                date_curr += seconds_per_day
                date_curr_str = datetime.datetime.fromtimestamp(date_curr).strftime('%Y-%m-%d')

            # if date_curr_str has progressed up to d_str, we are here. update curr values with real measurements
            citations_curr = a['citations'][i]
            h_index_curr   = a['h_index'][i]
            i10_index_curr = a['i10_index'][i]

            # advance time once more, as a preparation for iterating the measurements.
            date_curr += seconds_per_day
            date_curr_str = datetime.datetime.fromtimestamp(date_curr).strftime('%Y-%m-%d')
            continue #post condition: date_curr is prepared for the next loop


        # conclude by appending fillers to real data, then argsort by author date and permute everything.
        a['date'] = np.concatenate((date_filler, a['date']), axis=0)
        neworder = np.argsort(a['date'])

        a['date'] = a['date'][neworder]
        a['date_str']  = np.concatenate((date_str_filler, a['date_str']), axis=0)[neworder]
        a['citations'] = np.concatenate((citations_filler, a['citations']), axis=0)[neworder]
        a['h_index']   = np.concatenate((h_index_filler, a['h_index']), axis=0)[neworder]
        a['i10_index'] = np.concatenate((i10_index_filler, a['i10_index']), axis=0)[neworder]


        # 3) extend towards the end until max date.
        if max_date_str > a['date_str'][-1]:
            date_post        = np.arange(a['date'][-1], max_date+seconds_per_day+1, seconds_per_day)
            date_str_post    = np.array([datetime.datetime.fromtimestamp(d).strftime('%Y-%m-%d') for d in date_post])
            citations_post   = np.zeros_like(date_post, dtype=int)
            h_index_post     = np.zeros_like(date_post, dtype=int)
            i10_index_post   = np.zeros_like(date_post, dtype=int)

            a['date'] = np.concatenate((a['date'], date_post), axis=0)
            a['date_str'] = np.concatenate((a['date_str'], date_str_post), axis=0)
            a['citations'] = np.concatenate((a['citations'], citations_post), axis=0)
            a['h_index'] = np.concatenate((a['h_index'], h_index_post), axis=0)
            a['i10_index'] = np.concatenate((a['i10_index'], i10_index_post), axis=0)


    # TODO CLEAN OUT TIME-ZOME DEPENDENTLY ADDED REDUNDANT DATES.

    return author_data


def process_values(values, how_to_process):
    def plain(values):
        return values

    def delta_year(values): # assume 1 year = 365 days
        if len(values) < 365:
            return np.zeros_like(values) # the unlikely case of having recording data of less than a year in this case.
        else:
            tmp = values[365::] - values[0:-365:]
            return np.concatenate([np.zeros((365,),dtype=int),tmp], axis=0)

    def delta_month(values): # assume 1 year = 28 days
        if len(values) < 28:
            return np.zeros_like(values) # the unlikely case of having recording data of less than a year in this case.
        else:
            tmp = values[28::] - values[0:-28:]
            return np.concatenate([np.zeros((28,),dtype=int),tmp], axis=0)

    def growth_year(values): # assume 1 year = 365 days. return values in percent
        if len(values) < 365:
            return np.zeros_like(values) # the unlikely case of having recording data of less than a year in this case.
        else:
            tmp = (values[365::] / values[0:-365:]) - 1
            tmp[np.isnan(tmp)] = 0
            return np.concatenate([np.zeros((365,),dtype=int),tmp], axis=0) * 100

    def growth_month(values): # assume 1 year = 28 days. return values in percent
        if len(values) < 28:
            return np.zeros_like(values) # the unlikely case of having recording data of less than a year in this case.
        else:
            tmp = (values[28::] / values[0:-28:]) - 1
            tmp[np.isnan(tmp)] = 0
            return np.concatenate([np.zeros((28,),dtype=int),tmp], axis=0) * 100

    switchmap = {'plain': plain,
                 'delta_year': delta_year,
                 'delta_month':delta_month,
                 'growth_year':growth_year,
                 'growth_month':growth_month}
    return switchmap[how_to_process](values)