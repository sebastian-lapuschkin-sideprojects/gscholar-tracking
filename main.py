import scholarly
import multiprocessing
from tqdm import tqdm
from termcolor import colored
import click
import os

##############
# UTILITY FXNS
##############

def collect_authors_from_lists(author_lists):
    """ Load from autor list files into a single list of author names """
    author_list = []
    for a in author_lists:
        assert os.path.isfile(a), "The given author list file '{}' is not a file!".format(a)
        with open(a, 'rt') as f:
            # author name lists are expected to contain single full names per line
            # the "#" character initiates comment sections in a line. only keep data until the first #
            # discard empty line entries
            author_list.extend([c for c in [b.split('#')[0] for b in f.read().split('\n')] if len(c) > 0])
    return tuple(author_list)


def fetch_single_author_info(a):
        # fetch basic info of single author name
        tqdm.write('Collecting info for "{}"'.format(a))
        info = list(scholarly.scholarly.search_author(a))

        if len(info) == 0:
            # no match. return None.
            tqdm.write(colored('ERROR! No author info for "{}"'.format(a), 'red'))
            return None
        elif len(info) > 1:
            # warning: multiple matches
            tqdm.write(colored('WARNING! Multiple ({}) entries for "{}" discovered: {}. Please specify author further! Returning first encountered entry for now.'.format(
                        len(info),
                        a,
                        ', '.join(['"{}@{}"'.format(i.name,i.affiliation) for i in info])
                        ),
                        'yellow')
                        )
            info = info[0]
        else:
            # all is fine.
            info = info[0]

        # extend author info with additional stats and return
        info.fill(sections=['counts', 'indices', 'publications'])
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



##############
# ENTRY POINT
##############

@click.command()
@click.option('--authors'           , '-a'  , multiple=True         , help="The name of the authors to track on google scholar.")
@click.option('--author_list'       , '-al' , multiple=True         , help="Should point to a file of linebreak character separated author names.")
@click.option('--output_directory'  , '-o'  , default='.'           , help="Output directory of the stats to collect. A file will be created or appended to, named after the authors' google scholar ids.")
@click.option('--dry_run'           , '-d'  , is_flag=True          , help="Set this flag to only collect data without writing.")
@click.option('--fetch_async'       , '-fa' , is_flag=True          , help="Set this flag to fetch author data asynchronously from the web. Default behaviour is sequential processing.")
@click.option('--commit'            , '-c'  , is_flag=True          , help="Set this flag to auto-add and commit any change in the given output directory to your local git.")
@click.option('--keep_log'          , '-k'  , is_flag=True          , help="Set this flag to keep the scholar.log created by scholarly")
def main(authors, author_list, output_directory, dry_run, fetch_async, commit, keep_log):
    """
        This script collects author information on google scholar and writes the respective
        current reference count to a dated list.
        This allows for a more fine-grained tracking of citations compared to the yearly/current
        overview provided by google scholar itself.
    """
    authors += collect_authors_from_lists(author_list)
    author_infos = fetch_author_infos(authors, asynchronously=fetch_async)

    # request author info including counts.
    # if target file exists, append current count.
    # if target file does not exist, populate previous time points (years) with year-counts
    #
    # Example code:
    #
    # a = list(scholarly.scholarly.search_author("Sebastian lapuschkin"))[0]
    # a.fill(sections=['counts', 'indices', 'publications'])
    #
    # extend citation tracking to publications?
    # create output_dir/authors for authors
    # and    output_dir/publications for papers (normalize paper file names: no whitespace only ascii no cap.)
    # treat both equally by appending cites and appearances
    # first line contains meta info
    # remaining lines contain date -> value pairs/groups
    #
    # after each run, attempt to remove scholar.log (if not specified otherwise via --keep-logs)
    #
    # later: plotting/graphing



if __name__ == '__main__':
    main()