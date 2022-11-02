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
# UTILITY FXNS
##############

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
#TODO --list to list existing entries in the output folder.
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