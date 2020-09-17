# A More Fine-Grained Tool for Google Scholar Stat Tracking
Google scholar is tracking statistics such as citation counts for authors and papers. However, it only provides the number of total current citations, as well as the total citations of the current and past year. As someone who likes to watch lines go up, this was not enough *fine grained* info for me.

Knowing that google scholar updates its stats page every second day, I have thus created this neat little tool to track the citation and citation index progression of my own and my colleagues' and co-authors' work. I am very aware, that this is nothing else but a private d***k measuring contest ;)

For now, I will let this tool run every second day and auto-commit stats as a cron job on a raspberry pi sitting at home.

In the near future, there will be an extension for tracking paper info (for all authors?). This will probably require some more sparse data logging, to avoid an explosion of text data.

At some later time, once enough dated data points have been gathered, I will add functionality to draw some neat lines.

## How to use this tool
First, clone this repo. Then, `pip install -r requirements.txt` all required packages. The tool can then be neatly used from command line. The following help text should be self-explanatory.:
```
$ python main.py --help
Usage: main.py [OPTIONS]

  This script collects author information on google scholar and writes the
  respective current reference count to a dated list. This allows for a more
  fine-grained tracking of citations compared to the yearly/current overview
  provided by google scholar itself.

Options:
  -a, --authors TEXT           The name of the authors to track on google
                               scholar. Multiple uses possible

  -al, --author_list TEXT      Should point to a file of newline-character-
                               separated author names. Multiple uses possible

  -o, --output_directory TEXT  Output directory of the stats to collect. A
                               file will be created or appended to, named
                               after the authors' google scholar ids.

  -d, --dry_run                Set this flag to only collect data without
                               writing.

  -fa, --fetch_async           Set this flag to fetch author data
                               asynchronously from the web. Default behaviour
                               is sequential processing.

  -c, --commit                 Set this flag to auto-add and commit any change
                               in the given output directory to your CURRENT
                               BRANCH and local git.

  -k, --keep_log               Set this flag to keep the scholar.log and
                               geckodriver.log created by scholarly

  --help                       Show this message and exit.
```

I personally am running the tool, as a cron job, with
```
python main.py -al fhg-hhi-authors.txt -al coauthors.txt -o /some/location -c -fa
```
