import os
from tqdm import tqdm
import click
import datetime
import numpy as np
from termcolor import colored
import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta

from util import collect_authors_from_lists, check_if_data_available_for
from util import load_author_data, desparsify_time_series_data, process_values



##############
# ENTRY POINT
##############

whats = ['cited', 'h', 'i10']
whats_keys = {'cited':'citations', 'h': 'h_index', 'i10':'i10_index'} # translates cmi inputs to datastructure keys
hows  = ['plain', 'delta_year', 'delta_month', 'growth_year', 'growth_month' ]
hows_format = {'plain':'{}', 'delta_year':'{:+}', 'delta_month':'{:+}', 'growth_year':'{:+.2f}%', 'growth_month':'{:+.2f}%'}# format specifications for plotting collected values
#times = ['relative', 'absolute'] # all sorts of timing options. let's start with a just absolute handling.

@click.command()
@click.option('--authors'           , '-a'  , multiple=True                 , help="The name or google scholar id of the authors to visualize. Multiple uses possible.")
@click.option('--author_list'       , '-al' , multiple=True                 , help="Should point to a file of newline-character-separated author names or ids. Multiple uses possible")
@click.option('--author_record_dir' , '-ad' , default='./output/authors/'   , help="Shuold point at the folder containing all the pre-collected author data.")
@click.option('--output_file'       , '-o'  , default='./plot.png'          , help="Output file of the stats to collect. Only produces file if set.")
@click.option('--list'              , '-l'  , is_flag=True                  , help="Causes the script -- instead of plotting -- to list all the available author info(s) in the available files.")
@click.option('--show'              , '-s'  , is_flag=True                  , help="Shows the plotted data.")
@click.option('--what'              , '-w'  , default=whats[0]              , help="What data to plot? default: {} . all options: {}".format(whats[0], whats))
@click.option('--how'               , '-h'  , default=hows[0]               , help="How to present the data? default: {} . all options: {}".format(hows[0], hows))
@click.option('--min_date'          , '-mnd', default=None                  , help="min date. plot no date earlier than this date, to be given in %Y-%m-%d format.")
@click.option('--max_date'          , '-mxd', default=None                  , help="max date. plot no date later than this date, to be given in %Y-%m-%d format.")
@click.option('--figsize'           , '-figs' , default=5                   , help="Specifies the size of generated figure.")
@click.option('--fontsize'          , '-fs'  , default=8                    , help="Specifies the size of fonts used in the figure.")
@click.option('--num_xticks'        , '-nx' , default=5                     , help="Number of euqually spaced x-ticks. can be int or strings (TODO: 'year', 'month')")
#TODO --how and --what should be multiple=True fields
#TODO, maybe plotting parameters:
# --t_min (plot from a min absolute/relative time on (make it months?)) (absolute if both min and max are given)
# --t_max (plot until a max absolute/relative time on (make it months?))
# --cmap (default: no idea. pick something suitable.)
# all sorts of marker and line styles.... rather use config file?
# --test
def plot(authors, author_list, author_record_dir, output_file, list, show, what, how, min_date, max_date, figsize, fontsize, num_xticks):
    """
        This script collects (already downloaded) author information from google scholar located on the disc
    """

    # announce current time
    tqdm.write(colored('Data visualization process starting at {}'.format(datetime.datetime.now()), 'green'))

    # provide an overview over available data if requested, then exit.
    if list:
        tqdm.write('Checking "{}" for data...'.format(author_record_dir))
        author_files = [x for x in os.listdir(author_record_dir) if os.path.isfile(os.path.join(author_record_dir, x)) and x.endswith('.txt')]
        tqdm.write(colored('Available author data:', 'yellow'))
        for a in author_files: # read first line of file and print author name and affiliation.
            with open(os.path.join(author_record_dir,a)) as f:
                print('>  ', os.path.splitext(a)[0], ':', f.readline().lstrip(' #').rstrip())
        exit()

    # collect specified author files and test availability.
    authors += collect_authors_from_lists(author_list)
    authors = check_if_data_available_for(authors, author_record_dir)

    # load author data.
    author_data = load_author_data(authors, author_record_dir)

    # fill time series data wrt common time frames.
    # TODO resolve time-zone dependently added duplicates during pre- and postpending.
    author_data = desparsify_time_series_data(author_data)

    # TODO might be necessary on some instances to get unique valkues for some the entries.
    #print(author_data[0].keys())
    #print(len(author_data[0]['date_str']))
    #print(len(np.unique(author_data[0]['date_str'])))

    # select desired measurements as values to be visualized ("what")
    for a in author_data:
        a['value'] = a[whats_keys[what]]

    # process values as desired ("how")
    for a in author_data:
        a['value'] = process_values(a['value'], how_to_process=how)

    # apply some filters on the data.
    # TODO extract into own function with additional filters popping up over time
    for a in author_data:
        if min_date is not None:
            min_date_timestamp = datetime.datetime.strptime(min_date, '%Y-%m-%d').timestamp()
            not_too_old_idx = a['date'] >= min_date_timestamp
            a['date'] = a['date'][not_too_old_idx]
            a['date_str'] = a['date_str'][not_too_old_idx]
            a['citations'] = a['citations'][not_too_old_idx]
            a['h_index'] = a['h_index'][not_too_old_idx]
            a['i10_index'] = a['i10_index'][not_too_old_idx]
            a['value'] = a['value'][not_too_old_idx]
            
        if max_date is not None:
            max_date_timestamp = datetime.datetime.strptime(max_date, '%Y-%m-%d').timestamp()
            not_too_new_idx = a['date'] <= max_date_timestamp
            a['date'] = a['date'][not_too_new_idx]
            a['date_str'] = a['date_str'][not_too_new_idx]
            a['citations'] = a['citations'][not_too_new_idx]
            a['h_index'] = a['h_index'][not_too_new_idx]
            a['i10_index'] = a['i10_index'][not_too_new_idx]
            a['value'] = a['value'][not_too_new_idx]

    # draw plots
    fig = plt.figure(figsize=(figsize, figsize))
    for a in author_data:
        p = plt.plot(
            a['date'],
            a['value'],
            #marker='s', #make this optional
            label='{} ({})'.format(a['name'], a['scholar_id'])
        )
        a['plot_color'] = p[0].get_color()

    for a in author_data:
        plt.text(x=a['date'][-1],
                 y=a['value'][-1],
                 s='{} ->'.format(hows_format[how].format(a['value'][-1])),
                 color=a['plot_color'],
                 backgroundcolor=[1,1,1,0.5],
                 va='center', 
                 ha='right')

    # define decoration
    # TODO better way to figure out x-ticks to select and show. parameter? see commented code below.
    tick_indices    = np.linspace(start=0,
                              stop=len(author_data[0]['date'])-1,
                              num=num_xticks,
                              dtype=int) #assume all dates align
    x_ticks         = author_data[0]['date'][tick_indices]
    x_tick_labels   = author_data[0]['date_str'][tick_indices]


    # TODO show or safe.
    plt.xticks(x_ticks, x_tick_labels, rotation=45, ha='center',fontsize=fontsize)
    plt.yticks(fontsize=fontsize)
    plt.ylabel(how,fontsize=fontsize)
    plt.xlabel('date',fontsize=fontsize)
    plt.title('{} {}'.format(whats_keys[what], how))

    plt.legend(fontsize=fontsize)
    plt.show()


    # OLD CODE BELOW
    # collect authors and request author information from google scholar.
    # authors += collect_authors_from_lists(author_list)
    # if plot:
    #     load_and_plot(authors=authors,
    #                   data_dir=output_directory,
    #                   plot_show=plot_show,
    #                   plot_file=plot_file)
    #     exit()


# def load_and_plot(authors, data_dir, plot_show, plot_file):
#     # collect data first
#     data = {}
#     for a in authors:
#         a = a.strip()
#         author_file = '{}/authors/{}.txt'.format(data_dir,a)
#         if author_file:
#             with open(author_file) as f:
#                 lines = f.read().replace('#','').strip().split('\n')
#                 name, affiliation = lines[0].split(',',1)
#                 date = []; citations = []; h_index = []; i10_index = []
#                 for line in lines[2::]:
#                     d,c,h,i = line.split()
#                     date.append(d)
#                     citations.append(int(c))
#                     h_index.append(0 if h == 'none' else int(h))
#                     i10_index.append(0 if i == 'none' else int(i))

#                 data[name] = {'affiliation': affiliation,
#                             'scholar_id': a,
#                             'date'    :  np.array([datetime.datetime.strptime(di, '%Y-%m-%d').timestamp() for di in date]),
#                             'date_str':  np.array(date),
#                             'citations': np.array(citations),
#                             'h_index':   np.array(h_index),
#                             'i10_index': np.array(i10_index)
#                             }

#     # draw plots (rudimentary. TODO: upgrade! see ideas in @click at main)
#     # TODO preprocess parameters and data according to plotting parameters
#     t_min = np.inf ; t_max = 0
#     for name in data:
#         #track min and max time values
#         t_min = min(data[name]['date'].min(), t_min)
#         t_max = max(data[name]['date'].max(), t_max)

#         #some basic plotting
#         plt.plot(   data[name]['date'], # - data[name]['date'].min(), #right part: "relative time" meaning
#                     data[name]['citations'], #default setting
#                     marker="s", # TODO: make optional
#                     #drawstyle='steps-post',
#                     label='{} ({})'.format(name, data[name]['scholar_id']))

#     #decoration
#     # first fill list of x-ticks with days of months.
#     t_month = datetime.datetime.fromtimestamp(t_min)
#     t_month = t_month.replace(day=1).replace(month=t_month.month-t_month.month%3) #start with first day of respective quarter
#     x_ticks = []
#     while t_month.timestamp() <= t_max:
#         x_ticks.append(t_month.timestamp())
#         t_month += relativedelta(months=3)

#     plt.xticks(x_ticks, [datetime.datetime.fromtimestamp(t).strftime('%Y-%m') for t in x_ticks], rotation=90, ha='center')
#     plt.ylabel('citations (default)')
#     plt.xlabel('time') # adapt in relative variant.
#     plt.legend()


#     if plot_file:
#         plt.savefig(plot_file, dpi=300)

#     if plot_show:
#         plt.show()




if __name__ == '__main__':
    plot()