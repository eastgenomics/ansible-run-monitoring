import json
import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util import Retry
from typing import Union


class Assignee(object):
    """
    Assignee object for Jira assignee
    """
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.active = data.get('active', None)
        self.name = data.get('displayName', None)
        self.timezone = data.get('timeZone', None)


class Reporter(object):
    """
    Reporter object for Jira reporter
    """
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.account_type = data.get('accountType', None)
        self.active = data.get('active', None)
        self. name = data.get('displayName', None)
        self.email = data.get('emailAddress', None)
        self.time = data.get('timeZone', None)


class Creator(object):
    """
    Creator object for Jira creator
    """
    def __init__(self, data):
        self.id = data.get('accountId', None)
        self.account_type = data.get('accountType', None)
        self.active = data.get('active', None)
        self.name = data.get('displayName', None)
        self.time = data.get('timeZone', None)


class Priority(object):
    """
    Priority object for priority in Jira ticket
    """
    def __init__(self, data):
        self.id = data.get('id', None)
        self.name = data.get('name', None)


class Project(object):
    """
    Project object for project in Jira ticket
    """
    def __init__(self, data):
        self.id = data.get('id', None)
        self.key = data.get('key', None)
        self.name = data.get('name', None)
        self.category = data.get('projectCategory', None)


class Status(object):
    """
    Status object for status in Jira ticket
    """
    def __init__(self, data):
        self.id = data.get('id', None)
        self.name = data.get('name', None)
        self.category = data.get('statusCategory', None)


class Issue(object):
    """
    Issue object for Jira issue
    """
    def __init__(self, data):
        self.id = data['id']
        self.key = data['key']

        fields = data['fields']
        self.created = fields.get('created', None)
        self.creator = Creator(fields.get('creator', {})).__dict__
        self.priority = Priority(fields.get('priority', {})).__dict__
        self.summary = fields.get('summary', None)
        self.updated = fields.get('updated', None)
        if 'assignee' in fields:
            if fields['assignee'] is not None:
                self.assignee = Assignee(fields.get('assignee', {})).__dict__
            else:
                self.assignee = None
        else:
            self.assignee = None
        if 'status' in fields:
            self.status = Status(fields.get('status', {})).__dict__
        else:
            self.status = None
        if 'project' in fields:
            self.project = Project(fields.get('project', {})).__dict__
        else:
            self.project = None
        if 'reporter' in fields:
            self.reporter = Reporter(
                fields.get('reporter', {})).__dict__
        else:
            self.reporter = None
        if 'customfield_10070' in fields:
            if fields['customfield_10070'] is not None:
                self.assay = fields['customfield_10070'][0].get('value', None)
            else:
                self.assay = None
        else:
            self.assay = None


class Jira():
    """
    Jira Class Wrapper for Jira API request
    """
    headers = {"Accept": "application/json"}

    http = requests.Session()
    retries = Retry(total=5, backoff_factor=10, method_whitelist=['POST'])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    def __init__(self, token, email, api_url, debug):
        self.auth = HTTPBasicAuth(email, token)
        self.api_url = api_url
        self.url = f'{api_url}/servicedeskapi/servicedesk'
        self.debug = debug

    def get_all_service_desk(self):
        """
        Get all service desk on Jira
        """
        url = self.url
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)
        return response.json()

    def get_queues_in_service_desk(self, servicedesk_id):
        """
        Get all queues available in specified service desk on Jira
        """
        url = f"{self.url}/{servicedesk_id}/queue"
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)
        return response.json()

    def get_all_issues(
            self,
            servicedesk_id: int,
            queue_id: int,
            trimmed: bool = False) -> list:
        """
        Get all issues of a queue in specified service desk
        Inputs:
            servicedesk_id: service desk id
            queue_id: queue id (e.g. All Open or New Sequencing)
        """
        url = f"{self.url}/{servicedesk_id}/queue/{queue_id}/issue"
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)

        count = 50
        issues = response.json()['values']

        while response.json()['isLastPage'] is False:
            query_url = url + f'?start={count}'
            response = self.http.get(
                query_url,
                headers=self.headers,
                auth=self.auth)

            if not response.ok:
                break

            issues += response.json()['values']
            count += 50

            if count > 5000:
                break

        if trimmed:
            result = []

            for issue in issues:
                result.append(Issue(issue).__dict__)
            return result
        return issues

    def get_issue(
            self,
            issue_id: Union[int, str],
            trimmed: bool = False):
        """
        Get details of specified issue
        If trimmed: return a pre-processed issue json()
        Input:
            issue_id: issue id or key
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)
        if trimmed:
            return Issue(response.json()).__dict__
        return response.json()

    def search_issue(
            self,
            sequence_name: str,
            assays: list = [],
            project_name: str = 'EBH',
            status: list = [],
            trimmed: bool = False):
        """
        Search issues based on input text
        If trimmed: return a pre-processed issue json()
        Inputs:
            assays: limit search to certain assays
            status: limit search to certain status
        """

        url = f"{self.api_url}/api/3/search"
        query_cmd = f'project={project_name} and summary ~ \"{sequence_name}\"'

        # filter by specific status
        if status:
            status_options = ','.join('"{0}"'.format(w) for w in status)
            query_cmd += f' and status IN ({status_options})'

        query = {'jql': query_cmd}
        response = self.http.get(
            url,
            headers=self.headers,
            params=query,
            auth=self.auth)
        res = response.json()
        if 'errorMessages' in res:
            return res
        elif len(res['issues']) == 0:
            return res

        if assays:
            assays = [a.lower() for a in assays]
            if len(res['issues']) > 1:
                print('Multiple issue found.')
                output = []
                for issue in res['issues']:
                    assay = self.get_assay(issue)
                    if assay is not None:
                        if assay.lower() in assays:
                            output.append(Issue(issue))
                if output:
                    return output
                else:
                    print('no ticket fits assay options')
                    return {'total': 0}
            else:
                issue = res['issues'][0]
                assay = self.get_assay(issue)
                if assay is not None:
                    if assay.lower() in assays:
                        if trimmed:
                            return {
                                'total': res['total'],
                                'maxResults': res['maxResults'],
                                'startAt': res['startAt'],
                                'issues': Issue(issue).__dict__
                            }
                        else:
                            return res
                    else:
                        print('no ticket fits assay options')
                        return {'total': 0}
        else:
            # if assay not specified
            if trimmed:
                if len(res['issues']) > 1:
                    # if multiple issues
                    issues = []
                    for issue in res['issues']:
                        issues.append(Issue(issue).__dict__)

                    return {
                        'total': res['total'],
                        'maxResults': res['maxResults'],
                        'startAt': res['startAt'],
                        'issues': issues
                    }
                else:
                    issue = res['issues'][0]
                    return {
                        'total': res['total'],
                        'maxResults': res['maxResults'],
                        'startAt': res['startAt'],
                        'issues': Issue(issue).__dict__
                    }

            else:
                return res

    def get_assay(issue: dict):
        """
        Get assay options of an issue
        """
        if 'customfield_10070' in issue['fields']:
            return issue['fields']['customfield_10070'][0].get('value', None)
        return None

    def get_issue_detail(
            self,
            project: str):

        """
        Function to do an issue search and return its
        assay options and status
        Specific for Ansible-Run-Monitoring
        """

        if self.debug:
            # debug helpdesk
            desk = 'EBHD'
        else:
            desk = 'EBH'

        jira_data = self.search_issue(
            project,
            project_name=desk,
            trimmed=True)

        if jira_data['total'] < 1:
            assay = 'No Jira ticket found'
            status = 'No Jira ticket found'
            key = None
        elif jira_data['total'] > 1:
            # if there's more than one issue with
            # the same name
            # we remove those that start with 'RE' (replies)
            issues = jira_data['issues']

            the_issue = [
                issue for issue in issues if not issue['summary'].startswith(
                    'RE')]
            if len(the_issue) == 1:
                assay = the_issue[0]['assay']
                status = the_issue[0]['status']['name']
                key = the_issue[0]['key']
            else:
                assay = 'More than 1 Jira ticket detected'
                status = 'More than 1 Jira ticket detected'
                key = None
        else:
            # found only one Jira issue
            assay = jira_data['issues']['assay']
            status = jira_data['issues']['status']['name']
            key = jira_data['issues']['key']

        return assay, status, key

    def create_issue(
            self,
            summary: str,
            issue_id: int,
            project_id: int,
            reporter_id: str,
            priority_id: int,
            desc: str,
            assay: bool):

        """
        Create a ticket issue
        Inputs:
            summary: issue title
            issue_id: id of issue type
            project_id: id of project
            reporter_id: id of reporter
            desc: issue description
            priority_id: id of priority (e.g. 3)
        """
        url = f"{self.api_url}/api/3/issue"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        if self.debug:
            project_id = 10042

        if assay:
            # likely for debug purpose
            payload = json.dumps({
                "fields": {
                    "summary": summary,
                    "issuetype": {
                        "id": str(issue_id)
                    },
                    "project": {
                        "id": str(project_id)
                    },
                    "reporter": {
                        "id": reporter_id
                    },
                    "priority": {
                        "id": str(priority_id)
                    },
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "text": desc,
                                        "type": "text"
                                    }
                                ]
                            }
                        ]
                    },
                    "customfield_10070": [
                        {
                            "value": 'MYE'
                        }
                    ]
                }
            })
        else:
            payload = json.dumps({
                "fields": {
                    "summary": summary,
                    "issuetype": {
                        "id": str(issue_id)
                    },
                    "project": {
                        "id": str(project_id)
                    },
                    "reporter": {
                        "id": reporter_id
                    },
                    "priority": {
                        "id": str(priority_id)
                    },
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "text": desc,
                                        "type": "text"
                                    }
                                ]
                            }
                        ]
                    },
                }
            })

        response = self.http.post(
            url,
            data=payload,
            headers=headers,
            auth=self.auth
            )

        return response.json()

    def make_transition(self, issue_id, transition_id):
        """
        Make a transition for an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}/transitions"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = json.dumps({
            "transition": {
                "id": transition_id
            }
        })

        response = self.http.post(
            url,
            data=payload,
            headers=headers,
            auth=self.auth
        )

        if response.status_code == 204:
            return 'Request successful'
        else:
            return response.text

    def delete_issue(self, issue_id):
        """
        Delete an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"

        response = requests.request(
            "DELETE",
            url,
            auth=self.auth
        )

        if response.status_code == 204:
            return 'Request successful'
        else:
            return response.text

    def get_available_transitions(self, issue_id):
        """
        Get all available transitions for an issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}/transitions"

        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth
        )

        return response.json()
