# -*- coding: utf-8 -*-

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from django.conf import settings
from lms.djangoapps.courseware.tabs import get_course_tab_list
from lms.djangoapps.courseware.courses import get_course_about_section, get_studio_url

from lms.djangoapps.courseware.views.views import get_cert_data 
from lms.djangoapps.certificates.models import CertificateStatuses

from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from student.models import CourseEnrollment

from django.template.loader import render_to_string
from web_fragments.fragment import Fragment
from courseware.courses import get_course_with_access
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from opaque_keys.edx.keys import CourseKey
from django.contrib.auth.models import User
from django.http import Http404, HttpResponse
from django.urls import reverse

from courseware.access import has_access
from courseware.masquerade import setup_masquerade
from django.db.models import prefetch_related_objects

from lms.djangoapps.courseware.permissions import MASQUERADE_AS_STUDENT


import json
from bson import json_util
from six import string_types, itervalues, text_type
from numpy import around
from django.utils import timezone

import logging
logger = logging.getLogger(__name__)

class EolProgressTabFragmentView(EdxFragmentView):
    def render_to_fragment(self, request, course_id, **kwargs):
        if(not _has_page_access(request.user, course_id)):
            raise Http404()

        course_key = CourseKey.from_string(course_id)
        course = get_course_with_access(request.user, "load", course_key)

        # masquerade and student required for preview_menu (admin)
        staff_access = bool(has_access(request.user, 'staff', course))
        can_masquerade = request.user.has_perm(MASQUERADE_AS_STUDENT, course)
        masquerade, student = setup_masquerade(request, course_key, staff_access, reset_masquerade_data=True)
        prefetch_related_objects([student], 'groups')
        if request.user.id != student.id:
            course = get_course_with_access(student, 'load', course_key, check_if_enrolled=True)

        context = {
            "course": course,
            "student_id": student.id,
            "supports_preview_menu": True,
            "staff_access": staff_access,
            "can_masquerade": can_masquerade,
            "masquerade": masquerade,
            'studio_url': get_studio_url(course, 'settings/grading'),
            "DEV_URL": configuration_helpers.get_value('EOL_PROGRESS_TAB_DEV_URL', settings.EOL_PROGRESS_TAB_DEV_URL)
        }
        html = render_to_string('eol_progress_tab/eol_progress_tab_fragment.html', context)
        fragment = Fragment(html)
        return fragment
            
def get_student_data(request, course_id, user_id):
    """
        Get student grades in two formats: percents and scaled (1. -> 7.)
        List of categories with respective weight, grades & problem scores.
    """
    user_id = int(user_id)
    # if 'view course as' is active then user_id could be different than request.user
    user = request.user if user_id == request.user.id else User.objects.get(pk=user_id)
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(user, "load", course_key)

    # check if user has access. If masquerade view, check if user is staff
    if( not _has_page_access(request.user, course_id)
        or (user_id != request.user.id and not bool(has_access(request.user, 'staff', course))) ):
        raise Http404()

    grade_cutoff = min(course.grade_cutoffs.values())
    # Create dict with category weights (% 0. -> 1.) and drop_count
    category_config = {
        assignment_type.upper() : {
            'weight'    : weight,
            'drop_count': grader.drop_count,
            'min_count' : grader.min_count
        }
        for grader, assignment_type, weight in course.grader.subgraders
    }
    # Student grades information
    course_grade = CourseGradeFactory().read(user, course)

    # Get category detail and problem scores by subsection
    category_scores_detail = _get_category_scores_detail(course_grade, course_key)

    # Certificate
    enrollment_mode, _ = CourseEnrollment.enrollment_mode_for_user(user, course_key)
    certificate_data = _get_certificate_data(user, course, enrollment_mode, course_grade)

    # Student final grade scaled
    student_grade_scaled = _grade_percent_scaled(course_grade.percent, grade_cutoff)
    # Category average grades
    student_category_grades = filter(_prominent_section_filter, course_grade.summary['section_breakdown'])
    # Student data summary
    student_data = {
        'username'              : user.username,
        'final_grade_percent'   : course_grade.percent,
        'final_grade_scaled'    : student_grade_scaled,
        'passed'                : course_grade.passed,
        'certificate_data'      : certificate_data,
        'category_grades'       : [
            {
                'grade_percent' : grade['percent'],
                'grade_scaled'  : _grade_percent_scaled(grade['percent'], grade_cutoff),
                'category'      : grade['category'].title(),
                'weight'        : category_config[grade['category'].upper()]['weight'],
                'drop_count'    : category_config[grade['category'].upper()]['drop_count'],
                'min_count'     : category_config[grade['category'].upper()]['min_count'],
                'detail'        : category_scores_detail[grade['category'].upper()] if grade['category'].upper() in category_scores_detail else []
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
    if(not _has_page_access(request.user, course_id)):
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
        'effort'            : course_effort,
        'display_name'      : course.display_name_with_default
    }

    data = json.dumps(course_info, default=json_util.default)
    return HttpResponse(data)


def _has_page_access(user, course_id):
    """
        Check if tab is enabled and user is enrolled
    """ 
    course_key = CourseKey.from_string(course_id)
    course = get_course_with_access(user, "load", course_key)

    if bool(has_access(user, 'staff', course)):
        return True # Allow page access to staff
    
    tabs = get_course_tab_list(user, course)
    tabs_list = [tab.tab_id for tab in tabs]
    if 'eol_progress_tab' not in tabs_list:
        return False

    return User.objects.filter(
        courseenrollment__course_id=course_key,
        courseenrollment__is_active=1,
        pk = user.id
    ).exists()

def _get_category_scores_detail(course_grade, course_key):
    """
        Get subsections by category_grade with their respective problem scores
    """
    graded_subsections_by_format = course_grade.graded_subsections_by_format
    category_scores_detail = {}

    # subsection by format (category_grades)
    for key, values in graded_subsections_by_format.items():
        # a category_grade can be in more than one subsection
        for subsection in itervalues(values):
            show_problem_scores_value = _show_problem_scores(subsection.show_correctness, subsection.due)
            subsection_data = {
                'subsection_display_name'   : subsection.display_name,
                'url'                       : _get_subsection_url(subsection.location, course_key),
                'total_earned'              : subsection.graded_total.earned, # only graded scores
                'total_possible'            : subsection.graded_total.possible, # only graded scores
                'total_percent'             : around(subsection.graded_total.earned / subsection.graded_total.possible, decimals=2),
                'due'                       : _format_date(subsection.due),
                'attempted'                 : subsection.graded_total.first_attempted is not None,
                'show_problem_scores'       : show_problem_scores_value,
                'problem_scores'            : [
                    {
                        'earned'            : score.earned,
                        'possible'          : score.possible
                    }
                    for score in subsection.problem_scores.values() if score.graded # only graded scores
                ] if show_problem_scores_value else []
            }
            category_scores_detail.setdefault(subsection.format.upper(),[]).append(subsection_data)
    return category_scores_detail


def _show_problem_scores(show_correctness, due):
    """
        Show problem scores
            show_correctness values:
                'always'
                'past_due'
                'never'
    """
    if show_correctness == 'always':
        return True
    elif show_correctness == 'past_due':
        return due is None or timezone.now() > due
    # show_correctness == 'never'
    return False

def _get_subsection_url(location, course_key):
    """
        URL Redirect to specific location in the course
    """
    return reverse(
        'jump_to', 
        kwargs=dict(
            course_id=text_type(course_key),
            location=text_type(location)
        )
    )

def _get_certificate_data(user, course, enrollment_mode, course_grade):
    """
        Get student certificate url and messages.
    """
    certificate_data = get_cert_data(user, course, enrollment_mode, course_grade)
    if certificate_data:
        request_method = "GET"
        if certificate_data.cert_web_view_url:
            url = certificate_data.cert_web_view_url
            button_msg = "Ver Certificado"
        elif certificate_data.cert_status == CertificateStatuses.downloadable and certificate_data.download_url:
            url = certificate_data.download_url
            button_msg = "Descargar Certificado"
        elif certificate_data.cert_status == CertificateStatuses.requesting:
            url = reverse('generate_user_cert', args=[text_type(course.id)])
            button_msg = "Solicitar Certificado"
            request_method = "POST"
        else:
            url = "#"
            button_msg = "Certificado No Disponible"
        return {
            'url'           : url,
            'title'         : text_type(certificate_data.title),
            'msg'           : text_type(certificate_data.msg),
            'button_msg'    : button_msg,
            'button_method' : request_method
        }
    else:
        return { }

def _prominent_section_filter(elem):
    """
        Filter only average grades
    """
    return 'prominent' in elem

def _get_course_dates(course):
    """
        Get course dates string
    """
    course_start_date = None
    if not course.start_date_is_still_default:
        course_start_date = _format_date(course.advertised_start or course.start)

    course_end_date = None
    if course.end:
        course_end_date = _format_date(course.end)

    return course_start_date, course_end_date

def _format_date(date):
    if not isinstance(date, string_types) and date is not None:
        date = date.strftime('%Y-%m-%dT%H:%M:%S%z')
    return date

def _grade_percent_scaled(grade_percent, grade_cutoff):
    """
        Scale grade percent by grade cutoff. Grade between 1.0 - 7.0
    """
    if grade_percent == 0.:
        return 1.
    if grade_percent < grade_cutoff:
        return min(round(10. * (3. / grade_cutoff * grade_percent + 1.)) / 10., 3.9)
    return round((3. / (1. - grade_cutoff) * grade_percent + (7. - (3. / (1. - grade_cutoff)))) * 10.) / 10.
