import requests
import json
from requests.auth import HTTPBasicAuth

from urllib3.util import Retry
from requests.adapters import HTTPAdapter


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
                self.array = fields['customfield_10070'][0].get('value', None)
            else:
                self.array = None
        else:
            self.array = None


class Jira():
    """
    Jira Class Wrapper for Jira API request
    EBH is service desk number 4, All Open 14
    EBHD is service desk number 5, All Open 18
    """
    headers = {"Accept": "application/json"}

    http = requests.Session()
    retries = Retry(total=5, backoff_factor=10, allowed_methods=['POST'])
    http.mount("https://", HTTPAdapter(max_retries=retries))

    def __init__(self, token, email, api_url):
        self.auth = HTTPBasicAuth(email, token)
        self.api_url = api_url
        self.url = f'{api_url}/servicedeskapi/servicedesk'

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
            trimmed: bool = False):
        """
        Get all issues of a queue in specified service desk
        """
        url = f"{self.url}/{servicedesk_id}/queue/{queue_id}/issue"
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)

        if trimmed:
            result = []
            data = response.json()

            for issue in data['values']:
                result.append(Issue(issue).__dict__)

            return {
                'size': data['size'],
                'isLastPage': data['isLastPage'],
                'limit': data['limit'],
                'start': data['start'],
                'values': result
                }

        return response.json()

    def get_issue(
            self,
            issue_id: int,
            trimmed: bool = False):
        """
        Get details of specified issue
        """
        url = f"{self.api_url}/api/3/issue/{issue_id}"
        response = self.http.get(
            url,
            headers=self.headers,
            auth=self.auth)
        if trimmed:
            return Issue(response.json())
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
        Inputs:
            assays: limit search to certain arrays
            status: limit search to certain status
        """

        url = f"{self.api_url}/api/3/search"
        query_cmd = f'project={project_name} and summary ~ \"{sequence_name}\"'
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
                    array = self.get_assay(issue)
                    if array.lower() in assays:
                        output.append(Issue(issue))
                if output:
                    return output
                else:
                    print('no ticket fits array options')
                    return {'total': 0}
            else:
                issue = res['issues'][0]
                array = self.get_assay(issue)
                if array.lower() in assays:
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
                    print('no ticket fits array options')
                    return {'total': 0}
        else:
            if trimmed:
                if len(res['issues']) > 1:
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
        Get array options of an issue
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

        jira_data = self.search_issue(
            project,
            project_name='EBH',
            trimmed=True)

        if jira_data['total'] < 1:
            assay = 'No Jira ticket found'
            status = 'No Jira ticket found'
            key = None
        elif jira_data['total'] > 1:
            issues = jira_data['issues']

            the_issue = [
                issue for issue in issues if not issue['summary'].startswith(
                    'RE')]
            if len(the_issue) == 1:
                assay = the_issue[0]['array']
                status = the_issue[0]['status']['name']
                key = the_issue[0]['key']
            else:
                assay = 'More than 1 Jira ticket detected'
                status = 'More than 1 Jira ticket detected'
                key = None
        else:
            assay = jira_data['issues']['array']
            status = jira_data['issues']['status']['name']
            key = jira_data['issues']['key']

        return assay, status, key

    def create_issue(
            self,
            summary: str,
            issue_type: str,
            project_id: str,
            reporter_id: str,
            priority: str):

        """
        Create a ticket issue
        """
        url = f"{self.api_url}/api/3/issue"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        payload = json.dumps({
            "fields": {
                "summary": summary,
                "issuetype": {
                    "id": issue_type
                },
                "project": {
                    "id": project_id
                },
                "reporter": {
                    "id": reporter_id
                },
                "priority": {
                    "id": priority
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