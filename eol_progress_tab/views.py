# -*- coding: utf-8 -*-

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from django.conf import settings
from lms.djangoapps.courseware.tabs import get_course_tab_list

from django.template.loader import render_to_string
from web_fragments.fragment import Fragment
from courseware.courses import get_course_with_access
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from opaque_keys.edx.keys import CourseKey
from django.contrib.auth.models import User
from django.http import Http404

import logging
logger = logging.getLogger(__name__)

class EolProgressTabFragmentView(EdxFragmentView):
    def render_to_fragment(self, request, course_id, **kwargs):
        logger.warning("RENDER EOL PROGRESS TAB")
        if(not _has_page_access(request, course_id)):
            raise Http404()

        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, "load", course_key)
        context = {
            "course": course,
            "DEV_URL": configuration_helpers.get_value('EOL_PROGRESS_TAB_DEV_URL', settings.EOL_PROGRESS_TAB_DEV_URL)
        }
        logger.warning(context)
        html = render_to_string('eol_progress_tab/eol_progress_tab_fragment.html', context)
        fragment = Fragment(html)
        return fragment
            

def _has_page_access(request, course_id):
    """
        Check if tab is enabled and user is enrolled
    """ 
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, "load", course_key)
    tabs = get_course_tab_list(request.user, course)
    tabs_list = [tab.tab_id for tab in tabs]
    if 'eol_progress_tab' not in tabs_list:
        return False
    return User.objects.filter(
        courseenrollment__course_id=course_key,
        courseenrollment__is_active=1,
        pk = request.user.id
    ).exists()
