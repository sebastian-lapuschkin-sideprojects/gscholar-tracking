import io
import os
import click
import tctim
import datetime
import requests
import scholarly
import numpy as np
from PIL import Image
from tqdm import tqdm
import multiprocessing
from termcolor import colored
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta



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
            author_list.extend([c for c in [b.split('#')[0] for b in f.read().split('\n')] if len(c) > 0])
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

        # TODO: add 'publications' once I figured out what to do with that.
        # NOTE: 'publication' info takes (by far) the most time to requests
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
    # (1.1) TODO:  later add /publications subdir
    # (2) create/append to a file /authors/author-id which contains all the things.
    # (2.1) first line of file is a header (which may be updated later)
    # (2.2) then all info.
    # TODO maybe add read/update fxns
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



def load_and_plot(authors, data_dir, plot_show, plot_file):
    # collect data first
    data = {}
    for a in authors:
        a = a.strip()
        author_file = '{}/authors/{}.txt'.format(data_dir,a)
        if author_file:
            with open(author_file) as f:
                lines = f.read().replace('#','').strip().split('\n')
                name, affiliation = lines[0].split(',',1)
                date = []; citations = []; h_index = []; i10_index = []
                for line in lines[2::]:
                    d,c,h,i = line.split()
                    date.append(d)
                    citations.append(int(c))
                    h_index.append(0 if h == 'none' else int(h))
                    i10_index.append(0 if i == 'none' else int(i))

                data[name] = {'affiliation': affiliation,
                            'scholar_id': a,
                            'date'    :  np.array([datetime.datetime.strptime(di, '%Y-%m-%d').timestamp() for di in date]),
                            'date_str':  np.array(date),
                            'citations': np.array(citations),
                            'h_index':   np.array(h_index),
                            'i10_index': np.array(i10_index)
                            }

    # draw plots (rudimentary. TODO: upgrade! see ideas in @click at main)
    # TODO preprocess parameters and data according to plotting parameters
    t_min = np.inf ; t_max = 0
    for name in data:
        #track min and max time values
        t_min = min(data[name]['date'].min(), t_min)
        t_max = max(data[name]['date'].max(), t_max)

        #some basic plotting
        plt.plot(   data[name]['date'], # - data[name]['date'].min(), #right part: "relative time" meaning
                    data[name]['citations'], #default setting
                    marker="s", # TODO: make optional
                    #drawstyle='steps-post',
                    label='{} ({})'.format(name, data[name]['scholar_id']))

    #decoration
    # first fill list of x-ticks with days of months.
    t_month = datetime.datetime.fromtimestamp(t_min)
    t_month = t_month.replace(day=1).replace(month=t_month.month-t_month.month%3) #start with first day of respective quarter
    x_ticks = []
    while t_month.timestamp() <= t_max:
        x_ticks.append(t_month.timestamp())
        t_month += relativedelta(months=3)

    plt.xticks(x_ticks, [datetime.datetime.fromtimestamp(t).strftime('%Y-%m') for t in x_ticks], rotation=90, ha='center')
    plt.ylabel('citations (default)')
    plt.xlabel('time') # adapt in relative variant.
    plt.legend()


    if plot_file:
        plt.savefig(plot_file, dpi=300)

    if plot_show:
        plt.show()



##############
# ENTRY POINT
##############

@click.command()
@click.option('--authors'           , '-a'  , multiple=True         , help="The name or google scholar id of the authors to track on google scholar. Multiple uses possible.")
@click.option('--author_list'       , '-al' , multiple=True         , help="Should point to a file of newline-character-separated author names or ids. Multiple uses possible")
@click.option('--output_directory'  , '-o'  , default='./output'    , help="Output directory of the stats to collect. A file will be created or appended to, named after the authors' google scholar ids.")
@click.option('--dry_run'           , '-d'  , is_flag=True          , help="Set this flag to only collect data without writing. Prints the collected data to the terminal instead. Author search by name also prints the profile picture to console.")
@click.option('--fetch_async'       , '-fa' , is_flag=True          , help="Set this flag to fetch author data asynchronously from the web. Default behaviour is sequential processing.")
@click.option('--commit'            , '-c'  , is_flag=True          , help="Set this flag to auto-add and commit any change in the given output directory to your CURRENT BRANCH and local git.")
@click.option('--keep_log'          , '-k'  , is_flag=True          , help="Set this flag to keep the scholar.log and geckodriver.log created by scholarly")
@click.option('--plot'              , '-p'  , is_flag=True          , help="Set this flag to draw plots for the already collected data for authors as specified via -a or -al, and saved in <output_directory>. Collection of new data is then skipped. This is only compatible with author IDs!")
@click.option('--plot_show'         , '-ps' , is_flag=True          , help="Only relevant if --plot has been set. Shows the plotted data.")
@click.option('--plot_file'         , '-pf' , default=None          , help="Only relevant if --plot has been set. Output path of the figure to draw.")
#TODO plotting parameters:
# --plot_delta (plot change in citations/etc instead of total citations/etc.)
# --plot_relative_time (plot data wrt to relative "author carreer time". Changes xtick meaning)
# --plot_time_min (plot from a min absolute/relative time on (make it months?))
# --plot_time_max (plot until a max absolute/relative time on (make it months?))
# --plot_data (default:citations. options: i10_index, h_index)
# --plot_cmap (default: no idea. pick something suitable.)
# --plot_size (sets figsize for matplotlib)
# --plot_marker optional marker style.
def main(authors, author_list, output_directory, dry_run, fetch_async, commit, keep_log, plot, plot_show, plot_file):
    """
        This script collects author information on google scholar and writes the respective
        current reference count to a dated list.
        This allows for a more fine-grained tracking of citations compared to the yearly/current
        overview provided by google scholar itself.
    """

    # announce current time
    tqdm.write(colored('Process starting at {}'.format(datetime.datetime.now()),'green'))

    # collect authors and request author information from google scholar.
    authors += collect_authors_from_lists(author_list)
    if plot:
        load_and_plot(authors=authors,
                      data_dir=output_directory,
                      plot_show=plot_show,
                      plot_file=plot_file)
        exit()

    author_infos = fetch_author_infos(authors, asynchronously=fetch_async)

    # clean up
    if not keep_log:
        try:
            os.remove('scholar.log')
            os.remove('geckodriver.log')
        except:
            pass


    if dry_run:
        #abort after data collection
        tqdm.write(colored('Flag "--dry_run" has been set. Printing collected data and terminating after data collection.', 'yellow'))
        for a in author_infos:
            try:
                img = Image.open(io.BytesIO(requests.get(a['url_picture']).content))
                img.thumbnail((64,64))  # smallify
                tqdm.write(tctim.tctim(np.array(img)))
            except:
                #fail silently, if you must.
                pass
            tqdm.write(str(a) + '\n'*2)
        exit()

    # create or extend author records
    create_extend_author_records(author_infos, output_directory)

    if commit:
        tqdm.write(colored('Flag "--commit" as been set. Auto-committing data updates in "{}" .'.format(output_directory), 'yellow'))
        os.system('git add {}'.format(output_directory))
        os.system('git commit -m "auto-commit of data at {}"'.format(datetime.datetime.now()))


# TODO: plotting/graphing
# TODO: paper info handling
if __name__ == '__main__':
    main()