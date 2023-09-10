#!/usr/bin/env python
# Copyright 2018-2023 John T. Foster
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""grader

Usage:
  grader.py <assignment_name>
  grader.py <assignment_name> [(--env <NAME> <VALUE>)...]
  grader.py <assignment_name> [--due (<DATE> <TIME> <TIME_ZONE> <MULTIPLIER>)]
  grader.py <assignment_name> [--due (<DATE> <TIME> <TIME_ZONE> <MULTIPLIER>) (--env <NAME> <VALUE>)...]
  grader.py [-E] <google_client_secret.json>
  grader.py [-T] <assignment_name>

Options:
  -h --help      Show this screen.
  --version      Show version.
  -v --verbose   Show verbose output.
  -e --env       Specify environment variables.
  -d --due       Specify due date/time with (format YYYY-MM-DD HH:MM:SS TZ multiplier)
  -E --encode    Encode a Google Client secret file
  -T --trigger   Trigger a rerun of all assignment workflows
"""

from docopt import docopt
from ghapi.all import GhApi, paged
from canvasapi import Canvas
import pandas as pd
import os.path
from dateutil.tz import gettz
import dateutil.parser
import json
import base64
import gspread

def google_creditial_encoder(json_file):
    """
    Encode a Google credentials JSON file into a base64 string.

    Parameters
    ----------
    json_file : str
        Path to the JSON file containing the Google credentials.

    Returns
    -------
    base64_bytes : str
        The base64 encoded string of the Google credentials.
    """
    with open(json_file) as f:
        minified_json = json.dumps(json.load(f),
                                   separators=(',', ':'))

    base64_bytes = base64.b64encode(minified_json.encode('ascii'))
    return base64_bytes.decode('ascii')

def google_creditial_decoder(base64_byte_string:str):
    """Decode a base64 encoded byte string into a JSON object.

    Parameters
    ----------
    base64_byte_string : str
        A base64 encoded byte string.

    Returns
    -------
    dict
        A JSON object decoded from the base64 encoded byte string.
    """
    base64_str = base64.b64decode(base64_byte_string)
    return json.loads(base64_str.decode('ascii'))

def username_map_from_google_sheet(creditials:str, classname:str):
    """
    Create a mapping of Github usernames to EIDs from a Google Sheet.

    Parameters
    ----------
    creditials : str
        Google credentials.
    classname : str
        Name of the class.

    Returns
    -------
    DataFrame
        A mapping of Github usernames to EIDs.
    """
    creditials = google_creditial_decoder(creditials)

    gc = gspread.service_account_from_dict(creditials)

    sh1 = gc.open(f'{classname} Github Names').sheet1
    df = pd.DataFrame(sh1.get_all_records())
    df['Github Username'] = df['Github Username'].apply(lambda s: s.lower())
    df['EID'] = df['EID'].apply(lambda s: s.lower())

    return df.set_index(['Github Username'])

def filter_repos(api: GhApi, org: str, filter_string: str):
    """
    Retrieve a list of repositories from a given organization that match a given filter string.

    Parameters
    ----------
    api : GhApi
        The Github API object.
    org : str
        The organization name.
    filter_string : str
        The string to filter the repository names by.

    Returns
    -------
    list
        A list of repository names that match the filter string.
    """
    repos = list()
    for page in paged(api.repos.list_for_org, org=org):
        for item in page:
            if filter_string in item.get('name'):
                repos.append(item['name'])

    return repos

def get_latest_workflow_run(api: GhApi, repo: str, workflow_filename: str='main.yml'):
    """
    Get the latest workflow run for a given repository and workflow filename.

    Parameters
    ----------
    api : GhApi
        The Github API object.
    repo : str
        The repository name.
    workflow_filename : str, optional
        The workflow filename, by default 'main.yml'.

    Returns
    -------
    dict
        The workflow run information.
    None
        If no workflow runs are found.
    """
    runs = api.actions.list_workflow_runs_for_repo(repo=repo)

    if runs['total_count'] == 0:
        return None
    else:
        for i, workflow_run in enumerate(runs['workflow_runs']):
            if workflow_filename in workflow_run['name']:
                return runs['workflow_runs'][i]


def get_latest_workflow_conclusion(api, repo: str, workflow_filename: str='main.yml'):
    """
    Get the latest workflow conclusion from a given repository.

    Parameters
    ----------
    api : GitHub API
        The GitHub API object.
    repo : str
        The repository name.
    workflow_filename : str, optional
        The workflow filename (default is 'main.yml').

    Returns
    -------
    str
        The workflow conclusion.
    None
        If no workflow runs are found.
    """
    run = get_latest_workflow_run(api, repo, workflow_filename)

    if run is None:
        return None
    else:
        return run['conclusion']


def get_latest_workflow_commit_time_and_conclusion(api, repo: str,
                                                   workflow_filename: str='main.yml'):
    """
    Get the latest workflow commit time and conclusion from a given repository.

    Parameters
    ----------
    api : object
        The GitHub API object.
    repo : str
        The repository name.
    workflow_filename : str, optional
        The workflow filename (default is 'main.yml').

    Returns
    -------
    tuple
        A tuple containing the latest workflow commit time and conclusion.
    """
    run = get_latest_workflow_run(api, repo, workflow_filename)

    if run is None:
        return (None, None)
    else:
        return (run['head_commit']['timestamp'], run['conclusion'])

def strip_github_username(repo: str):
    """
    strip_github_username(repo: str)

    Returns a lowercase string of the username from a given GitHub repository.

    Parameters
    ----------
    repo : str
        The name of the GitHub repository.

    Returns
    -------
    str
        The username from the given repository.
    """
    return '-'.join(repo.split('-')[1:]).lower()

def rerun_latest_workflow(api, repo, workflow_filename: str='main.yml'):
    """Re-run the latest workflow for a given repository.

    Parameters
    ----------
    api : object
        The Github Actions API object.
    repo : str
        The repository name.
    workflow_filename : str, optional
        The name of the workflow file, by default 'main.yml'.

    Returns
    -------
    None
        This function does not return anything.
    """
    run_id = get_latest_workflow_run(api, repo, workflow_filename)['id']

    try:
        api.actions.re_run_workflow(repo=repo, run_id=run_id)
    except:
        pass

    return

def rerun_all_worflows_for_assignment(api, org, assignment_name:str,
                                      workflow_filename: str='main.yml'):
    """Rerun all workflows for a given assignment.

    Parameters
    ----------
    api : object
        Github API object.
    org : str
        Name of the organization.
    assignment_name : str
        Name of the assignment.
    workflow_filename : str, optional
        Name of the workflow file, by default 'main.yml'.

    Returns
    -------
    None
    """
    repos = filter_repos(gh_api, org, assignment_name)

    for repo in repos:
        rerun_latest_workflow(api, repo, workflow_filename)

    return


def read_username_map(creditials:str=None, classname:str=None):
    """Read username map from either a csv file or a Google sheet.

    Parameters
    ----------
    creditials : str, optional
        Creditials for accessing the Google sheet.
    classname : str, optional
        Name of the Google sheet.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing the username map.

    Raises
    ------
    ValueError
        If an error occurs while reading the Google sheet.
    """
    if os.path.isfile('username_map.csv'):
        df = pd.read_csv('username_map.csv')
        df['EID'] = df['EID'].convert_dtypes('str').apply(lambda s: s.lower())
        df['Github Username'] = df['Github Username'].convert_dtypes('str').apply(lambda s: s.lower())
        return df.set_index(['Github Username'])
    elif creditials is not None and classname is not None:
        try:
            return username_map_from_google_sheet(creditials, classname)
        except ValueError:
            print("Error reading Google Sheet")
    else:
        print('You must specify a username map from a file name "username_map.csv" or Google sheet.')

def score_multiplier(args,
                     commit_time,
                     comparison_operator=lambda a,b: a <= b):
    """Calculate a score multiplier based on the commit time and due time.

    Args:
        args (dict): A dictionary of command line arguments.
        commit_time (str): The commit time as a string.
        comparison_operator (function, optional): A comparison operator to use for the calculation. Defaults to lambda a,b: a <= b.

    Returns:
        float: The score multiplier.
    """
    if args['--due']:
        commit_time = dateutil.parser.parse(commit_time)
        date_time_string = f'{args["<DATE>"]} {args["<TIME>"]} {args["<TIME_ZONE>"]}'
        due_time = dateutil.parser.parse(date_time_string, tzinfos={"CST": gettz("America/Chicago")})
        rel_time = dateutil.relativedelta.relativedelta(commit_time, due_time)
        if (comparison_operator(rel_time.hours, 0) and
            comparison_operator(rel_time.minutes, 0) and
            comparison_operator(rel_time.seconds, 0)):
            return float(args['<MULTIPLIER>'])
        else:
            return 1.0
    else:
        return 1.0

def get_assignment_id(course, assignment_name:str):
    """
    Retrieve the assignment id of a given assignment name from a course.

    Parameters
    ----------
    course : object
        The course object from which to retrieve the assignment id.
    assignment_name : str
        The name of the assignment to retrieve the id from.

    Returns
    -------
    int
        The id of the assignment with the given name.
        None if no assignment with the given name is found.
    """
    assignments = course.get_assignments()

    for assignment in assignments:

        if assignment.name == assignment_name:
            return assignment.id

    print(f"No assignment id with corresponding name: {assignment_name}")
    return


if __name__ == '__main__':

    args = docopt(__doc__, version='grader 0.2.0')

    if args['--encode']:
        print(google_creditial_encoder(args['<google_client_secret.json>']))
        exit()


    if args['--env']:
        for name, value in zip(args['<NAME>'], args['<VALUE>']):
            os.environ[name] = value

    verbose = True

    org = os.environ['GITHUB_REPOSITORY'].split('/')[0]

    gh_api = GhApi(owner=org,
                   token=os.environ['GH_TOKEN'])

    if args['--trigger']:
        rerun_all_worflows_for_assignment(gh_api, org, args["<assignment_name>"])
        exit()

    canvas = Canvas('https://utexas.instructure.com',
                    os.environ['CANVAS_TOKEN'])

    course = canvas.get_course(os.environ['CANVAS_COURSE_ID'])

    username_map = read_username_map(os.environ['GOOGLE_CLIENT_SECRET'], org)

    repos = filter_repos(gh_api, org, args["<assignment_name>"])

    print(f"Grading: {args['<assignment_name>']}")
    print('Found repos:')
    for repo in repos:
        print(f'    {repo}')

    for repo in repos:

        commit_time, conclusion = \
                        get_latest_workflow_commit_time_and_conclusion(gh_api,
                                                                       repo,
                                                                       workflow_filename='main.yml')

        if conclusion is not None:
            github_username = strip_github_username(repo)

            multiplier = score_multiplier(args, commit_time)

            assignment = course.get_assignment(get_assignment_id(course,
                                                                 args["<assignment_name>"]))

            try:
                eid = username_map.loc[github_username, "EID"]
                canvas_id = course.get_user(eid, 'sis_login_id').id
                submission = assignment.get_submission(canvas_id)
                if conclusion == 'success':
                    score = 1 * multiplier
                elif conclusion == 'failure':
                    score = 0
                submission.edit(submission={'posted_grade': score})
                if verbose:
                    print(f"Updated grade: {canvas_id} = {score}")
            except:
                pass
        else:
            print(f"No workflow runs for {repo}")
