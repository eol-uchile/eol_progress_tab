# -*- coding: utf-8 -*-

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from django.conf import settings
from lms.djangoapps.courseware.tabs import get_course_tab_list
from lms.djangoapps.courseware.courses import get_course_about_section
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from django.template.loader import render_to_string
from web_fragments.fragment import Fragment
from courseware.courses import get_course_with_access
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from opaque_keys.edx.keys import CourseKey
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse

import json
from bson import json_util
from six import string_types, itervalues

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
        html = render_to_string('eol_progress_tab/eol_progress_tab_fragment.html', context)
        fragment = Fragment(html)
        return fragment
            
def get_student_data(request, course_id):
    """
        Get student grades in two formats: percents and scaled (1. -> 7.)
        List of categories with respective weight and grades
    """
    if(not _has_page_access(request, course_id)):
        raise Http404()

    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, "load", course_key)

    grade_cutoff = min(course.grade_cutoffs.values())
    # Create dict with category weights (% 0. -> 1.)
    category_weights = {
        assignment_type.upper() : weight
        for grader, assignment_type, weight in course.grader.subgraders
    }
    # Student grades information
    course_grade = CourseGradeFactory().read(request.user, course)
    # Student final grade scaled
    student_grade_scaled = _grade_percent_scaled(course_grade.percent, grade_cutoff)
    # Category average grades
    student_category_grades = filter(_prominent_section_filter, course_grade.summary['section_breakdown'])
    # Student data summary
    student_data = {
        'username'              : request.user.username,
        'final_grade_percent'   : course_grade.percent,
        'final_grade_scaled'    : student_grade_scaled,
        'passed'                : course_grade.passed,
        'category_grades'       : [
            {
                'grade_percent' : grade['percent'],
                'grade_scaled'  : _grade_percent_scaled(grade['percent'], grade_cutoff),
                'category'      : grade['category'].title(),
                'weight'        : category_weights[grade['category'].upper()]
            }
            for grade in student_category_grades
        ]
    }
    data = json.dumps(student_data, default=json_util.default)
    return HttpResponse(data)

def get_course_info(request, course_id):
    """
        Get course info related to dates and grades
    """
    if(not _has_page_access(request, course_id)):
        raise Http404()
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(request.user, "load", course_key)

    grade_cutoff = min(course.grade_cutoffs.values())
    min_grade_approval = _grade_percent_scaled(grade_cutoff, grade_cutoff)
    course_start_date, course_end_date = _get_course_dates(course)
    course_effort = (
        get_course_about_section(request, course, "effort") or 'None'
    ).strip()

    course_info = {
        'grade_cutoff'      : grade_cutoff,
        'min_grade_approval': min_grade_approval,
        'start_date'        : course_start_date,
        'end_date'          : course_end_date,
        'effort'            : course_effort
    }

    data = json.dumps(course_info, default=json_util.default)
    return HttpResponse(data)


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

def _prominent_section_filter(elem):
    """
        Filter only average grades
    """
    return 'prominent' in elem

def _get_course_dates(course):
    """
        Get course dates string
    """
    course_start_date = 'None'
    if not course.start_date_is_still_default:
        course_start_date = course.advertised_start or course.start
        if not isinstance(course_start_date, string_types):
            course_start_date = course_start_date.strftime('%Y-%m-%dT%H:%M:%S%z')

    course_end_date = 'None'
    if course.end:
        course_end_date = course.end
        if not isinstance(course_end_date, string_types):
            course_end_date = course_end_date.strftime('%Y-%m-%dT%H:%M:%S%z')

    return course_start_date, course_end_date

def _grade_percent_scaled(grade_percent, grade_cutoff):
    """
        Scale grade percent by grade cutoff. Grade between 1.0 - 7.0
    """
    if grade_percent == 0.:
        return 1.
    if grade_percent < grade_cutoff:
        return round(10. * (3. / grade_cutoff * grade_percent + 1.)) / 10.
    return round((3. / (1. - grade_cutoff) * grade_percent + (7. - (3. / (1. - grade_cutoff)))) * 10.) / 10.