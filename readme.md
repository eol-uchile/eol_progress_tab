# EOL Progress Tab

![https://github.com/eol-uchile/eol_progress_tab/actions](https://github.com/eol-uchile/eol_progress_tab/workflows/Python%20application/badge.svg)

Student Progress Tab with scaled grades

## Configurations

LMS/CMS Django Admin:

- */admin/site_configuration/siteconfiguration/*
    - **"EOL_PROGRESS_TAB_ENABLED":true**


## Development Settings

Set React app url:

    EOL_PROGRESS_TAB_DEV_URL = '/eol/eol_progress_tab/static'

## Compile frontend (production)

    > cd frontend
    > docker build -t frontend .
    > docker run -v $(pwd)/dist:/app/dist frontend npm run-script build
    > rm ../eol_progress_tab/static/eol_progress_tab/*
    > cp -r dist/* ../eol_progress_tab/static/eol_progress_tab/

## TESTS
**Prepare tests:**

    > cd .github/
    > docker-compose run --rm lms /openedx/requirements/eol_progress_tab/.github/test.sh
