import io
import os
import click
import tctim
import datetime
import requests
import numpy as np
from PIL import Image
from tqdm import tqdm
from termcolor import colored
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

from util import create_extend_author_records
from util import collect_authors_from_lists
from util import fetch_author_infos


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
def main(authors, author_list, output_directory, dry_run, fetch_async, commit, keep_log, plot, plot_show, plot_file):
    """
        This script collects author information on google scholar and writes the respective
        current reference count to a dated list.
        This allows for a more fine-grained tracking of citations compared to the yearly/current
        overview provided by google scholar itself.
    """

    # announce current time
    tqdm.write(colored('Data collection process starting at {}'.format(datetime.datetime.now()),'green'))

    # collect authors and request author information from google scholar.
    authors += collect_authors_from_lists(author_list)
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

# TODO: paper info handling
if __name__ == '__main__':
    main()