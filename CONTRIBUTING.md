
Contributing to QUADS
=====================

## How to Contribute
The QUADS project welcomes contributions from everyone!  Please read the below steps to see how you can contribute to QUADS.

## Contribution Basics
  * We **do not** use the Github Pull Request system.
  * We use [Gerrit](https://review.gerrithub.io/q/project:quadsproject%252Fquads) for code review instead.
  * You can also find us on IRC at **#quads** on ```irc.libera.chat``` [webchat](https://web.libera.chat/?channels=#quads)

    * [QUADS Development Setup](#quads-development-setup)
        * [The QUADS Repository](#the-quads-repository)
        * [Virtual Environment Setup](#virtual-environment-setup)
        * [Pre-commit Hooks](#pre-commit-hooks)
        * [Running QUADS Locally](#running-quads-locally)
            * [Running the DB](#running-the-db)
            * [Running the QUADS Server App](#running-the-quads-server-app)
            * [Running the QUADS Web Flask App](#running-the-quads-web-flask-app)
        * [Running the Tox Testing Suite](#running-the-tox-testing-suite)
    * [Create a Tracking Issue](#create-a-tracking-issue)
    * [Setup Github and Gerrit Account](#setup-github-and-gerrit-account)
    * [Make a Commit and Submit Review](#make-a-commit-and-submit-review)
        * [Make Initial Commit](#make-initial-commit)
        * [Ensure Change ID is Present](#ensure-change-id-is-present)
        * [Integrate Git Review](#integrate-git-review)
        * [Managing Git Review Patchsets](#managing-git-review-patchsets)
        * [Monitor your Patchset Lifecycle](#monitor-your-patchset-lifecycle)
        * [Promoting Development to Production](#promoting-development-to-production)
        * [Continuous Integration](#continuous-integration)
            * [Commit Hooks](#commit-hooks)
            * [Jenkins CI Pipeline](#jenkins-ci-pipeline)
            * [Code Review Tips](#code-review-tips)
            * [QUADS CI Architecture](#quads-ci-architecture)

## QUADS Development Setup

### The QUADS Repository
  - Clone `development` branch.

    ```
    git clone --single-branch --branch development https://github.com/quadsproject/quads
    ```

  - Change directory to the code and create your own branch to work
    ```
    cd quads
    git checkout -b name_of_change
    ```

### Virtual Environment Setup

  - Create virtualenv, install dependencies and the QUADS package
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e .
    ```
  - Relocate configuration files to the correct location
    ```bash
    mkdir -p /opt/quads/conf
    cp -r conf/* /opt/quads/conf/
    ```

### Pre-commit Hooks

  - Install pre-commit
    ```bash
    dnf -y install pre-commit
    ```
  - Install the pre-commit hooks
    ```bash
    pre-commit install
    ```

### Running QUADS Locally
> [!CAUTION]
> Never run tests on live data or a live database even in STAGE.
>
> In your sandbox this is fine and you'll actually want to create some dummy data after you have it all stood up.


#### Running the DB
  - Instantiate a PostgreSQL container via podman

    ```
    podman run -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres
    ```
  - This will not background the podman container, so open other terminals to work.
  - Initialize the database with the quads model
    ```bash
    SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@localhost:5432/quads flask --app src/quads/server/app.py init-db
    ```
  > NOTE: If you're using Docker on Mac OSX you may want to switch to the [overlay2 driver](https://stackoverflow.com/questions/39455764/change-storage-driver-for-docker-on-os-x#39737553)  This is not strictly a requirement but can significantly improve performance on a Mac for the local driver.  For more details see this [article](https://markshust.com/2017/03/02/making-docker-mac-faster-overlay2-filesystem/).  Local driver mapped content is stored in ~/Library/Containers/com.docker.docker/Data/vms/0/ in a disk image.

#### Running the QUADS Server Flask App
  - Start the Flask development server instance
    ```bash
    gunicorn quads.server.app:create_app\(\) -b :5000 -w 4 -k gthread --max-requests=5000 --max-requests-jitter=500 --log-level=DEBUG
    ```
  - You can now access the QUADS API at `http://localhost:5000/api/v3/`
  - You can also use the `quads-cli` to interact with the API
    ```bash
    quads --ls-hosts
    ```
#### Running the QUADS Web Flask App
  - Create the directory for the web app to load dynamic content
    ```bash
    mkdir -p /opt/quads/web
    ```
  - Start the Flask development server instance
    ```bash
    gunicorn quads.web.app:create_app\(\) -b :5001 -w 4 -k gthread --max-requests=5000 --max-requests-jitter=500 --log-level=DEBUG
    ```
  - You can now access the QUADS Web UI at `http://localhost:5001/`

### Running Tox Testing Suite

  - After all steps on the [Running QUADS Locally](#Running-QUADS-Locally) section have been completed, you can run the tests.
  - To run the full suite of tests, you can use the `tox` command
    ```bash
    SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@localhost:5432/quads tox
    ```
  - To run a specific test environment, you can use the `-e` flag
    ```bash
    SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@localhost:5432/quads tox -e py312
    ```

## Create a Tracking Issue
* Create a [Github issue](https://github.com/quadsproject/quads/issues/new) to track your work.
  - Provide a meaningful explanation, citing code lines when relevant.
  - Explain what you are trying to fix, or what you're trying to contribute.

## Setup Github and Gerrit Account
* **This is a one-time only setup step**
* You'll need a Github account to proceed.
* Setup username/email for Github and Gerrithub (one time only):
  - Ensure Github and Gerrithub are linked by [signing into Gerrithub via Github](https://review.gerrithub.io/login)
  - match ```gitreview.username``` to your Github username
  - match ```user.name``` to your real name or how you want credit for commits to display in Git history.
  - match ```user.email``` to your email address associated with Github.

* Setup Inside Cloned QUADS Repo
  - Setup your username, email address as needed
  - Set your `gitreview.username`
```
git config user.email "venril@karnors-castle.com"
git config user.name "Venril Sathir"
git config --add gitreview.username "vsathir"
```

## Make a Commit and Submit Review
* Add a local commit with a meaningful, short title followed by a space and a summary (you can check our [commit history](https://github.com/quadsproject/quads/commits/latest) for examples.
* Add a line that relates to a new or existing github issue, e.g. ```fixes: https://github.com/quadsproject/quads/issues/5``` or ```related-to: https://github.com/quadsproject/quads/issues/25```

### Make Initial Commit
* First make your commit
* **Leave an extra few lines of space at the bottom of the commit message**

```
git add quads/api_v2.py
git commit
```

### Ensure Change ID is Present
* Now you need to amend your comment so a Gerrit Change-ID gets appended.

```
git commit --amend
```

### Integrate Git Review
* **This is a one-time only setup step**
* Install git-review and run it for first time.

```
yum install git-review
git review -s
```

* Now submit your patchset with git review (future patches you only need to run ```git review```)

```
git review
```

* If you are adding new functionality or methods you'll need to also include unit tests or CI will get upset.

### Managing Git Review Patchsets

* If you want to make changes to your patchset you can run the ```git commit --amend``` command.

```
vim src/quads/cli/cli.py
git add src/quads/cli/cli.py
git commit --amend
git review development
```

* If you just want to check out an existing patchset in Gerrit you can use the `git review -d $CHANGEID` command.

```
git review -d $CHANGEID
```

### Monitor your Patchset Lifecycle
* Keep an eye on your patchset in Gerrithub, this is where CI will run, where we'll provide feedback and where you can monitor changes and status.  Your git review command will print the correct URL to your patchset.

### Promoting Development to Production
* This is usually done by QUADS maintainers, but to promote your change to production via the `latest` branch we now use [git cherry-pick](https://git-scm.com/docs/git-cherry-pick)
* This will require an up-to-date checkout of the `latest` branch.

Let's say your patch into `development` has commit hash `e6fcc94732266568f72d22e0cd24d9f06d9060c7` and it's the latest commit in the branch, we will use this as an example:

```
git checkout development
git pull
git log | head -1
commit e6fcc94732266568f72d22e0cd24d9f06d9060c7
```

* Now `git cherry-pick` your change against the `latest` branch and submit review.

```
git checkout latest
git pull
git cherry-pick e6fcc94732266568f72d22e0cd24d9f06d9060c7
git review latest
```

### Continuous Integration

#### Commit Hooks
  - We use [black](https://github.com/psf/black) and [flake8](https://flake8.pycqa.org/en/latest/) pre-commit hooks.

#### Jenkins CI Pipeline
The CI pipeline currently checks the following for every submitted patchset:
  - shellcheck - checks for common shell syntax errors and issues
  - flake8 - checks Python tools for common syntax errors and issues
  - [unit tests](https://github.com/quadsproject/quads/tree/latest/tests)

#### Code Review Tips
  - You can trigger CI to run again by commenting on your patchset in gerrit with `retrigger`

#### QUADS CI Architecture

![quads-ci](/image/quads-ci.png?raw=true)

