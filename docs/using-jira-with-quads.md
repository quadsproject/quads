Using Optional JIRA Library and Tools
======================================

Internally we use the [JIRA](https://www.atlassian.com/software/jira) as is
common with a lot of development/devops organizations.  To this end we are
providing some tools and libraries within QUADS with the hope it's useful to
others.

![jira](../image/jira.jpg?raw=true)
   * [Requirements for JIRA QUADS Automation](#requirements-for-jira-quads-automation)
      * [JIRA Basic Authentication](#jira-basic-authentication)
      * [JIRA Token Authentication](#jira-token-authentication)
   * [Perfoming API Activities with jira.py](#api-activities-with-jirapy)
   * [Applying Labels and Adding Watchers](#applying-labels-and-adding-watchers)
   * [Common JIRA Labels](#common-jira-labels)

## Requirements for JIRA QUADS Automation
JIRA is integrated with QUADS through the `jira` ticketing plugin, configured in
`/opt/quads/conf/plugins.yml`.  Enable it and provide the connection details
under the `plugins.jira` section, please adapt these to your environment.

* JIRA API user with admin capability for your JIRA project.
* Placing JIRA credentials or alternatively a token auth string in `/opt/quads/conf/plugins.yml`

```yaml
plugins:
  jira:
    enabled: true
    # takes 2 values only, basic or token, defaults to basic
    # basic will make use of username and password
    # token will make use of token
    auth_type: basic
    url: https://projects.engineering.example.com/rest/api/2
    username: admin
    password: password
    token: 7h1515@v3ryl0n6@ndcr1p71c70k3n
    # (optional ticket queue name) this is typically the ticket queue
    # name or abbreviation in the case of JIRA
    ticket_queue: SCALELAB
```

   - The `ticket_url` and `ticket_queue` keys used by the web UI to build ticket
     links are configured separately in `/opt/quads/conf/quadsweb.yml`.

### JIRA Basic Authentication
By default we support BasicAuth for JIRA (username/password), you just need to enter in the credentials like below in `/opt/quads/conf/plugins.yml`.

```yaml
    auth_type: basic
    username: admin
    password: password
```

### JIRA Token Authentication
We also support token/bearer auth for API token access as well, to utilize this you'll need to change the `auth_type` value to `token`.
These authentication methods are mutually exclusive.

```yaml
    auth_type: token
    token: 7h1515@v3ryl0n6@ndcr1p71c70k3n
```

## API activities with jira.py
  * Library: `/opt/quads/quads/tools/external/jira.py`
  * The `jira.py` library in QUADS helps with auto-updating JIRA tickets using the API user.
  * If you are using `--host-list` for en-masse scheduling this will be called to update the
    ticket template found in `/opt/quads/templates/jira_ticket_assignment`
  * The `jira_workflow.py` tool closes expired assignment tickets by
    transitioning them to `Done` and can be run out of cron or a systemd timer.

## Applying labels and adding watchers
  * Tool: `/opt/quads/quads/tools/jira_watchers.py`
  * The `jira_watchers.py` tool will assist you with ad-hoc (perhaps run out of cron or systemd timer)
    batch processing to do the following:
    * Ensure the person submitting the request is added as a _watcher_ in JIRA
    * Checking the viability of extension request with appropriate labels, e.g. `CAN_EXTEND` or `CANNOT_EXTEND`
  * Below is a reference of how we use labels in JIRA.

## Common JIRA Labels
  * Below is a chart of common labels we use in JIRA with `jira.py` managing/automating this aspect of
    our request workflow.

| Label Name       |Category    | Purpose of Label                                                |
|------------------|------------|-----------------------------------------------------------------|
| EXTENSION        |  Assignment| Label for existing assignment extension                         |
| EXPANSION        |  Assignment| Request for expansion of existing assignment                    |
| CAN_EXTEND       |  Viability | Label indicating assignment could be extended with no conflicts |
| CANNOT_EXTEND    |  Viability | Label indicating a conflict in at least one system for extension|
