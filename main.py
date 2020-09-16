import scholarly
import tqdm
import click
import os

@click.command()
@click.option('--authors'           , '-a'  , multiple=True , help="The name of the authors to track on google scholar.")
@click.option('--author_list'       , '-al' , multiple=True , help="Should point to a file of linebreak character separated author names.")
@click.option('--output_directory'  , '-o'  , default='.'   , help="Output directory of the stats to collect. A file will be created or appended to, named after the authors' google scholar ids")
def main(authors, author_list, output_directory):
    """
        This script collects author information on google scholar and writes the respective
        current reference count to a dated list.
        This allows for a more fine-grained tracking of citations compared to the yearly/current
        overview provided by google scholar itself.
    """
    print(authors, author_list, output_directory)

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
    # later: plotting/graphing


if __name__ == '__main__':
    main()