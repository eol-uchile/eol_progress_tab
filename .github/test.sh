#!/bin/dash

pip install -e /openedx/requirements/eol_progress_tab

cd /openedx/requirements/eol_progress_tab/eol_progress_tab
cp /openedx/edx-platform/setup.cfg .
mkdir test_root
cd test_root/
ln -s /openedx/staticfiles .

cd /openedx/requirements/eol_progress_tab/eol_progress_tab

DJANGO_SETTINGS_MODULE=lms.envs.test EDXAPP_TEST_MONGO_HOST=mongodb pytest tests.py
